"""Gap assessment scoring engine for AASB S2 requirements."""

from .framework import FRAMEWORK, PILLAR_DATA_KEYS

STATUS_SCORES: dict[str, int] = {
    "met": 2,
    "partial": 1,
    "not_met": 0,
    "": 0,
}

STATUS_LABELS: dict[str, str] = {
    "met": "Met",
    "partial": "Partial",
    "not_met": "Not Met",
    "": "Not Assessed",
}

STATUS_COLORS: dict[str, str] = {
    "met": "#22C55E",
    "partial": "#F59E0B",
    "not_met": "#EF4444",
    "": "#9CA3AF",
}

STATUS_BG: dict[str, str] = {
    "met": "#DCFCE7",
    "partial": "#FEF3C7",
    "not_met": "#FEE2E2",
    "": "#F3F4F6",
}

MATURITY_BANDS = [
    (80, "Advanced", "#15803D", "#DCFCE7"),
    (60, "Developing", "#65A30D", "#ECFCCB"),
    (40, "Emerging", "#D97706", "#FEF3C7"),
    (20, "Initial", "#EA580C", "#FFEDD5"),
    (0,  "Not Started", "#DC2626", "#FEE2E2"),
]


def get_maturity(pct: float) -> tuple[str, str, str]:
    """Return (label, text_color, bg_color) for a percentage score."""
    for threshold, label, color, bg in MATURITY_BANDS:
        if pct >= threshold:
            return label, color, bg
    return "Not Started", "#DC2626", "#FEE2E2"


def score_pillar(client_data: dict, pillar_name: str) -> dict:
    pillar_key = PILLAR_DATA_KEYS[pillar_name]
    pillar_data = client_data.get(pillar_key, {})
    requirements = FRAMEWORK[pillar_name]["requirements"]

    total = 0
    max_score = len(requirements) * 2
    gaps: list[dict] = []

    for req in requirements:
        req_id = req["id"]
        req_data = pillar_data.get(req_id, {})
        status = req_data.get("status", "")
        score = STATUS_SCORES.get(status, 0)
        total += score

        if score < 2:
            gaps.append(
                {
                    "id": req_id,
                    "ref": req["ref"],
                    "title": req["title"],
                    "status": status,
                    "score": score,
                    "gap": 2 - score,
                    "notes": req_data.get("notes", ""),
                }
            )

    pct = (total / max_score * 100) if max_score else 0
    label, color, bg = get_maturity(pct)

    return {
        "pillar": pillar_name,
        "score": total,
        "max_score": max_score,
        "percentage": round(pct, 1),
        "maturity_label": label,
        "maturity_color": color,
        "maturity_bg": bg,
        "gaps": gaps,
        "req_count": len(requirements),
        "met_count": sum(1 for r in requirements if pillar_data.get(r["id"], {}).get("status") == "met"),
        "partial_count": sum(1 for r in requirements if pillar_data.get(r["id"], {}).get("status") == "partial"),
        "not_met_count": sum(1 for r in requirements if pillar_data.get(r["id"], {}).get("status") == "not_met"),
    }


def score_overall(client_data: dict) -> dict:
    pillar_scores: dict[str, dict] = {}
    total = 0
    max_total = 0

    for pillar_name in FRAMEWORK:
        result = score_pillar(client_data, pillar_name)
        pillar_scores[pillar_name] = result
        total += result["score"]
        max_total += result["max_score"]

    pct = (total / max_total * 100) if max_total else 0
    label, color, bg = get_maturity(pct)

    all_gaps = []
    for ps in pillar_scores.values():
        all_gaps.extend(ps["gaps"])
    all_gaps.sort(key=lambda g: g["gap"], reverse=True)

    return {
        "overall_pct": round(pct, 1),
        "maturity_label": label,
        "maturity_color": color,
        "maturity_bg": bg,
        "total_score": total,
        "max_score": max_total,
        "pillars": pillar_scores,
        "priority_gaps": all_gaps,
    }


def requirement_completion(client_data: dict, pillar_name: str, req_id: str) -> str:
    """Return the status string for a single requirement."""
    pillar_key = PILLAR_DATA_KEYS[pillar_name]
    return client_data.get(pillar_key, {}).get(req_id, {}).get("status", "")
