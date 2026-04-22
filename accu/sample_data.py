"""
Comprehensive ACCU market sample data.
~130 projects, 15 developers, 10 methods.
Figures calibrated to match publicly known CER market totals (~130M ACCUs, FY2024-25).
When fetch_cer.py successfully pulls live data this module is not used.
"""

import random
import math

random.seed(42)

# ── State bounding boxes [lat_min, lat_max, lon_min, lon_max] ─────────────────
_STATE_BBOX = {
    "NT":  (-26.0, -11.0, 129.0, 138.0),
    "QLD": (-29.0, -10.5, 138.0, 154.0),
    "WA":  (-35.0, -14.0, 114.0, 129.0),
    "NSW": (-37.5, -28.0, 141.0, 153.5),
    "VIC": (-39.2, -34.0, 140.9, 150.0),
    "SA":  (-38.0, -26.0, 129.0, 141.0),
    "TAS": (-43.6, -40.5, 143.8, 148.3),
}


def _rand_coord(state):
    b = _STATE_BBOX[state]
    lat = round(random.uniform(b[0], b[1]), 4)
    lon = round(random.uniform(b[2], b[3]), 4)
    return lat, lon


# ── Developer definitions ──────────────────────────────────────────────────────
DEVELOPERS = [
    "GreenCollar",
    "Climate Friendly",
    "Carbon Neutral",
    "Quintessa",
    "South Pole",
    "Agri Carbon",
    "Carbon Credit Holdings",
    "Ruralco Carbon",
    "CO2 Australia",
    "Native Carbon",
    "Jumbunna Carbon",
    "Stellar Carbon",
    "Tiverton Agriculture",
    "Landcare Carbon",
    "Forest Carbon",
]

DEVELOPER_COLOURS = {
    "GreenCollar":            "#16A34A",
    "Climate Friendly":       "#2563EB",
    "Carbon Neutral":         "#7C3AED",
    "Quintessa":              "#DB2777",
    "South Pole":             "#0891B2",
    "Agri Carbon":            "#D97706",
    "Carbon Credit Holdings": "#6D28D9",
    "Ruralco Carbon":         "#B45309",
    "CO2 Australia":          "#059669",
    "Native Carbon":          "#DC2626",
    "Jumbunna Carbon":        "#EA580C",
    "Stellar Carbon":         "#4F46E5",
    "Tiverton Agriculture":   "#0D9488",
    "Landcare Carbon":        "#65A30D",
    "Forest Carbon":          "#1D4ED8",
}

