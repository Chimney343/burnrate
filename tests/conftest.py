"""Pytest configuration and fixtures."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from src.lib.providers.base import DownloadResult
from src.config import GarminConfig


@pytest.fixture
def mock_garmin_api():
    """Create a mock Garmin API client with common method stubs."""
    api = MagicMock()
    api.get_activities.return_value = []
    api.get_devices.return_value = []
    api.get_gear.return_value = []
    api.get_stats.return_value = {}
    api.get_heart_rates.return_value = {}
    api.get_body_composition.return_value = {}
    api.get_user_profile.return_value = {"displayName": "Test User"}
    api.get_unit_system.return_value = {"id": 1}
    api.get_full_name.return_value = "Test User"
    api.get_device_last_used.return_value = {"userProfileNumber": 12345}
    return api


@pytest.fixture
def mock_garmin_authenticator(mock_garmin_api):
    """Create a mock GarminAuthenticator that returns the mock API."""
    with patch("src.lib.providers.garmin.downloader.GarminAuthenticator") as MockAuth:
        mock_auth_instance = MockAuth.return_value
        mock_auth_instance.get_client.return_value = mock_garmin_api
        yield MockAuth


@pytest.fixture
def garmin_config(tmp_path):
    """Create a GarminConfig for testing."""
    return GarminConfig(
        garmin_email="test@example.com",
        garmin_password="password123",
        token_store=str(tmp_path / "tokens.json"),
        data_dir=tmp_path / "data",
        days_back=7,
        download_activities=True,
        download_health=True,
        download_devices=True,
        download_gear=True,
        activity_limit=100,
    )


@pytest.fixture
def sample_download_result():
    """Create a sample DownloadResult for testing."""
    return DownloadResult(
        provider="garmin",
        success=True,
        items_downloaded={"activities": 10, "health_days": 5, "devices": 2, "gear": 3},
        items_cached={"health_days": 3},
        duration_seconds=2.5,
        data_dir="/tmp/data",
    )


@pytest.fixture
def failed_download_result():
    """Create a failed DownloadResult for testing."""
    return DownloadResult(
        provider="garmin",
        success=False,
        error="Authentication failed",
        warnings=["Could not connect", "Timeout occurred"],
    )


@pytest.fixture
def mock_bigquery_client():
    """Create a mock BigQuery client."""
    with patch("src.lib.bigquery.uploader.bigquery.Client") as MockClient:
        mock_client = MockClient.return_value
        mock_table = MagicMock()
        mock_client.create_table.return_value = mock_table
        mock_job = MagicMock()
        mock_job.result.return_value = None
        mock_client.load_table_from_json.return_value = mock_job
        yield mock_client


@pytest.fixture
def temp_garmin_data_dir(tmp_path):
    """Create a temporary Garmin data directory structure."""
    garmin_dir = tmp_path / "garmin"
    garmin_dir.mkdir()
    (garmin_dir / "activities").mkdir()
    (garmin_dir / "devices").mkdir()
    (garmin_dir / "gear").mkdir()
    (garmin_dir / "health").mkdir()
    return tmp_path
