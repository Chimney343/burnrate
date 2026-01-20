"""Main CLI entry point for multi-provider data downloader."""

import logging
import sys

from config import AppConfig, GarminConfig
from lib.providers import DownloadResult
from lib.providers.garmin import GarminDataDownloader
from lib.providers import DataProviderManager


def setup_logging(config: AppConfig) -> None:
    """Configure logging based on settings.

    Args:
        config: Application configuration
    """
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler with UTF-8 encoding
    console_handler = logging.StreamHandler(sys.stdout)
    if hasattr(console_handler.stream, "reconfigure"):
        console_handler.stream.reconfigure(encoding="utf-8")
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # File handler (if configured)
    file_handler = None
    if config.log_file:
        config.log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(config.log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)

    if file_handler:
        root_logger.addHandler(file_handler)

    # Suppress noisy library logging
    logging.getLogger("garminconnect").setLevel(logging.WARNING)


def display_provider_result(logger: logging.Logger, result: DownloadResult) -> None:
    """Display formatted result for a single provider.
    
    Args:
        logger: Logger instance
        result: DownloadResult from provider
    """
    logger.info(f"\n{result.provider.upper()}:")
    
    if not result.success:
        logger.info(f"  Error: {result.error}")
        return
    
    # Display downloaded items
    for item_type, count in result.items_downloaded.items():
        cached = result.items_cached.get(item_type, 0)
        new = count - cached
        
        if cached > 0:
            logger.info(f"  {item_type.replace('_', ' ').title()}: {count} ({new} new, {cached} cached)")
        else:
            logger.info(f"  {item_type.replace('_', ' ').title()}: {count}")
    
    # Display warnings if any
    if result.warnings:
        logger.info(f"  Warnings: {len(result.warnings)}")
        for warning in result.warnings[:3]:
            logger.info(f"    - {warning}")
    
    logger.info(f"  Duration: {result.duration_seconds:.1f}s")


def main() -> int:
    """Run the multi-provider data downloader.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = logging.getLogger(__name__)

    try:
        # Load configuration first, then setup logging
        config = GarminConfig()
        setup_logging(config)
        
        logger.info("Configuration loaded.")

        logger.info("=" * 70)
        logger.info("Multi-Provider Data Downloader")
        logger.info("=" * 70)
        logger.info(f"Data directory: {config.data_dir}")

        # Initialize provider manager
        provider_manager = DataProviderManager(data_dir=config.data_dir)

        # Setup Garmin provider using factory method
        logger.info("\nSetting up Garmin provider...")
        garmin_downloader = GarminDataDownloader.from_config(config)
        
        if not garmin_downloader:
            logger.error("Failed to initialize Garmin provider")
            return 1
            
        provider_manager.register_provider(garmin_downloader)

        # TODO: Add more providers here
        # strava_downloader = StravaDataDownloader.from_config(strava_config)
        # provider_manager.register_provider(strava_downloader)

        # Execute downloads
        logger.info("\nStarting multi-provider download...")
        results = provider_manager.download_all()

        # Display results
        logger.info("\n" + "=" * 70)
        logger.info("DOWNLOAD SUMMARY")
        logger.info("=" * 70)

        for result in results.values():
            display_provider_result(logger, result)

        # Overall summary
        summary = provider_manager.get_summary(results)
        logger.info("\n" + "-" * 70)
        logger.info(f"Providers: {summary['providers_successful']}/{summary['providers_total']} successful")
        logger.info(f"Total duration: {summary['total_duration_seconds']:.1f}s")
        logger.info(f"Data saved to: {summary['data_dir']}")
        logger.info("=" * 70)

        # Return error if any provider failed
        return 0 if summary['providers_failed'] == 0 else 1

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
