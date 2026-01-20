"""Tests for garmin.downloader module - refactored architecture."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, mock_open, PropertyMock

import pytest

from src.lib.base import DownloadResult, DataProvider
from src.lib.garmin.downloader import GarminDataDownloader
from src.config import GarminConfig
from src.lib.garmin.auth import GarminAuthenticator


class TestGarminDataDownloaderFactory:
    """Test factory method from_config."""

    def test_from_config_creates_instance(self, tmp_path):
        """Test from_config creates downloader with proper configuration."""
        config = GarminConfig(
            garmin_email="test@example.com",
            garmin_password="password123",
            garmin_token_store=str(tmp_path / "tokens.json"),
            data_dir=str(tmp_path / "data"),
            days_back=7,
            download_activities=True,
            download_health=True,
            download_devices=True,
            download_gear=True,
            activity_limit=100,
        )

        with patch("src.lib.garmin.downloader.GarminAuthenticator") as MockAuth:
            mock_auth_instance = MockAuth.return_value
            mock_client = MagicMock()
            mock_auth_instance.get_client.return_value = mock_client

            downloader = GarminDataDownloader.from_config(config)

            assert downloader is not None
            assert downloader.PROVIDER == "garmin"
            MockAuth.assert_called_once()
            mock_auth_instance.get_client.assert_called()

    def test_from_config_returns_none_on_auth_failure(self, tmp_path):
        """Test from_config returns None when authentication fails."""
        config = GarminConfig(
            garmin_email="test@example.com",
            garmin_password="wrong_password",
            garmin_token_store=str(tmp_path / "tokens.json"),
            data_dir=str(tmp_path / "data"),
        )

        with patch("src.lib.garmin.downloader.GarminAuthenticator") as MockAuth:
            mock_auth_instance = MockAuth.return_value
            mock_auth_instance.get_client.return_value = None

            downloader = GarminDataDownloader.from_config(config)

            assert downloader is None


class TestGarminDataDownloaderProtocol:
    """Test that GarminDataDownloader implements DataProvider protocol."""

    def test_implements_data_provider_protocol(self, tmp_path):
        """Test GarminDataDownloader is a valid DataProvider."""
        config = GarminConfig(
            garmin_email="test@example.com",
            garmin_password="password123",
            garmin_token_store=str(tmp_path / "tokens.json"),
            data_dir=str(tmp_path / "data"),
        )

        with patch("src.lib.garmin.downloader.GarminAuthenticator") as MockAuth:
            mock_auth_instance = MockAuth.return_value
            mock_auth_instance.get_client.return_value = MagicMock()

            downloader = GarminDataDownloader.from_config(config)

            # Check Protocol requirements
            assert hasattr(downloader, "PROVIDER")
            assert hasattr(downloader, "download_all")
            assert callable(getattr(downloader, "download_all"))
            assert isinstance(downloader, DataProvider)


class TestGarminDataDownloaderDownloadAll:
    """Test download_all method returns DownloadResult."""

    @pytest.fixture
    def mock_downloader(self, tmp_path):
        """Create a mock-configured downloader."""
        config = GarminConfig(
            garmin_email="test@example.com",
            garmin_password="password123",
            garmin_token_store=str(tmp_path / "tokens.json"),
            data_dir=str(tmp_path / "data"),
            days_back=7,
            download_activities=True,
            download_health=True,
            download_devices=True,
            download_gear=True,
            activity_limit=10,
        )

        with patch("src.lib.garmin.downloader.GarminAuthenticator") as MockAuth:
            mock_auth_instance = MockAuth.return_value
            mock_api = MagicMock()
            mock_api.get_activities.return_value = []
            mock_api.get_device_alarms.return_value = None
            mock_api.get_devices.return_value = []
            mock_api.get_gear.return_value = []
            mock_api.get_heart_rates.return_value = {}
            mock_api.get_sleep_data.return_value = {}
            mock_api.get_hydration_data.return_value = {}
            mock_api.get_body_composition.return_value = {}
            mock_api.get_stress_data.return_value = {}
            mock_api.get_respiration_data.return_value = {}
            mock_api.get_stats.return_value = {}
            
            mock_auth_instance.get_client.return_value = mock_api

            return GarminDataDownloader.from_config(config)

    def test_download_all_returns_download_result(self, mock_downloader):
        """Test that download_all returns DownloadResult, not dict."""
        result = mock_downloader.download_all()

        # Check it's a DownloadResult by checking its attributes
        assert hasattr(result, 'provider')
        assert hasattr(result, 'success')
        assert hasattr(result, 'items_downloaded')
        assert result.provider == "garmin"
        assert result.success is True

    def test_download_all_result_has_items_downloaded(self, mock_downloader):
        """Test that result includes download item counts."""
        result = mock_downloader.download_all()

        assert result.items_downloaded is not None
        assert isinstance(result.items_downloaded, dict)
        # items_downloaded should include at least some keys
        assert "activities" in result.items_downloaded or "health_days" in result.items_downloaded

    def test_download_all_result_to_dict(self, mock_downloader):
        """Test that result can be converted to dict for backward compatibility."""
        result = mock_downloader.download_all()

        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert "provider" in result_dict
        assert "success" in result_dict
        assert result_dict["provider"] == "garmin"


class TestGarminDataDownloaderConfigFlags:
    """Test that config flags control what gets downloaded."""

    def test_download_activities_disabled(self, tmp_path):
        """Test activities are skipped when download_activities=False."""
        config = GarminConfig(
            garmin_email="test@example.com",
            garmin_password="password123",
            garmin_token_store=str(tmp_path / "tokens.json"),
            data_dir=str(tmp_path / "data"),
            download_activities=False,
            download_health=False,
            download_devices=False,
            download_gear=False,
        )

        with patch("src.lib.garmin.downloader.GarminAuthenticator") as MockAuth:
            mock_auth_instance = MockAuth.return_value
            mock_api = MagicMock()
            mock_auth_instance.get_client.return_value = mock_api

            downloader = GarminDataDownloader.from_config(config)
            result = downloader.download_all()

            # get_activities should not be called if download_activities=False
            mock_api.get_activities.assert_not_called()

    def test_activity_limit_respected(self, tmp_path):
        """Test activity_limit is passed to API."""
        config = GarminConfig(
            garmin_email="test@example.com",
            garmin_password="password123",
            garmin_token_store=str(tmp_path / "tokens.json"),
            data_dir=str(tmp_path / "data"),
            download_activities=True,
            download_health=False,
            download_devices=False,
            download_gear=False,
            activity_limit=50,
        )

        with patch("src.lib.garmin.downloader.GarminAuthenticator") as MockAuth:
            mock_auth_instance = MockAuth.return_value
            mock_api = MagicMock()
            mock_api.get_activities.return_value = []
            mock_auth_instance.get_client.return_value = mock_api

            downloader = GarminDataDownloader.from_config(config)
            downloader.download_all()

            # Verify activity_limit was used
            mock_api.get_activities.assert_called()
            call_args = mock_api.get_activities.call_args
            # Check limit parameter
            assert call_args[0][1] == 50 or call_args[1].get("limit") == 50


class TestGarminDataDownloaderSubdirs:
    """Test SUBDIRS constant is properly used."""

    def test_subdirs_created_on_init(self, tmp_path):
        """Test that SUBDIRS directories are created during initialization."""
        config = GarminConfig(
            garmin_email="test@example.com",
            garmin_password="password123",
            garmin_token_store=str(tmp_path / "tokens.json"),
            data_dir=str(tmp_path / "data"),
        )

        with patch("src.lib.garmin.downloader.GarminAuthenticator") as MockAuth:
            mock_auth_instance = MockAuth.return_value
            mock_auth_instance.get_client.return_value = MagicMock()

            downloader = GarminDataDownloader.from_config(config)

            # Check expected subdirectories exist
            data_dir = tmp_path / "data" / "garmin"
            expected_subdirs = ["activities", "health", "devices", "gear"]
            for subdir in expected_subdirs:
                assert (data_dir / subdir).exists(), f"Expected {subdir} directory to exist"
