"""
Draft disclosure text generator.
Produces AASB S2-aligned disclosure paragraphs from entered client data.
"""

from .framework import FRAMEWORK, PILLAR_DATA_KEYS


def _v(data: dict, key: str, default: str = "[not yet disclosed]") -> str:
    val = data.get(key, "")
    return val.strip() if val and str(val).strip() else default


def generate_all_disclosures(client_data: dict) -> dict[str, list[dict]]:
    result = {}
    for pillar_name in FRAMEWORK:
        result[pillar_name] = generate_pillar_disclosures(client_data, pillar_name)
    return result


def generate_pillar_disclosures(client_data: dict, pillar_name: str) -> list[dict]:
    pillar_key = PILLAR_DATA_KEYS[pillar_name]
    pillar_data = client_data.get(pillar_key, {})
    entity = client_data.get("client_name", "the Entity")
    disclosures = []

    for req in FRAMEWORK[pillar_name]["requirements"]:
        req_id = req["id"]
        req_data = pillar_data.get(req_id, {})
        status = req_data.get("status", "")
        data = req_data.get("data", {})
        text = _dispatch(req_id, data, entity, status)
        disclosures.append(
            {
                "id": req_id,
                "ref": req["ref"],
                "title": req["title"],
                "status": status,
                "text": text,
            }
        )

    return disclosures


def _dispatch(req_id: str, data: dict, entity: str, status: str) -> str:
    if not status or status == "not_met":
        return (
            f"[Disclosure not yet prepared for this requirement. "
            f"Complete the data entry form and set status to Partial or Met to generate draft text.]"
        )

    generators = {
        "GOV-1": _gov1,
        "GOV-2": _gov2,
        "GOV-3": _gov3,
        "GOV-4": _gov4,
        "STR-1": _str1,
        "STR-2": _str2,
        "STR-3": _str3,
        "STR-4": _str4,
        "STR-5": _str5,
        "RSK-1": _rsk1,
        "RSK-2": _rsk2,
        "RSK-3": _rsk3,
        "RSK-4": _rsk4,
        "MET-1": _met1,
        "MET-2": _met2,
        "MET-3": _met3,
        "MET-4": _met4,
        "MET-5": _met5,
        "MET-6": _met6,
    }
    fn = generators.get(req_id)
    if fn:
        return fn(data, entity)
    return f"[Draft disclosure for {req_id} – please review and finalise.]"


# ── Governance ────────────────────────────────────────────────────────────────

def _gov1(d: dict, e: str) -> str:
    body = _v(d, "responsible_body", "the Board")
    freq = _v(d, "review_frequency", "on a regular basis")
    desc = _v(d, "oversight_description", "")
    text = (
        f"{e}'s {body} is responsible for overseeing climate-related risks and opportunities. "
        f"Climate matters are reviewed {freq.lower()}."
    )
    if desc and desc != "[not yet disclosed]":
        text += f" {desc}"
    return text


def _gov2(d: dict, e: str) -> str:
    mechanism = _v(d, "skills_mechanism", "a combination of external advisors and board training")
    desc = _v(d, "skills_description", "")
    text = (
        f"{e} ensures appropriate climate-related skills and competencies at board level "
        f"through {mechanism.lower()}."
    )
    if desc and desc != "[not yet disclosed]":
        text += f" {desc}"
    return text


def _gov3(d: dict, e: str) -> str:
    decision = _v(d, "decision_integration", "")
    target = _v(d, "target_oversight", "")
    parts = []
    if decision and decision != "[not yet disclosed]":
        parts.append(
            f"Climate considerations are integrated into {e}'s board-level strategic "
            f"decisions and major transactions as follows: {decision}"
        )
    if target and target != "[not yet disclosed]":
        parts.append(
            f"The board oversees the setting of climate-related targets and monitors "
            f"progress against them as follows: {target}"
        )
    return " ".join(parts) if parts else (
        f"[Partial disclosure: details of board decision-making integration and "
        f"target oversight are being developed.]"
    )


