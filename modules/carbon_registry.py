"""
CER Carbon Market Registry
Downloads and processes ACCU project and Safeguard compliance data
from the Clean Energy Regulator (cer.gov.au).
"""

import io
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

# ── Cache config ───────────────────────────────────────────────────────────────
CACHE_DIR = Path("data/cer_cache")
CACHE_TTL_HOURS = 24

# ── CER download URLs ──────────────────────────────────────────────────────────
# The document URL redirects to the latest CSV on CER's Drupal CMS.
CER_PROJECT_REGISTER_URL = (
    "https://cer.gov.au/document/accu-scheme-project-register-0"
)
# Safeguard compliance data (annual, most-recent published Apr 2026)
CER_SAFEGUARD_URLS = [
    "https://cer.gov.au/sites/default/files/2026-04/2024-25-safeguard-data.csv",
    "https://cer.gov.au/sites/default/files/2026-04/safeguard-data-2024-25.csv",
    "https://cer.gov.au/sites/default/files/2025-04/2023-24-safeguard-data.csv",
]
# Carbon Abatement Contract register
CER_CONTRACT_URL = (
    "https://cer.gov.au/document/carbon-abatement-contract-register"
)

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "application/csv,application/octet-stream,*/*;q=0.8"
    ),
    "Accept-Language": "en-AU,en;q=0.9",
    "Referer": "https://cer.gov.au/",
}


# ── HTTP helper ────────────────────────────────────────────────────────────────

def _try_download_csv(url: str, timeout: int = 20) -> pd.DataFrame | None:
    """Attempt to download a CSV from a URL. Returns None on failure."""
    try:
        sess = requests.Session()
        # Warm the session with a visit to the homepage (picks up cookies)
        try:
            sess.get("https://cer.gov.au/", headers=_HTTP_HEADERS, timeout=8)
        except Exception:
            pass
        time.sleep(0.5)
        resp = sess.get(url, headers=_HTTP_HEADERS, timeout=timeout,
                        allow_redirects=True)
        if resp.status_code != 200:
            return None
        ct = resp.headers.get("Content-Type", "")
        # Accept CSV, Excel, or binary streams
        if any(k in ct for k in ("csv", "excel", "spreadsheet", "octet")):
            return pd.read_csv(io.BytesIO(resp.content))
        # If we got HTML, try parsing for a redirect CSV link
        if "html" in ct:
            from html.parser import HTMLParser

            class _LinkParser(HTMLParser):
                links: list[str] = []
                def handle_starttag(self, tag, attrs):
                    if tag == "a":
                        for attr, val in attrs:
                            if attr == "href" and val and val.endswith(".csv"):
                                self.links.append(val)

            p = _LinkParser()
            p.feed(resp.text)
            for link in p.links:
                full = link if link.startswith("http") else f"https://cer.gov.au{link}"
                inner = sess.get(full, headers=_HTTP_HEADERS, timeout=timeout,
                                 allow_redirects=True)
                if inner.status_code == 200:
                    return pd.read_csv(io.BytesIO(inner.content))
        return None
    except Exception:
        return None


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.parquet"


def _cache_valid(key: str) -> bool:
    p = _cache_path(key)
    if not p.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)
    return age < timedelta(hours=CACHE_TTL_HOURS)


