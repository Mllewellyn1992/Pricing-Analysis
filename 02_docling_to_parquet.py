"""
02_docling_to_parquet.py  --  Parallel PDF-to-Parquet with Docling.

Features
--------
- Parallel workers via subprocesses  (WORKERS env var, default 2)
- Resume support    (tracks completed files in done_list.txt)
- Batch writes      (writes parquet in small batches to avoid data loss)
- Merge step        (combines batch files into final parquet outputs)

Env vars
--------
  WORKERS             Number of parallel workers      (default 2)
  BATCH_SIZE          PDFs per batch flush             (default 50)
  MAX_PDFS            Limit total PDFs to process      (0 = all)
  FORCE_REPROCESS     Set to 1 to redo everything
  MERGE_ONLY          Set to 1 to only merge batches
  PDF_PATH            Process a single PDF
  PDF_GLOB            Process PDFs matching a glob

Internal (set by launcher):
  _WORKER_ID          This process's worker ID
  _WORKER_FILE        Path to this worker's PDF list file
"""

import csv
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# ── paths ──────────────────────────────────────────────────────────────────
_LOCAL_BASE = r"C:\Users\mllew\OneDrive\Desktop\Data Mining"
_UNC_BASE = r"\\tsclient\C\Users\mllew\OneDrive\Desktop\Data Mining"
_BASE = _LOCAL_BASE if os.path.isdir(_LOCAL_BASE) else _UNC_BASE
INPUT_DIR = os.path.join(_BASE, "Financials")
OUTPUT_DIR = os.path.join(_BASE, "Parquet Financials")
OCR_DIR = os.path.join(OUTPUT_DIR, "OCR_PDFs")
LOG_DIR = os.path.join(OUTPUT_DIR, "logs")

TEXT_BATCHES_DIR = os.path.join(OUTPUT_DIR, "text_batches")
SUMMARY_BATCHES_DIR = os.path.join(OUTPUT_DIR, "summary_batches")
TABLES_BATCHES_DIR = os.path.join(OUTPUT_DIR, "tables_batches")
DONE_LIST_PATH = os.path.join(OUTPUT_DIR, "done_list.txt")

TEXT_PARQUET = os.path.join(OUTPUT_DIR, "financials_text.parquet")
SUMMARY_PARQUET = os.path.join(OUTPUT_DIR, "financials.parquet")
TABLES_PARQUET = os.path.join(OUTPUT_DIR, "financials_tables.parquet")


# ── helpers ────────────────────────────────────────────────────────────────
def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def log(msg):
    print(msg, flush=True)


def iter_pdfs(root_dir):
    single_path = os.getenv("PDF_PATH")
    if single_path and os.path.exists(single_path):
        yield single_path
        return
    glob_pattern = os.getenv("PDF_GLOB")
    if glob_pattern:
        for path in glob.glob(glob_pattern, recursive=True):
            if path.lower().endswith(".pdf"):
                yield path
        return
    for base, _, files in os.walk(root_dir):
        for name in sorted(files):
            if name.lower().endswith(".pdf"):
                yield os.path.join(base, name)


def ocr_output_path(source_file):
    relative = os.path.relpath(source_file, INPUT_DIR)
    base, ext = os.path.splitext(relative)
    return os.path.join(OCR_DIR, f"{base}_ocr{ext}")


_OCRMYPDF_AVAILABLE = None

def ocrmypdf_preprocess(source_file, worker_id=0):
    """Run OCRmyPDF on a source PDF to deskew, clean, and add a text layer.

    Returns the path to the OCR'd file, or the original path if OCRmyPDF
    is unavailable or fails.
    """
    global _OCRMYPDF_AVAILABLE
    if _OCRMYPDF_AVAILABLE is False:
        return source_file

    out_path = ocr_output_path(source_file)
    if os.path.exists(out_path):
        return out_path

    ensure_dir(os.path.dirname(out_path))

    if _OCRMYPDF_AVAILABLE is None:
        try:
            import ocrmypdf  # noqa: F401
            _OCRMYPDF_AVAILABLE = True
        except ImportError:
            log(f"[Worker {worker_id}] ocrmypdf not installed — skipping OCR pre-processing. "
                "Install with: pip install ocrmypdf")
            _OCRMYPDF_AVAILABLE = False
            return source_file

    import ocrmypdf
    try:
        ocrmypdf.ocr(
            source_file,
            out_path,
            deskew=False,
            rotate_pages=True,
            skip_text=True,       # don't re-OCR pages that already have text
            optimize=1,           # light optimization
            progress_bar=False,
            language=["eng"],
            invalidate_digital_signatures=True,
        )
        return out_path
    except Exception as e:
        log(f"[Worker {worker_id}] OCRmyPDF failed for {os.path.basename(source_file)}: {e}")
        return source_file


