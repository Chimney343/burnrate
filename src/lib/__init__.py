"""Library package for data providers.

Provides base classes and utilities for multi-provider data downloading.
"""

from .base import DataProvider, BaseDataProvider, DownloadResult
from .bq_uploader import BigQueryUploader
from .provider_manager import DataProviderManager

__all__ = [
    "DataProvider",
    "BaseDataProvider",
    "DownloadResult",
    "DataProviderManager",
    "BigQueryUploader",
]
