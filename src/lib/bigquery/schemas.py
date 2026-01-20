"""BigQuery table schemas for different providers.

Contains table configurations and schema definitions for uploading
provider data to BigQuery.
"""

from dataclasses import dataclass
from typing import Any

from google.cloud.bigquery import SchemaField


@dataclass
class TableConfig:
    """Configuration for a BigQuery table."""
    name: str
    schema: list[SchemaField]
    source_pattern: str  # glob pattern for source files
    merge_files: bool = False  # whether to merge multiple files into one table


def _make_schema(*fields: tuple[str, str, str]) -> list[SchemaField]:
    """Helper to build schema from (name, type, mode) tuples."""
    return [SchemaField(name, field_type, mode=mode) for name, field_type, mode in fields]


# Schema definitions for Garmin data
GARMIN_SCHEMAS: dict[str, TableConfig] = {
    "activities": TableConfig(
        name="activities",
        schema=_make_schema(
            ("activityId", "INTEGER", "REQUIRED"),
            ("activityName", "STRING", "NULLABLE"),
            ("startTimeLocal", "STRING", "NULLABLE"),
            ("startTimeGMT", "STRING", "NULLABLE"),
            ("activityType", "JSON", "NULLABLE"),
            ("eventType", "JSON", "NULLABLE"),
            ("distance", "FLOAT", "NULLABLE"),
            ("duration", "FLOAT", "NULLABLE"),
            ("elapsedDuration", "FLOAT", "NULLABLE"),
            ("movingDuration", "FLOAT", "NULLABLE"),
            ("elevationGain", "FLOAT", "NULLABLE"),
            ("elevationLoss", "FLOAT", "NULLABLE"),
            ("averageSpeed", "FLOAT", "NULLABLE"),
            ("maxSpeed", "FLOAT", "NULLABLE"),
            ("startLatitude", "FLOAT", "NULLABLE"),
            ("startLongitude", "FLOAT", "NULLABLE"),
            ("endLatitude", "FLOAT", "NULLABLE"),
            ("endLongitude", "FLOAT", "NULLABLE"),
            ("calories", "FLOAT", "NULLABLE"),
            ("bmrCalories", "FLOAT", "NULLABLE"),
            ("averageHR", "FLOAT", "NULLABLE"),
            ("maxHR", "FLOAT", "NULLABLE"),
            ("steps", "INTEGER", "NULLABLE"),
            ("ownerId", "INTEGER", "NULLABLE"),
            ("ownerFullName", "STRING", "NULLABLE"),
            ("deviceId", "INTEGER", "NULLABLE"),
            ("manufacturer", "STRING", "NULLABLE"),
            ("locationName", "STRING", "NULLABLE"),
            ("lapCount", "INTEGER", "NULLABLE"),
            ("sportTypeId", "INTEGER", "NULLABLE"),
            ("aerobicTrainingEffect", "FLOAT", "NULLABLE"),
            ("anaerobicTrainingEffect", "FLOAT", "NULLABLE"),
            ("vO2MaxValue", "FLOAT", "NULLABLE"),
            ("trainingEffectLabel", "STRING", "NULLABLE"),
            ("activityTrainingLoad", "FLOAT", "NULLABLE"),
            ("hasPolyline", "BOOLEAN", "NULLABLE"),
            ("favorite", "BOOLEAN", "NULLABLE"),
            ("manualActivity", "BOOLEAN", "NULLABLE"),
        ),
        source_pattern="all_activities.json",
        merge_files=False,
    ),
    "activity_details": TableConfig(
        name="activity_details",
        schema=_make_schema(
            ("activityId", "INTEGER", "REQUIRED"),
            ("measurementCount", "INTEGER", "NULLABLE"),
            ("metricsCount", "INTEGER", "NULLABLE"),
            ("totalMetricsCount", "INTEGER", "NULLABLE"),
            ("metricDescriptors", "JSON", "NULLABLE"),
            ("activityDetailMetrics", "JSON", "NULLABLE"),
        ),
        source_pattern="activity_*_details.json",
        merge_files=True,
    ),
    "devices": TableConfig(
        name="devices",
        schema=_make_schema(
            ("deviceTypePk", "INTEGER", "NULLABLE"),
            ("applicationKey", "STRING", "NULLABLE"),
            ("productDisplayName", "STRING", "NULLABLE"),
            ("productSku", "STRING", "NULLABLE"),
            ("partNumber", "STRING", "NULLABLE"),
            ("imageUrl", "STRING", "NULLABLE"),
            ("deviceCategories", "JSON", "NULLABLE"),
            ("primary", "BOOLEAN", "NULLABLE"),
            ("wifi", "BOOLEAN", "NULLABLE"),
            ("hasOpticalHeartRate", "BOOLEAN", "NULLABLE"),
            ("appSupport", "BOOLEAN", "NULLABLE"),
            ("minGCMAndroidVersion", "INTEGER", "NULLABLE"),
            ("minGCMiOSVersion", "INTEGER", "NULLABLE"),
        ),
        source_pattern="devices.json",
        merge_files=False,
    ),
    "device_last_used": TableConfig(
        name="device_last_used",
        schema=_make_schema(
            ("userDeviceId", "INTEGER", "NULLABLE"),
            ("userProfileNumber", "INTEGER", "NULLABLE"),
            ("applicationNumber", "INTEGER", "NULLABLE"),
            ("lastUsedDeviceApplicationKey", "STRING", "NULLABLE"),
            ("lastUsedDeviceName", "STRING", "NULLABLE"),
            ("lastUsedDeviceUploadTime", "INTEGER", "NULLABLE"),
            ("imageUrl", "STRING", "NULLABLE"),
            ("released", "BOOLEAN", "NULLABLE"),
        ),
        source_pattern="device_last_used.json",
        merge_files=False,
    ),
    "gear": TableConfig(
        name="gear",
        schema=_make_schema(
            ("gearPk", "INTEGER", "REQUIRED"),
            ("uuid", "STRING", "NULLABLE"),
            ("userProfilePk", "INTEGER", "NULLABLE"),
            ("gearMakeName", "STRING", "NULLABLE"),
            ("gearModelName", "STRING", "NULLABLE"),
            ("gearTypeName", "STRING", "NULLABLE"),
            ("gearStatusName", "STRING", "NULLABLE"),
            ("displayName", "STRING", "NULLABLE"),
            ("customMakeModel", "STRING", "NULLABLE"),
            ("dateBegin", "STRING", "NULLABLE"),
            ("dateEnd", "STRING", "NULLABLE"),
            ("maximumMeters", "FLOAT", "NULLABLE"),
            ("notified", "BOOLEAN", "NULLABLE"),
            ("createDate", "STRING", "NULLABLE"),
            ("updateDate", "STRING", "NULLABLE"),
        ),
        source_pattern="gear_list.json",
        merge_files=False,
    ),
    "health": TableConfig(
        name="health",
        schema=_make_schema(
            ("date", "DATE", "REQUIRED"),
            ("stats", "JSON", "NULLABLE"),
            ("heart_rate", "JSON", "NULLABLE"),
            ("stress", "JSON", "NULLABLE"),
            ("sleep", "JSON", "NULLABLE"),
            ("body_battery", "JSON", "NULLABLE"),
            ("respiration", "JSON", "NULLABLE"),
            ("hrv", "JSON", "NULLABLE"),
            ("steps", "JSON", "NULLABLE"),
            ("hydration", "JSON", "NULLABLE"),
        ),
        source_pattern="health_*.json",
        merge_files=True,
    ),
    "profile": TableConfig(
        name="profile",
        schema=_make_schema(
            ("id", "INTEGER", "REQUIRED"),
            ("userData", "JSON", "NULLABLE"),
            ("userSleep", "JSON", "NULLABLE"),
            ("connectDate", "STRING", "NULLABLE"),
            ("sourceType", "STRING", "NULLABLE"),
            ("userSleepWindows", "JSON", "NULLABLE"),
        ),
        source_pattern="profile.json",
        merge_files=False,
    ),
    "unit_system": TableConfig(
        name="unit_system",
        schema=_make_schema(
            ("value", "STRING", "REQUIRED"),
        ),
        source_pattern="unit_system.json",
        merge_files=False,
    ),
    "user_info": TableConfig(
        name="user_info",
        schema=_make_schema(
            ("full_name", "STRING", "NULLABLE"),
        ),
        source_pattern="user_info.json",
        merge_files=False,
    ),
}

# Provider to schema mapping
PROVIDER_SCHEMAS: dict[str, dict[str, TableConfig]] = {
    "garmin": GARMIN_SCHEMAS,
}