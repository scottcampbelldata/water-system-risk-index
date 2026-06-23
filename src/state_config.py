"""Config-driven target-state selection so the pipeline is not hardcoded to Ohio.

Set the target state(s) via the WATER_STATES environment variable (comma-separated
USPS abbreviations, e.g. "OH" or "OH,IN,PA") or the `target_states` key in
config/sources.yaml. Defaults to Ohio. Adding a state becomes a config change plus
staging that state's source data - no code edits to the pipeline.
"""

from __future__ import annotations

import os

from utils import REPO_ROOT, load_yaml

# USPS abbreviation -> 2-digit state FIPS (50 states + DC).
STATE_FIPS: dict[str, str] = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09",
    "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15", "ID": "16", "IL": "17",
    "IN": "18", "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24",
    "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29", "MT": "30", "NE": "31",
    "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53", "WV": "54",
    "WI": "55", "WY": "56",
}


def target_state_abbrs() -> list[str]:
    env = os.environ.get("WATER_STATES")
    if env:
        abbrs = [s.strip().upper() for s in env.split(",") if s.strip()]
    else:
        try:
            config = load_yaml(REPO_ROOT / "config" / "sources.yaml").get("project", {})
        except Exception:
            config = {}
        raw = config.get("target_states") or config.get("prototype_state") or "OH"
        abbrs = [s.strip().upper() for s in str(raw).split(",") if s.strip()]
    unknown = [a for a in abbrs if a not in STATE_FIPS]
    if unknown:
        raise ValueError(f"Unknown state abbreviation(s): {unknown}")
    return abbrs or ["OH"]


def target_state_fips() -> list[str]:
    return [STATE_FIPS[a] for a in target_state_abbrs()]
