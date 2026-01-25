"""Garmin data downloader using python-garminconnect library."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING, TypeVar, Union

from garminconnect import Garmin, GarminConnectConnectionError
from garth.exc import GarthHTTPError, GarthException
from tqdm import tqdm

from ..base import BaseDataProvider, DownloadResult
from .auth import GarminAuthenticator

if TYPE_CHECKING:
    from config import GarminConfig

logger = logging.getLogger(__name__)


class GarminDownloaderException(Exception):
    """Base exception for download operations."""


class GarminDataDownloader(BaseDataProvider):
    """Gracefully downloads all user Garmin data using python-garminconnect."""

    PROVIDER = "garmin"
    SUBDIRS = ["activities", "health", "devices", "gear"]

    def __init__(
        self,
        api: Union[Garmin, GarminAuthenticator],
        data_dir: Path,
        days_back: int = 30,
        download_activities: bool = True,
        download_health: bool = True,
        download_devices: bool = True,
        download_gear: bool = True,
        activity_limit: int = 100,
    ):
        """Initialize downloader.

        Args:
            api: Authenticated Garmin API client OR GarminAuthenticator instance
            data_dir: Root data directory
            days_back: Days of history to download (0 = all)
            download_activities: Whether to download activities
            download_health: Whether to download health data
            download_devices: Whether to download device info
            download_gear: Whether to download gear data
            activity_limit: Number of activities per API request
        """
        super().__init__(data_dir)
        
        # Handle both raw API client or Authenticator class
        if hasattr(api, "get_client") and callable(api.get_client):
            self._auth = api
            self._api_client = None
        else:
            self._auth = None
            self._api_client = api
        
        self.days_back = days_back
        self.download_activities = download_activities
        self.download_health = download_health
        self.download_devices = download_devices
        self.download_gear = download_gear
        self.activity_limit = activity_limit

        # Set up subdirectory paths using SUBDIRS
        self.activities_dir = self.provider_dir / "activities"
        self.health_dir = self.provider_dir / "health"
        self.devices_dir = self.provider_dir / "devices"
        self.gear_dir = self.provider_dir / "gear"

    @property
    def api(self) -> Garmin:
        """Get the authenticated API client."""
        if self._auth:
            client = self._auth.get_client()
            if not client:
                raise GarminDownloaderException("Failed to retrieve authenticated client")
            return client
        
        if self._api_client:
            return self._api_client
            
        raise GarminDownloaderException("No API client or authenticator available")

    @classmethod
    def from_config(cls, config: GarminConfig) -> GarminDataDownloader | None:
        """Create a downloader instance from configuration.
        
        Handles authentication automatically.
        
        Args:
            config: GarminConfig with credentials and settings
            
        Returns:
            Configured GarminDataDownloader or None if auth fails
        """
        auth = GarminAuthenticator(
            email=config.garmin_email,
            password=config.garmin_password,
            token_store=config.token_store,
        )
        
        if not auth.get_client():
            logger.error("Failed to authenticate with Garmin")
            return None
            
        return cls(
            api=auth,
            data_dir=config.data_dir,
            days_back=config.days_back,
            download_activities=config.download_activities,
            download_health=config.download_health,
            download_devices=config.download_devices,
            download_gear=config.download_gear,
            activity_limit=config.activity_limit,
        )

    def download_all(self) -> DownloadResult:
        """Download all available Garmin data.

        Returns:
            DownloadResult with statistics
        """
        result = self._create_result()
        result.start_time = datetime.now()

        try:
            logger.info("Starting comprehensive Garmin data download...")

            # Initialize counters in result
            result.items_downloaded = {
                "activities": 0,
                "health_days": 0,
                "devices": 0,
                "gear": 0
            }
            result.items_cached = {
                "health_days": 0
            }

            # Download user profile info (always)
            self._download_user_profile(result)

            # Download based on config flags
            if self.download_activities:
                self._download_activities(result)

            if self.download_health:
                self._download_health_data(result)

            if self.download_devices:
                self._download_devices(result)

            if self.download_gear:
                self._download_gear(result)

            result.success = True
            logger.info("Garmin download completed successfully")

        except Exception as e:
            logger.error(f"Garmin download failed: {e}")
            result.success = False
            result.error = str(e)
            result.warnings.append(f"Critical failure: {e}")
            # We explicitly RETURN the result instead of raising,
            # so the manager can report partial success

        finally:
            result.end_time = datetime.now()
            result.duration_seconds = (
                result.end_time - result.start_time
            ).total_seconds()

            logger.info(f"Download duration: {result.duration_seconds:.1f}s")
            logger.info(f"Activities: {result.items_downloaded.get('activities', 0)}")
            logger.info(f"Health days: {result.items_downloaded.get('health_days', 0)}")
            
            if result.warnings:
                logger.warning(f"Encountered {len(result.warnings)} warnings")

        return result

    def _download_user_profile(self, result: DownloadResult) -> None:
        """Download user profile information."""
        logger.info("Downloading user profile...")

        try:
            profile_file = self.provider_dir / "profile.json"

            # Get user profile
            profile = self.api.get_user_profile()
            self._save_json(profile_file, profile)

            # Get unit system
            unit_system = self.api.get_unit_system()
            self._save_json(self.provider_dir / "unit_system.json", unit_system)

            # Get full name
            full_name = self.api.get_full_name()
            self._save_json(self.provider_dir / "user_info.json", {"full_name": full_name})

            logger.info("User profile downloaded")

        except (GarthHTTPError, GarthException, GarminConnectConnectionError) as e:
            error_msg = f"Failed to download user profile: {e}"
            logger.warning(error_msg)
            result.warnings.append(error_msg)

    def _download_activities(self, result: DownloadResult) -> None:
        """Download all activities."""
        logger.info("Downloading activities...")

        try:
            all_activities = []
            start_index = 0
            batch_size = self.activity_limit

            while True:
                try:
                    logger.debug(f"Fetching activities from index {start_index}...")

                    activities = self.api.get_activities(start_index, batch_size)

                    if not activities:
                        logger.info("No more activities to fetch")
                        break

                    all_activities.extend(activities)
                    logger.info(f"Downloaded {len(all_activities)} activities so far...")

                    if len(activities) < batch_size:
                        break

                    start_index += batch_size

                except (GarthHTTPError, GarthException) as e:
                    error_msg = f"Failed to fetch activities batch at index {start_index}: {e}"
                    logger.warning(error_msg)
                    result.warnings.append(error_msg)
                    break

            # Save activities summary
            if all_activities:
                self._save_json(self.activities_dir / "all_activities.json", all_activities)
                result.items_downloaded["activities"] = len(all_activities)

                # Download detailed data for recent activities
                self._download_activity_details(all_activities[:10])

                logger.info(f"Downloaded {len(all_activities)} activities")

        except Exception as e:
            error_msg = f"Activity download failed: {e}"
            logger.error(error_msg)
            result.warnings.append(error_msg)

    def _download_activity_details(self, activities: list[dict[str, Any]]) -> None:
        """Download detailed information for activities."""
        logger.info(f"Downloading details for {len(activities)} activities...")

        for activity in activities:
            try:
                activity_id = activity.get("activityId")
                if not activity_id:
                    continue

                logger.debug(f"Fetching details for activity {activity_id}...")
                details = self.api.get_activity_details(activity_id)
                details_file = self.activities_dir / f"activity_{activity_id}_details.json"
                self._save_json(details_file, details)

            except (GarthHTTPError, GarthException) as e:
                logger.debug(f"Failed to download activity details for {activity_id}: {e}")

    def _find_earliest_health_date(self) -> datetime.date:
        """Find the earliest date when user has data by checking activities."""
        logger.info("Finding earliest data date...")
        
        try:
            all_activities = []
            start_index = 0
            batch_size = 100
            
            while True:
                activities = self.api.get_activities(start_index, batch_size)
                if not activities:
                    break
                all_activities.extend(activities)
                if len(activities) < batch_size:
                    break
                start_index += batch_size
            
            if all_activities:
                oldest_activity = all_activities[-1]
                if "startTimeLocal" in oldest_activity:
                    date_str = oldest_activity["startTimeLocal"]
                    earliest_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").date()
                    logger.info(f"Earliest activity found: {earliest_date}")
                    return earliest_date
        except Exception as e:
            logger.warning(f"Could not find earliest activity: {e}")
        
        fallback_date = datetime.now().date() - timedelta(days=30)
        logger.info(f"Using fallback date: {fallback_date}")
        return fallback_date

    def _download_health_data(self, result: DownloadResult) -> None:
        """Download health metrics for the past N days (or all if days_back=0)."""
        if self.days_back == 0:
            logger.info("Downloading ALL health data from account...")
            start_date = self._find_earliest_health_date()
            end_date = datetime.now().date()
            days_to_check = (end_date - start_date).days
        else:
            logger.info(f"Downloading health data for last {self.days_back} days...")
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=self.days_back)
            days_to_check = self.days_back

        health_summary = {}

        try:
            logger.info(f"Date range: {start_date} to {end_date} ({days_to_check} days total)")
            
            pbar = tqdm(range(days_to_check), desc="Health Data", unit="day")
            for i in pbar:
                current_date = start_date + timedelta(days=i)
                date_str = current_date.isoformat()

                if not date_str or date_str == "None":
                    continue

                try:
                    daily_file = self.health_dir / f"health_{date_str}.json"
                    if daily_file.exists():
                        logger.debug(f"[CACHED] {date_str}")
                        health_summary[date_str] = {"cached": True}
                        result.items_downloaded["health_days"] += 1
                        result.items_cached["health_days"] += 1
                        continue

                    logger.debug(f"Fetching health data for {date_str}...")

                    stats = self._safe_api_call(lambda: self.api.get_stats(date_str))
                    heart_rate = self._safe_api_call(lambda: self.api.get_heart_rates(date_str))
                    body_composition = self._safe_api_call(
                        lambda: self.api.get_body_composition(date_str, date_str)
                    )

                    if stats or heart_rate or body_composition:
                        daily_health = {
                            "date": date_str,
                            "stats": stats,
                            "heart_rate": heart_rate,
                            "body_composition": body_composition,
                        }
                        self._save_json(daily_file, daily_health)

                        health_summary[date_str] = {
                            "has_stats": bool(stats),
                            "has_heart_rate": bool(heart_rate),
                            "has_body_composition": bool(body_composition),
                        }
                        result.items_downloaded["health_days"] += 1

                except (GarthHTTPError, GarthException) as e:
                    logger.debug(f"Failed to download health data for {date_str}: {e}")

            self._save_json(self.health_dir / "health_summary.json", health_summary)
            cached = result.items_cached.get("health_days", 0)
            total = result.items_downloaded.get("health_days", 0)
            new = total - cached
            logger.info(f"Downloaded health data: {total} days ({new} new, {cached} cached)")

        except Exception as e:
            error_msg = f"Health data download failed: {e}"
            logger.error(error_msg)
            result.warnings.append(error_msg)

    def _download_devices(self, result: DownloadResult) -> None:
        """Download device information."""
        logger.info("Downloading device information...")

        try:
            devices = self.api.get_devices()
            if devices:
                self._save_json(self.devices_dir / "devices.json", devices)
                count = len(devices) if isinstance(devices, list) else 1
                result.items_downloaded["devices"] = count
                logger.info(f"Downloaded {count} device(s)")

            last_used = self._safe_api_call(lambda: self.api.get_device_last_used())
            if last_used:
                self._save_json(self.devices_dir / "device_last_used.json", last_used)

        except (GarthHTTPError, GarthException, GarminConnectConnectionError) as e:
            error_msg = f"Failed to download device information: {e}"
            logger.warning(error_msg)
            result.warnings.append(error_msg)

    def _download_gear(self, result: DownloadResult) -> None:
        """Download gear/equipment information."""
        logger.info("Downloading gear information...")

        try:
            device_info = self._safe_api_call(lambda: self.api.get_device_last_used())
            if not device_info:
                logger.debug("Could not get user profile number for gear")
                return

            user_profile_number = device_info.get("userProfileNumber")
            if not user_profile_number:
                logger.debug("User profile number not available")
                return

            gear_list = self._safe_api_call(lambda: self.api.get_gear(user_profile_number))
            if gear_list:
                self._save_json(self.gear_dir / "gear_list.json", gear_list)
                count = len(gear_list) if isinstance(gear_list, list) else 1
                result.items_downloaded["gear"] = count
                logger.info(f"Downloaded {count} gear item(s)")

        except Exception as e:
            logger.warning(f"Gear download failed: {e}")

    _T = TypeVar("_T")

    @staticmethod
    def _safe_api_call(func: Callable[[], _T]) -> _T | None:
        """Execute API call, log and return None on failure."""
        try:
            return func()
        except Exception as e:
            logger.debug(f"API call failed: {e}")
            return None

    @staticmethod
    def _save_json(file_path: Path, data: Any) -> None:
        """Save data to JSON file with UTF-8 encoding."""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str, ensure_ascii=False)
        except OSError as e:
            logger.error(f"Failed to save to {file_path}: {e}")
