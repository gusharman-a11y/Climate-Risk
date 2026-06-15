"""Net Zero Tracker (NZT) data loader and AUS Company Profile overlay.

Source: https://zerotracker.net/ — "current_snapshot" XLSX download.

File structure:
  Row 1  — group headers (skipped via header=1 in pandas)
  Row 2  — column names (used as header)
  Row 3+ — data

Key columns used:
  Name                              — entity name for matching
  Country                           — "AUS" for Australia
  Entity_type                       — "Company" to exclude governments/cities
  End_target                        — end-target type (Net-zero, Carbon neutral, …)
  End_target_year                   — year of end target
  Status_of_end_target              — In corporate strategy / Declaration…
  End_target_text                   — full target description
  Interim_target                    — interim target type
  Interim_target_year               — interim target year
  Interim_target_percentage_reduction — % reduction commitment
  Published_plan                    — whether a decarbonisation plan is published
  Race_to_zero_member               — UN RTZ membership flag
  Industry                          — sector label
  GHG_emissions                     — emissions reported (tCO2e)

Public API:
  load_nzt(file)                    — load & filter to AUS companies
  nzt_target_class(row)             — map NZT fields → 6-tier Target Classification
  overlay_nzt(screen_df, nzt_df)    — apply NZT as research overlay on screen
  NZT_COLS                          — display column names added by overlay
"""
from __future__ import annotations

import re

import pandas as pd

# ── Column name constants ─────────────────────────────────────────────────────

NZT_NAME            = "Name"
NZT_COUNTRY         = "Country"
NZT_ENTITY_TYPE     = "Entity_type"
NZT_END_TARGET      = "End_target"
NZT_END_YEAR        = "End_target_year"
NZT_STATUS          = "Status_of_end_target"
NZT_END_TEXT        = "End_target_text"
NZT_INTERIM         = "Interim_target"
NZT_INTERIM_YEAR    = "Interim_target_year"
NZT_INTERIM_PCT     = "Interim_target_percentage_reduction"
NZT_PLAN            = "Published_plan"
NZT_RTZ             = "Race_to_zero_member"
NZT_INDUSTRY        = "Industry"
NZT_EMISSIONS       = "GHG_emissions"

# Columns added to screen DataFrame by overlay_nzt()
NZT_COLS = [
    "NZT End Target",
    "NZT End Year",
    "NZT Status",
    "NZT Interim %",
    "NZT Published Plan",
    "NZT Race to Zero",
    "NZT Target Classification",
]


# ── Name normalisation (mirrors country_profile.py) ──────────────────────────

_STRIP_TOKENS = re.compile(
    r"\b(?:corporation|corp|incorporated|inc|limited|ltd|berhad|bhd|"
    r"group|holdings|holding|company|co\b|plc|pte|sdn|tbk|the|and|"
    r"australia|australian|pty)\b",
    re.I,
)


