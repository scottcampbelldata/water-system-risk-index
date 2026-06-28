"""Shared geography confidence hierarchy for the water system pipeline.

Single source of truth for the geometry-source tiers, their spatial-confidence
levels, and user-facing labels. Modeled EPA polygons are deliberately NOT treated
as verified boundaries; the user-facing label for system-sourced boundaries is
"System-Sourced Service Area" (not "Verified") because EPA does not assert a legal
service-area determination.
"""

from __future__ import annotations

# Stored enum -> spatial confidence level
TIER_TO_CONFIDENCE = {
    "verified_service_area_boundary": "very_high",
    "modeled_service_area_boundary": "medium_high",
    "validated_system_coordinate": "medium",
    "city_or_zip_centroid": "low",
    "county_centroid": "very_low",
    "unmatched": "unknown",
}

# Stored enum -> user-facing label
TIER_TO_LABEL = {
    "verified_service_area_boundary": "System-Sourced Service Area",
    "modeled_service_area_boundary": "Modeled Service Area",
    "validated_system_coordinate": "Approximate Location",
    "city_or_zip_centroid": "Approximate Location",
    "county_centroid": "Approximate Location",
    "unmatched": "Unmatched Geography",
}

# Phase 1 populates verified/modeled (EPA service-area polygons), county_centroid,
# and unmatched. The validated_system_coordinate and city_or_zip_centroid tiers are
# defined for the hierarchy but not yet sourced.
# TODO (Phase 2+): investigate EPA ECHO SDWA_FACILITIES or other public sources for
# facility points (wells/intakes/treatment plants) to populate validated_system_coordinate.
# No public Ohio source with usable coordinates has been confirmed yet.
VALID_TIERS = set(TIER_TO_CONFIDENCE)
VALID_CONFIDENCE = set(TIER_TO_CONFIDENCE.values())

# KPI buckets (user-facing geography breakdown)
APPROXIMATE_TIERS = {"validated_system_coordinate", "city_or_zip_centroid", "county_centroid"}

LIMITATION_NOTES = {
    "verified_service_area_boundary": (
        "System-sourced service-area boundary reported by a water system, state, or local "
        "provider. Suitable for screening and visualization, not a legal service-area determination."
    ),
    "modeled_service_area_boundary": (
        "Modeled service-area boundaries are suitable for screening and visualization, but "
        "should not be interpreted as legal service-area determinations."
    ),
    "county_centroid": (
        "No service-area boundary matched; the county centroid is used only for screening-level "
        "mapping and does not represent the system's actual service area."
    ),
    "unmatched": ("No service-area boundary and no county geography matched; location is unknown."),
}
