# Copilot Instructions for Burnrate Project

## Progress Bars

For all loops that process multiple items (batches, date ranges, lists), use `tqdm` to display progress:

### Installation
`tqdm` is already included in dependencies in `pyproject.toml`.

### Usage Pattern

```python
from tqdm import tqdm

# For simple loops
for item in tqdm(items, desc="Processing", unit="item"):
    # process item
    pass

# For numbered loops
for i in tqdm(range(1000), desc="Scanning", unit="day"):
    # process i
    pass

# For writing messages during progress
tqdm.write(f"[CACHED] {date_str}")  # Preserves progress bar
```

### Examples in Codebase

1. **Health Data Download** - `src/lib/garmin_downloader.py`
   - Shows date ranges and caching status
   - Format: `Health Data: 245/948 [26%, 00:45<02:15, 5.43day/s]`

2. **Activity Details Download** - `src/lib/garmin_downloader.py`
   - Shows activity details fetching progress
   - Format: `Activity Details: 10/10 [100%, 00:05<00:00, 2.00activity/s]`

## Logging Guidelines

- Use `logger.info()` for high-level progress (start/end of major operations)
- Use `logger.debug()` for detailed per-item information
- Use `tqdm.write()` when you need to log during a progress bar loop to avoid corrupting the display

## Date Range Handling

For health data downloads:
- If `days_back=0`: Download from earliest activity date to today
- If `days_back=N`: Download last N days
- Always check if files exist before downloading (skip cached data)
- Log the date range at the start: `Date range: {start_date} to {end_date} ({days_to_check} days total)`

## Polish Character Support

- All JSON files use `ensure_ascii=False` to preserve Polish characters (ó, ą, ę, etc.)
- Config uses `env_file_encoding: utf-8`
- Console output uses UTF-8 encoding
