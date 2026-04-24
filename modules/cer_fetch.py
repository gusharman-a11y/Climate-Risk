"""
One-shot fetcher for Clean Energy Regulator (CER) public ACCU data.

Downloads two artefacts from the CER website and caches them locally under
`data_cache/`:

  1. ACCU Scheme project register   – every registered ACCU project
  2. ACCU issuance table            – ACCUs issued per project / month

The CER publishes these as XLSX/CSV linked from public pages. URLs include the
publication date (e.g. `...-18-march-2026.xlsx`) and change each month, so we
scrape the register page HTML to discover the current asset. The scraped URL is
persisted next to the data file so subsequent runs can skip HTML parsing if the
user re-points at a specific file.

Usage:

    # one-shot download, populates data_cache/
    python -m modules.cer_fetch

    # or force refresh
    python -m modules.cer_fetch --refresh

    # or supply a file you downloaded manually
    python -m modules.cer_fetch --register /path/to/register.xlsx \\
                                --issuance /path/to/issuance.xlsx

The Streamlit dashboard (`modules.carbon_market`) prefers the cache when
present and falls back to the illustrative sample data otherwise.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

CACHE_DIR = Path(__file__).resolve().parent.parent / "data_cache"
REGISTER_PAGE = "https://cer.gov.au/markets/reports-and-data/accu-project-and-contract-register"
ISSUANCE_PAGE = "https://cer.gov.au/markets/reports-and-data/australian-carbon-credit-unit-data"

REGISTER_FILE_STEM = "accu_project_register"
ISSUANCE_FILE_STEM = "accu_issuances"

USER_AGENT = (
    "Mozilla/5.0 (climate-risk-dashboard; +https://github.com/) "
    "python-urllib one-shot fetch"
)


class _LinkScraper(HTMLParser):
    """Collect every <a href="..."> with its anchor text."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []  # (href, text)
        self._pending_href: str | None = None
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href:
                self._pending_href = href
                self._buf = []

    def handle_data(self, data: str) -> None:
        if self._pending_href is not None:
            self._buf.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._pending_href is not None:
            text = " ".join(" ".join(self._buf).split())
            self.links.append((self._pending_href, text))
            self._pending_href = None
            self._buf = []


def _http_get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _find_asset(page_url: str, keywords: list[str], extensions: tuple[str, ...]) -> str:
    """Scrape `page_url` for a link whose href or anchor mentions every keyword
    (case-insensitive) and whose href ends in one of `extensions`. Returns the
    absolute URL of the best match, preferring the most recent-looking one.
    """
    html = _http_get(page_url).decode("utf-8", errors="replace")
    parser = _LinkScraper()
    parser.feed(html)

    candidates: list[tuple[str, str]] = []
    kws = [k.lower() for k in keywords]
    for href, text in parser.links:
        haystack = f"{href} {text}".lower()
        if all(k in haystack for k in kws) and href.lower().endswith(extensions):
            candidates.append((href, text))

    if not candidates:
        raise RuntimeError(
            f"No matching asset on {page_url} for keywords={keywords} "
            f"ext={extensions}. The page markup may have changed."
        )

    # Prefer links that contain a 4-digit year – picks the newest release when
    # multiple months are archived side-by-side.
    date_re = re.compile(r"(20\d{2})[-_/ ]?(0?[1-9]|1[0-2])")

    def _rank(item: tuple[str, str]) -> tuple[int, str]:
        href, text = item
        m = date_re.search(href) or date_re.search(text)
        if m:
            return (int(f"{m.group(1)}{int(m.group(2)):02d}"), href)
        return (0, href)

    candidates.sort(key=_rank, reverse=True)
    best_href, _ = candidates[0]
    return urljoin(page_url, best_href)


def _download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = _http_get(url)
    dest.write_bytes(data)
    (dest.parent / f"{dest.stem}.source.txt").write_text(url + "\n", encoding="utf-8")
    return dest


def _cache_path(stem: str, url_or_path: str | Path) -> Path:
    ext = Path(str(url_or_path)).suffix.lower()
    if ext not in (".csv", ".xlsx", ".xls"):
        ext = ".xlsx"
    return CACHE_DIR / f"{stem}{ext}"


def fetch_register(force: bool = False) -> Path:
    """Download the latest ACCU project register to the cache. Returns the path."""
    existing = list(CACHE_DIR.glob(f"{REGISTER_FILE_STEM}.*"))
    existing = [p for p in existing if p.suffix.lower() in (".csv", ".xlsx", ".xls")]
    if existing and not force:
        return existing[0]

    url = _find_asset(
        REGISTER_PAGE,
        keywords=["project", "register"],
        extensions=(".xlsx", ".xls", ".csv"),
    )
    dest = _cache_path(REGISTER_FILE_STEM, url)
    print(f"[cer_fetch] register → {url}")
    return _download(url, dest)


def fetch_issuances(force: bool = False) -> Path:
    """Download the latest ACCU issuance table to the cache. Returns the path."""
    existing = list(CACHE_DIR.glob(f"{ISSUANCE_FILE_STEM}.*"))
    existing = [p for p in existing if p.suffix.lower() in (".csv", ".xlsx", ".xls")]
    if existing and not force:
        return existing[0]

    url = _find_asset(
        ISSUANCE_PAGE,
        keywords=["issuance"],
        extensions=(".xlsx", ".xls", ".csv"),
    )
    dest = _cache_path(ISSUANCE_FILE_STEM, url)
    print(f"[cer_fetch] issuances → {url}")
    return _download(url, dest)


def install_manual(register: Path | None, issuance: Path | None) -> None:
    """Copy a manually-supplied file into the cache under the canonical name."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if register:
        dest = _cache_path(REGISTER_FILE_STEM, register)
        shutil.copyfile(register, dest)
        print(f"[cer_fetch] copied register → {dest}")
    if issuance:
        dest = _cache_path(ISSUANCE_FILE_STEM, issuance)
        shutil.copyfile(issuance, dest)
        print(f"[cer_fetch] copied issuances → {dest}")


def cached_register_path() -> Path | None:
    for ext in (".csv", ".xlsx", ".xls"):
        p = CACHE_DIR / f"{REGISTER_FILE_STEM}{ext}"
        if p.exists():
            return p
    return None


def cached_issuance_path() -> Path | None:
    for ext in (".csv", ".xlsx", ".xls"):
        p = CACHE_DIR / f"{ISSUANCE_FILE_STEM}{ext}"
        if p.exists():
            return p
    return None


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Fetch CER ACCU data into data_cache/")
    ap.add_argument("--refresh", action="store_true", help="re-download even if cached")
    ap.add_argument("--register", type=Path, help="use a manually-downloaded register file")
    ap.add_argument("--issuance", type=Path, help="use a manually-downloaded issuance file")
    args = ap.parse_args(argv)

    if args.register or args.issuance:
        install_manual(args.register, args.issuance)
        return 0

    try:
        fetch_register(force=args.refresh)
        fetch_issuances(force=args.refresh)
    except Exception as exc:
        print(f"[cer_fetch] failed: {exc}", file=sys.stderr)
        print(
            "Hint: CER publishes the files at:\n"
            f"  {REGISTER_PAGE}\n  {ISSUANCE_PAGE}\n"
            "Download them manually and re-run:\n"
            "  python -m modules.cer_fetch "
            "--register <file> --issuance <file>",
            file=sys.stderr,
        )
        return 1

    print("[cer_fetch] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