def doc_id_for_path(path):
    return hashlib.sha256(path.lower().encode("utf-8")).hexdigest()


def company_name_from_path(path):
    name = os.path.splitext(os.path.basename(path))[0]
    return re.sub(r"[_\-]+", " ", name).strip()


# ── done-list (resume tracking) ───────────────────────────────────────────
def load_done_set():
    done = set()
    if os.path.exists(DONE_LIST_PATH):
        with open(DONE_LIST_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    done.add(line)
    return done


def append_done(source_file):
    """Append one source file to done list (call only after data is written to batch)."""
    with open(DONE_LIST_PATH, "a", encoding="utf-8") as f:
        f.write(source_file + "\n")


def append_done_batch(source_files):
    """Append multiple source files to done list (after a batch is written)."""
    if not source_files:
        return
    with open(DONE_LIST_PATH, "a", encoding="utf-8") as f:
        for path in source_files:
            f.write(path + "\n")


# ── logging ────────────────────────────────────────────────────────────────
def append_log_row(worker_id, row):
    log_path = os.path.join(LOG_DIR, f"docling_worker_{worker_id}.csv")
    fieldnames = [
        "source_file", "effective_pdf_path", "status",
        "pages", "tables", "message", "processed_at",
    ]
    file_exists = os.path.exists(log_path)
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


# ── batch I/O ──────────────────────────────────────────────────────────────
def write_batch(worker_id, batch_num, text_rows, summary_rows, table_rows):
    ensure_dir(TEXT_BATCHES_DIR)
    ensure_dir(SUMMARY_BATCHES_DIR)
    ensure_dir(TABLES_BATCHES_DIR)
    tag = f"w{worker_id}_b{batch_num:05d}"
    if text_rows:
        path = os.path.join(TEXT_BATCHES_DIR, f"{tag}.parquet")
        table = pa.Table.from_pandas(pd.DataFrame(text_rows), preserve_index=False)
        pq.write_table(table, path, compression="snappy")
    if summary_rows:
        path = os.path.join(SUMMARY_BATCHES_DIR, f"{tag}.parquet")
        table = pa.Table.from_pandas(pd.DataFrame(summary_rows), preserve_index=False)
        pq.write_table(table, path, compression="snappy")
    if table_rows:
        path = os.path.join(TABLES_BATCHES_DIR, f"{tag}.parquet")
        table = pa.Table.from_pandas(pd.DataFrame(table_rows), preserve_index=False)
        pq.write_table(table, path, compression="snappy")


# ── index build (run when Docling exits so Streamlit search is up to date) ─
def run_index_build():
    """Run 03_build_fts_index.py so the search index matches current parquet. Safe to call on exit or Ctrl+C."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path_03 = os.path.join(script_dir, "03_build_fts_index.py")
    if not os.path.exists(path_03):
        log("[index] 03_build_fts_index.py not found, skipping.")
        return
    log("\n[index] Updating search index for Streamlit...")
    try:
        subprocess.run(
            [sys.executable, path_03],
            cwd=script_dir,
            timeout=3600,
        )
        log("[index] Index update finished.")
    except Exception as e:
        log(f"[index] Index update failed: {e}")


# ── merge ──────────────────────────────────────────────────────────────────
def merge_batches():
    """Merge batch files into final parquet, including any existing final parquet so we never lose data."""
    log("Merging text batches...")
    text_tables = []
    if os.path.exists(TEXT_PARQUET):
        try:
            text_tables.append(pq.read_table(TEXT_PARQUET))
        except Exception:
            pass
    text_files = sorted(glob.glob(os.path.join(TEXT_BATCHES_DIR, "*.parquet")))
    for f in text_files:
        text_tables.append(pq.read_table(f))
    if text_tables:
        combined = pa.concat_tables(text_tables, promote_options="default")
        df = combined.to_pandas()
        df = df.drop_duplicates(subset=["doc_id", "page_number"], keep="last")
        pq.write_table(
            pa.Table.from_pandas(df, preserve_index=False),
            TEXT_PARQUET, compression="snappy",
        )
        log(f"  -> {TEXT_PARQUET}  ({len(df):,} rows from existing + {len(text_files)} batches)")
    else:
        log("  No text data or batches found.")

    log("Merging summary batches...")
    summary_tables = []
    if os.path.exists(SUMMARY_PARQUET):
        try:
            summary_tables.append(pq.read_table(SUMMARY_PARQUET))
        except Exception:
            pass
    summary_files = sorted(glob.glob(os.path.join(SUMMARY_BATCHES_DIR, "*.parquet")))
    for f in summary_files:
        summary_tables.append(pq.read_table(f))
    if summary_tables:
        combined = pa.concat_tables(summary_tables, promote_options="default")
        df = combined.to_pandas()
        df = df.drop_duplicates(subset=["doc_id"], keep="last")
        pq.write_table(
            pa.Table.from_pandas(df, preserve_index=False),
            SUMMARY_PARQUET, compression="snappy",
        )
        log(f"  -> {SUMMARY_PARQUET}  ({len(df):,} rows from existing + {len(summary_files)} batches)")
    else:
        log("  No summary data or batches found.")

    log("Merging table batches...")
    tables_tables = []
    if os.path.exists(TABLES_PARQUET):
        try:
            tables_tables.append(pq.read_table(TABLES_PARQUET))
        except Exception:
            pass
    table_files = sorted(glob.glob(os.path.join(TABLES_BATCHES_DIR, "*.parquet")))
    for f in table_files:
        tables_tables.append(pq.read_table(f))
    if tables_tables:
        combined = pa.concat_tables(tables_tables, promote_options="default")
        df = combined.to_pandas()
        df = df.drop_duplicates(subset=["doc_id", "page_number", "table_id", "row_index"], keep="last")
        pq.write_table(
            pa.Table.from_pandas(df, preserve_index=False),
            TABLES_PARQUET, compression="snappy",
        )
        log(f"  -> {TABLES_PARQUET}  ({len(df):,} rows from existing + {len(table_files)} batches)")
    else:
        log("  No table data or batches found.")


# ── ETA formatting ─────────────────────────────────────────────────────────
def format_eta(seconds):
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.0f}m"
    hours = seconds / 3600
    if hours < 24:
        return f"{hours:.1f}h"
    return f"{hours / 24:.1f}d"


# ══════════════════════════════════════════════════════════════════════════
# WORKER MODE  (launched as a subprocess by the main process)
# ══════════════════════════════════════════════════════════════════════════
def run_worker(worker_id, pdf_list_file, batch_size):
    """Process PDFs listed in pdf_list_file. Runs in its own process."""
    from docling.document_converter import DocumentConverter, FormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling_core.types.doc import TextItem

    # Read PDF list
    with open(pdf_list_file, "r", encoding="utf-8") as f:
        pdf_list = [line.strip() for line in f if line.strip()]

    total = len(pdf_list)
    log(f"[Worker {worker_id}] Starting with {total:,} PDFs")

    # Init Docling
    pdf_options = PdfPipelineOptions(
        do_ocr=False,
        force_backend_text=True,
        do_table_structure=True,
    )
    format_options = {
        InputFormat.PDF: FormatOption(
            pipeline_cls=StandardPdfPipeline,
            pipeline_options=pdf_options,
            backend=PyPdfiumDocumentBackend,
        )
    }
    converter = DocumentConverter(format_options=format_options)
    log(f"[Worker {worker_id}] Docling ready")

    text_rows = []
    summary_rows = []
    table_rows = []
    batch_num = 0
    ok_count = 0
    err_count = 0
    t0 = time.time()

    for i, source_file in enumerate(pdf_list):
        processed_at = datetime.now(timezone.utc).isoformat()
        try:
            effective = ocrmypdf_preprocess(source_file, worker_id)

            result = converter.convert(effective)
            document = getattr(result, "document", result)
            doc_id = doc_id_for_path(source_file)
            company_name = company_name_from_path(source_file)

            # Docling page_no is 0-based; normalize to 1-based for app/PDF viewer
            page_text_map = {}
            if hasattr(document, "iterate_items"):
                for item, _level in document.iterate_items(with_groups=False):
                    if not getattr(item, "prov", None):
                        continue
                    page_no = item.prov[0].page_no
                    page_key = int(page_no) + 1 if isinstance(page_no, (int, float)) else 1
                    if page_key < 1:
                        page_key = 1
                    if isinstance(item, TextItem):
                        page_text_map.setdefault(page_key, []).append(item.text)

            page_count = len(getattr(result, "pages", []) or []) or 1
            page_texts = []
            for page_index in range(1, page_count + 1):
                text = "\n".join(page_text_map.get(page_index, [])).strip()
                text_rows.append({
                    "doc_id": doc_id,
                    "company_name": company_name,
                    "source_file": source_file,
                    "effective_pdf_path": effective,
                    "page_number": page_index,
                    "text": text,
                    "processed_at": processed_at,
                })
                page_texts.append(text)

            # Extract tables (row per table row for FTS)
            tables = getattr(document, "tables", None) or []
            for table_ix, table in enumerate(tables):
                page_no = 0
                if getattr(table, "prov", None) and len(table.prov) > 0:
                    page_no = getattr(table.prov[0], "page_no", 0)
                # Docling page_no is 0-based; normalize to 1-based for app/PDF viewer
                page_number = max(1, int(page_no) + 1) if isinstance(page_no, (int, float)) else 1
                table_title = (
                    getattr(table, "caption", None) or getattr(table, "label", None) or ""
                )
                if isinstance(table_title, str):
                    table_title = table_title.strip()
                else:
                    table_title = str(table_title).strip() if table_title is not None else ""
                try:
                    df_table = table.export_to_dataframe()
                except Exception:
                    df_table = pd.DataFrame()

                # Structured JSON so the app can reconstruct the full table
                col_names = [str(c) for c in df_table.columns]
                matrix = []
                for _, r in df_table.iterrows():
                    matrix.append([str(v) if pd.notna(v) else "" for v in r.values])
                cells_json_str = json.dumps({"columns": col_names, "rows": matrix})

                # Column headers are meaningful when they aren't just 0, 1, 2…
                has_headers = any(
                    str(c).strip() and not str(c).strip().isdigit()
                    for c in df_table.columns
                )

                for ri, (row_index, row) in enumerate(df_table.iterrows()):
                    try:
                        row_idx = int(row_index)
                    except (TypeError, ValueError):
                        row_idx = ri

                    if has_headers:
                        parts = []
                        for col, val in zip(df_table.columns, row.values):
                            if pd.notna(val) and str(val).strip():
                                col_str = str(col).strip()
                                val_str = str(val).strip()
                                if col_str and col_str.lower() != val_str.lower():
                                    parts.append(f"{col_str}: {val_str}")
                                else:
                                    parts.append(val_str)
                        row_text = " | ".join(parts).strip()
                    else:
                        parts = [str(v) for v in row.values if pd.notna(v) and str(v).strip()]
                        row_text = " ".join(parts).strip()

                    if not row_text:
                        continue
                    table_rows.append({
                        "doc_id": doc_id,
                        "company_name": company_name,
                        "source_file": source_file,
                        "effective_pdf_path": effective,
                        "page_number": page_number,
                        "table_id": table_ix,
                        "table_title": table_title[:500] if table_title else "",
                        "row_index": row_idx,
                        "row_text": row_text,
                        "cells_json": cells_json_str,
                        "processed_at": processed_at,
                    })

            word_count = sum(len((t or "").split()) for t in page_texts)
            num_tables = len(tables)
            summary_rows.append({
                "doc_id": doc_id,
                "company_name": company_name,
                "source_file": source_file,
                "effective_pdf_path": effective,
                "page_count": page_count,
                "word_count": word_count,
                "table_count": num_tables,
                "processed_at": processed_at,
            })

            append_log_row(worker_id, {
                "source_file": source_file,
                "effective_pdf_path": effective,
                "status": "ok", "pages": page_count,
                "tables": num_tables, "message": "",
                "processed_at": processed_at,
            })
            ok_count += 1

        except Exception as exc:
            append_log_row(worker_id, {
                "source_file": source_file,
                "effective_pdf_path": "",
                "status": "error", "pages": 0,
                "tables": 0, "message": str(exc),
                "processed_at": processed_at,
            })
            err_count += 1
            # Failed PDFs still go into "done" so we don't retry forever; add to a list to append on next flush
            summary_rows.append({
                "doc_id": doc_id_for_path(source_file),
                "company_name": company_name_from_path(source_file),
                "source_file": source_file,
                "effective_pdf_path": "",
                "page_count": 0,
                "word_count": 0,
                "table_count": 0,
                "processed_at": processed_at,
            })

        # Periodic batch flush (only mark done after data is on disk)
        if (i + 1) % batch_size == 0:
            write_batch(worker_id, batch_num, text_rows, summary_rows, table_rows)
            append_done_batch([r["source_file"] for r in summary_rows])
            text_rows = []
            summary_rows = []
            table_rows = []
            batch_num += 1
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = (total - i - 1) / rate if rate > 0 else 0
            log(
                f"[Worker {worker_id}] {i + 1:,}/{total:,}  "
                f"ok:{ok_count} err:{err_count}  "
                f"{rate:.2f}/s  ETA:{format_eta(remaining)}"
            )

    # Final flush (only mark done after data is on disk)
    if text_rows or summary_rows or table_rows:
        write_batch(worker_id, batch_num, text_rows, summary_rows, table_rows)
        append_done_batch([r["source_file"] for r in summary_rows])

    elapsed = time.time() - t0
    log(
        f"[Worker {worker_id}] Done — {ok_count:,} ok, {err_count:,} errors "
        f"in {format_eta(elapsed)}"
    )


# ══════════════════════════════════════════════════════════════════════════
# MAIN / LAUNCHER MODE
# ══════════════════════════════════════════════════════════════════════════
def main():
    # Check if we're a worker subprocess
    worker_id = os.getenv("_WORKER_ID")
    worker_file = os.getenv("_WORKER_FILE")
    if worker_id is not None and worker_file is not None:
        batch_size = int(os.getenv("BATCH_SIZE", "50") or "50")
        run_worker(int(worker_id), worker_file, batch_size)
        return

    # ── Launcher mode ──────────────────────────────────────────────────
    ensure_dir(OUTPUT_DIR)
    ensure_dir(LOG_DIR)
    ensure_dir(TEXT_BATCHES_DIR)
    ensure_dir(SUMMARY_BATCHES_DIR)
    ensure_dir(TABLES_BATCHES_DIR)

    force = os.getenv("FORCE_REPROCESS", "").strip().lower() in {"1", "true", "yes"}
    limit = int(os.getenv("MAX_PDFS", "0") or "0")
    workers = int(os.getenv("WORKERS", "2") or "2")
    batch_size = int(os.getenv("BATCH_SIZE", "1") or "1")
    merge_only = os.getenv("MERGE_ONLY", "").strip().lower() in {"1", "true", "yes"}

    if merge_only:
        merge_batches()
        run_index_build()
        return

    # Resume tracking
    if force:
        done = set()
        if os.path.exists(DONE_LIST_PATH):
            os.remove(DONE_LIST_PATH)
    else:
        done = load_done_set()

    # Collect work
    log("Scanning for PDFs...")
    all_pdfs = sorted(iter_pdfs(INPUT_DIR))
    todo = [p for p in all_pdfs if p not in done]
    if limit:
        todo = todo[:limit]

    total = len(todo)
    log(f"Total PDFs found : {len(all_pdfs):,}")
    log(f"Already completed: {len(done):,}")
    log(f"To process       : {total:,}")
    log(f"Workers          : {workers}")
    log(f"Batch size       : {batch_size}")
    log("")

    # Merge any batches from a previous (interrupted) run so final parquet is up to date
    log("Merging any previous batches into final parquet...")
    merge_batches()
    log("")

    if total == 0:
        log("Nothing new to process.")
        run_index_build()
        return

    # Split work across workers (round-robin)
    chunks = [[] for _ in range(workers)]
    for i, pdf in enumerate(todo):
        chunks[i % workers].append(pdf)

    # Write each worker's PDF list to a temp file
    temp_files = []
    for wid, chunk in enumerate(chunks):
        if not chunk:
            continue
        tf = tempfile.NamedTemporaryFile(
            mode="w", suffix=f"_worker_{wid}.txt",
            delete=False, encoding="utf-8",
        )
        for pdf in chunk:
            tf.write(pdf + "\n")
        tf.close()
        temp_files.append((wid, tf.name, len(chunk)))

    # Launch worker subprocesses (cwd = script dir so paths resolve correctly)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log(f"Launching {len(temp_files)} worker subprocesses...\n")
    procs = []
    for wid, tf_path, count in temp_files:
        env = os.environ.copy()
        env["_WORKER_ID"] = str(wid)
        env["_WORKER_FILE"] = tf_path
        env["BATCH_SIZE"] = str(batch_size)
        p = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__)],
            env=env,
            cwd=script_dir,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        procs.append((wid, p, tf_path))
        log(f"  Worker {wid}: PID {p.pid}, {count:,} PDFs")

    log("")

    try:
        # Wait for all workers
        for wid, p, tf_path in procs:
            p.wait()
            log(f"  Worker {wid} exited with code {p.returncode}")
            try:
                os.unlink(tf_path)
            except OSError:
                pass

        # Final merge
        log("\nAll workers finished. Merging batches...")
        merge_batches()
        log("\nAll done!")
    except KeyboardInterrupt:
        log("\nInterrupted. Merging batches and updating index so you can use Streamlit...")
        for wid, p, tf_path in procs:
            try:
                p.terminate()
            except Exception:
                pass
        for wid, p, tf_path in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                pass
        try:
            merge_batches()
        except Exception as e:
            log(f"[merge] {e}")
        run_index_build()
        raise

    # Update search index so Streamlit search is current when Docling exits
    run_index_build()


if __name__ == "__main__":
    main()
