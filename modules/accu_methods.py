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
