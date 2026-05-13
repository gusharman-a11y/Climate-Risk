"""
ACCU Methods overview data store.

The dashboard organises methods under five fixed categories:
    1. Vegetation Management
    2. Mining, Oil and Gas
    3. Agriculture
    4. Energy Efficiency
    5. Landfill and Waste

Each method carries a status of ``active``, ``next_to_close`` or
``under_development``. The dashboard lets the user edit, add and remove rows
per category; data is persisted to ACCU_DATA_FILE.

Sources:
  - DCCEEW, Australian Carbon Credit Unit Scheme – Methods (Current)
  - DCCEEW, Method Development Tracker
  - DCCEEW, Guidance for ACCU Scheme participants impacted by the expiry
    (or sunsetting) of an ACCU Scheme method
"""

import copy
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

ACCU_DATA_FILE = Path("accu_methods_data.json")

# ── Fixed taxonomy ────────────────────────────────────────────────────────────
CATEGORIES = [
    "Vegetation Management",
    "Mining, Oil and Gas",
    "Agriculture",
    "Energy Efficiency",
    "Landfill and Waste",
]

CATEGORY_COLORS = {
    "Vegetation Management": "#2F855A",
    "Mining, Oil and Gas": "#92400E",
    "Agriculture": "#9C7A1F",
    "Energy Efficiency": "#1E40AF",
    "Landfill and Waste": "#5B21B6",
}

STATUSES = ["active", "next_to_close", "under_development"]

STATUS_LABELS = {
    "active": "Active",
    "next_to_close": "Next to Close",
    "under_development": "Under Development",
}

STATUS_COLORS = {
    "active": "#15803D",
    "next_to_close": "#D97706",
    "under_development": "#1D4ED8",
}

STATUS_BG = {
    "active": "#DCFCE7",
    "next_to_close": "#FEF3C7",
    "under_development": "#DBEAFE",
}

# Row schema
COLUMNS = ["methodology", "category", "status", "status_timing", "updates"]
COLUMN_LABELS = {
    "methodology": "Methodology",
    "category": "Category",
    "status": "Status",
    "status_timing": "Status / Timing",
    "updates": "Updates",
}

