"""
MMM Quality Framework for ERF/ACCU methodologies.
A = Methodology Integrity  (additionality, permanence, leakage, baselines)
B = MRV Quality           (measurement rigour, monitoring frequency, verifiability)
Scale: 1 (Low) → 5 (High)
Sources: Chubb Integrity Review (2022), CER method documents, academic literature.
"""

MMM = {
    "Savanna Fire Management": {
        "integrity":  4,
        "mrv":        3,
        "overall":    "High–Medium",
        "colour":     "#C2410C",
        "integrity_notes": (
            "Robust deforestation accounting using satellite remote sensing. "
            "Well-accepted internationally. Additionality clear in fire-prone landscapes. "
            "Not flagged by Chubb Review."
        ),
        "mrv_notes": (
            "NDVI / satellite fire-scar mapping. Some uncertainty in non-CO₂ gas emissions "
            "(CH₄, N₂O). MRV quality improved substantially in v3.0 with enhanced monitoring protocols."
        ),
        "chubb_status": "Not Flagged",
        "chubb_colour": "#15803D",
        "versions": {
            "v1.0": {"year": 2014, "notes": "Original method; superseded. Coarser emissions factors."},
            "v2.0": {"year": 2018, "notes": "Improved non-CO₂ emissions accounting."},
            "v3.0": {"year": 2022, "notes": "Current. Enhanced satellite monitoring; highest MRV quality."},
        },
    },
    "Human Induced Regeneration": {
        "integrity":  2,
        "mrv":        2,
        "overall":    "Low–Medium",
        "colour":     "#DC2626",
        "integrity_notes": (
            "Chubb Review (2022) identified significant over-crediting risk. "
            "Counterfactual baseline contested in high-rainfall zones where regrowth "
            "occurs naturally. Additionality difficult to establish. Permanence risk in drought."
        ),
        "mrv_notes": (
            "Remote sensing canopy cover as proxy for carbon stock. "
            "High uncertainty in biomass conversion. Soil carbon component rarely verified. "
            "Reversion risk poorly accounted for in v1.0."
        ),
        "chubb_status": "Flagged – Over-Crediting Risk",
        "chubb_colour": "#DC2626",
        "versions": {
            "v1.0": {"year": 2015, "notes": "Legacy. Highest integrity concerns. CER tightened eligibility post-Chubb."},
            "v2.0": {"year": 2023, "notes": "Revised baselines; tighter additionality test; still elevated risk."},
        },
    },
    "Soil Carbon": {
        "integrity":  3,
        "mrv":        2,
        "overall":    "Medium",
        "colour":     "#92400E",
        "integrity_notes": (
            "Sound concept but permanence and additionality questions remain. "
            "Practices must be additional to business-as-usual. "
            "Under regulatory review for measurement uncertainty."
        ),
        "mrv_notes": (
            "Direct soil core sampling required (expensive, infrequent). "
            "High spatial variability demands dense sampling. "
            "v1.1 allows modelling to supplement sampling but introduces model uncertainty."
        ),
        "chubb_status": "Under Review – Measurement Uncertainty",
        "chubb_colour": "#D97706",
        "versions": {
            "v1.0": {"year": 2018, "notes": "Sampling-only approach. High cost limits verification frequency."},
            "v1.1": {"year": 2021, "notes": "Modelling allowed as supplement. Wider uptake but higher model risk."},
        },
    },
    "Environmental Plantings": {
        "integrity":  4,
        "mrv":        3,
        "overall":    "Medium–High",
        "colour":     "#065F46",
        "integrity_notes": (
            "Well-established. Clear additionality in cleared agricultural landscapes. "
            "25 or 100-year permanence periods enforced. Not flagged by Chubb Review."
        ),
        "mrv_notes": (
            "Remote sensing canopy cover + field plot biomass sampling. "
            "Allometric equations well-validated for major species. "
            "LiDAR improving carbon stock estimates."
        ),
        "chubb_status": "Not Flagged",
        "chubb_colour": "#15803D",
        "versions": {
            "v1.0": {"year": 2015, "notes": "Standard method; sound and accepted."},
            "v1.1": {"year": 2020, "notes": "Updated species-specific biomass equations; minor improvement."},
        },
    },
    "Vegetation – Reforestation": {
        "integrity":  4,
        "mrv":        4,
        "overall":    "High",
        "colour":     "#15803D",
        "integrity_notes": (
            "Clear land-use-change baseline. Internationally aligned with IPCC guidelines. "
            "Strong additionality demonstrated by land-use history."
        ),
        "mrv_notes": (
            "Standard forest inventory methods. Well-validated allometric equations. "
            "Remote sensing integration for large sites."
        ),
        "chubb_status": "Not Flagged",
        "chubb_colour": "#15803D",
        "versions": {
            "v1.0": {"year": 2016, "notes": "Consistent with IPCC Tier 2. Robust and well-accepted."},
        },
    },
    "Landfill Gas": {
        "integrity":  5,
        "mrv":        5,
        "overall":    "High",
        "colour":     "#1D4ED8",
        "integrity_notes": (
            "Direct displacement of fossil-fuel electricity. No additionality ambiguity. "
            "Engineering-grade baseline from pre-capture emissions. Highest integrity of all methods."
        ),
        "mrv_notes": (
            "Continuous gas flow metering. Industry-standard equipment (CEMS). "
            "Third-party auditable with minimal subjectivity. "
            "Gas composition regularly tested."
        ),
        "chubb_status": "Not Flagged",
        "chubb_colour": "#15803D",
        "versions": {
            "v1.0": {"year": 2014, "notes": "Established and highly reliable."},
            "v2.0": {"year": 2020, "notes": "Minor updates to gas composition testing requirements."},
        },
    },
    "Industrial Fugitive Emissions": {
        "integrity":  5,
        "mrv":        5,
        "overall":    "High",
        "colour":     "#1D4ED8",
        "integrity_notes": (
            "Direct measurement of avoided fugitive emissions from coal mines and oil & gas. "
            "Engineering-grade. No additionality ambiguity."
        ),
        "mrv_notes": (
            "Continuous monitoring of gas capture volumes. Well-defined measurement protocols. "
            "Independently auditable."
        ),
        "chubb_status": "Not Flagged",
        "chubb_colour": "#15803D",
        "versions": {
            "v1.0": {"year": 2015, "notes": "Robust and well-accepted."},
        },
    },
    "Avoided Deforestation": {
        "integrity":  3,
        "mrv":        3,
        "overall":    "Medium",
        "colour":     "#D97706",
        "integrity_notes": (
            "Additionality dependent on credible land-clearing threat. "
            "Baseline methodology critical and contested. "
            "Leakage possible where clearing shifts to other properties."
        ),
        "mrv_notes": (
            "Remote sensing (Landsat/Sentinel) for deforestation detection. "
            "Established satellite methods but baseline construction subjective."
        ),
        "chubb_status": "Flagged – Baseline Integrity",
        "chubb_colour": "#D97706",
        "versions": {
            "v1.0": {"year": 2016, "notes": "Requires demonstrated credible clearing threat. Varies by case."},
        },
    },
    "Native Forest Protection": {
        "integrity":  3,
        "mrv":        3,
        "overall":    "Medium",
        "colour":     "#D97706",
        "integrity_notes": (
            "Permanence and additionality concerns. "
            "Leakage risk where logging shifts to other forests. "
            "Ongoing regulatory review of additionality requirements."
        ),
        "mrv_notes": (
            "Remote sensing based carbon stock estimation. "
            "Methods improving but still carry uncertainty in old-growth biomass."
        ),
        "chubb_status": "Under Review",
        "chubb_colour": "#D97706",
        "versions": {
            "v1.0": {"year": 2017, "notes": "Ongoing review; use with caution until review complete."},
        },
    },
    "Rangeland Beef": {
        "integrity":  3,
        "mrv":        2,
        "overall":    "Medium",
        "colour":     "#D97706",
        "integrity_notes": (
            "Emissions reduction from altered herd management. "
            "Additionality shown via management change. Permanence questions remain."
        ),
        "mrv_notes": (
            "IPCC Tier 2 modelled emissions factors. "
            "Herd data verification via property records. "
            "Limited direct measurement; model-dependent."
        ),
        "chubb_status": "Under Review",
        "chubb_colour": "#D97706",
        "versions": {
            "v1.0": {"year": 2019, "notes": "Based on IPCC Tier 2; acknowledged measurement limitations."},
        },
    },
}

OVERALL_COLOURS = {
    "High":         "#15803D",
    "High–Medium":  "#65A30D",
    "Medium–High":  "#65A30D",
    "Medium":       "#D97706",
    "Low–Medium":   "#DC2626",
    "Low":          "#991B1B",
}

CHUBB_ORDER = ["Not Flagged", "Under Review", "Under Review – Measurement Uncertainty",
                "Flagged – Baseline Integrity", "Flagged – Over-Crediting Risk"]


def get_method_names():
    return list(MMM.keys())


def quality_summary():
    """Return list of dicts for table display."""
    rows = []
    for method, q in MMM.items():
        for ver, vdata in q["versions"].items():
            rows.append({
                "method": method,
                "version": ver,
                "version_year": vdata["year"],
                "version_notes": vdata["notes"],
                "integrity": q["integrity"],
                "mrv": q["mrv"],
                "overall": q["overall"],
                "chubb_status": q["chubb_status"],
                "integrity_notes": q["integrity_notes"],
                "mrv_notes": q["mrv_notes"],
                "colour": q["colour"],
            })
    return rows
