"""Tests for base module classes and protocols."""

import pytest
from datetime import datetime
from pathlib import Path
from src.lib.base import DownloadResult, DataProvider, BaseDataProvider


class TestDownloadResult:
    """Test suite for DownloadResult dataclass."""

    def test_default_values(self):
        """Test DownloadResult has correct defaults."""
        result = DownloadResult(provider="test")
        
        assert result.provider == "test"
        assert result.success is True
        assert result.error is None
        assert result.duration_seconds == 0.0
        assert result.items_downloaded == {}
        assert result.items_cached == {}
        assert result.warnings == []
        assert result.data_dir == ""

    def test_to_dict_basic(self):
        """Test to_dict conversion with basic data."""
        result = DownloadResult(
            provider="garmin",
            success=True,
            duration_seconds=5.5,
            data_dir="/tmp/data",
        )
        
        d = result.to_dict()
        
        assert d["provider"] == "garmin"
        assert d["success"] is True
        assert d["duration_seconds"] == 5.5
        assert d["data_dir"] == "/tmp/data"

    def test_to_dict_with_items(self):
        """Test to_dict includes items_downloaded counts."""
        result = DownloadResult(
            provider="garmin",
            items_downloaded={"activities": 100, "health_days": 30},
            items_cached={"health_days": 25},
        )
        
        d = result.to_dict()
        
        assert d["activities"] == 100
        assert d["health_days"] == 30
        assert d["health_days_cached"] == 25

    def test_to_dict_with_error(self):
        """Test to_dict includes error when present."""
        result = DownloadResult(
            provider="garmin",
            success=False,
            error="Connection failed",
        )
        
        d = result.to_dict()
        
        assert d["success"] is False
        assert d["error"] == "Connection failed"


class TestDataProviderProtocol:
    """Test suite for DataProvider protocol."""

    def test_protocol_check_valid(self):
        """Test that classes with PROVIDER and download_all are valid."""
        class ValidProvider:
            PROVIDER = "test"
            def download_all(self) -> DownloadResult:
                return DownloadResult(provider=self.PROVIDER)
        
        provider = ValidProvider()
        assert isinstance(provider, DataProvider)

    def test_protocol_check_missing_provider(self):
        """Test that classes without PROVIDER fail protocol check."""
        class InvalidProvider:
            def download_all(self) -> DownloadResult:
                return DownloadResult(provider="test")
        
        provider = InvalidProvider()
        # Should not be instance of DataProvider
        assert not isinstance(provider, DataProvider)


class TestBaseDataProvider:
    """Test suite for BaseDataProvider abstract class."""

    def test_directory_creation(self, tmp_path):
        """Test that provider creates directory structure."""
        class TestProvider(BaseDataProvider):
            PROVIDER = "test_provider"
            SUBDIRS = ["subdir1", "subdir2"]
            
            def download_all(self) -> DownloadResult:
                return self._create_result()
        
        provider = TestProvider(data_dir=tmp_path)
        
        assert provider.provider_dir == tmp_path / "test_provider"
        assert provider.provider_dir.exists()
        assert (tmp_path / "test_provider" / "subdir1").exists()
        assert (tmp_path / "test_provider" / "subdir2").exists()

    def test_create_result(self, tmp_path):
        """Test _create_result helper method."""
        class TestProvider(BaseDataProvider):
            PROVIDER = "my_provider"
            SUBDIRS = []
            
            def download_all(self) -> DownloadResult:
                return self._create_result()
        
        provider = TestProvider(data_dir=tmp_path)
        result = provider.download_all()
        
        assert result.provider == "my_provider"
        assert result.success is True
        assert result.data_dir == str(tmp_path)