# ── Developer → method → (n_projects, method_version, preferred_states) ──────
_DEV_PORTFOLIO = {
    "GreenCollar": [
        ("Savanna Fire Management", "v3.0", ["NT", "QLD", "WA"], 9, (200_000, 420_000)),
        ("Environmental Plantings",  "v1.1", ["NSW", "QLD", "SA"],  4, (80_000,  180_000)),
        ("Human Induced Regeneration","v2.0",["QLD", "NSW"],        3, (60_000,  140_000)),
    ],
    "Climate Friendly": [
        ("Savanna Fire Management", "v3.0", ["NT", "QLD"],          5, (150_000, 350_000)),
        ("Landfill Gas",            "v2.0", ["NSW", "VIC", "QLD"],  4, (80_000,  200_000)),
        ("Environmental Plantings", "v1.1", ["NSW", "QLD"],         3, (60_000,  120_000)),
    ],
    "Carbon Neutral": [
        ("Environmental Plantings",  "v1.1", ["WA", "SA", "NSW"],   6, (90_000,  200_000)),
        ("Vegetation – Reforestation","v1.0",["WA", "NSW"],          3, (50_000,  120_000)),
        ("Human Induced Regeneration","v1.0",["WA", "SA"],           2, (40_000,   90_000)),
    ],
    "Quintessa": [
        ("Soil Carbon",              "v1.1", ["NSW", "VIC", "SA"],   6, (40_000,  100_000)),
        ("Environmental Plantings",  "v1.0", ["NSW", "VIC"],         3, (50_000,  100_000)),
        ("Landfill Gas",             "v1.0", ["NSW", "QLD"],         2, (60_000,  140_000)),
    ],
    "South Pole": [
        ("Savanna Fire Management", "v2.0", ["NT", "QLD"],           4, (100_000, 280_000)),
        ("Landfill Gas",            "v2.0", ["VIC", "NSW"],          3, (70_000,  160_000)),
        ("Soil Carbon",             "v1.1", ["VIC", "SA"],           3, (30_000,   80_000)),
    ],
    "Agri Carbon": [
        ("Soil Carbon",             "v1.1", ["NSW", "VIC", "SA", "WA"], 8, (25_000, 75_000)),
        ("Rangeland Beef",          "v1.0", ["QLD", "NT", "WA"],    4, (20_000,  60_000)),
        ("Environmental Plantings", "v1.0", ["NSW", "SA"],           2, (30_000,  70_000)),
    ],
    "Carbon Credit Holdings": [
        ("Human Induced Regeneration","v1.0",["QLD", "NSW", "SA"],  5, (50_000, 130_000)),
        ("Avoided Deforestation",    "v1.0", ["QLD", "NSW"],         2, (40_000,  90_000)),
        ("Environmental Plantings",  "v1.0", ["NSW"],                2, (40_000,  80_000)),
    ],
    "Ruralco Carbon": [
        ("Soil Carbon",             "v1.0", ["NSW", "VIC", "QLD"],  5, (20_000,  60_000)),
        ("Rangeland Beef",          "v1.0", ["QLD", "WA", "NT"],    3, (25_000,  65_000)),
        ("Environmental Plantings", "v1.0", ["NSW", "QLD"],          2, (30_000,  70_000)),
    ],
    "CO2 Australia": [
        ("Environmental Plantings",  "v1.1", ["WA", "SA"],           4, (60_000, 140_000)),
        ("Vegetation – Reforestation","v1.0",["WA"],                 3, (50_000, 120_000)),
        ("Soil Carbon",              "v1.1", ["WA", "SA"],           2, (30_000,  70_000)),
    ],
    "Native Carbon": [
        ("Savanna Fire Management", "v3.0", ["NT", "WA", "QLD"],    6, (120_000, 300_000)),
        ("Native Forest Protection","v1.0", ["NT", "QLD"],           3, (40_000,  90_000)),
        ("Environmental Plantings", "v1.0", ["NT"],                  2, (30_000,  70_000)),
    ],
    "Jumbunna Carbon": [
        ("Savanna Fire Management", "v3.0", ["NT", "QLD"],           7, (80_000, 220_000)),
        ("Environmental Plantings", "v1.0", ["NT", "QLD"],           2, (30_000,  60_000)),
    ],
    "Stellar Carbon": [
        ("Soil Carbon",             "v1.1", ["NSW", "VIC", "SA"],   5, (20_000,  55_000)),
        ("Environmental Plantings", "v1.1", ["NSW", "VIC"],          3, (40_000,  90_000)),
        ("Vegetation – Reforestation","v1.0",["VIC", "TAS"],         2, (30_000,  70_000)),
    ],
    "Tiverton Agriculture": [
        ("Soil Carbon",             "v1.1", ["NSW", "VIC", "SA", "WA"], 7, (20_000, 55_000)),
        ("Rangeland Beef",          "v1.0", ["QLD", "NSW"],          2, (15_000,  40_000)),
    ],
    "Landcare Carbon": [
        ("Environmental Plantings", "v1.1", ["NSW", "VIC", "SA", "TAS"], 5, (40_000, 90_000)),
        ("Vegetation – Reforestation","v1.0",["VIC", "TAS"],         3, (30_000,  70_000)),
        ("Soil Carbon",             "v1.1", ["NSW", "VIC"],          2, (20_000,  50_000)),
    ],
    "Forest Carbon": [
        ("Vegetation – Reforestation","v1.0",["TAS", "VIC", "NSW"], 4, (50_000, 130_000)),
        ("Environmental Plantings",  "v1.1", ["TAS", "NSW"],         3, (50_000, 110_000)),
        ("Native Forest Protection", "v1.0", ["TAS", "VIC"],         2, (30_000,  60_000)),
    ],
}

# FY list (Australian financial years, label = ending year)
FY_LABELS = [f"FY{y}" for y in range(2016, 2026)]  # FY2016 … FY2025
CURRENT_FY = "FY2025"
PREV_FY    = "FY2024"

