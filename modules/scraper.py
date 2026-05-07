"""Sustainability-report ingestion — three layers, most reliable first.

Layer 1: PDF upload (user uploads file directly — always works, parses locally)
Layer 2: URL paste (fetch + parse a URL the user provides)
Layer 3: Auto-search (DuckDuckGo HTML search → first PDF link → fetch + parse)

All three feed the same parser and the same emissions cache. Whichever layer
populates a record, the Phase 2 trajectory math runs the same way.
"""

from __future__ import annotations

import io
import re
from urllib.parse import quote_plus, urljoin, urlparse

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


# ─── PDF parsing ─────────────────────────────────────────────────────────────

# Numbers in sustainability reports often have commas, full stops, or spaces
# as thousands separators. e.g. "12,345" / "12 345" / "12.345" (EU style).
_NUM = r"(\d{1,3}(?:[,\. \s]\d{3})+|\d+(?:\.\d+)?)"
_UNIT = r"(?:tco2e?|tco2-?e|t\s*co2-?e|tonnes?\s*co2|kt\s*co2|mt\s*co2|tonnes?)"

# Patterns for headline scope figures
SCOPE_PATTERNS = [
    (re.compile(rf"scope\s*1[^a-z0-9\n]{{0,80}}{_NUM}\s*{_UNIT}?", re.I), "s1"),
    (re.compile(rf"scope\s*2[^a-z0-9\n]{{0,80}}{_NUM}\s*{_UNIT}?", re.I), "s2"),
    (re.compile(rf"scope\s*3[^a-z0-9\n]{{0,80}}{_NUM}\s*{_UNIT}?", re.I), "s3"),
]

# Reporting year — usually "FY24" or "for the year ended 30 June 2024" or "2024"
YEAR_PATTERNS = [
    re.compile(r"for the (?:year|financial year)\s+ended\s+(?:\d{1,2}\s+)?(?:[a-z]+\s+)?((?:19|20)\d{2})", re.I),
    re.compile(r"\bFY\s*(\d{2})\b"),
    re.compile(r"\b((?:19|20)\d{2})\s*sustainability report\b", re.I),
    re.compile(r"\bsustainability report\s+((?:19|20)\d{2})\b", re.I),
]


def _to_float(s: str) -> float | None:
    """Parse '12,345', '12 345', '12.345', '12345.67' to float."""
    s = s.strip().replace(" ", " ")
    # If there's a decimal-looking last segment with 1-2 digits, treat as decimal
    if re.match(r"^\d{1,3}(\.\d{3})+$", s):  # European style 12.345 = 12345
        s = s.replace(".", "")
    s = s.replace(",", "").replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return None


def _normalise_to_tco2e(value: float, unit_hint: str) -> float:
    u = unit_hint.lower()
    if "kt" in u:
        return value * 1_000
    if "mt" in u:
        return value * 1_000_000
    return value


def parse_emissions(pdf_bytes: bytes) -> dict:
    """Extract reporting year and Scope 1/2/3 from a sustainability-report PDF.
    Returns a dict with keys: reporting_year, s1, s2, s3, pages_read, snippets."""
    try:
        import pdfplumber
    except ImportError:
        return {"error": "pdfplumber not installed"}

    text_chunks: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages[:160]:
            t = page.extract_text() or ""
            text_chunks.append(t)
    full = "\n".join(text_chunks)
    text = full.lower()

    # ── Reporting year ──
    reporting_year: int | None = None
    for pat in YEAR_PATTERNS:
        m = pat.search(full)
        if m:
            v = m.group(1)
            if len(v) == 2:
                reporting_year = 2000 + int(v)
            else:
                reporting_year = int(v)
            break

    # ── Scope figures ── take the first plausible match per scope.
    findings: dict[str, float | None] = {"s1": None, "s2": None, "s3": None}
    snippets: dict[str, str] = {}
    for pat, key in SCOPE_PATTERNS:
        for m in pat.finditer(text):
            num = _to_float(m.group(1))
            if num is None or num < 1:
                continue
            unit_hint = m.group(0)[m.end(1) - m.start():] if m.end(1) <= len(m.group(0)) else ""
            findings[key] = _normalise_to_tco2e(num, unit_hint)
            snippets[key] = m.group(0)[:200]
            break

    return {
        "reporting_year": reporting_year,
        "s1": findings["s1"], "s2": findings["s2"], "s3": findings["s3"],
        "pages_read": len(text_chunks),
        "snippets": snippets,
    }


