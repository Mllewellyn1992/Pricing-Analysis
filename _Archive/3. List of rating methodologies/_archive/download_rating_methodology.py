import re
import time
from pathlib import Path
from urllib.parse import urlparse

import os
import tempfile
from typing import Optional

import win32com.client as win32


EXCEL_PATH = Path(
    r"C:\Users\michael.lewellyn\OneDrive - Bancorp\Desktop\Moody's Score Card\3. List of rating methodologies\List of Rating Methodologies (21-10-2025).xlsx"
)
DOWNLOAD_DIR = Path(
    r"C:\Users\michael.lewellyn\OneDrive - Bancorp\Desktop\Moody's Score Card\3. List of rating methodologies\Moody's Methodologies"
)
SHEET_NAME = "Rating Methodologies"
START_ROW = 12
MAX_ROW = 179
WAIT_SECONDS = 3

# Optional: limit downloads while testing (set to None to download everything).
MAX_DOWNLOADS: Optional[int] = 2

# Browser config. If you want to reuse your already-logged-in Chrome session,
# set CHROME_USER_DATA_DIR to your Chrome "User Data" folder.
#
# Typical path:
#   C:\Users\<you>\AppData\Local\Google\Chrome\User Data
#
# If left as None, the script will use a temporary profile (you may need to log in).
CHROME_USER_DATA_DIR: Optional[str] = os.getenv("CHROME_USER_DATA_DIR") or None
CHROME_PROFILE_DIR: str = "Default"


def _safe_filename(candidate: str, fallback: str) -> str:
    """Return a filesystem-safe filename that ends in .pdf."""
    base = candidate.strip() or fallback
    base = re.sub(r'[<>:"/\\|?*]', "_", base)
    if not base.lower().endswith(".pdf"):
        base = f"{base}.pdf"
    return base


def _infer_filename(cell_value: str, pdf_url: str) -> str:
    tail = Path(urlparse(pdf_url).path).name
    fallback = tail or "rating_methodology"
    return _safe_filename(cell_value or fallback, fallback)


def _looks_like_pdf(path: Path) -> bool:
    try:
        return path.read_bytes()[:4] == b"%PDF"
    except Exception:
        return False


def _create_webdriver(download_dir: Path):
    """
    Start Chrome via Selenium with a deterministic download directory.

    This enables the "press download icon and save file" behaviour you want.
    If Chrome still shows a Save As dialog (because of corporate policy / settings),
    we will handle it via UI automation in _handle_save_as_dialog().
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Missing dependencies. Install with:\n"
            "  python -m pip install selenium webdriver-manager pywinauto\n"
            f"Original error: {exc}"
        ) from exc

    download_dir.mkdir(parents=True, exist_ok=True)

    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--start-maximized")

    # Use existing Chrome profile if provided (so Moody's login carries over).
    if CHROME_USER_DATA_DIR:
        options.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
        options.add_argument(f"--profile-directory={CHROME_PROFILE_DIR}")

    # Try to force automatic downloads into our folder.
    prefs = {
        "download.default_directory": str(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        # Often helps: open PDFs in Chrome viewer (so we can click the toolbar download),
        # not always respected under managed policies.
        "plugins.always_open_pdf_externally": False,
    }
    options.add_experimental_option("prefs", prefs)

    # webdriver-manager will fetch a matching chromedriver.
    driver = webdriver.Chrome(
        options=options,
        service=webdriver.ChromeService(ChromeDriverManager().install()),
    )
    driver.set_page_load_timeout(120)
    return driver


def _handle_save_as_dialog(full_destination: Path, timeout_seconds: int = 15) -> bool:
    """
    If Chrome shows a Windows "Save As" dialog, fill the file name + click Save.
    Returns True if we handled a dialog, else False.
    """
    try:
        from pywinauto import Desktop
        from pywinauto.keyboard import send_keys
    except Exception:  # pragma: no cover
        return False

    end = time.time() + timeout_seconds
    while time.time() < end:
        try:
            # Title can vary slightly (sometimes includes app name), so keep it broad.
            dlg = Desktop(backend="uia").window(title_re=".*Save As.*")
            if not dlg.exists(timeout=0.2):
                time.sleep(0.2)
                continue
            dlg.set_focus()

            # Prefer setting the filename via UIA edit control (more reliable than hotkeys),
            # but keep hotkey fallback for different dialog layouts.
            wrote_path = False
            try:
                edit = dlg.child_window(control_type="Edit")
                if edit.exists(timeout=0.5):
                    edit.set_focus()
                    send_keys("^a")
                    send_keys(str(full_destination), with_spaces=True)
                    wrote_path = True
            except Exception:
                wrote_path = False

            if not wrote_path:
                # Alt+N tends to focus "File name" field on standard Save As dialogs.
                send_keys("%n")
                send_keys("^a")
                send_keys(str(full_destination), with_spaces=True)

            # Click Save (or press Enter). Clicking is usually safer if focus is elsewhere.
            clicked_save = False
            try:
                save_btn = dlg.child_window(title_re="^Save$", control_type="Button")
                if save_btn.exists(timeout=0.5):
                    save_btn.click_input()
                    clicked_save = True
            except Exception:
                clicked_save = False

            if not clicked_save:
                send_keys("{ENTER}")

            # If overwrite confirmation appears, accept it.
            try:
                confirm = Desktop(backend="uia").window(title_re=".*Confirm Save As.*")
                if confirm.exists(timeout=1):
                    confirm.set_focus()
                    # Try clicking a button if present; otherwise fall back to common hotkeys.
                    try:
                        yes_btn = confirm.child_window(title_re="^(Yes|Replace)$", control_type="Button")
                        if yes_btn.exists(timeout=0.5):
                            yes_btn.click_input()
                        else:
                            send_keys("%y")  # Alt+Y = Yes (replace)
                    except Exception:
                        send_keys("%y")
            except Exception:
                pass

            return True
        except Exception:
            time.sleep(0.2)
            continue
    return False


def _wait_for_new_pdf(download_dir: Path, before: set[Path], timeout_seconds: int = 90) -> Path:
    """
    Wait for a new .pdf file to appear in download_dir (and not be a partial .crdownload).
    """
    end = time.time() + timeout_seconds
    while time.time() < end:
        # Ignore in-progress chrome partials.
        partials = list(download_dir.glob("*.crdownload"))
        if partials:
            time.sleep(0.25)
            continue

        after = set(download_dir.glob("*.pdf"))
        created = sorted(after - before, key=lambda p: p.stat().st_mtime, reverse=True)
        if created:
            return created[0]
        time.sleep(0.25)

    raise TimeoutError(f"No new PDF appeared in {download_dir} within {timeout_seconds}s.")


def _click_download_and_save(driver, page_url: str, destination: Path) -> None:
    """
    Open Moody's viewer page, click the toolbar download icon, and save to destination.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    destination.parent.mkdir(parents=True, exist_ok=True)

    before = set(destination.parent.glob("*.pdf"))
    driver.get(page_url)

    # Give the page a moment to load its PDF viewer scripts.
    time.sleep(WAIT_SECONDS)

    # Try a few common selectors for PDF viewer download buttons (Moody's varies by template).
    candidate_selectors = [
        (By.CSS_SELECTOR, "button#download"),
        (By.CSS_SELECTOR, "a#download"),
        (By.CSS_SELECTOR, "button[aria-label='Download']"),
        (By.CSS_SELECTOR, "a[aria-label='Download']"),
        (By.CSS_SELECTOR, "button[title='Download']"),
        (By.CSS_SELECTOR, "a[title='Download']"),
        (By.CSS_SELECTOR, ".toolbarButton.download"),
        (By.CSS_SELECTOR, "[data-testid*='download']"),
    ]

    clicked = False
    last_error = None
    for by, sel in candidate_selectors:
        try:
            btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((by, sel)))
            btn.click()
            clicked = True
            break
        except Exception as exc:
            last_error = exc
            continue

    if not clicked:
        raise RuntimeError(f"Could not find/click download button on {page_url}: {last_error}")

    # If Chrome prompts with a Save As dialog, handle it; otherwise wait for auto download.
    handled = _handle_save_as_dialog(destination)
    if handled:
        # Wait until the chosen destination exists and is a real PDF.
        end = time.time() + 90
        while time.time() < end:
            if destination.exists() and _looks_like_pdf(destination):
                return
            time.sleep(0.25)
        raise TimeoutError(f"Save As handled but {destination} did not appear as a valid PDF.")

    # Auto-download path: wait for a new PDF to show up, then rename to our clean filename.
    downloaded = _wait_for_new_pdf(destination.parent, before=before)
    if downloaded != destination:
        try:
            if destination.exists():
                destination.unlink()
        except Exception:
            pass
        downloaded.replace(destination)

    if not _looks_like_pdf(destination):
        raise RuntimeError(f"Downloaded file is not a valid PDF: {destination}")


