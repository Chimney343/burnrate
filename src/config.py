"""Configuration management for multi-provider data downloader."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


# Find .env file in project root or current directory
_env_file_path = Path(__file__).parent.parent / ".env"
if _env_file_path.exists():
    _env_file = str(_env_file_path)
else:
    _env_file = ".env"


class AppConfig(BaseSettings):
    """Base application configuration shared across all providers."""

    # Data storage paths
    data_dir: Path = Field(
        default_factory=lambda: Path.cwd() / "data",
        description="Root directory to store all downloaded data"
    )

    # Download settings
    days_back: int = Field(
        default=30, 
        description="Days of history to download (use 0 for ALL data)"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Path | None = Field(default=None, description="Log file path")

    model_config = {
        "env_file": _env_file, 
        "case_sensitive": False, 
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # Ignore extra fields from subclasses
    }

    def __init__(self, **data):
        """Initialize config and ensure data directories exist."""
        super().__init__(**data)
        # If data_dir is empty or current dir, use default
        if not self.data_dir or str(self.data_dir) == ".":
            self.data_dir = Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)


class GarminConfig(AppConfig):
    """Configuration for Garmin API authentication and data storage."""

    # Garmin API credentials
    garmin_email: str = Field(default="", description="Garmin account email")
    garmin_password: str = Field(default="", description="Garmin account password")

    # Token storage
    token_store: str = Field(
        default="~/.garminconnect",
        description="Path to store Garmin authentication tokens"
    )

    # Garmin-specific download settings
    download_activities: bool = Field(default=True, description="Download activities")
    download_health: bool = Field(default=True, description="Download health metrics")
    download_devices: bool = Field(default=True, description="Download device info")
    download_gear: bool = Field(default=True, description="Download gear/equipment")
    activity_limit: int = Field(default=100, description="Activities per API request")
