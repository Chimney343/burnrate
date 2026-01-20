"""Library package for data providers.

Provides base classes and utilities for multi-provider data downloading.
"""

from .bigquery import BaseUploader, GarminUploader, get_uploader
from .providers import BaseDataProvider, DataProvider, DataProviderManager, DownloadResult

__all__ = [
    "DataProvider",
    "BaseDataProvider",
    "DownloadResult",
    "DataProviderManager",
    "BaseUploader",
    "GarminUploader",
    "get_uploader",
]