def _process_cell(worksheet, row: int) -> bool:
    """Select the cell, follow its hyperlink, and download the PDF. Returns False if no more links."""
    cell_address = f"A{row}"
    cell = worksheet.Range(cell_address)
    cell_value = (str(cell.Value).strip() if cell.Value is not None else "") or f"rating_methodology_row_{row}"
    hyperlink_count = cell.Hyperlinks.Count

    if hyperlink_count == 0:
        # Stop if column A is empty—this indicates we've reached the end of the list.
        if not cell.Value:
            print(f"Row {row}: no value or hyperlink detected. Stopping.")
            return False
        print(f"Row {row}: value present but no hyperlink; skipping.")
        return True

    hyperlink = cell.Hyperlinks(1)
    pdf_url = hyperlink.Address
    if not pdf_url:
        raise RuntimeError(f"Row {row}: hyperlink does not contain an address.")

    filename = _infer_filename(cell_value, pdf_url)
    destination = DOWNLOAD_DIR / filename
    _click_download_and_save(_process_cell.driver, pdf_url, destination)
    print(f"Row {row}: downloaded PDF to {destination}")
    return True


def main() -> None:
    excel = None
    workbook = None
    driver = None
    try:
        # Create a single browser instance for the whole run.
        driver = _create_webdriver(DOWNLOAD_DIR)
        _process_cell.driver = driver

        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = True
        workbook = excel.Workbooks.Open(str(EXCEL_PATH), UpdateLinks=False, ReadOnly=True)
        worksheet = workbook.Worksheets(SHEET_NAME)
        worksheet.Activate()

        downloaded_count = 0
        for row in range(START_ROW, MAX_ROW + 1):
            # Skip rows hidden by filters so we only download visible entries.
            try:
                if worksheet.Rows(row).EntireRow.Hidden:
                    continue
            except Exception:
                # Some Excel states (filters/COM flakiness) can throw; keep going without this optimization.
                pass
            try:
                should_continue = _process_cell(worksheet, row)
                if should_continue and worksheet.Range(f"A{row}").Hyperlinks.Count > 0:
                    downloaded_count += 1
            except Exception as exc:
                print(f"Row {row}: failed to download ({exc})")
                should_continue = True

            if MAX_DOWNLOADS is not None and downloaded_count >= MAX_DOWNLOADS:
                print(f"Reached MAX_DOWNLOADS={MAX_DOWNLOADS}; stopping.")
                break

            if not should_continue:
                break

    finally:
        if workbook is not None:
            workbook.Close(SaveChanges=False)
        if excel is not None:
            excel.Quit()
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()

