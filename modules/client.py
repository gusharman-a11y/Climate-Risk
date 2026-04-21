"""Client file management – one JSON file per client stored in the clients/ directory."""

import json
import os
from datetime import datetime
from pathlib import Path

CLIENTS_DIR = Path("clients")

ENTITY_TYPES = [
    "Large listed company (ASX)",
    "Large proprietary company",
    "Financial institution (bank / insurer / super fund)",
    "Government / public sector entity",
    "SME / unlisted company",
    "Not-for-profit",
    "Other",
]

INDUSTRIES = [
    "Agriculture, Forestry & Fishing",
    "Mining",
    "Oil & Gas",
    "Manufacturing",
    "Electricity, Gas & Water",
    "Construction",
    "Retail & Wholesale Trade",
    "Transport & Logistics",
    "Financial Services & Insurance",
    "Real Estate",
    "Professional Services",
    "Technology",
    "Healthcare",
    "Education",
    "Other",
]


def _ensure_dir() -> None:
    CLIENTS_DIR.mkdir(exist_ok=True)


def list_clients() -> list[str]:
    _ensure_dir()
    return sorted(f.stem for f in CLIENTS_DIR.glob("*.json"))


def load_client(name: str) -> dict | None:
    path = CLIENTS_DIR / f"{name}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_client(data: dict) -> None:
    _ensure_dir()
    data["updated_at"] = datetime.now().isoformat()
    name = data["client_name"]
    path = CLIENTS_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def new_client(name: str, entity_type: str, industry: str, reporting_period: str) -> dict:
    return {
        "client_name": name,
        "entity_type": entity_type,
        "industry": industry,
        "reporting_period": reporting_period,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "governance": {},
        "strategy": {},
        "risk_management": {},
        "metrics": {},
    }


def delete_client(name: str) -> None:
    path = CLIENTS_DIR / f"{name}.json"
    if path.exists():
        path.unlink()


def rename_safe(name: str) -> str:
    """Sanitise a client name for use as a filename."""
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip()
