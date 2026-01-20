"""BigQuery uploader for provider data.

Handles uploading JSON data from local storage to BigQuery tables.
Supports multiple providers (garmin, strava, etc.) and datasets (dev, prod).
"""

import json
import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING

from google.cloud import bigquery
from google.cloud.bigquery import SchemaField
from tqdm import tqdm

from .schemas import PROVIDER_SCHEMAS, TableConfig

if TYPE_CHECKING:
    from ...config import BigQueryConfig


logger = logging.getLogger(__name__)


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