def _save_cache(df: pd.DataFrame, key: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(_cache_path(key))


def _load_cache(key: str) -> pd.DataFrame:
    return pd.read_parquet(_cache_path(key))


# ── Sample / demo data ─────────────────────────────────────────────────────────

_METHODS = [
    "Human-induced regeneration",
    "Reforestation by environmental plantings",
    "Savanna fire management",
    "Soil carbon",
    "Methane avoidance - piggeries",
    "Landfill gas",
    "Avoided deforestation",
    "Vegetation – reforestation",
    "Feral animal management",
    "Sequestration by native revegetation",
    "Industrial energy efficiency",
    "Coal mine waste gas",
    "Captured and destroyed methane",
    "Beef cattle herd management",
    "Fertiliser use efficiency",
]

_METHOD_TYPES = {
    "Human-induced regeneration": "Sequestration",
    "Reforestation by environmental plantings": "Sequestration",
    "Savanna fire management": "Emissions avoidance",
    "Soil carbon": "Sequestration",
    "Methane avoidance - piggeries": "Emissions avoidance",
    "Landfill gas": "Emissions avoidance",
    "Avoided deforestation": "Sequestration",
    "Vegetation – reforestation": "Sequestration",
    "Feral animal management": "Emissions avoidance",
    "Sequestration by native revegetation": "Sequestration",
    "Industrial energy efficiency": "Emissions avoidance",
    "Coal mine waste gas": "Emissions avoidance",
    "Captured and destroyed methane": "Emissions avoidance",
    "Beef cattle herd management": "Emissions avoidance",
    "Fertiliser use efficiency": "Emissions avoidance",
}

_PROPONENTS = [
    "GreenCarbon Pty Ltd",
    "AusNative Land Management",
    "Carbon Neutral Australia",
    "Terrosa Carbon Pty Ltd",
    "Indigenous Carbon Industry Network",
    "Murray Darling Carbon Co.",
    "OzSequester Pty Ltd",
    "Pastoral Carbon Solutions",
    "AgriCarbon Pty Ltd",
    "EcoSink Investments",
    "RegenAg Carbon",
    "Northern Savanna Partners",
    "CleanGround Carbon Pty Ltd",
    "WasteGas Capture Co.",
    "Blue Gum Carbon Trust",
]

_STATES_PROBS = {
    "QLD": 0.28, "NSW": 0.20, "WA": 0.18, "NT": 0.14,
    "SA": 0.10, "VIC": 0.07, "TAS": 0.02, "ACT": 0.01,
}


def _make_sample_projects() -> pd.DataFrame:
    import random
    random.seed(42)
    states = list(_STATES_PROBS.keys())
    state_w = list(_STATES_PROBS.values())
    rows = []
    for i in range(1, 201):
        method = random.choice(_METHODS)
        state = random.choices(states, weights=state_w)[0]
        proponent = random.choice(_PROPONENTS)
        reg_year = random.randint(2012, 2024)
        reg_date = datetime(reg_year, random.randint(1, 12), random.randint(1, 28))
        crediting_start = reg_date
        crediting_end = datetime(reg_year + 25, reg_date.month, reg_date.day)
        status = "Active" if random.random() > 0.08 else "Revoked"
        accus_issued = random.randint(0, 180_000) if status == "Active" else 0
        area = random.randint(500, 50_000) if "Sequestration" in _METHOD_TYPES[method] else None
        rows.append({
            "Project Proponent": proponent,
            "Project Name": f"{proponent.split()[0]} {state} Project {i:04d}",
            "Project ID": f"ERF{180000 + i}",
            "Method": method,
            "Method Type": _METHOD_TYPES[method],
            "Date Project Registered": reg_date.strftime("%d/%m/%Y"),
            "Crediting Period Start Date": crediting_start.strftime("%d/%m/%Y"),
            "Crediting Period End Date": crediting_end.strftime("%d/%m/%Y"),
            "Project location (State)": state,
            "Project Status": status,
            "ACCUs Issued": accus_issued,
            "Area Ha": area,
        })
    return pd.DataFrame(rows)


_SECTORS = [
    "Oil and gas extraction",
    "Coal mining",
    "Aluminium smelting",
    "Iron and steel manufacturing",
    "Cement and lime manufacturing",
    "Chemicals manufacturing",
    "Copper, silver, lead and zinc smelting",
    "LNG processing",
    "Coal seam gas extraction",
    "Petroleum refining",
]

_OPERATORS = [
    ("Apex LNG Pty Ltd", "WA", "LNG processing"),
    ("Northern Gas Processing Co.", "NT", "LNG processing"),
    ("Pacific LNG Operations", "QLD", "LNG processing"),
    ("Southern LNG Terminal", "VIC", "LNG processing"),
    ("Midwest Coal Operations", "QLD", "Coal mining"),
    ("Hunter Valley Coal", "NSW", "Coal mining"),
    ("Bowen Basin Resources", "QLD", "Coal mining"),
    ("Pilbara Coal Co.", "WA", "Coal mining"),
    ("Central Queensland Mining", "QLD", "Coal mining"),
    ("Hunter Coalfields", "NSW", "Coal mining"),
    ("Macquarie Metals", "NSW", "Iron and steel manufacturing"),
    ("Southern Aluminium Works", "VIC", "Aluminium smelting"),
    ("Gladstone Alumina", "QLD", "Aluminium smelting"),
    ("Pacific Aluminium", "QLD", "Aluminium smelting"),
    ("Australian Cement Ltd", "VIC", "Cement and lime manufacturing"),
    ("Boral Cement Operations", "NSW", "Cement and lime manufacturing"),
    ("Chemical Industries Corp.", "SA", "Chemicals manufacturing"),
    ("Orica Mining Services", "NSW", "Chemicals manufacturing"),
    ("Copper Refineries Ltd", "QLD", "Copper, silver, lead and zinc smelting"),
    ("Bass Strait Oil Pty Ltd", "VIC", "Oil and gas extraction"),
    ("Northwest Shelf Resources", "WA", "Oil and gas extraction"),
    ("Timor Sea Gas Co.", "NT", "Oil and gas extraction"),
    ("Carnarvon Basin Petroleum", "WA", "Oil and gas extraction"),
    ("Cooper Basin Energy", "SA", "Coal seam gas extraction"),
    ("Surat Basin Gas Pty Ltd", "QLD", "Coal seam gas extraction"),
    ("Brisbane Refinery Co.", "QLD", "Petroleum refining"),
    ("Kwinana Refining Ltd", "WA", "Petroleum refining"),
    ("Laminaria Oil Operations", "NT", "Oil and gas extraction"),
    ("Gippsland Basin Energy", "VIC", "Oil and gas extraction"),
    ("Port Hedland Minerals", "WA", "Copper, silver, lead and zinc smelting"),
]


def _make_sample_safeguard() -> pd.DataFrame:
    import random
    random.seed(99)
    rows = []
    for facility, state, sector in _OPERATORS:
        covered = random.randint(500_000, 8_000_000)
        baseline = int(covered * random.uniform(0.90, 1.15))
        net_position = baseline - covered
        # Deficit means they need to surrender credits
        if net_position < 0:
            deficit = abs(net_position)
            accus_surr = int(deficit * random.uniform(0.5, 1.0))
            smcs_surr = max(0, deficit - accus_surr)
        else:
            accus_surr = 0
            smcs_surr = 0
        rows.append({
            "Facility Name": facility,
            "State/Territory": state,
            "Industry Sector": sector,
            "Covered Emissions (tCO2e)": covered,
            "Baseline Emissions (tCO2e)": baseline,
            "Net Position (tCO2e)": net_position,
            "ACCUs Surrendered": accus_surr,
            "SMCs Surrendered": smcs_surr,
            "Total Credits Surrendered": accus_surr + smcs_surr,
            "Compliance Year": "2024-25",
            "Compliance Status": "Compliant" if net_position >= 0 or (accus_surr + smcs_surr) >= abs(net_position) else "Non-compliant",
        })
    return pd.DataFrame(rows)


def _make_sample_contracts() -> pd.DataFrame:
    import random
    random.seed(77)
    rows = []
    for i, proponent in enumerate(_PROPONENTS):
        n_contracts = random.randint(1, 4)
        for j in range(n_contracts):
            rows.append({
                "Project Proponent": proponent,
                "Project ID": f"ERF{180001 + i * 10 + j}",
                "Contract Type": random.choice(["Delivery", "Fixed Delivery", "Optional Delivery"]),
                "Contracted Volume (ACCUs)": random.randint(5_000, 500_000),
                "Contract Status": random.choice(["Active", "Active", "Active", "Completed"]),
                "Contract Start Date": f"0{random.randint(1,9)}/20{random.randint(14,22)}",
            })
    return pd.DataFrame(rows)


# ── Public loaders ─────────────────────────────────────────────────────────────

def load_project_register(
    uploaded_file=None,
    force_download: bool = False,
) -> tuple[pd.DataFrame, str]:
    """
    Returns (DataFrame, source) where source is one of:
    'upload', 'cache', 'live', 'sample'.
    """
    if uploaded_file is not None:
        try:
            name = getattr(uploaded_file, "name", "")
            if name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            _save_cache(_normalise_projects(df), "project_register")
            return _normalise_projects(df), "upload"
        except Exception:
            pass

    if not force_download and _cache_valid("project_register"):
        return _load_cache("project_register"), "cache"

    if force_download:
        df = _try_download_csv(CER_PROJECT_REGISTER_URL)
        if df is not None:
            df = _normalise_projects(df)
            _save_cache(df, "project_register")
            return df, "live"

    return _make_sample_projects(), "sample"


def load_safeguard_data(
    uploaded_file=None,
    force_download: bool = False,
    year: str = "2024-25",
) -> tuple[pd.DataFrame, str]:
    """Returns (DataFrame, source)."""
    cache_key = f"safeguard_{year.replace('-', '_')}"

    if uploaded_file is not None:
        try:
            name = getattr(uploaded_file, "name", "")
            df = pd.read_csv(uploaded_file) if name.endswith(".csv") else pd.read_excel(uploaded_file)
            _save_cache(_normalise_safeguard(df), cache_key)
            return _normalise_safeguard(df), "upload"
        except Exception:
            pass

    if not force_download and _cache_valid(cache_key):
        return _load_cache(cache_key), "cache"

    if force_download:
        for url in CER_SAFEGUARD_URLS:
            df = _try_download_csv(url)
            if df is not None:
                df = _normalise_safeguard(df)
                _save_cache(df, cache_key)
                return df, "live"

    return _make_sample_safeguard(), "sample"


def load_contract_register(
    uploaded_file=None,
    force_download: bool = False,
) -> tuple[pd.DataFrame, str]:
    """Returns (DataFrame, source)."""
    if uploaded_file is not None:
        try:
            name = getattr(uploaded_file, "name", "")
            df = pd.read_csv(uploaded_file) if name.endswith(".csv") else pd.read_excel(uploaded_file)
            _save_cache(df, "contract_register")
            return df, "upload"
        except Exception:
            pass

    if not force_download and _cache_valid("contract_register"):
        return _load_cache("contract_register"), "cache"

    if force_download:
        df = _try_download_csv(CER_CONTRACT_URL)
        if df is not None:
            _save_cache(df, "contract_register")
            return df, "live"

    return _make_sample_contracts(), "sample"


# ── Column normalisation ───────────────────────────────────────────────────────

def _normalise_projects(df: pd.DataFrame) -> pd.DataFrame:
    """Attempt to standardise column names from various CER project register versions."""
    rename = {
        # Common CER column names → our canonical names
        "Scheme Participant": "Project Proponent",
        "scheme_participant": "Project Proponent",
        "Project Proponent": "Project Proponent",
        "proponent": "Project Proponent",
        "project_name": "Project Name",
        "project_id": "Project ID",
        "method": "Method",
        "method_type": "Method Type",
        "project_status": "Project Status",
        "State": "Project location (State)",
        "state": "Project location (State)",
        "accus_issued": "ACCUs Issued",
        "ACCUs issued": "ACCUs Issued",
        "area_ha": "Area Ha",
        "date_registered": "Date Project Registered",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    if "ACCUs Issued" not in df.columns:
        df["ACCUs Issued"] = 0
    df["ACCUs Issued"] = pd.to_numeric(df["ACCUs Issued"], errors="coerce").fillna(0).astype(int)
    return df


def _normalise_safeguard(df: pd.DataFrame) -> pd.DataFrame:
    rename = {
        "Facility name": "Facility Name",
        "facility_name": "Facility Name",
        "Operator": "Operator",
        "operator": "Operator",
        "State": "State/Territory",
        "state": "State/Territory",
        "Sector": "Industry Sector",
        "sector": "Industry Sector",
        "Covered emissions": "Covered Emissions (tCO2e)",
        "covered_emissions": "Covered Emissions (tCO2e)",
        "Baseline emissions": "Baseline Emissions (tCO2e)",
        "Net position": "Net Position (tCO2e)",
        "ACCUs surrendered": "ACCUs Surrendered",
        "accus_surrendered": "ACCUs Surrendered",
        "SMCs surrendered": "SMCs Surrendered",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    for col in ("ACCUs Surrendered", "SMCs Surrendered", "Total Credits Surrendered"):
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    if "Total Credits Surrendered" not in df.columns:
        df["Total Credits Surrendered"] = df["ACCUs Surrendered"] + df["SMCs Surrendered"]
    for col in ("Covered Emissions (tCO2e)", "Baseline Emissions (tCO2e)", "Net Position (tCO2e)"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df


# ── Analytics ──────────────────────────────────────────────────────────────────

def summarise_developers(projects: pd.DataFrame) -> pd.DataFrame:
    """Aggregate ACCU project stats by proponent (project developer)."""
    grp = projects.groupby("Project Proponent", dropna=False).agg(
        Projects=("Project ID", "count"),
        Active_Projects=("Project Status", lambda s: (s == "Active").sum()),
        ACCUs_Issued=("ACCUs Issued", "sum"),
        States=("Project location (State)", lambda s: ", ".join(sorted(s.dropna().unique()))),
        Methods=("Method", lambda s: s.nunique()),
    ).reset_index()
    grp.columns = [
        "Developer", "Total Projects", "Active Projects",
        "ACCUs Issued", "States Active In", "Distinct Methods",
    ]
    return grp.sort_values("ACCUs Issued", ascending=False).reset_index(drop=True)


def summarise_retirements(safeguard: pd.DataFrame) -> pd.DataFrame:
    """Aggregate credit surrender (retirement) data by sector."""
    grp = safeguard.groupby("Industry Sector", dropna=False).agg(
        Facilities=("Facility Name", "count"),
        Total_Covered=("Covered Emissions (tCO2e)", "sum"),
        Total_Baseline=("Baseline Emissions (tCO2e)", "sum"),
        ACCUs_Surrendered=("ACCUs Surrendered", "sum"),
        SMCs_Surrendered=("SMCs Surrendered", "sum"),
        Total_Surrendered=("Total Credits Surrendered", "sum"),
    ).reset_index()
    grp.columns = [
        "Industry Sector", "Facilities", "Covered Emissions (tCO2e)",
        "Baseline Emissions (tCO2e)", "ACCUs Surrendered", "SMCs Surrendered",
        "Total Credits Surrendered",
    ]
    return grp.sort_values("Total Credits Surrendered", ascending=False).reset_index(drop=True)


# ── Download instructions ──────────────────────────────────────────────────────

DOWNLOAD_INSTRUCTIONS = {
    "Project Register": {
        "url": "https://cer.gov.au/markets/reports-and-data/accu-project-and-contract-register",
        "steps": [
            "Go to the CER ACCU Project and Contract Register page (link above).",
            "Scroll to 'ACCU Scheme project register' and click the CSV download link.",
            "Upload the downloaded file using the uploader below.",
        ],
    },
    "Safeguard Data": {
        "url": "https://cer.gov.au/markets/reports-and-data/safeguard-data",
        "steps": [
            "Go to the CER Safeguard Data page (link above).",
            "Click the most recent year's 'baselines and emissions data' link.",
            "Download the CSV or Excel file and upload it below.",
        ],
    },
    "Contract Register": {
        "url": "https://cer.gov.au/markets/reports-and-data/accu-project-and-contract-register",
        "steps": [
            "Go to the CER ACCU Project and Contract Register page (link above).",
            "Scroll to 'Carbon abatement contract register' and click the CSV download link.",
            "Upload the downloaded file using the uploader below.",
        ],
    },
}
