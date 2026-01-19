"""Multi-provider data download orchestrator."""

import logging
from pathlib import Path
from typing import Any

from lib.base import DataProvider, DownloadResult

logger = logging.getLogger(__name__)


class DataProviderManager:
    """Manages multiple data providers and orchestrates downloads.

    Each provider must implement the DataProvider protocol with:
    - PROVIDER: str attribute
    - download_all() -> DownloadResult method
    """

    def __init__(self, data_dir: Path):
        """Initialize the provider manager.

        Args:
            data_dir: Root directory for all provider data
        """
        self.data_dir = Path(data_dir)
        self._providers: dict[str, DataProvider] = {}

    def register_provider(self, provider: DataProvider) -> None:
        """Register a data provider.

        Args:
            provider: Provider instance implementing DataProvider protocol
        """
        if not isinstance(provider, DataProvider):
            raise TypeError(
                f"Provider must implement DataProvider protocol. "
                f"Got {type(provider).__name__}"
            )
        
        provider_name = provider.PROVIDER
        self._providers[provider_name] = provider
        logger.debug(f"Registered provider: {provider_name}")

    @property
    def providers(self) -> dict[str, DataProvider]:
        """Get registered providers."""
        return self._providers

    def download_all(self) -> dict[str, DownloadResult]:
        """Execute downloads for all registered providers.

        Returns:
            Dictionary mapping provider names to their DownloadResult
        """
        if not self._providers:
            logger.warning("No providers registered")
            return {}

        results: dict[str, DownloadResult] = {}

        for provider_name, provider in self._providers.items():
            try:
                result = provider.download_all()
                results[provider_name] = result

            except Exception as e:
                logger.error(f"Provider {provider_name} failed: {e}")
                # Create error result
                results[provider_name] = DownloadResult(
                    provider=provider_name,
                    success=False,
                    error=str(e),
                )

        return results

    def get_summary(self, results: dict[str, DownloadResult]) -> dict[str, Any]:
        """Get aggregated summary across all providers.

        Args:
            results: Dictionary of DownloadResult from download_all()

        Returns:
            Summary statistics
        """
        total_duration = sum(
            r.duration_seconds for r in results.values() if r.success
        )
        successful = sum(1 for r in results.values() if r.success)
        failed = sum(1 for r in results.values() if not r.success)

        return {
            "providers_total": len(results),
            "providers_successful": successful,
            "providers_failed": failed,
            "total_duration_seconds": total_duration,
            "data_dir": str(self.data_dir),
        }