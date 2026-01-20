"""Base classes and protocols for data providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass
class DownloadResult:
    """Standardized result from a provider download operation.
    
    Each provider populates the fields relevant to their data types.
    """
    provider: str
    success: bool = True
    error: str | None = None
    
    # Timing
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_seconds: float = 0.0
    
    # Generic counts - providers use what's relevant
    items_downloaded: dict[str, int] = field(default_factory=dict)
    items_cached: dict[str, int] = field(default_factory=dict)
    
    # Errors/warnings encountered during download
    warnings: list[str] = field(default_factory=list)
    
    # Where data was saved
    data_dir: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        result = {
            "provider": self.provider,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "data_dir": self.data_dir,
            "errors": self.warnings,  # backward compat
        }
        
        # Add all item counts directly
        result.update(self.items_downloaded)
        
        # Add cached counts with suffix
        for key, value in self.items_cached.items():
            result[f"{key}_cached"] = value
            
        if self.error:
            result["error"] = self.error
            
        return result


@runtime_checkable
class DataProvider(Protocol):
    """Protocol defining the interface for all data providers.
    
    Any class implementing this protocol can be registered with DataProviderManager.
    """
    
    PROVIDER: str  # Unique provider identifier (e.g., 'garmin', 'strava')
    
    def download_all(self) -> DownloadResult:
        """Download all available data from this provider.
        
        Returns:
            DownloadResult with statistics and status
        """
        ...


class BaseDataProvider(ABC):
    """Abstract base class for data providers with common functionality.
    
    Providers can inherit from this for shared utilities, or just implement
    the DataProvider protocol directly.
    """
    
    PROVIDER: str = "base"
    SUBDIRS: list[str] = []
    
    def __init__(self, data_dir: Path):
        """Initialize provider with data directory.
        
        Args:
            data_dir: Root data directory (provider creates subdirectory)
        """
        self.data_dir = Path(data_dir)
        self.provider_dir = self.data_dir / self.PROVIDER
        
        # Create provider directory and subdirectories
        self._setup_directories()
        
    def _setup_directories(self) -> None:
        """Create provider directory structure."""
        self.provider_dir.mkdir(parents=True, exist_ok=True)
        for subdir in self.SUBDIRS:
            (self.provider_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    @abstractmethod
    def download_all(self) -> DownloadResult:
        """Download all available data. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement download_all()")
    
    def _create_result(self, success: bool = True) -> DownloadResult:
        """Create a new DownloadResult pre-populated with provider info."""
        return DownloadResult(
            provider=self.PROVIDER,
            success=success,
            data_dir=str(self.data_dir),
        )