# ── Seed data ─────────────────────────────────────────────────────────────────
# Seed taken from the Pollination overview slide (DCCEEW, April 2026) for the
# Under Development bucket, plus a representative sample of currently active
# and sunsetting methods. All rows are editable in the dashboard.
SEED_METHODS = [
    # ── Under Development (from the Pollination slide) ────────────────────
    {
        "methodology": "Integrated Farm and Land Management (IFLM)",
        "category": "Vegetation Management",
        "status": "under_development",
        "status_timing": "Under development",
        "updates": "Public consultation recently closed 9 March 2026",
    },
    {
        "methodology": "Extending Savanna Fire Management to the Northern Arid Zone method",
        "category": "Vegetation Management",
        "status": "under_development",
        "status_timing": "Under development",
        "updates": "Proponent preparing method",
    },
    {
        "methodology": "Improved Native Forest Management in Multi-use Public Native Forest method",
        "category": "Vegetation Management",
        "status": "under_development",
        "status_timing": "Under development",
        "updates": "Public consultation on the draft proposed method closed on 30 January 2026",
    },
    {
        "methodology": "Improved Avoided Clearing of Native Regrowth method",
        "category": "Vegetation Management",
        "status": "under_development",
        "status_timing": "Under development",
        "updates": "Proponent preparing method",
    },
    {
        "methodology": "Livestock Method",
        "category": "Agriculture",
        "status": "under_development",
        "status_timing": "Under development",
        "updates": "Proponent preparing method",
    },
    {
        "methodology": "Reducing disturbance of coastal and floodplain wetlands by managing ungulates method",
        "category": "Agriculture",
        "status": "under_development",
        "status_timing": "Under development",
        "updates": "Proponent preparing method",
    },
    {
        "methodology": "Alternative waste treatment method remake",
        "category": "Landfill and Waste",
        "status": "under_development",
        "status_timing": "Under development",
        "updates": "Proponent preparing method",
    },

    # ── Active – Vegetation Management ────────────────────────────────────
    {
        "methodology": "Human-Induced Regeneration of a Permanent Even-Aged Native Forest (HIR)",
        "category": "Vegetation Management",
        "status": "active",
        "status_timing": "Active",
        "updates": "Open to new registrations",
    },
    {
        "methodology": "Plantation Forestry",
        "category": "Vegetation Management",
        "status": "active",
        "status_timing": "Active",
        "updates": "Open to new registrations",
    },
    {
        "methodology": "Environmental Plantings",
        "category": "Vegetation Management",
        "status": "active",
        "status_timing": "Active",
        "updates": "Open to new registrations",
    },
    {
        "methodology": "Savanna Fire Management – Emissions Avoidance and Sequestration",
        "category": "Vegetation Management",
        "status": "active",
        "status_timing": "Active",
        "updates": "Open to new registrations",
    },
    {
        "methodology": "Reforestation by Environmental or Mallee Plantings",
        "category": "Vegetation Management",
        "status": "active",
        "status_timing": "Active",
        "updates": "Open to new registrations",
    },

    # ── Active – Agriculture ──────────────────────────────────────────────
    {
        "methodology": "Estimating Soil Organic Carbon Sequestration using Measurement and Models",
        "category": "Agriculture",
        "status": "active",
        "status_timing": "Active",
        "updates": "Open to new registrations",
    },
    {
        "methodology": "Beef Cattle Herd Management",
        "category": "Agriculture",
        "status": "active",
        "status_timing": "Active",
        "updates": "Open to new registrations",
    },
    {
        "methodology": "Reducing Greenhouse Gas Emissions from Milk Production by Feeding Dietary Additives",
        "category": "Agriculture",
        "status": "active",
        "status_timing": "Active",
        "updates": "Open to new registrations",
    },

    # ── Active – Mining, Oil and Gas ──────────────────────────────────────
    {
        "methodology": "Coal Mine Waste Gas",
        "category": "Mining, Oil and Gas",
        "status": "active",
        "status_timing": "Active",
        "updates": "Open to new registrations",
    },
    {
        "methodology": "Oil and Gas Fugitives",
        "category": "Mining, Oil and Gas",
        "status": "active",
        "status_timing": "Active",
        "updates": "Open to new registrations",
    },

    # ── Active – Landfill and Waste ───────────────────────────────────────
    {
        "methodology": "Landfill Gas",
        "category": "Landfill and Waste",
        "status": "active",
        "status_timing": "Active",
        "updates": "Open to new registrations",
    },
    {
        "methodology": "Source Separated Organic Waste",
        "category": "Landfill and Waste",
        "status": "active",
        "status_timing": "Active",
        "updates": "Open to new registrations",
    },

    # ── Next to Close – Energy Efficiency (the sunsetting cohort) ────────
    {
        "methodology": "Industrial Energy Efficiency",
        "category": "Energy Efficiency",
        "status": "next_to_close",
        "status_timing": "Sunsetting – closing to new registrations",
        "updates": "Replacement under development; CER transition guidance issued",
    },
    {
        "methodology": "Commercial Buildings",
        "category": "Energy Efficiency",
        "status": "next_to_close",
        "status_timing": "Sunsetting – closing to new registrations",
        "updates": "Replacement under development; CER transition guidance issued",
    },
    {
        "methodology": "Aggregated Small Energy Users",
        "category": "Energy Efficiency",
        "status": "next_to_close",
        "status_timing": "Sunsetting – closing to new registrations",
        "updates": "Replacement under development",
    },
    {
        "methodology": "High Efficiency Commercial Appliances",
        "category": "Energy Efficiency",
        "status": "active",
        "status_timing": "Active",
        "updates": "Open to new registrations",
    },
]

DEFAULT_KEY_INSIGHTS = [
    "Seven methods are currently under review by the ERAC, with draft "
    "determinations still pending. Since 31 March 2026, five methods have "
    "closed, reducing energy efficiency origination pathways from four to "
    "two. As expired methods cannot accept new project registrations, this "
    "limits entry points and constrains near-term supply until replacement "
    "methods are in place.",
    "At the same time, development of new methods has been delayed, with "
    "the IFLM timeline continuing to slip.",
    "While this reflects ongoing evolution of the scheme, the misalignment "
    "between method expiries and new method delivery has created a "
    "temporary supply gap. The CER expects Safeguard-driven demand to "
    "increase and potentially exceed supply by the end of the decade, "
    "leading to a drawdown of existing inventories. In this context, the "
    "current transition period is likely to constrain available supply and "
    "support elevated spot and forward ACCU prices.",
]

DEFAULT_HEADLINE = (
    "ACCU Methods overview – active pathways, sunsetting methods "
    "and methods under development across the five core categories"
)

