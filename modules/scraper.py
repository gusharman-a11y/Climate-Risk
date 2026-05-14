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

# Numeric patterns. Sustainability reports use commas, spaces, or full stops
# as thousands separators. e.g. "12,345" / "12 345" / "12.345" (EU style).
_NUM = r"-?\d{1,3}(?:[,\. ]\d{3})+|-?\d+(?:\.\d+)?"
_UNIT_RX = re.compile(r"(?:t\s?co2-?e?|tco2-?e?|tonnes?|kt\s?co2-?e?|mt\s?co2-?e?)", re.I)

YEAR_PATTERNS = [
    re.compile(r"for the (?:year|financial year)\s+ended\s+(?:\d{1,2}\s+)?(?:[a-z]+\s+)?((?:19|20)\d{2})", re.I),
    re.compile(r"\b(FY\s?\d{2,4}|CY\s?\d{2,4})\b", re.I),
    re.compile(r"\b((?:19|20)\d{2})\s*sustainability report\b", re.I),
    re.compile(r"\bsustainability report\s+((?:19|20)\d{2})\b", re.I),
    re.compile(r"\b((?:19|20)\d{2})\s+annual report\b", re.I),
]


def _to_float(s):
    """Parse '12,345' / '12 345' / '12.345' / '12345.67' to float."""
    if not s:
        return None
    s = str(s).strip().replace(",", "").replace(" ", "")
    if re.match(r"^-?\d{1,3}(\.\d{3})+$", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _normalise_to_tco2e(value, unit_hint):
    u = (unit_hint or "").lower()
    if "kt" in u:
        return value * 1_000
    if "mt" in u:
        return value * 1_000_000
    return value


def _extract_year(s):
    """Extract a 4-digit year from any string ('FY24', '2024', 'CY23')."""
    if not s:
        return None
    m = re.search(r"(19|20)\d{2}", str(s))
    if m:
        return int(m.group(0))
    m = re.search(r"FY\s?(\d{2})", str(s), re.I)
    if m:
        return 2000 + int(m.group(1))
    m = re.search(r"CY\s?(\d{2})", str(s), re.I)
    if m:
        return 2000 + int(m.group(1))
    return None


def _row_scope(row):
    """Identify which scope a table row refers to, if any."""
    if not row:
        return None
    text = " ".join(str(c) for c in row[:3] if c).lower()
    # Skip rows about targets/baselines/changes — we want absolute emissions
    if "target" in text or "baseline" in text or "% change" in text or "reduction" in text:
        return None
    if re.search(r"\bscope\s*1\b", text) and "total" not in text:
        if re.search(r"scope\s*1\s*[,&+]|scope\s*1\s*and", text):
            return None
        return "s1"
    if re.search(r"\bscope\s*2\b", text):
        if "market" in text:
            return "s2_market"
        if "location" in text:
            return "s2_location"
        return "s2"
    if re.search(r"\bscope\s*3\b", text):
        if re.search(r"scope\s*3\s*category\s*\d+", text):
            return None
        return "s3"
    return None


def _candidate_from_table(table):
    """Walk a table looking for Scope 1/2/3 rows with numeric year columns."""
    if not table or len(table) < 2:
        return []
    header_years = []
    header_idx = -1
    for i, row in enumerate(table[:4]):
        years = [_extract_year(c) for c in row]
        non_none = sum(1 for y in years if y)
        if non_none >= 2:
            header_years = years
            header_idx = i
            break
    candidates = []
    data_rows = table[header_idx + 1:] if header_idx >= 0 else table
    for row in data_rows:
        scope = _row_scope(row)
        if not scope:
            continue
        for col_idx, cell in enumerate(row):
            num = _to_float(str(cell))
            if num is None or abs(num) < 1:
                continue
            year = header_years[col_idx] if 0 <= col_idx < len(header_years) else None
            candidates.append({
                "scope": scope, "year": year, "value": num,
                "row_text": " | ".join(str(c) for c in row if c)[:200],
            })
    return candidates


def parse_emissions(pdf_bytes):
    """Extract reporting year and Scope 1/2/3 from a sustainability-report PDF.

    Strategy:
      1. Try pdfplumber.extract_tables() on every page — sustainability reports
         present emissions in multi-year tables. Match Scope 1/2/3 rows against
         year-headed columns; prefer the latest year. Scope 2 prefers market-based.
      2. Fall back to regex over the full text for any scope not found in tables.

    Returns reporting_year, s1, s2, s3, pages_read, snippets, all_candidates.
    """
    try:
        import pdfplumber
    except ImportError:
        return {"error": "pdfplumber not installed"}

    text_chunks = []
    all_table_candidates = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages[:200]:
            t = page.extract_text() or ""
            text_chunks.append(t)
            try:
                tables = page.extract_tables() or []
            except Exception:
                tables = []
            for tbl in tables:
                all_table_candidates.extend(_candidate_from_table(tbl))
    full = "\n".join(text_chunks)

    reporting_year = None
    for pat in YEAR_PATTERNS:
        m = pat.search(full)
        if m:
            reporting_year = _extract_year(m.group(1))
            if reporting_year:
                break

    findings = {"s1": None, "s2": None, "s3": None}
    sources = {}

    def _pick(scope_keys):
        cs = [c for c in all_table_candidates if c["scope"] in scope_keys]
        if not cs:
            return None
        with_year = [c for c in cs if c.get("year")]
        if with_year:
            return max(with_year, key=lambda c: (c["year"], c["value"]))
        return max(cs, key=lambda c: c["value"])

    s1 = _pick(["s1"])
    if s1:
        findings["s1"] = s1["value"]
        sources["s1"] = f"Table (year={s1.get('year') or '?'}): {s1['row_text']}"
    s2 = _pick(["s2_market"]) or _pick(["s2"]) or _pick(["s2_location"])
    if s2:
        findings["s2"] = s2["value"]
        sources["s2"] = f"Table (year={s2.get('year') or '?'}): {s2['row_text']}"
    s3 = _pick(["s3"])
    if s3:
        findings["s3"] = s3["value"]
        sources["s3"] = f"Table (year={s3.get('year') or '?'}): {s3['row_text']}"

    # Regex fallback for any scope not yet found
    text = full.lower()
    fallback_patterns = [
        (re.compile(rf"scope\s*1\b[^a-z0-9\n]{{0,60}}({_NUM})", re.I), "s1"),
        (re.compile(rf"scope\s*2\b[^a-z0-9\n]{{0,60}}({_NUM})", re.I), "s2"),
        (re.compile(rf"scope\s*3\b[^a-z0-9\n]{{0,60}}({_NUM})", re.I), "s3"),
    ]
    for pat, key in fallback_patterns:
        if findings[key] is not None:
            continue
        for m in pat.finditer(text):
            num = _to_float(m.group(1))
            if num is None or num < 1:
                continue
            tail = text[m.end():m.end() + 30]
            unit_hint = ""
            um = _UNIT_RX.search(tail)
            if um:
                unit_hint = um.group(0)
            findings[key] = _normalise_to_tco2e(num, unit_hint)
            sources[key] = f"Regex: {m.group(0)[:160]}"
            break

    return {
        "reporting_year": reporting_year,
        "s1": findings["s1"],
        "s2": findings["s2"],
        "s3": findings["s3"],
        "pages_read": len(text_chunks),
        "snippets": sources,
        "emissions_candidates": all_table_candidates,
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


def fetch_html(url: str, timeout: int = 30) -> tuple[str, str]:
    """Fetch an HTML page. Returns (final_url, html_text)."""
    import requests
    r = requests.get(url, headers={"User-Agent": DEFAULT_UA}, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    return r.url, r.text


# ─── Auto-discover PDF links from an IR landing page ─────────────────────────

# Keywords ranked by likelihood of pointing at the latest sustainability/annual
# report. Used to score and rank candidate PDF links.
_KEYWORDS_HIGH = [
    "sustainability report", "climate report", "esg report", "tcfd report",
    "impact report", "annual sustainability",
]
_KEYWORDS_MED = ["annual report", "corporate report", "integrated report"]
_KEYWORDS_LOW = ["climate", "sustainability", "esg", "tcfd", "annual", "report"]


def _candidate_score(url: str, text: str) -> int:
    blob = (url + " " + text).lower()
    score = 0
    # Recency — current and recent years
    import datetime
    yr = datetime.datetime.utcnow().year
    for delta, weight in ((0, 6), (-1, 4), (-2, 2)):
        target = str(yr + delta)
        if target in blob:
            score += weight
        # FY24, FY25 abbreviations
        if f"fy{(yr + delta) % 100}" in blob or f"fy{yr + delta}" in blob:
            score += weight
    # Title/topic keywords
    for kw in _KEYWORDS_HIGH:
        if kw in blob:
            score += 5
    for kw in _KEYWORDS_MED:
        if kw in blob:
            score += 3
    for kw in _KEYWORDS_LOW:
        if kw in blob:
            score += 1
    # Penalise obviously-irrelevant
    for noise in ("policy", "terms", "cookies", "privacy", "media-release",
                  "presentation", "investor-presentation", "appendix", "minutes"):
        if noise in blob:
            score -= 4
    return score


def discover_pdfs(landing_url: str, max_results: int = 5) -> list[dict]:
    """Fetch an IR/sustainability landing page; return ranked PDF candidates.
    Each result: {url, anchor_text, score}. Empty list if no PDFs found."""
    final_url, html = fetch_html(landing_url)
    base = urlparse(final_url)
    base_host = f"{base.scheme}://{base.netloc}"

    # Find <a href="...pdf...">anchor text</a>
    candidates: dict[str, tuple[str, int]] = {}
    for m in re.finditer(
        r'<a\s+[^>]*href\s*=\s*"([^"]+\.(?:pdf|ashx)(?:[?#][^"]*)?)"[^>]*>(.*?)</a>',
        html, re.I | re.S,
    ):
        href = m.group(1).strip()
        text = re.sub(r"<[^>]+>", " ", m.group(2))
        text = re.sub(r"\s+", " ", text).strip()
        # Resolve relative URLs
        if href.startswith("/"):
            href = base_host + href
        elif not href.startswith("http"):
            href = urljoin(final_url, href)
        score = _candidate_score(href, text)
        # Keep highest-scoring entry per URL
        if href not in candidates or candidates[href][1] < score:
            candidates[href] = (text, score)

    ranked = sorted(
        ({"url": u, "anchor_text": t, "score": s} for u, (t, s) in candidates.items()),
        key=lambda d: d["score"], reverse=True,
    )
    return ranked[:max_results]


def resolve_url(url: str) -> tuple[str, list[dict]]:
    """If `url` ends with .pdf/.ashx, return (url, []) — already a direct PDF.
    Otherwise treat as a landing page; discover candidates and return
    (best_candidate_url, all_candidates). Raises if no candidates found."""
    if re.search(r"\.(pdf|ashx)(?:$|[?#])", url, re.I):
        return url, []
    candidates = discover_pdfs(url)
    if not candidates:
        raise ValueError(f"No PDF candidates found on {url}")
    return candidates[0]["url"], candidates


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
    """One-shot: fetch a URL and parse emissions. If the URL is a landing
    page rather than a direct PDF, discover the best candidate and follow
    that. Returns the parser dict with the resolved source URL."""
    resolved, candidates = resolve_url(url)
    pdf = fetch_pdf(resolved)
    out = parse_emissions(pdf)
    out["source_url"] = resolved
    out["original_url"] = url
    if candidates:
        out["all_candidates"] = candidates
    return out


# ─── Stored URL registry (data/report_urls.csv) ──────────────────────────────

from pathlib import Path

_URLS_CSV = Path(__file__).resolve().parent.parent / "data" / "report_urls.csv"
_ASX200_CSV = Path(__file__).resolve().parent.parent / "data" / "asx200_non_sbti.csv"


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "")).strip().lower()


def load_stored_urls():
    """Read curated report URLs from both data/report_urls.csv (SBTi cohort)
    and data/asx200_non_sbti.csv (non-SBTi cohort). Returns a list of dicts
    with keys 'company', 'name_norm', 'report', 'period', 'url', 'notes',
    'source' ('sbti' or 'asx200')."""
    rows = []
    try:
        import pandas as pd
        if _URLS_CSV.exists():
            df = pd.read_csv(_URLS_CSV)
            df.columns = [c.strip() for c in df.columns]
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
                    "source": "sbti",
                })
        if _ASX200_CSV.exists():
            df = pd.read_csv(_ASX200_CSV)
            df.columns = [c.strip() for c in df.columns]
            for _, r in df.iterrows():
                company = str(r.get("Company Name", "")).strip()
                url = str(r.get("Source URL", "")).strip()
                if not company or not url or url.lower() in ("nan", ""):
                    continue
                rows.append({
                    "company": company,
                    "name_norm": _norm(company),
                    "report": "Sustainability/IR landing",
                    "period": str(r.get("Stated Target Year", "")).strip(),
                    "url": url,
                    "notes": str(r.get("Notes", "") or "").strip(),
                    "source": "asx200",
                })
    except Exception:
        return rows
    # De-duplicate by URL — keep the first occurrence (sbti cohort takes priority)
    seen = set()
    unique = []
    for r in rows:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        unique.append(r)
    return unique


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
