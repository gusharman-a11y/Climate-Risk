"""
fetch_cer.py  –  Live CER data fetcher.
Run locally (Python 3.8+, pip install requests openpyxl pandas).
Falls back to sample_data.py when the CER site is unreachable.
"""

import io
import json
import os
import re
import time
import urllib.request
import urllib.error
from datetime import datetime, date

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

CACHE_FILE = os.path.join(os.path.dirname(__file__), "_cer_cache.json")
CACHE_MAX_HOURS = 12

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
}

# Known CER register page – we scrape the CSV download link from this page
_REGISTER_PAGE = "https://cer.gov.au/markets/reports-and-data/accu-project-and-contract-register"


def _fetch_url(url, timeout=20):
    req = urllib.request.Request(url, headers=_HEADERS)
    resp = urllib.request.urlopen(req, timeout=timeout)
    return resp.read()


def _find_csv_url(html: bytes) -> str | None:
    """Extract direct CSV download URL from the CER register page."""
    text = html.decode("utf-8", errors="replace")
    # Look for .csv or .xlsx href patterns
    for pattern in [
        r'href=["\']([^"\']*\.csv[^"\']*)["\']',
        r'href=["\']([^"\']*accu[^"\']*project[^"\']*register[^"\']*\.xlsx[^"\']*)["\']',
        r'href=["\']([^"\']*document[^"\']*accu[^"\']*)["\']',
    ]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            url = match.group(1)
            if not url.startswith("http"):
                url = "https://cer.gov.au" + url
            return url
    return None


def _parse_register_xlsx(data: bytes) -> list[dict]:
    """Parse the CER ACCU project register Excel file."""
    if not HAS_PANDAS:
        return []
    df = pd.read_excel(io.BytesIO(data), sheet_name=0, header=0)
    df.columns = [str(c).strip() for c in df.columns]

    # Normalise common column name variants
    col_map = {}
    for col in df.columns:
        cl = col.lower()
        if "participant" in cl or "proponent" in cl or "developer" in cl:
            col_map[col] = "developer"
        elif "project name" in cl or "name" in cl:
            col_map[col] = "name"
        elif "project id" in cl or "id" in cl:
            col_map[col] = "id"
        elif "method" in cl and "type" not in cl:
            col_map[col] = "method_full"
        elif "state" in cl or "location" in cl:
            col_map[col] = "state"
        elif "accu" in cl and "issu" in cl:
            col_map[col] = "accu_issued"
        elif "status" in cl:
            col_map[col] = "status"
        elif "area" in cl:
            col_map[col] = "area_ha"
        elif "registered" in cl or "date" in cl:
            col_map[col] = "registered_date"
    df = df.rename(columns=col_map)

    projects = []
    for _, row in df.iterrows():
        p = {}
        for field in ["developer", "name", "id", "method_full", "state",
                       "accu_issued", "status", "area_ha", "registered_date"]:
            val = row.get(field, "")
            if pd.isna(val):
                val = ""
            p[field] = str(val).strip() if val != "" else ""

        # Skip rows with no useful data
        if not p.get("name") and not p.get("id"):
            continue

        # Parse method base + version
        mf = p.get("method_full", "")
        ver_match = re.search(r"v\d+\.\d+", mf, re.IGNORECASE)
        p["method_version"] = ver_match.group(0) if ver_match else "v1.0"
        p["method_base"]    = re.sub(r"\s*v\d+\.\d+.*$", "", mf, flags=re.IGNORECASE).strip()

        # Parse ACCUs
        try:
            p["accu_issued"] = int(float(str(p["accu_issued"]).replace(",", "")))
        except Exception:
            p["accu_issued"] = 0

        # Parse area
        try:
            p["area_ha"] = int(float(str(p["area_ha"]).replace(",", "")))
        except Exception:
            p["area_ha"] = None

        # Parse registration year
        try:
            p["registered_year"] = int(str(p.get("registered_date", ""))[:4])
        except Exception:
            p["registered_year"] = 2018

        # We have no FY breakdown from the register; leave empty (dashboard handles it)
        p["fy_issuances"] = {}
        p["lat"] = None
        p["lon"] = None

        projects.append(p)

    return projects


def _cache_is_fresh() -> bool:
    if not os.path.exists(CACHE_FILE):
        return False
    mtime = os.path.getmtime(CACHE_FILE)
    age_h = (time.time() - mtime) / 3600
    return age_h < CACHE_MAX_HOURS


def _load_cache() -> list[dict] | None:
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(projects: list[dict]):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(projects, f)
    except Exception:
        pass


def fetch_live_projects(verbose=True) -> tuple[list[dict], str]:
    """
    Returns (projects, source_label).
    source_label is "CER live", "CER cached", or "sample data".
    """
    # 1. Try cache first (avoids hammering CER on repeat runs)
    if _cache_is_fresh():
        data = _load_cache()
        if data:
            if verbose:
                print(f"[CER] Using cached data ({len(data)} projects)")
            return data, "CER (cached)"

    # 2. Try live fetch
    if verbose:
        print("[CER] Fetching live register page …")
    try:
        page_html = _fetch_url(_REGISTER_PAGE, timeout=15)
        csv_url   = _find_csv_url(page_html)

        if csv_url:
            if verbose:
                print(f"[CER] Downloading register: {csv_url}")
            file_data = _fetch_url(csv_url, timeout=30)
            projects  = _parse_register_xlsx(file_data)
            if projects:
                _save_cache(projects)
                if verbose:
                    print(f"[CER] Loaded {len(projects)} projects from live CER register")
                return projects, "CER (live)"

        if verbose:
            print("[CER] Could not find download link on register page")
    except urllib.error.HTTPError as e:
        if verbose:
            print(f"[CER] HTTP {e.code} — server blocked request (geo/bot filter)")
    except Exception as e:
        if verbose:
            print(f"[CER] Fetch failed: {e}")

    # 3. Fall back to sample data
    if verbose:
        print("[CER] Falling back to representative sample data")
    from accu.sample_data import PROJECTS
    return PROJECTS, "representative sample data (CER unreachable)"