def _name_key(name: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", " ", str(name).lower())
    n = _STRIP_TOKENS.sub("", n)
    return re.sub(r"\s+", " ", n).strip()


def _name_match(key_a: str, key_b: str) -> bool:
    if not key_a or not key_b:
        return False
    if key_a == key_b:
        return True
    ta = key_a.split()
    tb = key_b.split()
    if not ta or not tb:
        return False
    if ta[0] == tb[0]:
        overlap = len(set(ta) & set(tb))
        if overlap >= min(2, len(ta)):
            return True
    if len(key_a) >= 6 and key_b.startswith(key_a[:6]):
        return True
    if len(key_b) >= 6 and key_a.startswith(key_b[:6]):
        return True
    return False


# ── Loader ────────────────────────────────────────────────────────────────────

def load_nzt(file) -> pd.DataFrame:
    """Load the NZT snapshot XLSX and return Australian companies only.

    Parameters
    ----------
    file : file-like with .name attribute (from st.file_uploader)

    Returns
    -------
    pd.DataFrame filtered to Entity_type="Company", Country="AUS".
    Empty DataFrame on any error.
    """
    try:
        df = pd.read_excel(file, header=1)
    except Exception:
        return pd.DataFrame()

    # Strip whitespace from column names
    df.columns = [str(c).strip() for c in df.columns]

    # Filter to Australian companies
    if NZT_COUNTRY in df.columns and NZT_ENTITY_TYPE in df.columns:
        mask = (
            df[NZT_COUNTRY].astype(str).str.strip().str.upper().eq("AUS")
            & df[NZT_ENTITY_TYPE].astype(str).str.strip().str.lower().eq("company")
        )
        df = df[mask].copy()
    elif NZT_COUNTRY in df.columns:
        mask = df[NZT_COUNTRY].astype(str).str.strip().str.upper().eq("AUS")
        df = df[mask].copy()

    if df.empty:
        return df

    # Coerce numeric columns
    for col in (NZT_END_YEAR, NZT_INTERIM_YEAR, NZT_INTERIM_PCT, NZT_EMISSIONS):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Normalise boolean-ish columns
    for col in (NZT_PLAN, NZT_RTZ):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower().map(
                lambda v: "Yes" if v in ("yes", "true", "1", "y") else
                          ("No" if v in ("no", "false", "0", "n") else v.title())
            )

    return df.reset_index(drop=True)


# ── Target Classification mapping ─────────────────────────────────────────────

# Status tier (higher = more credible)
_STATUS_TIER = {
    "in corporate strategy": 3,
    "declaration/pledge":    2,
    "proposed/in discussion": 1,
}

_NET_ZERO_TARGETS = {"net-zero emissions", "net zero emissions", "net zero", "net-zero"}
_CARBON_NEUTRAL   = {"carbon neutral", "climate neutral", "climate positive", "climate-positive"}


def nzt_target_class(row: pd.Series) -> str:
    """Map NZT fields to the BD 6-tier Target Classification.

    Tiers (ascending ambition):
      No public target → Aspirational → Net-zero only →
      Quantitative non-validated → SBTi committed → Targets set
    """
    status_raw = str(row.get(NZT_STATUS, "")).strip().lower()
    end_target  = str(row.get(NZT_END_TARGET, "")).strip().lower()
    interim_pct = row.get(NZT_INTERIM_PCT, None)

    status_tier = _STATUS_TIER.get(status_raw, 0)

    if status_tier == 0:
        return "No public target"

    has_interim_pct = (
        pd.notna(interim_pct)
        and str(interim_pct).strip() not in ("", "nan", "0")
        and float(interim_pct) > 0
    )

    if status_tier >= 3 and has_interim_pct:
        # Strong status + quantified interim reduction
        return "Quantitative non-validated"

    if status_tier >= 3 and end_target in _NET_ZERO_TARGETS:
        if has_interim_pct:
            return "Quantitative non-validated"
        return "Net-zero only"

    if status_tier >= 2 or (status_tier >= 3 and end_target in _CARBON_NEUTRAL):
        return "Aspirational"

    return "Aspirational"


# ── Overlay ───────────────────────────────────────────────────────────────────

def overlay_nzt(screen_df: pd.DataFrame, nzt_df: pd.DataFrame) -> pd.DataFrame:
    """Apply NZT data as a research overlay on the AUS Company Profile screen.

    For non-SBTi companies, upgrades Target Classification where NZT provides
    stronger evidence.  Adds NZT_COLS columns to the DataFrame.

    Parameters
    ----------
    screen_df : output of add_asrs_columns(); must have 'Company Name' and 'SBTi'
    nzt_df    : output of load_nzt()

    Returns
    -------
    Enriched copy of screen_df.
    """
    out = screen_df.copy()

    # Initialise NZT columns as empty
    for col in NZT_COLS:
        out[col] = pd.NA

    if nzt_df.empty or NZT_NAME not in nzt_df.columns:
        return out

    # Build NZT lookup: normalised name key → first row
    nzt_lookup: dict[str, pd.Series] = {}
    for _, row in nzt_df.iterrows():
        key = _name_key(str(row.get(NZT_NAME, "")))
        if key and key not in nzt_lookup:
            nzt_lookup[key] = row

    name_col = next(
        (c for c in ("Company Name", "Organisation", "Name") if c in out.columns),
        out.columns[0],
    )

    for idx, row in out.iterrows():
        comp_key = _name_key(str(row.get(name_col, "")))
        match = None
        if comp_key in nzt_lookup:
            match = nzt_lookup[comp_key]
        else:
            for nk, nr in nzt_lookup.items():
                if _name_match(comp_key, nk):
                    match = nr
                    break

        if match is None:
            continue

        # Store raw NZT columns
        out.at[idx, "NZT End Target"] = _safe_str(match.get(NZT_END_TARGET))
        out.at[idx, "NZT End Year"]   = _safe_num(match.get(NZT_END_YEAR))
        out.at[idx, "NZT Status"]     = _safe_str(match.get(NZT_STATUS))
        out.at[idx, "NZT Interim %"]  = _safe_num(match.get(NZT_INTERIM_PCT))
        out.at[idx, "NZT Published Plan"] = _safe_str(match.get(NZT_PLAN))
        out.at[idx, "NZT Race to Zero"]   = _safe_str(match.get(NZT_RTZ))

        nzt_tc = nzt_target_class(match)
        out.at[idx, "NZT Target Classification"] = nzt_tc

        # Upgrade Target Classification for non-SBTi companies only
        sbti_val = str(row.get("SBTi", "No")).strip()
        if sbti_val != "Yes":
            _upgrade_target_class(out, idx, nzt_tc)

    return out


def _safe_str(val) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    return s if s and s.lower() != "nan" else None


def _safe_num(val):
    if val is None:
        return None
    try:
        f = float(val)
        return None if pd.isna(f) else f
    except (ValueError, TypeError):
        return None


_TC_ORDER = [
    "No public target",
    "Aspirational",
    "Net-zero only",
    "Quantitative non-validated",
    "SBTi committed",
    "Targets set",
]


def _upgrade_target_class(df: pd.DataFrame, idx, nzt_tc: str) -> None:
    """Replace Target Classification at idx only if NZT provides a higher tier."""
    target_col = next(
        (c for c in ("Target Classification", "Target Classification (BD)") if c in df.columns),
        None,
    )
    if target_col is None:
        return

    current = str(df.at[idx, target_col]).strip()
    current_rank = _TC_ORDER.index(current) if current in _TC_ORDER else 0
    nzt_rank     = _TC_ORDER.index(nzt_tc)  if nzt_tc  in _TC_ORDER else 0

    if nzt_rank > current_rank:
        df.at[idx, target_col] = nzt_tc
        # Append to Profile Source
        src_col = "Profile Source"
        if src_col in df.columns:
            existing = str(df.at[idx, src_col])
            if "Net Zero Tracker" not in existing:
                df.at[idx, src_col] = (existing.rstrip() + " + Net Zero Tracker").lstrip(" +")
