"""Upload local provider data to BigQuery.

Usage:
    python upload_to_bq.py                    # Upload with defaults from .env
    python upload_to_bq.py --dataset burnrate_prod  # Override dataset
    python upload_to_bq.py --provider strava  # Upload different provider
"""

import argparse
import logging
import sys

from config import BigQueryConfig
from lib.bigquery import BigQueryUploader


logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload provider data to BigQuery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--project",
        dest="gcp_project_id",
        help="GCP project ID (overrides GCP_PROJECT_ID env var)",
    )
    parser.add_argument(
        "--dataset",
        dest="bq_dataset",
        help="BigQuery dataset name (default: burnrate_dev)",
    )
    parser.add_argument(
        "--provider",
        help="Provider to upload (default: garmin)",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(args.log_level)

    overrides = {}
    if args.gcp_project_id:
        overrides["gcp_project_id"] = args.gcp_project_id
    if args.bq_dataset:
        overrides["bq_dataset"] = args.bq_dataset
    if args.provider:
        overrides["provider"] = args.provider

    config = BigQueryConfig(**overrides)

    logger.info("=" * 70)
    logger.info("BigQuery Uploader")
    logger.info("=" * 70)
    logger.info("Project: %s", config.gcp_project_id)
    logger.info("Dataset: %s", config.bq_dataset)
    logger.info("Provider: %s", config.provider)
    logger.info("Data dir: %s", config.data_dir)
    logger.info("")

    if not config.gcp_project_id:
        logger.error("GCP_PROJECT_ID is required. Set it in .env or pass --project")
        return 1

    try:
        uploader = BigQueryUploader.from_config(config)
        results = uploader.upload_all()
    except Exception as e:
        logger.error("Upload failed: %s", e)
        return 1

    logger.info("")
    logger.info("=" * 70)
    logger.info("Upload Complete")
    logger.info("=" * 70)

    total_rows = 0
    for table, count in results.items():
        if count > 0:
            logger.info("  %s: %d rows", table, count)
            total_rows += count

    logger.info("")
    logger.info("Total: %d rows uploaded to %s tables", total_rows, len([c for c in results.values() if c > 0]))

    return 0


if __name__ == "__main__":
    sys.exit(main())