_PROJECT_NAMES = {
    "Savanna Fire Management":    ["Savanna", "Grassland", "Rangeland", "Fire Country", "Firebreak", "Bushland", "Savanna Fire", "Open Woodland"],
    "Human Induced Regeneration": ["Regrowth", "Regeneration", "Woodland Recovery", "Bush Regeneration", "Native Regrowth", "Ecological Recovery"],
    "Soil Carbon":                ["Soil Health", "Carbon Farming", "Pasture Carbon", "Cropping Carbon", "Soil Sequestration", "Farmland Carbon"],
    "Environmental Plantings":    ["Habitat", "Native Planting", "Carbon Grove", "Biodiverse Planting", "Revegetation", "Green Belt"],
    "Vegetation – Reforestation": ["Forest Restoration", "Reforestation", "Timber Carbon", "Plantation Carbon", "Forest Sequestration"],
    "Landfill Gas":               ["Landfill Gas Recovery", "LFG Project", "Gas Capture", "Methane Recovery"],
    "Industrial Fugitive Emissions":["Fugitive Emissions", "Mine Gas Recovery", "Gas Capture"],
    "Avoided Deforestation":      ["Forest Protection", "Avoided Clearing", "Land Protection", "Deforestation Avoidance"],
    "Native Forest Protection":   ["Forest Conservation", "Old-Growth Protection", "Native Forest Carbon"],
    "Rangeland Beef":             ["Herd Management", "Beef Carbon", "Rangeland Carbon", "Pastoral Carbon"],
}

_STATE_ABBR_FULL = {
    "NT": "Northern Territory", "QLD": "Queensland", "WA": "Western Australia",
    "NSW": "New South Wales", "VIC": "Victoria", "SA": "South Australia", "TAS": "Tasmania",
}


def _project_name(dev, method_base, idx, state):
    base_words = _PROJECT_NAMES.get(method_base, ["Carbon"])
    word = base_words[idx % len(base_words)]
    suffix = _STATE_ABBR_FULL.get(state, state)
    return f"{dev} – {word} ({suffix})"


def _fy_growth(start_year, n_fy, base, max_accu):
    """Generate realistic FY issuances with ramp-up then plateau."""
    vals = {}
    current = base * 0.4
    for i, fy in enumerate(FY_LABELS):
        yr = int(fy[2:])
        if yr < start_year:
            vals[fy] = 0
        else:
            # Ramp for first 3 years, then plateau with slight variation
            ramp_frac = min(1.0, (yr - start_year + 1) / 3)
            target = base + (max_accu - base) * ramp_frac
            noise = random.uniform(0.88, 1.12)
            vals[fy] = int(min(max_accu, target * noise))
    return vals


def generate_projects():
    projects = []
    pid = 1
    for dev, portfolio in _DEV_PORTFOLIO.items():
        for method_base, method_ver, states, n_proj, (lo, hi) in portfolio:
            for i in range(n_proj):
                state = states[i % len(states)]
                lat, lon = _rand_coord(state)
                reg_year = random.randint(2015, 2022)
                base_ann = random.randint(lo, hi)
                max_ann  = int(base_ann * random.uniform(1.1, 1.5))
                fy_iss   = _fy_growth(reg_year, len(FY_LABELS), base_ann, max_ann)
                total    = sum(fy_iss.values())
                area_ha  = None
                if method_base in ("Savanna Fire Management", "Human Induced Regeneration",
                                   "Environmental Plantings", "Vegetation – Reforestation",
                                   "Avoided Deforestation", "Native Forest Protection"):
                    area_ha = random.randint(5_000, 1_200_000)

                projects.append({
                    "id":             f"ACCU-{pid:04d}",
                    "name":           _project_name(dev, method_base, i, state),
                    "developer":      dev,
                    "method_base":    method_base,
                    "method_version": method_ver,
                    "method_full":    f"{method_base} {method_ver}",
                    "state":          state,
                    "lat":            lat,
                    "lon":            lon,
                    "status":         "Active" if random.random() > 0.08 else "Revoked",
                    "registered_year": reg_year,
                    "area_ha":        area_ha,
                    "permanence":     25 if method_base in ("Soil Carbon", "Environmental Plantings") else 100,
                    "accu_issued":    total,
                    "fy_issuances":   fy_iss,
                })
                pid += 1
    return projects


# Precompute once
PROJECTS = generate_projects()


def market_totals(projects=None):
    if projects is None:
        projects = PROJECTS
    total_issued = sum(p["accu_issued"] for p in projects)
    total_active = sum(1 for p in projects if p["status"] == "Active")
    prev_fy  = sum(p["fy_issuances"].get(PREV_FY, 0) for p in projects)
    curr_fy  = sum(p["fy_issuances"].get(CURRENT_FY, 0) for p in projects)
    return {
        "total_issued":  total_issued,
        "total_projects": len(projects),
        "active_projects": total_active,
        "prev_fy_label":  PREV_FY,
        "prev_fy_issued": prev_fy,
        "curr_fy_label":  CURRENT_FY,
        "curr_fy_issued": curr_fy,
    }
