"""Financial quantification of transition-risk exposure for ASX-listed NGER reporters.

Prices each company's FY2024-25 Scope 1 + Scope 2 emissions under four carbon-price
levels and expresses the annual unpriced carbon cost as a share of market cap and
revenue. All damage-based prices exclude tipping points, so results are lower bounds.

Price levels (USD/tCO2-e, converted at AUD_PER_USD):
  paid      -- ~effective price actually paid today (World Bank global average, 2026)
  ngfs_nz30 -- NGFS Net Zero 2050 scenario carbon price c. 2030
  epa_scc   -- US EPA social cost of carbon (2023, 2% Ramsey discount)
  bilal     -- Bilal & Kanzig (NBER w32450) implied SCC

Outputs data/carbon_cost_exposure.csv and prints a ranked summary.
"""

import re

import pandas as pd

AUD_PER_USD = 1.55

PRICES_USD = {
    "paid": 21,        # World Bank State & Trends 2026 average priced ton
    "ngfs_nz30": 130,  # NGFS NZ2050, advanced-economy shadow price c.2030
    "epa_scc": 190,    # EPA 2023 SCC central estimate
    "bilal": 1056,     # Bilal & Kanzig implied SCC
}

STOPWORDS = {
    "limited", "ltd", "pty", "holdings", "group", "corporation", "inc",
    "plc", "company", "co", "the", "australia", "australian", "energy",
}


def _norm(name: str) -> frozenset:
    tokens = re.sub(r"[^a-z0-9 ]", " ", str(name).lower()).split()
    core = [t for t in tokens if t not in STOPWORDS]
    return frozenset(core or tokens)


def load_nger(path: str = "data/nger_2024_25.xlsx.xlsx") -> pd.DataFrame:
    df = pd.read_excel(path, header=3)
    df.columns = ["org", "abn", "scope1_t", "scope2_t", "energy_gj", "notes"]
    df = df.dropna(subset=["org"])
    for col in ("scope1_t", "scope2_t"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["s12_t"] = df["scope1_t"] + df["scope2_t"]
    return df[df["s12_t"] > 0][["org", "scope1_t", "scope2_t", "s12_t"]]


# NGER entities that share a core name with an unrelated ASX listing
UNLISTED_NAMESAKES = [
    "lion pty",             # brewer (Kirin), not Lion Energy Ltd
]


def match_to_asx(nger: pd.DataFrame, caps: pd.DataFrame) -> pd.DataFrame:
    cap_keys = {i: _norm(n) for i, n in caps["name"].items()}
    rows = []
    for _, r in nger.iterrows():
        nk = _norm(r["org"])
        if not nk or any(set(x.split()) <= set(str(r["org"]).lower().split())
                         for x in UNLISTED_NAMESAKES):
            continue
        # exact core-token match first; else the listed name fully contained in the
        # NGER name (>=2 tokens, unique) so "Arrow Minerals" can't claim "Arrow Energy"
        hit = next((i for i, k in cap_keys.items() if k == nk), None)
        if hit is None:
            subset_hits = [i for i, k in cap_keys.items() if len(k) >= 2 and k <= nk]
            hit = subset_hits[0] if len(subset_hits) == 1 else None
        if hit is not None:
            rows.append({**r.to_dict(),
                         "asx_code": caps.at[hit, "asx_code"],
                         "name": caps.at[hit, "name"],
                         "market_cap_aud": caps.at[hit, "market_cap_aud"]})
    matched = pd.DataFrame(rows)
    # a listed parent can have several NGER reporting entities -- aggregate
    return (matched.groupby(["asx_code", "name", "market_cap_aud"], as_index=False)
                   [["scope1_t", "scope2_t", "s12_t"]].sum())


def add_revenue(df: pd.DataFrame, path: str = "data/company_size.csv") -> pd.DataFrame:
    size = pd.read_csv(path)
    size["key"] = size["Company Name"].map(_norm)
    df["key"] = df["name"].map(_norm)
    rev = {}
    for _, r in df.iterrows():
        hits = size[size["key"].apply(lambda k: bool(k) and (k <= r["key"] or r["key"] <= k))]
        if len(hits) == 1:
            rev[r["asx_code"]] = hits["Revenue (AUD)"].iloc[0]
    df["revenue_aud"] = df["asx_code"].map(rev)
    return df.drop(columns="key")


def price_exposure(df: pd.DataFrame) -> pd.DataFrame:
    for label, usd in PRICES_USD.items():
        aud = usd * AUD_PER_USD
        df[f"cost_{label}_aud"] = df["s12_t"] * aud
        df[f"cost_{label}_pct_mcap"] = 100 * df[f"cost_{label}_aud"] / df["market_cap_aud"]
        df[f"cost_{label}_pct_rev"] = 100 * df[f"cost_{label}_aud"] / df["revenue_aud"]
    # underpricing gap: damages at EPA SCC minus what a fully-priced ton costs today
    df["unpriced_gap_aud"] = df["cost_epa_scc_aud"] - df["cost_paid_aud"]
    return df.sort_values("cost_epa_scc_pct_mcap", ascending=False)


def main() -> pd.DataFrame:
    nger = load_nger()
    caps = pd.read_csv("data/asx_market_caps.csv")
    df = price_exposure(add_revenue(match_to_asx(nger, caps)))
    df.to_csv("data/carbon_cost_exposure.csv", index=False)

    total_mt = df["s12_t"].sum() / 1e6
    print(f"Matched {len(df)} ASX-listed NGER reporters | "
          f"{total_mt:,.0f} MtCO2-e Scope 1+2 (FY2024-25)")
    for label, usd in PRICES_USD.items():
        cost = df[f"cost_{label}_aud"].sum()
        print(f"  @ USD {usd:>5}/t ({label:9}): A${cost/1e9:8.1f} bn/yr "
              f"= {100 * cost / df['market_cap_aud'].sum():5.1f}% of combined mkt cap")
    gap = df["unpriced_gap_aud"].sum()
    print(f"  Unpriced gap (EPA SCC - paid): A${gap/1e9:,.1f} bn/yr")

    cols = ["asx_code", "name", "s12_t", "cost_epa_scc_pct_mcap", "cost_epa_scc_pct_rev"]
    print("\nTop 15 by EPA-SCC carbon cost as % of market cap:")
    print(df[cols].head(15).to_string(index=False,
          formatters={"s12_t": "{:,.0f}".format,
                      "cost_epa_scc_pct_mcap": "{:.1f}%".format,
                      "cost_epa_scc_pct_rev": "{:.1f}%".format}))
    return df


if __name__ == "__main__":
    main()
