"""Tests for main module - refactored architecture."""

import logging
import sys
from io import StringIO
from unittest.mock import Mock, MagicMock, patch

import pytest

from src.lib.providers.base import DownloadResult
from src.main import setup_logging, display_provider_result
from src.config import AppConfig


class TestSetupLogging:
    """Test setup_logging function."""

    def test_setup_logging_configures_root_logger(self, tmp_path):
        """Test that setup_logging configures the root logger."""
        config = AppConfig(data_dir=str(tmp_path), log_level="DEBUG")

        # Clear existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        setup_logging(config)

        assert root_logger.level == logging.DEBUG

    def test_setup_logging_respects_level(self, tmp_path):
        """Test that log level is set correctly."""
        config = AppConfig(data_dir=str(tmp_path), log_level="WARNING")

        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        setup_logging(config)

        assert root_logger.level == logging.WARNING

    def test_setup_logging_default_info(self, tmp_path):
        """Test default log level is INFO."""
        config = AppConfig(data_dir=str(tmp_path), log_level="INFO")

        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        setup_logging(config)

        assert root_logger.level == logging.INFO


class TestDisplayProviderResult:
    """Test display_provider_result function."""

    def test_display_successful_result(self, caplog):
        """Test displaying successful result."""
        logger = logging.getLogger("test")
        result = DownloadResult(
            provider="garmin",
            success=True,
            items_downloaded={"activities": 10, "health_days": 5},
            duration_seconds=2.5,
        )

        with caplog.at_level(logging.INFO):
            display_provider_result(logger, result)

        # Should log provider name
        assert any("GARMIN" in record.message for record in caplog.records)

    def test_display_failed_result(self, caplog):
        """Test displaying failed result."""
        logger = logging.getLogger("test")
        result = DownloadResult(
            provider="garmin",
            success=False,
            error="Authentication failed",
        )

        with caplog.at_level(logging.INFO):
            display_provider_result(logger, result)

        # Should show error info
        assert any("Authentication failed" in record.message for record in caplog.records)

    def test_display_result_with_items(self, caplog):
        """Test that items are displayed properly."""
        logger = logging.getLogger("test")
        result = DownloadResult(
            provider="garmin",
            success=True,
            items_downloaded={
                "activities": 50,
                "health_days": 30,
                "devices": 2,
                "gear": 5,
            },
        )

        with caplog.at_level(logging.INFO):
            display_provider_result(logger, result)

        # Items should be visible in log
        log_output = " ".join(record.message for record in caplog.records)
        assert "50" in log_output or "Activities" in log_output


class TestMainIntegration:
    """Integration tests for main module."""

    @patch("src.main.GarminDataDownloader")
    @patch("src.main.GarminConfig")
    @patch("src.main.AppConfig")
    @patch("src.main.DataProviderManager")
    def test_main_creates_provider_via_factory(
        self, mock_manager_class, mock_app_config_class, mock_garmin_config_class, mock_downloader_class
    ):
        """Test that main uses from_config factory method."""
        from src.main import main

        mock_app_config = Mock()
        mock_app_config.data_dir = "/tmp/data"
        mock_app_config.log_level = "INFO"
        mock_app_config.log_file = None
        mock_app_config_class.return_value = mock_app_config

        mock_garmin_config = Mock()
        mock_garmin_config_class.return_value = mock_garmin_config

        mock_downloader = Mock()
        mock_downloader.PROVIDER = "garmin"
        mock_downloader.download_all = Mock(return_value=DownloadResult(
            provider="garmin", success=True
        ))
        mock_downloader_class.from_config.return_value = mock_downloader

        mock_manager = Mock()
        mock_manager.download_all.return_value = {
            "garmin": DownloadResult(provider="garmin", success=True)
        }
        mock_manager.get_summary.return_value = {
            "total_providers": 1,
            "successful": 1,
            "failed": 0,
        }
        mock_manager_class.return_value = mock_manager

        with patch("src.main.setup_logging"):
            main()

        # Verify factory pattern was used
        mock_downloader_class.from_config.assert_called_once()

    @patch("src.main.GarminDataDownloader")
    @patch("src.main.GarminConfig")
    @patch("src.main.AppConfig")
    @patch("src.main.DataProviderManager")
    def test_main_registers_provider_without_manual_name(
        self, mock_manager_class, mock_app_config_class, mock_garmin_config_class, mock_downloader_class
    ):
        """Test that main registers provider without manually specifying name."""
        from src.main import main

        mock_app_config = Mock()
        mock_app_config.data_dir = "/tmp/data"
        mock_app_config.log_level = "INFO"
        mock_app_config.log_file = None
        mock_app_config_class.return_value = mock_app_config

        mock_garmin_config = Mock()
        mock_garmin_config_class.return_value = mock_garmin_config

        mock_downloader = Mock()
        mock_downloader.PROVIDER = "garmin"
        mock_downloader_class.from_config.return_value = mock_downloader

        mock_manager = Mock()
        mock_manager.download_all.return_value = {}
        mock_manager.get_summary.return_value = {
            "total_providers": 0,
            "successful": 0,
            "failed": 0,
        }
        mock_manager_class.return_value = mock_manager

        with patch("src.main.setup_logging"):
            main()

        # Verify register_provider was called with just the provider object
        mock_manager.register_provider.assert_called_once_with(mock_downloader)

    @patch("src.main.GarminDataDownloader")
    @patch("src.main.GarminConfig")
    @patch("src.main.AppConfig")
    @patch("src.main.DataProviderManager")
    def test_main_handles_auth_failure(
        self, mock_manager_class, mock_app_config_class, mock_garmin_config_class, mock_downloader_class
    ):
        """Test that main handles authentication failure gracefully."""
        from src.main import main

        mock_app_config = Mock()
        mock_app_config.data_dir = "/tmp/data"
        mock_app_config.log_level = "INFO"
        mock_app_config.log_file = None
        mock_app_config_class.return_value = mock_app_config

        mock_garmin_config = Mock()
        mock_garmin_config_class.return_value = mock_garmin_config

        # Factory returns None on auth failure
        mock_downloader_class.from_config.return_value = None

        mock_manager = Mock()
        mock_manager.download_all.return_value = {}
        mock_manager.get_summary.return_value = {
            "total_providers": 0,
            "successful": 0,
            "failed": 0,
        }
        mock_manager_class.return_value = mock_manager

        with patch("src.main.setup_logging"):
            # Should not crash
            main()

        # Should not try to register None provider
        mock_manager.register_provider.assert_not_called()
