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
- **CRITICAL**: Do not use `logger.info()` or `print()` inside a `tqdm` loop. It causes the progress bar to duplicate on each update. If you must output text, use `tqdm.write("message")` or downgrade to `logger.debug()`.

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

## Pythonic Patterns Used in This Codebase

These patterns are already established in `src/` and should be followed for consistency:

### Type Hints
Use modern union syntax and generic types:
```python
# GOOD
def get_client(self, force_refresh: bool = False) -> Garmin | None:
    ...

def _prepare_rows(self, files: list[Path]) -> list[dict[str, Any]]:
    ...
```

### Dataclasses for Data Containers
Use `@dataclass` for structured data with automatic `__init__`, `__repr__`, etc.:
```python
@dataclass
class DownloadResult:
    provider: str
    success: bool = True
    items_downloaded: dict[str, int] = field(default_factory=dict)
```

### Protocols for Duck Typing
Use `Protocol` from `typing` when you want structural subtyping (duck typing with type safety):
```python
@runtime_checkable
class DataProvider(Protocol):
    PROVIDER: str
    def download_all(self) -> DownloadResult: ...
```

### Factory Methods with `from_config()`
Use `@classmethod` factory methods to create instances from configuration:
```python
@classmethod
def from_config(cls, config: GarminConfig) -> GarminDataDownloader | None:
    auth = GarminAuthenticator(...)
    if not auth.get_client():
        return None
    return cls(api=auth, data_dir=config.data_dir, ...)
```

### Factory Functions for Polymorphism
Use factory functions when the return type depends on input:
```python
def get_uploader(config: BigQueryConfig) -> BaseUploader:
    if config.provider == "garmin":
        return GarminUploader(...)
    raise ValueError(f"No uploader for: {config.provider}")
```

### Pathlib Over Strings
Always use `pathlib.Path` for file system operations:
```python
from pathlib import Path

self.provider_dir = data_dir / "garmin"  # NOT: os.path.join(data_dir, "garmin")
self.provider_dir.mkdir(parents=True, exist_ok=True)
```

### Module-Level Logger
Define logger at module level, not inside classes:
```python
logger = logging.getLogger(__name__)

class MyClass:
    def method(self):
        logger.info("message")  # NOT: self.logger.info()
```

### Private Methods with Underscore
Prefix internal methods with `_`:
```python
def download_all(self):       # Public API
    self._download_activities()  # Internal helper
    self._download_health()
```

### `TYPE_CHECKING` for Circular Imports
Use `if TYPE_CHECKING:` to avoid runtime circular imports:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import BigQueryConfig

def get_uploader(config: "BigQueryConfig") -> BaseUploader:
    ...
```

### Generator Expressions in Aggregations
Use generator expressions instead of list comprehensions when iterating once:
```python
# GOOD - no intermediate list created
total = sum(r.duration_seconds for r in results.values() if r.success)

# LESS GOOD - creates intermediate list
total = sum([r.duration_seconds for r in results.values() if r.success])
```

### `__all__` in Package `__init__.py`
Explicitly declare public API:
```python
# src/lib/providers/__init__.py
from .base import BaseDataProvider, DataProvider, DownloadResult
from .manager import DataProviderManager

__all__ = [
    "BaseDataProvider",
    "DataProvider", 
    "DownloadResult",
    "DataProviderManager",
]
```

### Pydantic for Configuration
Use `pydantic_settings.BaseSettings` for env-based config:
```python
class AppConfig(BaseSettings):
    data_dir: Path = Field(default_factory=lambda: Path.cwd() / "data")
    log_level: str = Field(default="INFO")
    
    model_config = {"env_file": ".env", "extra": "ignore"}
```

## Jupyter Notebooks

Notebooks live in `notebooks/` and are used for exploratory data analysis (EDA), not production code.

### Cell Structure

Keep cells focused and executable independently:
```python
# GOOD - one logical unit per cell
df = pd.read_json("../data/garmin/activities/all_activities.json")
df["startTimeLocal"] = pd.to_datetime(df["startTimeLocal"])
df.head()
```

```python
# BAD - mixing unrelated operations
df = pd.read_json("../data/garmin/activities/all_activities.json")
df["startTimeLocal"] = pd.to_datetime(df["startTimeLocal"])
# ... 50 lines later ...
plt.figure(figsize=(12, 6))
plt.plot(df["distance"])
```

### Imports

Put all imports in the first code cell:
```python
# Cell 1 - always imports
import pandas as pd
import plotly.express as px
from pathlib import Path
```

### Function Wrapping

Wrap any code block with 5+ lines in a function to improve readability and reusability:
```python
# GOOD - wrapped in function
def load_activities_data(data_dir: Path) -> pd.DataFrame:
    df = pd.read_json(data_dir / "activities/all_activities.json")
    df["startTimeLocal"] = pd.to_datetime(df["startTimeLocal"])
    df["distance_km"] = df["distance"] / 1000
    df["duration_min"] = df["duration"] / 60
    return df

DATA_DIR = Path("../data/garmin")
df = load_activities_data(DATA_DIR)
df.head()
```

```python
# BAD - inline logic makes cells hard to test and reuse
df = pd.read_json("../data/garmin/activities/all_activities.json")
df["startTimeLocal"] = pd.to_datetime(df["startTimeLocal"])
df["distance_km"] = df["distance"] / 1000
df["duration_min"] = df["duration"] / 60
df.head()
```

Benefits of function wrapping:
- Easier to test the logic independently
- Can reuse the same function in multiple cells
- Clear function name documents what the code does
- Type hints make inputs and outputs explicit
- Easier to extract to `src/` if it becomes production code

### Paths

Use relative paths from the notebook location:
```python
# GOOD - relative to notebooks/
DATA_DIR = Path("../data/garmin")
df = pd.read_json(DATA_DIR / "activities/all_activities.json")

# BAD - absolute paths break portability
df = pd.read_json("C:/Users/mkkom/burnrate/data/garmin/activities/all_activities.json")
```

### Output Control

Limit DataFrame output to avoid cluttering:
```python
# GOOD - explicit head/tail
df.head(10)
df.tail(5)
df.sample(5)

# GOOD - summary stats
df.describe()
df.info()

# BAD - printing entire large DataFrames
df  # Shows all 10,000 rows
```

### Visualization

Use Plotly for interactive charts:
```python
import plotly.express as px

fig = px.line(df, x="date", y="distance", title="Daily Distance")
fig.show()
```

### Markdown Cells

Use markdown cells to document analysis steps:
- Describe what the next code cell does
- Document findings and insights
- Add section headers for navigation

### Clean State Before Sharing

Before committing or sharing:
1. Restart kernel and run all cells (`Kernel > Restart & Run All`)
2. Ensure cells execute in order without errors
3. Clear unnecessary output for large datasets

### Do NOT

- Store credentials or secrets in notebooks
- Use notebooks for production code (extract to `src/` instead)
- Leave cells with errors in committed notebooks
- Use `print()` when the last expression would display naturally

