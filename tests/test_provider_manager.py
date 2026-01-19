"""Tests for provider_manager module - refactored architecture."""

from pathlib import Path
from unittest.mock import Mock, MagicMock

import pytest

from src.lib.base import DownloadResult, DataProvider
from src.lib.provider_manager import DataProviderManager


class TestDataProviderManagerRegistration:
    """Test provider registration functionality."""

    def test_register_provider_extracts_name(self, tmp_path):
        """Test that register_provider automatically uses PROVIDER attribute."""
        manager = DataProviderManager(data_dir=tmp_path)
        
        # Create a mock that implements DataProvider protocol
        mock_provider = Mock(spec=DataProvider)
        mock_provider.PROVIDER = "test_provider"
        mock_provider.download_all = Mock(return_value=DownloadResult(
            provider="test_provider", success=True
        ))

        manager.register_provider(mock_provider)

        assert "test_provider" in manager.providers
        assert manager.providers["test_provider"] is mock_provider

    def test_register_multiple_providers(self, tmp_path):
        """Test registering multiple providers."""
        manager = DataProviderManager(data_dir=tmp_path)

        provider1 = Mock(spec=DataProvider)
        provider1.PROVIDER = "garmin"
        provider1.download_all = Mock()

        provider2 = Mock(spec=DataProvider)
        provider2.PROVIDER = "strava"
        provider2.download_all = Mock()

        manager.register_provider(provider1)
        manager.register_provider(provider2)

        assert len(manager.providers) == 2
        assert "garmin" in manager.providers
        assert "strava" in manager.providers

    def test_register_overwrites_existing_provider(self, tmp_path):
        """Test that registering same provider name overwrites."""
        manager = DataProviderManager(data_dir=tmp_path)

        provider1 = Mock(spec=DataProvider)
        provider1.PROVIDER = "garmin"
        provider1.download_all = Mock()

        provider2 = Mock(spec=DataProvider)
        provider2.PROVIDER = "garmin"
        provider2.download_all = Mock()

        manager.register_provider(provider1)
        manager.register_provider(provider2)

        assert len(manager.providers) == 1
        assert manager.providers["garmin"] is provider2


class TestDataProviderManagerDownload:
    """Test download_all functionality."""

    def test_download_all_returns_dict_of_download_results(self, tmp_path):
        """Test download_all returns dict[str, DownloadResult]."""
        manager = DataProviderManager(data_dir=tmp_path)

        mock_provider = Mock(spec=DataProvider)
        mock_provider.PROVIDER = "garmin"
        mock_result = DownloadResult(
            provider="garmin",
            success=True,
            items_downloaded={"activities": 10},
        )
        mock_provider.download_all = Mock(return_value=mock_result)

        manager.register_provider(mock_provider)
        results = manager.download_all()

        assert isinstance(results, dict)
        assert "garmin" in results
        assert isinstance(results["garmin"], DownloadResult)
        assert results["garmin"].success is True

    def test_download_all_handles_provider_exception(self, tmp_path):
        """Test download_all handles provider exceptions gracefully."""
        manager = DataProviderManager(data_dir=tmp_path)

        mock_provider = Mock(spec=DataProvider)
        mock_provider.PROVIDER = "failing_provider"
        mock_provider.download_all = Mock(side_effect=Exception("API Error"))

        manager.register_provider(mock_provider)
        results = manager.download_all()

        assert "failing_provider" in results
        result = results["failing_provider"]
        # Check it's a DownloadResult by checking attributes
        assert hasattr(result, 'provider')
        assert hasattr(result, 'success')
        assert hasattr(result, 'error')
        assert result.success is False
        assert "API Error" in result.error

    def test_download_all_empty_manager(self, tmp_path):
        """Test download_all with no registered providers."""
        manager = DataProviderManager(data_dir=tmp_path)

        results = manager.download_all()

        assert results == {}

    def test_download_all_multiple_providers_mixed_results(self, tmp_path):
        """Test download_all with multiple providers, some failing."""
        manager = DataProviderManager(data_dir=tmp_path)

        # Successful provider
        provider_success = Mock(spec=DataProvider)
        provider_success.PROVIDER = "garmin"
        provider_success.download_all = Mock(return_value=DownloadResult(
            provider="garmin", success=True, items_downloaded={"items": 5}
        ))

        # Failing provider
        provider_fail = Mock(spec=DataProvider)
        provider_fail.PROVIDER = "strava"
        provider_fail.download_all = Mock(side_effect=Exception("Connection failed"))

        manager.register_provider(provider_success)
        manager.register_provider(provider_fail)

        results = manager.download_all()

        assert len(results) == 2
        assert results["garmin"].success is True
        assert results["strava"].success is False


class TestDataProviderManagerSummary:
    """Test get_summary functionality."""

    def test_get_summary_counts_success_failure(self, tmp_path):
        """Test get_summary provides correct counts."""
        manager = DataProviderManager(data_dir=tmp_path)

        # Add some successful results
        provider1 = Mock(spec=DataProvider)
        provider1.PROVIDER = "provider1"
        provider1.download_all = Mock(return_value=DownloadResult(
            provider="provider1", success=True
        ))

        provider2 = Mock(spec=DataProvider)
        provider2.PROVIDER = "provider2"
        provider2.download_all = Mock(return_value=DownloadResult(
            provider="provider2", success=True
        ))

        provider3 = Mock(spec=DataProvider)
        provider3.PROVIDER = "provider3"
        provider3.download_all = Mock(side_effect=Exception("Failed"))

        manager.register_provider(provider1)
        manager.register_provider(provider2)
        manager.register_provider(provider3)

        results = manager.download_all()
        summary = manager.get_summary(results)

        assert summary["providers_total"] == 3
        assert summary["providers_successful"] == 2
        assert summary["providers_failed"] == 1

    def test_get_summary_empty_results(self, tmp_path):
        """Test get_summary with no results."""
        manager = DataProviderManager(data_dir=tmp_path)

        summary = manager.get_summary({})

        assert summary["providers_total"] == 0
        assert summary["providers_successful"] == 0
        assert summary["providers_failed"] == 0


class TestDataProviderManagerProtocolChecking:
    """Test that manager properly validates DataProvider protocol."""

    def test_accepts_protocol_compliant_object(self, tmp_path):
        """Test manager accepts objects implementing DataProvider protocol."""
        manager = DataProviderManager(data_dir=tmp_path)

        class MyProvider:
            PROVIDER = "my_provider"
            
            def download_all(self) -> DownloadResult:
                return DownloadResult(provider="my_provider", success=True)

        provider = MyProvider()
        manager.register_provider(provider)

        assert "my_provider" in manager.providers

    def test_manager_uses_provider_attribute(self, tmp_path):
        """Test manager uses PROVIDER attribute as key."""
        manager = DataProviderManager(data_dir=tmp_path)

        class CustomProvider:
            PROVIDER = "custom_name_123"
            
            def download_all(self) -> DownloadResult:
                return DownloadResult(provider=self.PROVIDER, success=True)

        provider = CustomProvider()
        manager.register_provider(provider)

        # Key should be from PROVIDER, not class name
        assert "custom_name_123" in manager.providers
        assert "CustomProvider" not in manager.providers