# ─── HTTP fetch ──────────────────────────────────────────────────────────────

def fetch_pdf(url: str, timeout: int = 30) -> bytes:
    """Download a PDF from a URL with a browser-like UA. Raises on non-2xx."""
    import requests
    r = requests.get(url, headers={"User-Agent": DEFAULT_UA}, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    if "pdf" not in r.headers.get("content-type", "").lower() and not r.content[:4] == b"%PDF":
        raise ValueError(f"URL did not return a PDF (content-type={r.headers.get('content-type')}).")
    return r.content


# ─── Auto-search (best-effort) ───────────────────────────────────────────────

DDG_HTML = "https://html.duckduckgo.com/html/"


def search_report_url(company: str, year_hint: int | None = None, max_results: int = 5) -> list[str]:
    """Best-effort search for a company's latest sustainability report PDF.
    Returns up to `max_results` URLs ranked by likelihood."""
    import requests

    query = f'"{company}" sustainability report PDF'
    if year_hint:
        query += f" {year_hint}"
    r = requests.post(
        DDG_HTML, data={"q": query},
        headers={"User-Agent": DEFAULT_UA},
        timeout=20,
    )
    r.raise_for_status()
    html = r.text

    # Pull out result URLs. DDG HTML wraps results in <a class="result__a" href="...">.
    candidates: list[str] = []
    for m in re.finditer(r'href="(https?://[^"]+\.pdf[^"]*)"', html, re.I):
        url = m.group(1)
        if url not in candidates:
            candidates.append(url)
        if len(candidates) >= max_results:
            break
    # Fallback: result links that look like sustainability/IR pages
    if len(candidates) < max_results:
        for m in re.finditer(r'href="(https?://[^"]+(?:sustainab|esg|climate|annual)[^"]*)"', html, re.I):
            url = m.group(1)
            if url not in candidates:
                candidates.append(url)
            if len(candidates) >= max_results:
                break
    return candidates[:max_results]


def fetch_and_parse(url: str) -> dict:
    """One-shot: fetch a PDF URL and parse emissions. Returns the parser dict
    with the source URL added."""
    pdf = fetch_pdf(url)
    out = parse_emissions(pdf)
    out["source_url"] = url
    return out


# ─── Stored URL registry (data/report_urls.csv) ──────────────────────────────

from pathlib import Path

_URLS_CSV = Path(__file__).resolve().parent.parent / "data" / "report_urls.csv"


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "")).strip().lower()


def load_stored_urls():
    """Read data/report_urls.csv. Returns a list of dicts with keys
    'company', 'name_norm', 'report', 'period', 'url', 'notes'.
    Returns [] if the file is missing or unreadable."""
    if not _URLS_CSV.exists():
        return []
    try:
        import pandas as pd
        df = pd.read_csv(_URLS_CSV)
        df.columns = [c.strip() for c in df.columns]
    except Exception:
        return []
    rows = []
    for _, r in df.iterrows():
        company = str(r.get("SBTi Company Name", "")).strip()
        if not company:
            continue
        rows.append({
            "company": company,
            "name_norm": _norm(company),
            "report": str(r.get("Report Name", "")).strip(),
            "period": str(r.get("Reporting Period", "")).strip(),
            "url": str(r.get("URL", "")).strip(),
            "notes": str(r.get("Notes", "") or "").strip(),
        })
    return rows


def lookup_stored_url(company: str, isin: str | None = None,
                     stored: list | None = None) -> dict | None:
    """Find a stored URL entry matching the company. Tries exact name match
    first, then case-insensitive prefix/contains match."""
    stored = stored if stored is not None else load_stored_urls()
    target = _norm(company)
    if not target:
        return None
    # Exact normalised match
    for rec in stored:
        if rec["name_norm"] == target:
            return rec
    # Substring match either way
    for rec in stored:
        if target in rec["name_norm"] or rec["name_norm"] in target:
            return rec
    # Token-overlap match — strip "limited"/"group"/"corporation" and compare first word
    target_root = target.split()[0] if target else ""
    for rec in stored:
        if target_root and target_root == rec["name_norm"].split()[0]:
            return rec
    return None