DEFAULT_EYEBROW = "ACCU METHODS – ACTIVE, SUNSET AND UNDER DEVELOPMENT"

DEFAULT_FOOTNOTE = (
    "*When a method is closed (sunset / expired), it means it has reached "
    "its legislated expiry date and can no longer be used to register new "
    "ACCU projects, though existing registered projects may continue to "
    "generate credits for their approved crediting period."
)

DEFAULT_SOURCES = [
    "DCCEEW, Australian Carbon Credit Unit Scheme – Methods (Current)",
    "DCCEEW, Method Development Tracker",
    "DCCEEW, Guidance for ACCU Scheme participants impacted by the expiry "
    "(or sunsetting) of an ACCU Scheme method",
]


def default_data() -> dict:
    return {
        "headline": DEFAULT_HEADLINE,
        "eyebrow": DEFAULT_EYEBROW,
        "key_insights": list(DEFAULT_KEY_INSIGHTS),
        "footnote": DEFAULT_FOOTNOTE,
        "sources": list(DEFAULT_SOURCES),
        "methods": copy.deepcopy(SEED_METHODS),
    }


def load_data() -> dict:
    """Load persisted ACCU dashboard data, falling back to seed defaults."""
    if ACCU_DATA_FILE.exists():
        try:
            with ACCU_DATA_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return default_data()
        defaults = default_data()
        for k, v in defaults.items():
            data.setdefault(k, v)
        return data
    return default_data()


def save_data(data: dict) -> None:
    with ACCU_DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def reset_data() -> dict:
    data = default_data()
    save_data(data)
    return data


def methods_by_category(data: dict) -> dict:
    """Group method rows by category, preserving CATEGORIES order."""
    grouped: dict[str, list[dict]] = {c: [] for c in CATEGORIES}
    for row in data.get("methods", []):
        cat = row.get("category")
        if cat in grouped:
            grouped[cat].append(row)
    return grouped


def status_counts(data: dict) -> dict:
    counts = {s: 0 for s in STATUSES}
    for row in data.get("methods", []):
        s = row.get("status")
        if s in counts:
            counts[s] += 1
    return counts


# ── Audit ─────────────────────────────────────────────────────────────────────
NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12,
}


def _to_int(token: str) -> int | None:
    token = token.lower().strip()
    if token.isdigit():
        return int(token)
    return NUMBER_WORDS.get(token)


def _category_active_counts(data: dict) -> dict[str, int]:
    counts: dict[str, int] = {c: 0 for c in CATEGORIES}
    for row in data.get("methods", []):
        if row.get("status") == "active" and row.get("category") in counts:
            counts[row["category"]] += 1
    return counts


