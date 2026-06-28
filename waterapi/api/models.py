"""Pydantic response models for the API.

These give every endpoint a typed, documented response schema (visible in the
generated OpenAPI / Swagger UI at /docs) and let FastAPI validate the serialized
shape at the boundary instead of silently returning malformed JSON. Field names
match the camelCase keys the frontend already consumes.

Models are intentionally permissive about optionality: the underlying data has
real missing values (unmatched geography, absent funding records, null
coordinates), so most fields are Optional rather than forcing nulls into
non-nullable columns.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str


class TierCount(BaseModel):
    tier: str
    systems: int


class ComponentScores(BaseModel):
    compliance_risk_component: float | None = None
    enforcement_risk_component: float | None = None
    vulnerability_component: float | None = None
    drought_component: float | None = None
    funding_gap_component: float | None = None
    small_system_component: float | None = None
    data_quality_penalty: float | None = None


class System(BaseModel):
    """A scored water system as served to the table, map and detail panel."""

    pwsid: str
    name: str | None = None
    county: str | None = None
    population: int | None = None
    sizeClass: str | None = None
    ownerType: str | None = None
    waterSource: str | None = None
    activityStatus: str | None = None
    serviceConnections: int | None = None
    score: float | None = None
    tier: str | None = None
    rankStatewide: int | None = None
    rankCounty: int | None = None
    drivers: list[str | None] = []
    explanation: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geometrySourceTier: str | None = None
    boundaryType: str | None = None
    boundaryProvider: str | None = None
    matchMethod: str | None = None
    areaSqKm: float | None = None
    spatialConfidence: str | None = None
    spatialLimitationNote: str | None = None
    sourceProtectionStatus: str | None = None
    sourceProtectionKinds: str | None = None
    geoJoinConfidence: str | None = None
    svi: float | None = None
    droughtExposure: float | None = None
    severeDroughtWeeks: int | None = None
    violations36m: int | None = None
    healthViolations36m: int | None = None
    openViolation: bool | None = None
    violationTrend: str | None = None
    enforcement36m: int | None = None
    formalActions60m: int | None = None
    recentEnforcement: bool | None = None
    fundingGapFlag: str | None = None
    fundingMatchConfidence: str | None = None
    fundingNotes: str | None = None
    dataQualityFlags: str | None = None
    components: ComponentScores


class GeographyEvidence(BaseModel):
    primaryGeometry: str | None = None
    geometrySourceTier: str | None = None
    boundaryType: str | None = None
    boundaryProvider: str | None = None
    matchMethod: str | None = None
    areaSqKm: float | None = None
    spatialConfidence: str | None = None
    sourceProtectionStatus: str | None = None
    sourceProtectionKinds: str | None = None
    limitationNote: str | None = None


class SystemDetail(System):
    geographyEvidence: GeographyEvidence


class PaginatedSystems(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[System]


class GeographyBreakdown(BaseModel):
    verifiedServiceAreas: int
    modeledServiceAreas: int
    approximateLocations: int
    unmatchedGeography: int
    sourceProtectionAvailable: int


class TopCounty(BaseModel):
    county: str
    highReviewSystems: int


class SummaryResponse(BaseModel):
    total: int
    highReview: int
    criticalReview: int
    geography: GeographyBreakdown
    tiers: list[TierCount]
    topCounties: list[TopCounty]


class MapPoint(BaseModel):
    pwsid: str
    name: str | None = None
    county: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    tier: str | None = None
    score: float | None = None
    rankStatewide: int | None = None
    population: int | None = None
    spatialConfidence: str | None = None
    geometrySourceTier: str | None = None
    drivers: list[str | None] = []


class FeatureCollection(BaseModel):
    """A GeoJSON FeatureCollection. Feature geometry/properties are passed through
    as-is, so they are typed loosely here."""

    type: str = "FeatureCollection"
    features: list[dict[str, Any]]


class ScoreMover(BaseModel):
    pwsid: str
    name: str | None = None
    county: str | None = None
    scoreDelta: float
    tierFrom: str | None = None
    tierTo: str | None = None


class TrendsResponse(BaseModel):
    snapshots: int
    latest: str | None = None
    prior: str | None = None
    compared: int | None = None
    newly_escalated: int | None = None
    de_escalated: int | None = None
    top_score_increases: list[ScoreMover] | None = None
    message: str | None = None
