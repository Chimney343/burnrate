"""BigQuery uploader for provider data.

Handles uploading JSON data from local storage to BigQuery tables.
Supports multiple providers (garmin, strava, etc.) and datasets (dev, prod).
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google.cloud import bigquery
from google.cloud.bigquery import SchemaField
from tqdm import tqdm


logger = logging.getLogger(__name__)


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


class BigQueryUploader:
    """Uploads provider data to BigQuery."""
    
    def __init__(
        self,
        project_id: str,
        dataset: str,
        data_dir: Path,
        provider: str = "garmin",
    ):
        self.project_id = project_id
        self.dataset = dataset
        self.data_dir = data_dir
        self.provider = provider
        self.client = bigquery.Client(project=project_id)
        
        if provider not in PROVIDER_SCHEMAS:
            raise ValueError(f"Unknown provider: {provider}. Available: {list(PROVIDER_SCHEMAS.keys())}")
        
        self.schemas = PROVIDER_SCHEMAS[provider]
        self.provider_dir = data_dir / provider
    
    def _get_table_id(self, table_name: str) -> str:
        return f"{self.project_id}.{self.dataset}.{self.provider}_{table_name}"
    
    def _ensure_table_exists(self, table_name: str, schema: list[SchemaField]) -> bigquery.Table:
        table_id = self._get_table_id(table_name)
        table = bigquery.Table(table_id, schema=schema)
        table = self.client.create_table(table, exists_ok=True)
        return table
    
    def _load_json_file(self, path: Path) -> Any:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    
    def _find_source_files(self, config: TableConfig, subdir: str | None = None) -> list[Path]:
        if subdir:
            search_dir = self.provider_dir / subdir
        else:
            search_dir = self.provider_dir
        
        if not search_dir.exists():
            return []
        
        return list(search_dir.glob(config.source_pattern))
    
    def _prepare_rows(self, config: TableConfig, files: list[Path]) -> list[dict[str, Any]]:
        rows = []
        
        for file_path in files:
            data = self._load_json_file(file_path)
            
            if isinstance(data, list):
                rows.extend(data)
            elif isinstance(data, dict):
                rows.append(data)
            elif isinstance(data, str):
                rows.append({"value": data})
            else:
                logger.warning("Unexpected data type in %s: %s", file_path, type(data))
        
        return rows
    
    def _upload_table(self, table_name: str, config: TableConfig, subdir: str | None = None) -> int:
        files = self._find_source_files(config, subdir)
        
        if not files:
            logger.debug("No files found for %s", table_name)
            return 0
        
        rows = self._prepare_rows(config, files)
        
        if not rows:
            logger.debug("No rows to upload for %s", table_name)
            return 0
        
        table = self._ensure_table_exists(table_name, config.schema)
        
        job_config = bigquery.LoadJobConfig(
            schema=config.schema,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        )
        
        job = self.client.load_table_from_json(rows, table, job_config=job_config)
        job.result()
        
        logger.info("Uploaded %d rows to %s", len(rows), self._get_table_id(table_name))
        return len(rows)
    
    def upload_all(self) -> dict[str, int]:
        """Upload all data for the provider to BigQuery.
        
        Returns:
            Dict mapping table names to row counts uploaded.
        """
        results = {}
        
        table_configs = [
            ("activities", "activities"),
            ("activity_details", "activities"),
            ("devices", "devices"),
            ("device_last_used", "devices"),
            ("gear", "gear"),
            ("health", "health"),
            ("profile", None),
            ("unit_system", None),
            ("user_info", None),
        ]
        
        for table_name, subdir in tqdm(table_configs, desc="Uploading tables", unit="table"):
            if table_name not in self.schemas:
                continue
            
            config = self.schemas[table_name]
            try:
                count = self._upload_table(table_name, config, subdir)
                results[table_name] = count
            except Exception as e:
                logger.error("Failed to upload %s: %s", table_name, e)
                raise
        
        return results
    
    def upload_table(self, table_name: str, subdir: str | None = None) -> int:
        """Upload a single table.
        
        Args:
            table_name: Name of the table to upload.
            subdir: Subdirectory containing the source files.
            
        Returns:
            Number of rows uploaded.
        """
        if table_name not in self.schemas:
            raise ValueError(f"Unknown table: {table_name}. Available: {list(self.schemas.keys())}")
        
        config = self.schemas[table_name]
        return self._upload_table(table_name, config, subdir)

    @classmethod
    def from_config(cls, config: "BigQueryConfig") -> "BigQueryUploader":
        """Create uploader from configuration object."""
        from config import BigQueryConfig  # noqa: F811
        
        if not config.gcp_project_id:
            raise ValueError("GCP_PROJECT_ID is required")
        
        return cls(
            project_id=config.gcp_project_id,
            dataset=config.bq_dataset,
            data_dir=config.data_dir,
            provider=config.provider,
        )


def upload_provider_data(
    project_id: str,
    dataset: str,
    data_dir: Path,
    provider: str = "garmin",
) -> dict[str, int]:
    """Convenience function to upload all data for a provider.
    
    Args:
        project_id: GCP project ID.
        dataset: BigQuery dataset name (e.g., "burnrate_dev" or "burnrate_prod").
        data_dir: Root data directory containing provider subdirectories.
        provider: Provider name (e.g., "garmin", "strava").
        
    Returns:
        Dict mapping table names to row counts uploaded.
    """
    uploader = BigQueryUploader(
        project_id=project_id,
        dataset=dataset,
        data_dir=data_dir,
        provider=provider,
    )
    return uploader.upload_all()
