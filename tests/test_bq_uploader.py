"""Tests for the BigQuery uploader module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.lib.bigquery import (
    BaseUploader,
    GarminUploader,
    get_uploader,
)
from src.lib.bigquery.schemas import (
    GARMIN_SCHEMAS,
    PROVIDER_SCHEMAS,
    TableConfig,
    _make_schema,
)


class TestMakeSchema:
    def test_creates_schema_fields(self):
        schema = _make_schema(
            ("id", "INTEGER", "REQUIRED"),
            ("name", "STRING", "NULLABLE"),
        )
        assert len(schema) == 2
        assert schema[0].name == "id"
        assert schema[0].field_type == "INTEGER"
        assert schema[0].mode == "REQUIRED"
        assert schema[1].name == "name"
        assert schema[1].field_type == "STRING"
        assert schema[1].mode == "NULLABLE"


class TestTableConfig:
    def test_default_merge_files_false(self):
        config = TableConfig(
            name="test",
            schema=[],
            source_pattern="*.json",
        )
        assert config.merge_files is False

    def test_merge_files_can_be_set(self):
        config = TableConfig(
            name="test",
            schema=[],
            source_pattern="*.json",
            merge_files=True,
        )
        assert config.merge_files is True


class TestProviderSchemas:
    def test_garmin_schemas_exist(self):
        assert "garmin" in PROVIDER_SCHEMAS
        assert GARMIN_SCHEMAS is PROVIDER_SCHEMAS["garmin"]

    def test_garmin_has_expected_tables(self):
        expected = [
            "activities",
            "activity_details",
            "devices",
            "device_last_used",
            "gear",
            "health_stats",
            "health_heart_rate",
            "health_body_composition",
            "profile",
            "unit_system",
            "user_info",
        ]
        for table in expected:
            assert table in GARMIN_SCHEMAS, f"Missing table: {table}"


class TestBigQueryUploader:
    @pytest.fixture
    def mock_client(self):
        with patch("src.lib.bigquery.uploader.bigquery.Client") as mock:
            yield mock

    @pytest.fixture
    def temp_data_dir(self, tmp_path):
        garmin_dir = tmp_path / "garmin"
        garmin_dir.mkdir()
        (garmin_dir / "activities").mkdir()
        (garmin_dir / "devices").mkdir()
        (garmin_dir / "gear").mkdir()
        (garmin_dir / "health").mkdir()
        return tmp_path

    def test_init_with_valid_provider(self, mock_client, temp_data_dir):
        uploader = GarminUploader(
            project_id="test-project",
            dataset="test_dataset",
            data_dir=temp_data_dir,
            provider="garmin",
        )
        assert uploader.project_id == "test-project"
        assert uploader.dataset == "test_dataset"
        assert uploader.provider == "garmin"

    def test_init_with_invalid_provider_raises(self, mock_client, temp_data_dir):
        with pytest.raises(ValueError, match="Unknown provider"):
            GarminUploader(
                project_id="test-project",
                dataset="test_dataset",
                data_dir=temp_data_dir,
                provider="invalid_provider",
            )

    def test_get_table_id(self, mock_client, temp_data_dir):
        uploader = GarminUploader(
            project_id="my-project",
            dataset="burnrate_dev",
            data_dir=temp_data_dir,
            provider="garmin",
        )
        table_id = uploader._get_table_id("activities")
        assert table_id == "my-project.burnrate_dev.garmin_activities"

    def test_load_json_file(self, mock_client, temp_data_dir):
        test_file = temp_data_dir / "test.json"
        test_data = {"key": "value", "items": [1, 2, 3]}
        test_file.write_text(json.dumps(test_data), encoding="utf-8")

        uploader = GarminUploader(
            project_id="test-project",
            dataset="test_dataset",
            data_dir=temp_data_dir,
            provider="garmin",
        )
        loaded = uploader._load_json_file(test_file)
        assert loaded == test_data

    def test_find_source_files(self, mock_client, temp_data_dir):
        activities_dir = temp_data_dir / "garmin" / "activities"
        (activities_dir / "all_activities.json").write_text("[]")
        (activities_dir / "activity_123_details.json").write_text("{}")
        (activities_dir / "activity_456_details.json").write_text("{}")

        uploader = GarminUploader(
            project_id="test-project",
            dataset="test_dataset",
            data_dir=temp_data_dir,
            provider="garmin",
        )

        files = uploader._find_source_files(
            GARMIN_SCHEMAS["activities"], "activities"
        )
        assert len(files) == 1
        assert files[0].name == "all_activities.json"

        detail_files = uploader._find_source_files(
            GARMIN_SCHEMAS["activity_details"], "activities"
        )
        assert len(detail_files) == 2

    def test_prepare_rows_list_data(self, mock_client, temp_data_dir):
        test_file = temp_data_dir / "test.json"
        test_data = [{"id": 1}, {"id": 2}]
        test_file.write_text(json.dumps(test_data), encoding="utf-8")

        uploader = GarminUploader(
            project_id="test-project",
            dataset="test_dataset",
            data_dir=temp_data_dir,
            provider="garmin",
        )
        config = TableConfig(name="test", schema=[], source_pattern="test.json")
        rows = uploader._prepare_rows(config, [test_file])
        assert rows == [{"id": 1}, {"id": 2}]

    def test_prepare_rows_dict_data(self, mock_client, temp_data_dir):
        test_file = temp_data_dir / "test.json"
        test_data = {"id": 1, "name": "test"}
        test_file.write_text(json.dumps(test_data), encoding="utf-8")

        uploader = GarminUploader(
            project_id="test-project",
            dataset="test_dataset",
            data_dir=temp_data_dir,
            provider="garmin",
        )
        config = TableConfig(name="test", schema=[], source_pattern="test.json")
        rows = uploader._prepare_rows(config, [test_file])
        assert rows == [{"id": 1, "name": "test"}]

    def test_prepare_rows_string_data(self, mock_client, temp_data_dir):
        test_file = temp_data_dir / "test.json"
        test_file.write_text('"metric"', encoding="utf-8")

        uploader = GarminUploader(
            project_id="test-project",
            dataset="test_dataset",
            data_dir=temp_data_dir,
            provider="garmin",
        )
        config = TableConfig(name="test", schema=[], source_pattern="test.json")
        rows = uploader._prepare_rows(config, [test_file])
        assert rows == [{"value": "metric"}]

    def test_upload_table_invalid_table_raises(self, mock_client, temp_data_dir):
        uploader = GarminUploader(
            project_id="test-project",
            dataset="test_dataset",
            data_dir=temp_data_dir,
            provider="garmin",
        )
        with pytest.raises(ValueError, match="Unknown table"):
            uploader.upload_table("nonexistent_table")


class TestGetUploader:
    @pytest.fixture
    def mock_client(self):
        with patch("src.lib.bigquery.uploader.bigquery.Client") as mock:
            yield mock

    def test_get_uploader_creates_garmin_uploader(self, mock_client, tmp_path):
        from src.config import BigQueryConfig

        config = BigQueryConfig(
            gcp_project_id="my-project",
            bq_dataset="burnrate_prod",
            provider="garmin",
            data_dir=tmp_path,
        )

        uploader = get_uploader(config)

        assert isinstance(uploader, GarminUploader)
        assert uploader.project_id == "my-project"
        assert uploader.dataset == "burnrate_prod"
        assert uploader.provider == "garmin"
        assert uploader.data_dir == tmp_path

    def test_get_uploader_raises_without_project_id(self, mock_client, tmp_path):
        from src.config import BigQueryConfig

        config = BigQueryConfig(
            gcp_project_id="",
            data_dir=tmp_path,
        )

        with pytest.raises(ValueError, match="GCP_PROJECT_ID is required"):
            get_uploader(config)

    def test_get_uploader_raises_for_unknown_provider(self, mock_client, tmp_path):
        from src.config import BigQueryConfig

        config = BigQueryConfig(
            gcp_project_id="my-project",
            bq_dataset="burnrate_dev",
            provider="unknown",
            data_dir=tmp_path,
        )

        with pytest.raises(ValueError, match="No uploader implementation"):
            get_uploader(config)