def _gov4(d: dict, e: str) -> str:
    roles = _v(d, "management_roles", "dedicated sustainability and risk management roles")
    reporting = _v(d, "management_reporting", "")
    incentives = _v(d, "incentives", "")
    inc_desc = _v(d, "incentives_description", "")

    text = (
        f"{e} has established management-level accountability for climate-related risks "
        f"and opportunities through {roles}."
    )
    if reporting and reporting != "[not yet disclosed]":
        text += f" {reporting}"
    if incentives and incentives not in ("No", "", "[not yet disclosed]", "Under consideration"):
        inc_text = inc_desc if inc_desc != "[not yet disclosed]" else incentives
        text += f" Executive incentives are linked to climate performance: {inc_text}"
    return text


# ── Strategy ─────────────────────────────────────────────────────────────────

def _str1(d: dict, e: str) -> str:
    horizons = _v(d, "time_horizons", "short-, medium- and long-term")
    physical = _v(d, "physical_risks", "")
    transition = _v(d, "transition_risks", "")
    opps = _v(d, "opportunities", "")

    text = (
        f"{e} has identified the following climate-related risks and opportunities that "
        f"could reasonably affect its cash flows, access to finance or cost of capital "
        f"over {horizons} time horizons.\n\n"
    )
    if physical and physical != "[not yet disclosed]":
        text += f"Physical risks: {physical}\n\n"
    if transition and transition != "[not yet disclosed]":
        text += f"Transition risks: {transition}\n\n"
    if opps and opps != "[not yet disclosed]":
        text += f"Climate-related opportunities: {opps}"
    return text.strip()


def _str2(d: dict, e: str) -> str:
    bm = _v(d, "business_model_impact", "")
    vc = _v(d, "value_chain_impact", "")
    text = (
        f"Climate-related risks and opportunities affect {e}'s business model and "
        f"value chain as follows.\n\n"
    )
    if bm and bm != "[not yet disclosed]":
        text += f"Business model impacts: {bm}\n\n"
    if vc and vc != "[not yet disclosed]":
        text += f"Value chain impacts: {vc}"
    return text.strip()


def _str3(d: dict, e: str) -> str:
    fin = _v(d, "financial_position_impact", "")
    plan = _v(d, "financial_planning", "")
    quant = _v(d, "quantitative_estimates", "")

    text = f"{e} has assessed the financial effects of climate-related risks and opportunities.\n\n"
    if fin and fin != "[not yet disclosed]":
        text += f"Financial position and performance: {fin}\n\n"
    if plan and plan != "[not yet disclosed]":
        text += f"Financial planning: {plan}\n\n"
    if quant and quant not in ("No", "", "[not yet disclosed]"):
        text += f"Quantitative estimates: {quant}"
    return text.strip()


def _str4(d: dict, e: str) -> str:
    scenarios = _v(d, "scenarios_used", "")
    method = _v(d, "scenario_methodology", "")
    resilience = _v(d, "resilience_assessment", "")
    freq = _v(d, "scenario_frequency", "")

    text = (
        f"{e} has conducted climate scenario analysis to assess the resilience of its "
        f"strategy across a range of climate futures, including at least one scenario "
        f"consistent with limiting warming to 1.5°C.\n\n"
    )
    if scenarios and scenarios != "[not yet disclosed]":
        text += f"Scenarios used: {scenarios}\n\n"
    if method and method != "[not yet disclosed]":
        text += f"Methodology: {method}\n\n"
    if resilience and resilience != "[not yet disclosed]":
        text += f"Resilience assessment: {resilience}\n\n"
    if freq and freq not in ("Not yet conducted", "", "[not yet disclosed]"):
        text += f"Scenario analysis is conducted {freq.lower()}."
    return text.strip()


