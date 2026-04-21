"""
AASB S2 Climate-Related Financial Disclosures – requirements framework.
Each pillar maps directly to AASB S2 paragraph references.
"""

PILLAR_DATA_KEYS = {
    "Governance": "governance",
    "Strategy": "strategy",
    "Risk Management": "risk_management",
    "Metrics & Targets": "metrics",
}

FRAMEWORK = {
    "Governance": {
        "code": "GOV",
        "color": "#1E3A8A",
        "bar_color": "#3B82F6",
        "description": (
            "Disclosure of governance processes, controls and procedures used to monitor, "
            "manage and oversee climate-related risks and opportunities. (AASB S2, paras. 6–9)"
        ),
        "requirements": [
            {
                "id": "GOV-1",
                "ref": "Para. 6(a)",
                "title": "Board oversight of climate risks and opportunities",
                "description": (
                    "Disclose how the board/oversight body oversees climate-related risks and "
                    "opportunities, including the responsible committee, frequency of review, "
                    "and how climate is integrated into the board agenda."
                ),
                "fields": [
                    {
                        "key": "responsible_body",
                        "label": "Responsible board body or committee",
                        "type": "text",
                        "placeholder": "e.g. Audit & Risk Committee, full Board",
                    },
                    {
                        "key": "review_frequency",
                        "label": "Frequency of climate reviews by this body",
                        "type": "select",
                        "options": [
                            "",
                            "Not established",
                            "Ad hoc",
                            "Annually",
                            "Half-yearly",
                            "Quarterly",
                            "Monthly or more frequent",
                        ],
                    },
                    {
                        "key": "oversight_description",
                        "label": "Describe how the board oversees climate-related risks and opportunities",
                        "type": "textarea",
                        "placeholder": "",
                    },
                ],
            },
            {
                "id": "GOV-2",
                "ref": "Para. 6(b)",
                "title": "Board skills and competencies",
                "description": (
                    "Disclose how the board ensures it has, or has access to, appropriate skills "
                    "and competencies to oversee climate-related risks and opportunities."
                ),
                "fields": [
                    {
                        "key": "skills_mechanism",
                        "label": "How are climate skills/competencies assured at board level?",
                        "type": "select",
                        "options": [
                            "",
                            "Not addressed",
                            "External advisors engaged",
                            "Dedicated board member with climate expertise",
                            "Board training programme",
                            "Board skills matrix includes climate",
                            "Multiple mechanisms in place",
                        ],
                    },
                    {
                        "key": "skills_description",
                        "label": "Describe climate-related skills and competencies at board level",
                        "type": "textarea",
                        "placeholder": "",
                    },
                ],
            },
            {
                "id": "GOV-3",
                "ref": "Para. 6(c)–(e)",
                "title": "Board decision-making and target oversight",
                "description": (
                    "Disclose how climate is considered in the board's strategic decisions and "
                    "major transactions, and how the board oversees climate target-setting "
                    "and monitors progress."
                ),
                "fields": [
                    {
                        "key": "decision_integration",
                        "label": "How is climate integrated into board-level strategic decisions?",
                        "type": "textarea",
                        "placeholder": "",
                    },
                    {
                        "key": "target_oversight",
                        "label": "How does the board oversee climate targets and monitor progress?",
                        "type": "textarea",
                        "placeholder": "",
                    },
                ],
            },
            {
                "id": "GOV-4",
                "ref": "Para. 7–9",
                "title": "Management roles and responsibilities",
                "description": (
                    "Disclose management-level roles responsible for assessing and managing "
                    "climate-related risks and opportunities, how those roles are structured, "
                    "and how management reports to the board."
                ),
                "fields": [
                    {
                        "key": "management_roles",
                        "label": "Positions or committees responsible for climate at management level",
                        "type": "textarea",
                        "placeholder": "e.g. Chief Sustainability Officer, Climate Risk Working Group",
                    },
                    {
                        "key": "management_reporting",
                        "label": "How does management report climate information to the board?",
                        "type": "textarea",
                        "placeholder": "",
                    },
                    {
                        "key": "incentives",
                        "label": "Are executive incentives linked to climate outcomes?",
                        "type": "select",
                        "options": [
                            "",
                            "No",
                            "Under consideration",
                            "Yes – short-term incentives (STI)",
                            "Yes – long-term incentives (LTI)",
                            "Yes – both STI and LTI",
                        ],
                    },
                    {
                        "key": "incentives_description",
                        "label": "If yes, describe the climate-related incentive structure",
                        "type": "textarea",
                        "placeholder": "",
                    },
                ],
            },
        ],
    },
    "Strategy": {
        "code": "STR",
        "color": "#14532D",
        "bar_color": "#22C55E",
        "description": (
            "Disclosure of how climate-related risks and opportunities affect the entity's "
            "business model, strategy and financial planning. (AASB S2, paras. 10–24)"
        ),
        "requirements": [
            {
                "id": "STR-1",
                "ref": "Para. 10–13",
                "title": "Climate risks and opportunities identified",
                "description": (
                    "Disclose the climate-related risks and opportunities identified that could "
                    "reasonably affect the entity's cash flows, access to finance or cost of "
                    "capital over the short, medium and long term."
                ),
                "fields": [
                    {
                        "key": "time_horizons",
                        "label": "Define the short, medium and long-term time horizons used",
                        "type": "textarea",
                        "placeholder": "e.g. Short: 0–3 years, Medium: 3–10 years, Long: 10+ years",
                    },
                    {
                        "key": "physical_risks",
                        "label": "Physical risks identified (acute and chronic)",
                        "type": "textarea",
                        "placeholder": "e.g. Increased frequency of extreme weather events (acute); sea-level rise, chronic heat stress (chronic)",
                    },
                    {
                        "key": "transition_risks",
                        "label": "Transition risks identified (policy, legal, technology, market, reputation)",
                        "type": "textarea",
                        "placeholder": "",
                    },
                    {
                        "key": "opportunities",
                        "label": "Climate-related opportunities identified",
                        "type": "textarea",
                        "placeholder": "e.g. Resource efficiency, new low-carbon products, access to green finance",
                    },
                ],
            },
            {
                "id": "STR-2",
                "ref": "Para. 14",
                "title": "Impact on business model and value chain",
                "description": (
                    "Disclose the current and anticipated effects of climate-related risks and "
                    "opportunities on the entity's business model and value chain."
                ),
                "fields": [
                    {
                        "key": "business_model_impact",
                        "label": "How do climate risks/opportunities affect the business model?",
                        "type": "textarea",
                        "placeholder": "",
                    },
                    {
                        "key": "value_chain_impact",
                        "label": "How do climate risks/opportunities affect the upstream and downstream value chain?",
                        "type": "textarea",
                        "placeholder": "",
                    },
                ],
            },
            {
                "id": "STR-3",
                "ref": "Para. 15–16",
                "title": "Financial effects and planning",
                "description": (
                    "Disclose the current and anticipated effects on financial position, "
                    "performance and cash flows, and how climate is integrated into financial planning."
                ),
                "fields": [
                    {
                        "key": "financial_position_impact",
                        "label": "Current effects on financial position, performance and cash flows",
                        "type": "textarea",
                        "placeholder": "",
                    },
                    {
                        "key": "financial_planning",
                        "label": "How is climate integrated into financial planning (capex, opex, funding)?",
                        "type": "textarea",
                        "placeholder": "",
                    },
                    {
                        "key": "quantitative_estimates",
                        "label": "Are quantitative financial impact estimates provided?",
                        "type": "select",
                        "options": [
                            "",
                            "No",
                            "Partial – qualitative ranges only",
                            "Yes – quantitative estimates for key risks",
                            "Yes – full quantitative impact analysis",
                        ],
                    },
                ],
            },
            {
                "id": "STR-4",
                "ref": "Para. 17–19",
                "title": "Climate scenario analysis and resilience",
                "description": (
                    "Disclose the climate scenarios used (including at least one aligned to "
                    "1.5°C), the methodology, and the resilience of the entity's strategy "
                    "under different climate futures."
                ),
                "fields": [
                    {
                        "key": "scenarios_used",
                        "label": "Climate scenarios used",
                        "type": "textarea",
                        "placeholder": "e.g. IEA Net Zero Emissions (NZE) 1.5°C, IEA Announced Pledges (APS), IPCC SSP3-7.0",
                    },
                    {
                        "key": "scenario_methodology",
                        "label": "Scenario analysis methodology and data sources",
                        "type": "textarea",
                        "placeholder": "",
                    },
                    {
                        "key": "resilience_assessment",
                        "label": "Resilience of the entity's strategy under each scenario",
                        "type": "textarea",
                        "placeholder": "",
                    },
                    {
                        "key": "scenario_frequency",
                        "label": "How frequently is scenario analysis conducted?",
                        "type": "select",
                        "options": [
                            "",
                            "Not yet conducted",
                            "Ad hoc / one-off",
                            "Every 3+ years",
                            "Every 2–3 years",
                            "Annually",
                            "Continuously updated",
                        ],
                    },
                ],
            },
            {
                "id": "STR-5",
                "ref": "Para. 20–24",
                "title": "Transition plan",
                "description": (
                    "If the entity has a climate-related transition plan, disclose the plan "
                    "including decarbonisation levers, interim milestones, resources, and "
                    "how the plan is reviewed and updated."
                ),
                "fields": [
                    {
                        "key": "has_transition_plan",
                        "label": "Does the entity have a climate transition plan?",
                        "type": "select",
                        "options": [
                            "",
                            "No",
                            "In development",
                            "Yes – internal only",
                            "Yes – publicly disclosed",
                        ],
                    },
                    {
                        "key": "net_zero_commitment",
                        "label": "Net zero or emissions reduction commitment",
                        "type": "textarea",
                        "placeholder": "e.g. Net zero Scope 1 and 2 by 2040",
                    },
                    {
                        "key": "decarbonisation_levers",
                        "label": "Key decarbonisation levers",
                        "type": "textarea",
                        "placeholder": "e.g. Energy efficiency, renewable energy procurement, electrification of fleet, carbon offsets",
                    },
                    {
                        "key": "interim_milestones",
                        "label": "Interim milestones and targets",
                        "type": "textarea",
                        "placeholder": "",
                    },
                    {
                        "key": "transition_plan_update",
                        "label": "How and when is the transition plan reviewed and updated?",
                        "type": "textarea",
                        "placeholder": "",
                    },
                ],
            },
        ],
    },
    "Risk Management": {
        "code": "RSK",
        "color": "#7C2D12",
        "bar_color": "#F97316",
        "description": (
            "Disclosure of processes for identifying, assessing, prioritising and monitoring "
            "climate-related risks and opportunities. (AASB S2, paras. 25–28)"
        ),
        "requirements": [
            {
                "id": "RSK-1",
                "ref": "Para. 25(a)–(b)",
                "title": "Risk identification and assessment process",
                "description": (
                    "Disclose the processes for identifying and assessing climate-related risks, "
                    "including inputs used, scope, coverage and frequency."
                ),
                "fields": [
                    {
                        "key": "identification_process",
                        "label": "How are climate risks identified? (tools, data sources, stakeholder inputs)",
                        "type": "textarea",
                        "placeholder": "",
                    },
                    {
                        "key": "assessment_criteria",
                        "label": "How are climate risks assessed? (likelihood, impact, time horizon criteria)",
                        "type": "textarea",
                        "placeholder": "",
                    },
                    {
                        "key": "risk_register",
                        "label": "Are climate risks formally included in the enterprise risk register?",
                        "type": "select",
                        "options": [
                            "",
                            "No",
                            "Partially – some risks captured",
                            "Yes – standalone climate risk register",
                            "Yes – fully integrated into ERM",
                        ],
                    },
                ],
            },
            {
                "id": "RSK-2",
                "ref": "Para. 25(c)",
                "title": "Risk prioritisation",
                "description": (
                    "Disclose how climate-related risks are prioritised relative to other risks "
                    "and how materiality is determined."
                ),
                "fields": [
                    {
                        "key": "prioritisation_method",
                        "label": "How are climate risks prioritised? (e.g. heat maps, materiality thresholds)",
                        "type": "textarea",
                        "placeholder": "",
                    },
                    {
                        "key": "materiality_threshold",
                        "label": "What materiality thresholds or criteria are applied?",
                        "type": "textarea",
                        "placeholder": "",
                    },
                ],
            },
            {
                "id": "RSK-3",
                "ref": "Para. 26",
                "title": "Opportunity identification and assessment",
                "description": (
                    "Disclose the processes for identifying, assessing and prioritising "
                    "climate-related opportunities."
                ),
                "fields": [
                    {
                        "key": "opportunity_process",
                        "label": "How are climate opportunities identified and assessed?",
                        "type": "textarea",
                        "placeholder": "",
                    },
                    {
                        "key": "opportunity_examples",
                        "label": "Key climate-related opportunities identified",
                        "type": "textarea",
                        "placeholder": "",
                    },
                ],
            },
            {
                "id": "RSK-4",
                "ref": "Para. 27–28",
                "title": "Integration into enterprise risk management",
                "description": (
                    "Disclose how climate risk processes are integrated into the overall "
                    "enterprise risk management framework and any changes during the reporting period."
                ),
                "fields": [
                    {
                        "key": "erm_integration",
                        "label": "How are climate risk processes integrated into overall risk management?",
                        "type": "textarea",
                        "placeholder": "",
                    },
                    {
                        "key": "process_changes",
                        "label": "Changes to climate risk processes during the reporting period",
                        "type": "textarea",
                        "placeholder": "Describe any changes, or state 'No material changes'",
                    },
                ],
            },
        ],
    },
    "Metrics & Targets": {
        "code": "MET",
        "color": "#4C1D95",
        "bar_color": "#8B5CF6",
        "description": (
            "Disclosure of metrics and targets used to measure, monitor and manage "
            "climate-related risks and opportunities. (AASB S2, paras. 29–50)"
        ),
        "requirements": [
            {
                "id": "MET-1",
                "ref": "Para. 29–31",
                "title": "Cross-industry category metrics",
                "description": (
                    "Disclose metrics across the cross-industry categories: transition risk "
                    "exposure, physical risk exposure, climate opportunities, capital deployed, "
                    "internal carbon price, and remuneration."
                ),
                "fields": [
                    {
                        "key": "transition_risk_exposure",
                        "label": "Assets / business activities exposed to transition risks ($)",
                        "type": "text",
                        "placeholder": "e.g. 450,000,000",
                    },
                    {
                        "key": "physical_risk_exposure",
                        "label": "Assets / business activities exposed to physical risks ($)",
                        "type": "text",
                        "placeholder": "e.g. 120,000,000",
                    },
                    {
                        "key": "climate_opportunity_revenue",
                        "label": "Revenue or assets aligned to climate opportunities ($)",
                        "type": "text",
                        "placeholder": "e.g. 30,000,000",
                    },
                    {
                        "key": "climate_capex",
                        "label": "Capital deployed for climate risks/opportunities ($)",
                        "type": "text",
                        "placeholder": "e.g. 15,000,000",
                    },
                    {
                        "key": "remuneration_pct",
                        "label": "% of executive remuneration linked to climate outcomes (%)",
                        "type": "text",
                        "placeholder": "e.g. 10",
                    },
                ],
            },
            {
                "id": "MET-2",
                "ref": "Para. 32–35",
                "title": "Industry-based metrics",
                "description": (
                    "Disclose industry-based metrics as required by the applicable SASB "
                    "industry standard(s) or other relevant industry metric sets."
                ),
                "fields": [
                    {
                        "key": "industry_standard",
                        "label": "Industry standard applied",
                        "type": "select",
                        "options": [
                            "",
                            "Not yet determined",
                            "SASB – Extractives & Minerals Processing",
                            "SASB – Financials",
                            "SASB – Food & Beverage",
                            "SASB – Infrastructure",
                            "SASB – Renewable Resources & Alternative Energy",
                            "SASB – Resource Transformation",
                            "SASB – Services",
                            "SASB – Technology & Communications",
                            "SASB – Transportation",
                            "Multiple SASB standards",
                            "Other industry framework",
                        ],
                    },
                    {
                        "key": "industry_metrics",
                        "label": "Industry-specific metrics disclosed and their values",
                        "type": "textarea",
                        "placeholder": "List each metric, unit and value",
                    },
                ],
            },
            {
                "id": "MET-3",
                "ref": "Para. 36–40",
                "title": "GHG emissions – Scope 1 and Scope 2",
                "description": (
                    "Disclose Scope 1 and Scope 2 GHG emissions in metric tonnes of CO₂e, "
                    "including the accounting methodology, consolidation approach and "
                    "assurance level."
                ),
                "fields": [
                    {
                        "key": "scope1_tco2e",
                        "label": "Scope 1 GHG emissions (tCO₂e)",
                        "type": "text",
                        "placeholder": "e.g. 12,500",
                    },
                    {
                        "key": "scope2_location_tco2e",
                        "label": "Scope 2 – location-based (tCO₂e)",
                        "type": "text",
                        "placeholder": "e.g. 8,200",
                    },
                    {
                        "key": "scope2_market_tco2e",
                        "label": "Scope 2 – market-based (tCO₂e)",
                        "type": "text",
                        "placeholder": "e.g. 3,100",
                    },
                    {
                        "key": "ghg_methodology",
                        "label": "GHG accounting methodology / standard",
                        "type": "select",
                        "options": [
                            "",
                            "Not yet measured",
                            "GHG Protocol Corporate Standard",
                            "ISO 14064",
                            "NGER Act (Australia)",
                            "GHG Protocol + NGER Act",
                            "Other",
                        ],
                    },
                    {
                        "key": "consolidation_approach",
                        "label": "Consolidation approach",
                        "type": "select",
                        "options": [
                            "",
                            "Not determined",
                            "Operational control",
                            "Financial control",
                            "Equity share",
                        ],
                    },
                    {
                        "key": "scope12_assurance",
                        "label": "External assurance over Scope 1 and 2 data",
                        "type": "select",
                        "options": [
                            "",
                            "None",
                            "Limited assurance",
                            "Reasonable assurance",
                        ],
                    },
                ],
            },
            {
                "id": "MET-4",
                "ref": "Para. 41–43",
                "title": "GHG emissions – Scope 3",
                "description": (
                    "Disclose Scope 3 GHG emissions across all relevant categories in tCO₂e, "
                    "or explain why categories are not relevant."
                ),
                "fields": [
                    {
                        "key": "scope3_total_tco2e",
                        "label": "Total Scope 3 GHG emissions (tCO₂e)",
                        "type": "text",
                        "placeholder": "e.g. 245,000",
                    },
                    {
                        "key": "scope3_categories",
                        "label": "Scope 3 categories included and individual emissions",
                        "type": "textarea",
                        "placeholder": "Cat 1 – Purchased goods & services: 90,000 tCO₂e\nCat 11 – Use of sold products: 120,000 tCO₂e",
                    },
                    {
                        "key": "scope3_methodology",
                        "label": "Scope 3 measurement methodology",
                        "type": "textarea",
                        "placeholder": "",
                    },
                    {
                        "key": "scope3_exclusions",
                        "label": "Scope 3 categories excluded and rationale",
                        "type": "textarea",
                        "placeholder": "",
                    },
                ],
            },
            {
                "id": "MET-5",
                "ref": "Para. 44–46",
                "title": "Internal carbon price",
                "description": (
                    "If an internal carbon price is used, disclose the price per tCO₂e and "
                    "how it is applied in decision-making."
                ),
                "fields": [
                    {
                        "key": "uses_carbon_price",
                        "label": "Does the entity use an internal carbon price?",
                        "type": "select",
                        "options": [
                            "",
                            "No",
                            "Under consideration",
                            "Yes – shadow price only",
                            "Yes – applied in capex decisions",
                            "Yes – applied across all operations",
                        ],
                    },
                    {
                        "key": "carbon_price_value",
                        "label": "Internal carbon price ($ per tCO₂e)",
                        "type": "text",
                        "placeholder": "e.g. 50",
                    },
                    {
                        "key": "carbon_price_application",
                        "label": "How is the internal carbon price applied?",
                        "type": "textarea",
                        "placeholder": "",
                    },
                ],
            },
            {
                "id": "MET-6",
                "ref": "Para. 47–50",
                "title": "Climate-related targets",
                "description": (
                    "Disclose climate-related targets including emission reduction targets, "
                    "base year, interim milestones, the role of offsets, and progress "
                    "against targets."
                ),
                "fields": [
                    {
                        "key": "emission_targets",
                        "label": "Emission reduction targets",
                        "type": "textarea",
                        "placeholder": "e.g. Net zero Scope 1+2 by 2040 from 2020 base year\n50% reduction Scope 1+2 by 2030",
                    },
                    {
                        "key": "base_year",
                        "label": "Base year for emission targets",
                        "type": "text",
                        "placeholder": "e.g. 2020",
                    },
                    {
                        "key": "science_based",
                        "label": "Are targets science-based (SBTi)?",
                        "type": "select",
                        "options": [
                            "",
                            "No",
                            "Committed to SBTi",
                            "SBTi validation in progress",
                            "SBTi validated – 1.5°C pathway",
                            "SBTi validated – Well-below 2°C pathway",
                        ],
                    },
                    {
                        "key": "offset_reliance",
                        "label": "Role of carbon offsets or removals in achieving targets",
                        "type": "textarea",
                        "placeholder": "",
                    },
                    {
                        "key": "target_progress",
                        "label": "Progress against targets in the current reporting period",
                        "type": "textarea",
                        "placeholder": "",
                    },
                    {
                        "key": "other_targets",
                        "label": "Other climate-related targets (energy, water, nature)",
                        "type": "textarea",
                        "placeholder": "",
                    },
                ],
            },
        ],
    },
}
