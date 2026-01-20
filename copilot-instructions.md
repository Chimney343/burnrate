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

## Avoiding AI Slop Patterns

When generating or reviewing code, avoid these common AI-generated code smells:

### Do NOT use emojis in logs
```python
# BAD
logger.info("✓ Successfully authenticated")
logger.info("📊 Starting download")

# GOOD
logger.info("Authenticated")
logger.info("Starting download")
```

### Do NOT add numbered step comments
```python
# BAD
# 1. Try to load from stored tokens first
# 2. If no stored tokens, try with credentials
# 3. Handle MFA if required

# GOOD - let the code speak for itself, or use a docstring
```

### Do NOT add trivial docstrings
```python
# BAD
def _setup_directories(self) -> None:
    """Create provider directory structure."""
    self.provider_dir.mkdir(parents=True, exist_ok=True)

# GOOD - method name is self-explanatory
def _setup_directories(self) -> None:
    self.provider_dir.mkdir(parents=True, exist_ok=True)
```

### Do NOT silently swallow exceptions
```python
# BAD
except Exception:
    return None

# GOOD
except Exception as e:
    logger.debug(f"API call failed: {e}")
    return None
```

### Use correct log levels
```python
# BAD - hiding failures in debug
logger.debug(f"Gear download failed: {e}")

# GOOD - failures should be warnings
logger.warning(f"Gear download failed: {e}")
```

### Avoid over-verbose messages
```python
# BAD
logger.error("Garmin credentials not found in configuration")
logger.error("Please set GARMIN_EMAIL and GARMIN_PASSWORD in .env file")

# GOOD
logger.error("Garmin credentials not found - set GARMIN_EMAIL and GARMIN_PASSWORD")
```

### YAGNI - Don't abstract prematurely
- Don't create base classes until you have 2+ implementations
- Don't add "future-proofing" parameters nobody uses
- Delete commented-out code instead of keeping "just in case"