def _str5(d: dict, e: str) -> str:
    has_plan = _v(d, "has_transition_plan", "")
    nz = _v(d, "net_zero_commitment", "")
    levers = _v(d, "decarbonisation_levers", "")
    milestones = _v(d, "interim_milestones", "")
    update = _v(d, "transition_plan_update", "")

    if has_plan == "No":
        return (
            f"{e} does not currently have a climate transition plan. "
            f"[Further disclosure required when a transition plan is developed.]"
        )
    if has_plan == "In development":
        return (
            f"{e} is in the process of developing a climate transition plan. "
            f"[Disclosure will be updated when the plan is finalised.]"
        )

    text = f"{e} has a climate transition plan to achieve its decarbonisation commitments.\n\n"
    if nz and nz != "[not yet disclosed]":
        text += f"Commitment: {nz}\n\n"
    if levers and levers != "[not yet disclosed]":
        text += f"Decarbonisation levers: {levers}\n\n"
    if milestones and milestones != "[not yet disclosed]":
        text += f"Interim milestones: {milestones}\n\n"
    if update and update != "[not yet disclosed]":
        text += f"Plan review cadence: {update}"
    return text.strip()


# ── Risk Management ───────────────────────────────────────────────────────────

def _rsk1(d: dict, e: str) -> str:
    ident = _v(d, "identification_process", "")
    assess = _v(d, "assessment_criteria", "")
    register = _v(d, "risk_register", "")

    text = f"{e} has established processes to identify and assess climate-related risks.\n\n"
    if ident and ident != "[not yet disclosed]":
        text += f"Identification: {ident}\n\n"
    if assess and assess != "[not yet disclosed]":
        text += f"Assessment criteria: {assess}\n\n"
    if register and register not in ("No", "", "[not yet disclosed]"):
        text += f"Risk register: {register}."
    return text.strip()


def _rsk2(d: dict, e: str) -> str:
    method = _v(d, "prioritisation_method", "")
    threshold = _v(d, "materiality_threshold", "")

    text = f"{e} prioritises climate-related risks using a structured approach.\n\n"
    if method and method != "[not yet disclosed]":
        text += f"Prioritisation method: {method}\n\n"
    if threshold and threshold != "[not yet disclosed]":
        text += f"Materiality threshold: {threshold}"
    return text.strip()


def _rsk3(d: dict, e: str) -> str:
    process = _v(d, "opportunity_process", "")
    examples = _v(d, "opportunity_examples", "")

    text = f"{e} identifies and assesses climate-related opportunities as follows.\n\n"
    if process and process != "[not yet disclosed]":
        text += f"Process: {process}\n\n"
    if examples and examples != "[not yet disclosed]":
        text += f"Key opportunities identified: {examples}"
    return text.strip()


def _rsk4(d: dict, e: str) -> str:
    integration = _v(d, "erm_integration", "")
    changes = _v(d, "process_changes", "")

    text = (
        f"{e} integrates climate risk identification and assessment into its enterprise "
        f"risk management (ERM) framework.\n\n"
    )
    if integration and integration != "[not yet disclosed]":
        text += f"Integration approach: {integration}\n\n"
    if changes and changes not in ("No material changes", "", "[not yet disclosed]"):
        text += f"Changes during reporting period: {changes}"
    return text.strip()


# ── Metrics & Targets ─────────────────────────────────────────────────────────

def _met1(d: dict, e: str) -> str:
    tr = _v(d, "transition_risk_exposure", "[not measured]")
    pr = _v(d, "physical_risk_exposure", "[not measured]")
    opp = _v(d, "climate_opportunity_revenue", "[not measured]")
    capex = _v(d, "climate_capex", "[not measured]")
    rem = _v(d, "remuneration_pct", "[not measured]")

    return (
        f"{e} discloses the following cross-industry category metrics for the reporting period:\n\n"
        f"  • Assets / activities exposed to transition risks: ${tr}\n"
        f"  • Assets / activities exposed to physical risks: ${pr}\n"
        f"  • Revenue / assets aligned to climate opportunities: ${opp}\n"
        f"  • Capital deployed for climate risks / opportunities: ${capex}\n"
        f"  • Executive remuneration linked to climate outcomes: {rem}%"
    )


