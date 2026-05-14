"""TPI-flavoured indicators derived from SBTi data.

The Transition Pathway Initiative assesses companies on:
  - Management Quality (MQ) — 5 levels (0..4*), how mature the company's
    governance and target-setting is.
  - Carbon Performance (CP) — alignment of stated targets with 1.5°C,
    Below-2°C, NDC, or Not Aligned pathways.

We don't have TPI's underlying questionnaire data, so we synthesise
TPI-style indicators from each SBTi record. These are flagged as
"derived from SBTi disclosures" — they're directional, not authoritative,
and should be supplemented with TPI's own assessments where they exist.
"""

from __future__ import annotations

import pandas as pd

from modules.sbti import CANON


# ─── Management Quality (synthetic) ───────────────────────────────────────────
# Levels mirror TPI's MQ 0-4 schema:
#   0 — Unaware / no public climate strategy
#   1 — Acknowledges climate but no validated target (removed/expired)
#   2 — Building capacity (Committed, no validated target yet)
#   3 — Integrating climate (validated near-term target)
#   4 — Strategic assessment (validated near-term AND net-zero)
#   4* — All of 4 plus an explicit 1.5°C-aligned classification

MQ_LABEL = {
    0: "Level 0 — Unaware",
    1: "Level 1 — Acknowledged but disengaged",
    2: "Level 2 — Building capacity",
    3: "Level 3 — Integrating climate",
    4: "Level 4 — Strategic assessment",
    "4*": "Level 4* — Aligned strategic assessment",
}

MQ_COLOUR = {
    0: "#7F1D1D",
    1: "#DC2626",
    2: "#D97706",
    3: "#F59E0B",
    4: "#16A34A",
    "4*": "#15803D",
}


def mq_level(row: pd.Series) -> tuple[str | int, str]:
    """Return (level, label). Level may be int 0-4 or '4*'."""
    near_term = str(row.get(CANON["near_term_status"], "")).strip().lower()
    nz_status = str(row.get(CANON["net_zero_status"], "")).strip().lower()
    long_term = str(row.get(CANON["long_term_status"], "")).strip().lower()
    classification = " ".join([
        str(row.get(CANON["target_class_long"], "")).lower(),
        str(row.get(CANON["target_class"], "")).lower(),
    ])
    ba15 = str(row.get(CANON["ba15_status"], "")).strip().lower()

    has_near = "targets set" in near_term or "validated" in near_term
    has_nz = ("targets set" in nz_status or "targets set" in long_term)
    is_15c = "1.5" in classification
    has_ba15 = ba15 in {"committed", "targets set", "approved"}

    # Truly disengaged = near-term itself was removed.
    if "removed" in near_term:
        return 1, MQ_LABEL[1]
    if not near_term or near_term == "nan":
        return 0, MQ_LABEL[0]
    if has_near and has_nz and is_15c and (has_ba15 or "aligned" in classification):
        return "4*", MQ_LABEL["4*"]
    if has_near and has_nz:
        return 4, MQ_LABEL[4]
    if has_near:
        return 3, MQ_LABEL[3]
    if "committed" in near_term:
        return 2, MQ_LABEL[2]
    return 0, MQ_LABEL[0]


# ─── Carbon Performance (synthetic) ───────────────────────────────────────────

CP_LABEL = {
    "1.5C": "Aligned 1.5°C",
    "WB2": "Aligned Below 2°C",
    "2C": "Aligned 2°C / NDC",
    "NA": "Not aligned",
    "INS": "Insufficient disclosure",
}

CP_COLOUR = {
    "Aligned 1.5°C": "#15803D",
    "Aligned Below 2°C": "#16A34A",
    "Aligned 2°C / NDC": "#D97706",
    "Not aligned": "#DC2626",
    "Insufficient disclosure": "#6B7280",
}


def cp_alignment(row: pd.Series) -> str:
    """Return CP alignment label per TPI categories."""
    near_term = str(row.get(CANON["near_term_status"], "")).strip().lower()
    classification = " ".join([
        str(row.get(CANON["target_class_long"], "")).lower(),
        str(row.get(CANON["target_class"], "")).lower(),
    ])

    if "removed" in near_term:
        return CP_LABEL["NA"]
    if "committed" in near_term and "targets set" not in near_term:
        return CP_LABEL["INS"]
    if "1.5" in classification:
        return CP_LABEL["1.5C"]
    if "well-below" in classification or "well below" in classification or "wb2" in classification:
        return CP_LABEL["WB2"]
    if "2°c" in classification or "2c" in classification:
        return CP_LABEL["2C"]
    if "targets set" in near_term:
        return CP_LABEL["INS"]
    return CP_LABEL["NA"]


# ─── Combined assessment ──────────────────────────────────────────────────────

def assess_tpi(row: pd.Series) -> dict:
    level, label = mq_level(row)
    return {
        "MQ Level": str(level),
        "MQ Description": label,
        "CP Alignment": cp_alignment(row),
    }


def attach_tpi(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    extra = df.apply(assess_tpi, axis=1, result_type="expand")
    return pd.concat([df.reset_index(drop=True), extra.reset_index(drop=True)], axis=1)
