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

    data_dir: Path = Field(
        default_factory=lambda: Path.cwd() / "data",
    )

    days_back: int = Field(default=30)
    log_level: str = Field(default="INFO")
    log_file: Path | None = Field(default=None)

    model_config = {
        "env_file": _env_file, 
        "case_sensitive": False, 
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # Ignore extra fields from subclasses
    }

    def __init__(self, **data):
        super().__init__(**data)
        if not self.data_dir or str(self.data_dir) == ".":
            self.data_dir = Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)


class BigQueryConfig(AppConfig):
    """Configuration for BigQuery uploads."""

    gcp_project_id: str = Field(default="")
    bq_dataset: str = Field(default="burnrate_dev")
    google_application_credentials: str = Field(default="")
    provider: str = Field(default="garmin")


class GarminConfig(AppConfig):
    """Configuration for Garmin API authentication and data storage."""

    garmin_email: str = Field(default="")
    garmin_password: str = Field(default="")
    token_store: str = Field(default="~/.garminconnect")
    download_activities: bool = Field(default=True)
    download_health: bool = Field(default=True)
    download_devices: bool = Field(default=True)
    download_gear: bool = Field(default=True)
    activity_limit: int = Field(default=100)


class CronometerConfig(AppConfig):
    """Configuration for Cronometer exports."""

    cronometer_email: str = Field(default="")
    cronometer_password: str = Field(default="")