def audit_data(data: dict, today: date | None = None) -> list[dict]:
    """Run internal-consistency checks on the ACCU dashboard data.

    Returns a list of findings: {severity, code, message}. Severity is
    "error", "warning" or "info". Empty list means everything checks out.
    """
    today = today or date.today()
    findings: list[dict] = []
    rows = data.get("methods", []) or []
    counts = status_counts(data)
    insights_text = " ".join(data.get("key_insights", []))

    # 1. Required fields populated
    for i, row in enumerate(rows, 1):
        for col in COLUMNS:
            if not str(row.get(col, "")).strip():
                findings.append({
                    "severity": "error",
                    "code": "missing_field",
                    "message": (
                        f"Row {i} ({row.get('methodology', '?')}): "
                        f"missing '{COLUMN_LABELS.get(col, col)}'."
                    ),
                })

    # 2. Category / status enums
    for i, row in enumerate(rows, 1):
        if row.get("category") and row["category"] not in CATEGORIES:
            findings.append({
                "severity": "error",
                "code": "bad_category",
                "message": (
                    f"Row {i} ({row.get('methodology', '?')}): "
                    f"unknown category '{row['category']}'."
                ),
            })
        if row.get("status") and row["status"] not in STATUSES:
            findings.append({
                "severity": "error",
                "code": "bad_status",
                "message": (
                    f"Row {i} ({row.get('methodology', '?')}): "
                    f"unknown status '{row['status']}'."
                ),
            })

    # 3. Status ↔ status_timing coherence
    timing_keywords = {
        "active": ("active",),
        "next_to_close": ("sunset", "closing", "expir", "close"),
        "under_development": ("development", "draft", "consultation"),
    }
    for i, row in enumerate(rows, 1):
        s = row.get("status")
        timing = str(row.get("status_timing", "")).lower()
        kws = timing_keywords.get(s, ())
        if s and timing and kws and not any(k in timing for k in kws):
            findings.append({
                "severity": "warning",
                "code": "status_timing_mismatch",
                "message": (
                    f"Row {i} ({row.get('methodology', '?')}): status is "
                    f"'{STATUS_LABELS.get(s, s)}' but timing reads "
                    f"'{row.get('status_timing')}'."
                ),
            })

    # 4. Duplicate methodology names
    name_counts = Counter(
        (row.get("methodology") or "").strip().lower() for row in rows
    )
    for name, n in name_counts.items():
        if name and n > 1:
            findings.append({
                "severity": "warning",
                "code": "duplicate_methodology",
                "message": f"Methodology appears {n} times: '{name}'.",
            })

    # 5. Empty categories
    grouped = methods_by_category(data)
    for cat, group_rows in grouped.items():
        if not group_rows:
            findings.append({
                "severity": "info",
                "code": "empty_category",
                "message": f"Category '{cat}' has no methods listed.",
            })

    # 6. Insights numeric claims vs table
    review_match = re.search(
        r"([A-Za-z]+|\d+)\s+methods?\s+(?:are\s+)?currently\s+under\s+review",
        insights_text, re.IGNORECASE,
    )
    if review_match:
        claimed = _to_int(review_match.group(1))
        actual = counts["under_development"]
        if claimed is not None and claimed != actual:
            findings.append({
                "severity": "error",
                "code": "insight_under_dev_mismatch",
                "message": (
                    f"Insights text says '{review_match.group(1)} methods "
                    f"currently under review' but the table has {actual} "
                    f"Under Development rows."
                ),
            })

    closed_match = re.search(
        r"([A-Za-z]+|\d+)\s+methods?\s+have\s+closed",
        insights_text, re.IGNORECASE,
    )
    if closed_match:
        claimed = _to_int(closed_match.group(1))
        actual = counts["next_to_close"]
        if claimed is not None and claimed != actual:
            findings.append({
                "severity": "warning",
                "code": "insight_closed_mismatch",
                "message": (
                    f"Insights text says '{closed_match.group(1)} methods "
                    f"have closed' but the table has {actual} Next to Close "
                    f"rows. (The table may not include already-expired "
                    f"methods — verify against the DCCEEW sunsetting list.)"
                ),
            })

    pathways_match = re.search(
        r"energy efficiency[^.]*?from\s+([A-Za-z]+|\d+)\s+to\s+([A-Za-z]+|\d+)",
        insights_text, re.IGNORECASE,
    )
    if pathways_match:
        to_claim = _to_int(pathways_match.group(2))
        actual_ee_active = _category_active_counts(data)["Energy Efficiency"]
        if to_claim is not None and to_claim != actual_ee_active:
            findings.append({
                "severity": "warning",
                "code": "insight_ee_pathways_mismatch",
                "message": (
                    f"Insights text says Energy Efficiency pathways reduced "
                    f"to {pathways_match.group(2)}, but the table shows "
                    f"{actual_ee_active} Active Energy Efficiency method(s)."
                ),
            })

    # 7. Future-dated references in updates / status_timing
    months = (
        r"(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)"
    )
    date_re = re.compile(rf"(\d{{1,2}})\s+({months})\s+(\d{{4}})", re.IGNORECASE)
    month_idx = {
        m: i + 1 for i, m in enumerate([
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ])
    }
    for i, row in enumerate(rows, 1):
        for field in ("updates", "status_timing"):
            text = str(row.get(field, ""))
            for d, m, y in date_re.findall(text):
                try:
                    found = date(int(y), month_idx[m.lower()], int(d))
                except ValueError:
                    continue
                if found > today:
                    findings.append({
                        "severity": "info",
                        "code": "future_date",
                        "message": (
                            f"Row {i} ({row.get('methodology', '?')}): "
                            f"'{field}' references future date "
                            f"{found.isoformat()}."
                        ),
                    })

    return findings


def methods_to_csv(data: dict) -> str:
    """Render the methods table as CSV (UTF-8, RFC 4180 quoting)."""
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow([COLUMN_LABELS[c] for c in COLUMNS])
    for row in data.get("methods", []) or []:
        writer.writerow([row.get(c, "") for c in COLUMNS])
    return buf.getvalue()
