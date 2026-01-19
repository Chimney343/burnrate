# Burnrate - Garmin Data Downloader

Download and backup all your Garmin Connect data locally.

## Features

- Downloads activities, health data, devices, and gear from Garmin Connect
- Supports OAuth authentication with MFA
- Caches downloaded data to avoid redundant requests
- Polish character support (UTF-8)
- Multi-provider architecture for extensibility
- Comprehensive progress tracking and logging

## Setup

```bash
poetry install
```

## Configuration

Create a `.env` file in the project root:

```env
GARMIN_EMAIL=your.email@example.com
GARMIN_PASSWORD=your_password
DATA_DIR=./data
DAYS_BACK=30
LOG_LEVEL=INFO
```

## Running

```bash
poetry run python src/main.py
```

## Commands

See `justfile` for available commands:

```bash
just download          # Download 30 days of data
just download-all      # Download all historical data
just download-debug    # Download with debug logging
```

## Testing

```bash
poetry run pytest
poetry run pytest --cov=src
```

## Architecture

- **src/lib/garmin/** - Garmin provider implementation
- **src/lib/provider_manager.py** - Multi-provider orchestration
- **src/main.py** - CLI entry point
- **src/config.py** - Configuration management
