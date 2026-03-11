from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml
from playwright.sync_api import sync_playwright

URL = (
    "https://www.anz.co.nz/business/lending/loans/?cid=sem--business--c&PPC=1"
    "&s_kwcid=AL!9240!3!690791405000!p!!g!!anz%20business%20loan"
    "&gclsrc=aw.ds&gad_source=1&gad_campaignid=11618986469"
    "&gbraid=0AAAAADO2W6XCG8kqjUJ6uE5YPJnBP9xYD"
    "&gclid=CjwKCAiAssfLBhBDEiwAcLpwfgc8SYye47GfLv_OV3-9WRUvLHryEogrZU4TDqG"
    "HzW6VlD7F0VrxHBoCdvMQAvD_BwE"
)

RATE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)%\s*p\.a\.\s*base rate, a margin will also apply\.?",
    re.IGNORECASE,
)
FLOATING_CONTEXT_PATTERN = re.compile(
    r"Floating interest rate[\s\S]{0,200}?(\d+(?:\.\d+)?)%\s*p\.a\.",
    re.IGNORECASE,
)
FLOATING_BLOCK_PATTERN = re.compile(
    r"Floating interest rate.{0,200}?(\d+(?:\.\d+)?)%\s*p\.a\.\s*base rate, "
    r"a margin will also apply\.",
    re.IGNORECASE | re.DOTALL,
)


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"series": []}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        return {"series": []}
    data.setdefault("series", [])
    return data


def _save_yaml(path: Path, data: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def _extract_rate(text: str) -> float:
    text = text.replace("\u00a0", " ")
    match = (
        FLOATING_CONTEXT_PATTERN.search(text)
        or FLOATING_BLOCK_PATTERN.search(text)
        or RATE_PATTERN.search(text)
    )
    if not match:
        raise ValueError("Could not find base rate text on the page.")
    return float(match.group(1))


def _extract_rate_from_block(text: str) -> float:
    text = text.replace("\u00a0", " ")
    match = RATE_PATTERN.search(text)
    if match:
        return float(match.group(1))
    match = re.search(r"(\\d+(?:\\.\\d+)?)%\\s*p\\.a\\.", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    raise ValueError("Could not find base rate in floating-rate block.")


def _find_rate_on_page(page) -> float:
    # Give the page a moment to render text
    try:
        page.get_by_text("Floating interest rate", exact=False).first.wait_for(
            timeout=10000
        )
    except Exception:
        pass

    # Try to extract from likely blocks first
    selectors = [
        "text=Floating interest rate",
        "text=base rate, a margin will also apply.",
        "text=base rate",
    ]
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            if loc.count() == 0:
                continue
            block_text = loc.evaluate(
                """(el) => {
                    let node = el;
                    for (let i = 0; i < 8 && node; i++) {
                        if (node.tagName && node.tagName.toLowerCase() === 'section') {
                            break;
                        }
                        node = node.parentElement;
                    }
                    return node ? node.innerText : el.parentElement?.innerText || el.innerText;
                }"""
            )
            if block_text:
                return _extract_rate_from_block(block_text)
        except Exception:
            continue

    # Fallback to full body text search
    text = page.inner_text("body")
    return _extract_rate(text)


def main() -> None:
    output_dir = Path(__file__).resolve().parent
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            }
        )
        page.goto(URL, wait_until="networkidle", timeout=60000)

        # Try to accept cookies if a banner appears (best effort)
        for selector in (
            "button:has-text('Accept')",
            "button:has-text('I accept')",
            "button:has-text('Agree')",
        ):
            try:
                page.locator(selector).first.click(timeout=2000)
                break
            except Exception:
                pass

        try:
            rate = _find_rate_on_page(page)
        except Exception:
            text = page.inner_text("body")
            debug_path = output_dir / f"anz_rate_debug_{timestamp}.txt"
            debug_path.write_text(text, encoding="utf-8")
            raise

        screenshot_path = output_dir / f"ANZ Business Base Rate - {timestamp}.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        browser.close()

    yaml_path = output_dir / "anz_business_base_rate.yaml"
    data = _load_yaml(yaml_path)
    series: List[Dict[str, Any]] = data.get("series", [])
    series.append(
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "rate_percent": rate,
            "source": URL,
        }
    )
    data["series"] = series
    _save_yaml(yaml_path, data)

    print(f"Saved rate: {rate:.2f}%")
    print(f"Screenshot: {screenshot_path}")


if __name__ == "__main__":
    main()