def _met2(d: dict, e: str) -> str:
    standard = _v(d, "industry_standard", "")
    metrics = _v(d, "industry_metrics", "")

    text = f"{e} applies the following industry-based metrics standard: {standard}.\n\n"
    if metrics and metrics != "[not yet disclosed]":
        text += f"Industry metrics disclosed:\n{metrics}"
    return text.strip()


def _met3(d: dict, e: str) -> str:
    s1 = _v(d, "scope1_tco2e", "[not measured]")
    s2_loc = _v(d, "scope2_location_tco2e", "[not measured]")
    s2_mkt = _v(d, "scope2_market_tco2e", "[not measured]")
    method = _v(d, "ghg_methodology", "")
    consol = _v(d, "consolidation_approach", "")
    assurance = _v(d, "scope12_assurance", "")

    text = (
        f"{e} discloses the following greenhouse gas (GHG) emissions for the reporting period:\n\n"
        f"  • Scope 1 (direct emissions): {s1} tCO₂e\n"
        f"  • Scope 2 – location-based: {s2_loc} tCO₂e\n"
        f"  • Scope 2 – market-based: {s2_mkt} tCO₂e\n\n"
    )
    meta = []
    if method and method not in ("Not yet measured", "", "[not yet disclosed]"):
        meta.append(f"Methodology: {method}")
    if consol and consol not in ("Not determined", "", "[not yet disclosed]"):
        meta.append(f"Consolidation: {consol}")
    if assurance and assurance != "[not yet disclosed]":
        meta.append(f"External assurance: {assurance}")
    if meta:
        text += "  " + " | ".join(meta)
    return text.strip()


def _met4(d: dict, e: str) -> str:
    total = _v(d, "scope3_total_tco2e", "[not measured]")
    cats = _v(d, "scope3_categories", "")
    method = _v(d, "scope3_methodology", "")
    exclusions = _v(d, "scope3_exclusions", "")

    text = f"{e} discloses total Scope 3 (indirect) GHG emissions of {total} tCO₂e.\n\n"
    if cats and cats != "[not yet disclosed]":
        text += f"By category:\n{cats}\n\n"
    if method and method != "[not yet disclosed]":
        text += f"Methodology: {method}\n\n"
    if exclusions and exclusions != "[not yet disclosed]":
        text += f"Exclusions: {exclusions}"
    return text.strip()


def _met5(d: dict, e: str) -> str:
    uses = _v(d, "uses_carbon_price", "No")
    price = _v(d, "carbon_price_value", "")
    application = _v(d, "carbon_price_application", "")

    if uses in ("No", ""):
        return f"{e} does not currently use an internal carbon price."
    if uses == "Under consideration":
        return f"{e} is evaluating the use of an internal carbon price."

    text = f"{e} applies an internal carbon price of ${price} per tCO₂e."
    if application and application != "[not yet disclosed]":
        text += f" {application}"
    return text


def _met6(d: dict, e: str) -> str:
    targets = _v(d, "emission_targets", "")
    base = _v(d, "base_year", "")
    sbt = _v(d, "science_based", "")
    offsets = _v(d, "offset_reliance", "")
    progress = _v(d, "target_progress", "")
    other = _v(d, "other_targets", "")

    text = f"{e} has established the following climate-related targets:\n\n"
    if targets and targets != "[not yet disclosed]":
        text += f"{targets}\n\n"
    if base and base != "[not yet disclosed]":
        text += f"Base year: {base}\n\n"
    if sbt and sbt not in ("No", "", "[not yet disclosed]"):
        text += f"Science-based targets: {sbt}\n\n"
    if offsets and offsets != "[not yet disclosed]":
        text += f"Role of offsets and removals: {offsets}\n\n"
    if progress and progress != "[not yet disclosed]":
        text += f"Progress in reporting period: {progress}\n\n"
    if other and other != "[not yet disclosed]":
        text += f"Other climate-related targets: {other}"
    return text.strip()
