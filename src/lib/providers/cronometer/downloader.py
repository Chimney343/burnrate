"""Cronometer data downloader using the cronometer-export binary."""

from __future__ import annotations

import csv
import io
import logging
import subprocess
import zipfile
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from tqdm import tqdm

from ..base import BaseDataProvider, DownloadResult

if TYPE_CHECKING:
    from config import CronometerConfig

logger = logging.getLogger(__name__)

_BINARY_URL = (
    "https://github.com/jrmycanady/cronometer-export/releases/download/v1.1.1/"
    "cronometer-export-windows-amd64.zip"
)
_BINARY_NAME = "cronometer-export.exe"

# All export types supported by the binary
_EXPORT_TYPES = [
    "servings",
    "daily-nutrition",
    "exercises",
    "biometrics",
    "notes",
]

# The date column name varies by export type
_DATE_COL: dict[str, str] = {
    "daily-nutrition": "Date",
}  # all others use "Day"


def _append_csv(src: Path, dst: Path) -> None:
    """Append rows from src into dst, skipping the header if dst already exists."""
    with src.open(encoding="utf-8") as s:
        lines = s.readlines()
    if not lines:
        return
    if dst.exists() and dst.stat().st_size > 0:
        lines = lines[1:]  # drop header — dst already has it
    with dst.open("a", encoding="utf-8") as d:
        d.writelines(lines)


class CronometerDownloader(BaseDataProvider):
    """Downloads all Cronometer export types by wrapping the cronometer-export binary.

    The binary authenticates directly against Cronometer's internal GWT API —
    no browser or Cloudflare bypass required.

    On first use the binary is downloaded automatically from GitHub releases and
    cached in <data_dir>/cronometer/bin/.
    """

    PROVIDER = "cronometer"
    SUBDIRS = ["bin"]

    def __init__(
        self,
        username: str,
        password: str,
        data_dir: Path,
        days_back: int = 30,
    ) -> None:
        super().__init__(data_dir)
        self.username = username
        self.password = password
        self.days_back = days_back
        self._binary = self.provider_dir / "bin" / _BINARY_NAME

    @classmethod
    def from_config(cls, config: CronometerConfig) -> CronometerDownloader:
        return cls(
            username=config.cronometer_email,
            password=config.cronometer_password,
            data_dir=config.data_dir,
            days_back=config.days_back,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download_all(self) -> DownloadResult:
        from datetime import datetime

        result = DownloadResult(provider=self.PROVIDER)
        result.start_time = datetime.now()
        result.data_dir = str(self.provider_dir)

        self._ensure_binary()

        end = date.today()
        start = end - timedelta(days=self.days_back) if self.days_back > 0 else date(2000, 1, 1)

        logger.info("Cronometer export window: %s to %s", start.isoformat(), end.isoformat())

        for export_type in tqdm(_EXPORT_TYPES, desc="Cronometer", unit="type"):
            canonical = self.provider_dir / f"{export_type}.csv"

            last = self._last_downloaded_date(export_type)
            fetch_start = (last + timedelta(days=1)) if last else start

            if fetch_start > end:
                tqdm.write(f"[CACHED] {export_type} (up to {last})")
                result.items_cached[export_type] = 1
                result.items_downloaded[export_type] = 1
                continue

            tmp = self.provider_dir / f"{export_type}.tmp.csv"
            try:
                self._run_export(export_type, fetch_start, end, tmp)
                _append_csv(tmp, canonical)
                result.items_downloaded[export_type] = 1
                tqdm.write(f"[OK] {export_type} ({fetch_start} -> {end})")
            except subprocess.CalledProcessError as e:
                msg = f"{export_type} export failed: {e.stderr or e}"
                logger.warning(msg)
                result.warnings.append(msg)
            finally:
                tmp.unlink(missing_ok=True)

        result.end_time = datetime.now()
        result.duration_seconds = (result.end_time - result.start_time).total_seconds()
        result.success = not any(
            k not in result.items_downloaded for k in _EXPORT_TYPES
            if k not in result.items_cached
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _last_downloaded_date(self, export_type: str) -> date | None:
        """Return the most recent date already stored for this export type."""
        canonical = self.provider_dir / f"{export_type}.csv"
        if not canonical.exists():
            return None
        date_col = _DATE_COL.get(export_type, "Day")
        with canonical.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            dates = [
                row[date_col]
                for row in reader
                if row.get(date_col, "").strip()
            ]
        if not dates:
            return None
        return date.fromisoformat(max(dates))

    def _run_export(
        self,
        export_type: str,
        start: date,
        end: date,
        out_file: Path,
    ) -> None:
        cmd = [
            str(self._binary),
            "-u", self.username,
            "-p", self.password,
            "-t", export_type,
            "-s", f"{start.isoformat()}T00:00:00Z",
            "-e", f"{end.isoformat()}T00:00:00Z",
            "-o", str(out_file),
        ]
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )

    def _ensure_binary(self) -> None:
        if self._binary.exists():
            return

        logger.info("Downloading cronometer-export binary from GitHub releases...")
        response = requests.get(_BINARY_URL, timeout=60)
        response.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            exe_names = [n for n in zf.namelist() if n.endswith(".exe")]
            if not exe_names:
                raise RuntimeError("No .exe found in cronometer-export zip")
            zf.extract(exe_names[0], self.provider_dir / "bin")
            extracted = self.provider_dir / "bin" / exe_names[0]
            if extracted != self._binary:
                extracted.rename(self._binary)

        logger.info("Binary saved to %s", self._binary)
