"""Garmin data provider module.

Provides authentication and data downloading for Garmin Connect.
"""

from .auth import authenticate_garmin
from .downloader import GarminDataDownloader, GarminDownloaderException

__all__ = [
    "authenticate_garmin",
    "GarminDataDownloader",
    "GarminDownloaderException",
]
