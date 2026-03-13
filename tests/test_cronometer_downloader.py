"""Tests for cronometer.downloader module."""

import io
import subprocess
import zipfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import CronometerConfig
from src.lib.providers.base import DataProvider, DownloadResult
from src.lib.providers.cronometer.downloader import (
    CronometerDownloader,
    _BINARY_NAME,
    _EXPORT_TYPES,
    _append_csv,
)

# ---------------------------------------------------------------------------
# Sample CSV content matching real downloaded files
# ---------------------------------------------------------------------------
_SAMPLE_BIOMETRICS = (
    "Day,Group,Metric,Unit,Amount\n"
    "2026-02-01,Uncategorized,Recovery (Garmin),%,73.0\n"
    "2026-02-01,Uncategorized,Weight (Garmin),kg,83.524\n"
)
_SAMPLE_DAILY_NUTRITION = (
    "Date,Energy (kcal),Protein (g),Carbs (g),Fat (g),Completed\n"
    "2026-02-01,,,,, false\n"
    "2026-02-02,2100.0,120.0,250.0,70.0,true\n"
)
_SAMPLE_EXERCISES = (
    "Day,Group,Exercise,Minutes,Calories Burned\n"
    "2026-02-02,Uncategorized,Daily Activity (Garmin),107.0,-527.00\n"
    "2026-02-02,Uncategorized,Skating ws (Garmin),68.83,-275.85\n"
)
_SAMPLE_NOTES = "Day,Group,Note\n"
_SAMPLE_SERVINGS = (
    "Day,Group,Food Name,Amount,Energy (kcal),Protein (g),Category\n"
    '2026-03-13,Lunch,Lumberjack Burger,1.00 full recipe,1204.10,53.89,""\n'
    '2026-03-13,Uncategorized,French Fries,150.00 g,293.24,2.90,"Vegetables"\n'
)

_SAMPLE_CSV = {
    "servings": _SAMPLE_SERVINGS,
    "daily-nutrition": _SAMPLE_DAILY_NUTRITION,
    "exercises": _SAMPLE_EXERCISES,
    "biometrics": _SAMPLE_BIOMETRICS,
    "notes": _SAMPLE_NOTES,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_zip_bytes(exe_name: str = _BINARY_NAME) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(exe_name, b"fake binary content")
    return buf.getvalue()


def _make_downloader(tmp_path: Path, days_back: int = 30) -> CronometerDownloader:
    return CronometerDownloader(
        username="test@example.com",
        password="secret",
        data_dir=tmp_path,
        days_back=days_back,
    )


def _canonical(downloader: CronometerDownloader, export_type: str) -> Path:
    return downloader.provider_dir / f"{export_type}.csv"


# ---------------------------------------------------------------------------
# TestCronometerDownloaderInit
# ---------------------------------------------------------------------------


class TestCronometerDownloaderInit:
    def test_provider_constant(self, tmp_path):
        d = _make_downloader(tmp_path)
        assert d.PROVIDER == "cronometer"

    def test_binary_path_inside_provider_dir(self, tmp_path):
        d = _make_downloader(tmp_path)
        assert d._binary == d.provider_dir / "bin" / _BINARY_NAME

    def test_directories_created_on_init(self, tmp_path):
        d = _make_downloader(tmp_path)
        assert d.provider_dir.exists()
        assert (d.provider_dir / "bin").exists()

    def test_implements_data_provider_protocol(self, tmp_path):
        d = _make_downloader(tmp_path)
        assert isinstance(d, DataProvider)


# ---------------------------------------------------------------------------
# TestFromConfig
# ---------------------------------------------------------------------------


class TestFromConfig:
    def test_creates_instance_from_config(self, tmp_path):
        cfg = CronometerConfig(
            cronometer_email="me@example.com",
            cronometer_password="pw",
            data_dir=tmp_path,
            days_back=14,
        )
        d = CronometerDownloader.from_config(cfg)
        assert d.username == "me@example.com"
        assert d.password == "pw"
        assert d.days_back == 14

    def test_data_dir_passed_through(self, tmp_path):
        cfg = CronometerConfig(
            cronometer_email="a@b.com",
            cronometer_password="x",
            data_dir=tmp_path,
        )
        d = CronometerDownloader.from_config(cfg)
        assert d.provider_dir.parent == tmp_path


# ---------------------------------------------------------------------------
# TestEnsureBinary
# ---------------------------------------------------------------------------


class TestEnsureBinary:
    def test_skips_download_if_binary_exists(self, tmp_path):
        d = _make_downloader(tmp_path)
        d._binary.touch()

        with patch("src.lib.providers.cronometer.downloader.requests.get") as mock_get:
            d._ensure_binary()
            mock_get.assert_not_called()

    def test_downloads_and_extracts_binary(self, tmp_path):
        d = _make_downloader(tmp_path)

        mock_response = MagicMock()
        mock_response.content = _make_zip_bytes(_BINARY_NAME)

        with patch(
            "src.lib.providers.cronometer.downloader.requests.get",
            return_value=mock_response,
        ):
            d._ensure_binary()

        assert d._binary.exists()
        mock_response.raise_for_status.assert_called_once()

    def test_raises_if_zip_contains_no_exe(self, tmp_path):
        d = _make_downloader(tmp_path)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", "no exe here")

        mock_response = MagicMock()
        mock_response.content = buf.getvalue()

        with patch(
            "src.lib.providers.cronometer.downloader.requests.get",
            return_value=mock_response,
        ):
            with pytest.raises(RuntimeError, match="No .exe found"):
                d._ensure_binary()

    def test_handles_nested_exe_path_in_zip(self, tmp_path):
        d = _make_downloader(tmp_path)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(f"subdir/{_BINARY_NAME}", b"fake binary")

        mock_response = MagicMock()
        mock_response.content = buf.getvalue()

        with patch(
            "src.lib.providers.cronometer.downloader.requests.get",
            return_value=mock_response,
        ):
            d._ensure_binary()

        assert d._binary.exists()


# ---------------------------------------------------------------------------
# TestRunExport
# ---------------------------------------------------------------------------


class TestRunExport:
    @pytest.fixture
    def downloader(self, tmp_path):
        d = _make_downloader(tmp_path)
        d._binary.touch()
        return d

    def test_calls_subprocess_with_correct_args(self, downloader, tmp_path):
        out_file = tmp_path / "out.csv"

        with patch("src.lib.providers.cronometer.downloader.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            downloader._run_export("servings", date(2026, 2, 1), date(2026, 3, 13), out_file)

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == str(downloader._binary)
        assert "-u" in cmd and "test@example.com" in cmd
        assert "-t" in cmd and "servings" in cmd
        assert "-s" in cmd and "2026-02-01T00:00:00Z" in cmd
        assert "-e" in cmd and "2026-03-13T00:00:00Z" in cmd
        assert "-o" in cmd and str(out_file) in cmd

    def test_raises_on_nonzero_exit(self, downloader, tmp_path):
        with patch("src.lib.providers.cronometer.downloader.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["binary"], stderr="invalid credentials"
            )
            with pytest.raises(subprocess.CalledProcessError):
                downloader._run_export(
                    "biometrics", date(2026, 2, 1), date(2026, 3, 13), tmp_path / "out.csv"
                )

    def test_dates_formatted_as_rfc3339(self, downloader, tmp_path):
        with patch("src.lib.providers.cronometer.downloader.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            downloader._run_export(
                "exercises", date(2025, 1, 5), date(2025, 12, 31), tmp_path / "out.csv"
            )

        cmd = mock_run.call_args[0][0]
        assert cmd[cmd.index("-s") + 1] == "2025-01-05T00:00:00Z"
        assert cmd[cmd.index("-e") + 1] == "2025-12-31T00:00:00Z"


# ---------------------------------------------------------------------------
# TestLastDownloadedDate
# ---------------------------------------------------------------------------


class TestLastDownloadedDate:
    def test_returns_none_when_no_file(self, tmp_path):
        d = _make_downloader(tmp_path)
        assert d._last_downloaded_date("servings") is None

    def test_returns_max_date_from_day_column(self, tmp_path):
        d = _make_downloader(tmp_path)
        _canonical(d, "servings").write_text(_SAMPLE_SERVINGS, encoding="utf-8")
        assert d._last_downloaded_date("servings") == date(2026, 3, 13)

    def test_returns_max_date_from_date_column(self, tmp_path):
        d = _make_downloader(tmp_path)
        _canonical(d, "daily-nutrition").write_text(_SAMPLE_DAILY_NUTRITION, encoding="utf-8")
        assert d._last_downloaded_date("daily-nutrition") == date(2026, 2, 2)

    def test_returns_none_when_file_is_header_only(self, tmp_path):
        d = _make_downloader(tmp_path)
        _canonical(d, "notes").write_text(_SAMPLE_NOTES, encoding="utf-8")
        assert d._last_downloaded_date("notes") is None

    def test_returns_max_across_multiple_rows(self, tmp_path):
        d = _make_downloader(tmp_path)
        _canonical(d, "biometrics").write_text(_SAMPLE_BIOMETRICS, encoding="utf-8")
        assert d._last_downloaded_date("biometrics") == date(2026, 2, 1)


# ---------------------------------------------------------------------------
# TestAppendCsv
# ---------------------------------------------------------------------------


class TestAppendCsv:
    def test_creates_destination_if_not_exists(self, tmp_path):
        src = tmp_path / "src.csv"
        dst = tmp_path / "dst.csv"
        src.write_text("Day,Val\n2026-01-01,1\n", encoding="utf-8")
        _append_csv(src, dst)
        assert dst.read_text(encoding="utf-8") == "Day,Val\n2026-01-01,1\n"

    def test_appends_without_duplicate_header(self, tmp_path):
        src = tmp_path / "src.csv"
        dst = tmp_path / "dst.csv"
        dst.write_text("Day,Val\n2026-01-01,1\n", encoding="utf-8")
        src.write_text("Day,Val\n2026-01-02,2\n", encoding="utf-8")
        _append_csv(src, dst)
        lines = dst.read_text(encoding="utf-8").splitlines()
        assert lines.count("Day,Val") == 1
        assert "2026-01-01,1" in lines
        assert "2026-01-02,2" in lines

    def test_noop_on_empty_src(self, tmp_path):
        src = tmp_path / "src.csv"
        dst = tmp_path / "dst.csv"
        src.write_text("", encoding="utf-8")
        dst.write_text("Day,Val\n2026-01-01,1\n", encoding="utf-8")
        original = dst.read_text(encoding="utf-8")
        _append_csv(src, dst)
        assert dst.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# TestDownloadAll
# ---------------------------------------------------------------------------


class TestDownloadAll:
    @pytest.fixture
    def downloader(self, tmp_path):
        d = _make_downloader(tmp_path, days_back=40)
        d._binary.touch()
        return d

    def _patch_run_export(self, downloader: CronometerDownloader):
        def fake_run_export(export_type, start, end, out_file):
            out_file.write_text(_SAMPLE_CSV[export_type], encoding="utf-8")

        return patch.object(downloader, "_run_export", side_effect=fake_run_export)

    def test_returns_download_result(self, downloader):
        with self._patch_run_export(downloader):
            result = downloader.download_all()
        assert isinstance(result, DownloadResult)

    def test_success_when_all_types_downloaded(self, downloader):
        with self._patch_run_export(downloader):
            result = downloader.download_all()
        assert result.success is True

    def test_all_export_types_in_items_downloaded(self, downloader):
        with self._patch_run_export(downloader):
            result = downloader.download_all()
        for export_type in _EXPORT_TYPES:
            assert export_type in result.items_downloaded

    def test_canonical_files_created(self, downloader):
        with self._patch_run_export(downloader):
            downloader.download_all()
        for export_type in _EXPORT_TYPES:
            assert _canonical(downloader, export_type).exists()

    def test_provider_is_cronometer(self, downloader):
        with self._patch_run_export(downloader):
            result = downloader.download_all()
        assert result.provider == "cronometer"

    def test_data_dir_set_in_result(self, downloader):
        with self._patch_run_export(downloader):
            result = downloader.download_all()
        assert result.data_dir == str(downloader.provider_dir)

    def test_duration_recorded(self, downloader):
        with self._patch_run_export(downloader):
            result = downloader.download_all()
        assert result.duration_seconds >= 0

    def test_up_to_date_files_skipped(self, downloader):
        """Types with max date >= today are marked cached without re-fetching."""
        today = date.today().isoformat()
        for export_type in _EXPORT_TYPES:
            date_col = "Date" if export_type == "daily-nutrition" else "Day"
            _canonical(downloader, export_type).write_text(
                f"{date_col},Val\n{today},x\n", encoding="utf-8"
            )

        with patch.object(downloader, "_run_export") as mock_run:
            result = downloader.download_all()
            mock_run.assert_not_called()

        assert result.items_cached == {t: 1 for t in _EXPORT_TYPES}

    def test_delta_fetch_starts_from_day_after_last(self, downloader):
        """If canonical file has data through last week, only fetch the gap."""
        last_date = date.today() - timedelta(days=3)
        date_col = "Day"
        _canonical(downloader, "servings").write_text(
            f"{date_col},Val\n{last_date.isoformat()},x\n", encoding="utf-8"
        )

        captured = {}

        def fake_run_export(export_type, start, end, out_file):
            captured[export_type] = start
            out_file.write_text(_SAMPLE_CSV[export_type], encoding="utf-8")

        with patch.object(downloader, "_run_export", side_effect=fake_run_export):
            downloader.download_all()

        assert captured["servings"] == last_date + timedelta(days=1)

    def test_tmp_file_cleaned_up_after_success(self, downloader):
        with self._patch_run_export(downloader):
            downloader.download_all()
        tmp_files = list(downloader.provider_dir.glob("*.tmp.csv"))
        assert tmp_files == []

    def test_tmp_file_cleaned_up_after_failure(self, downloader):
        def fail_first(export_type, start, end, out_file):
            if export_type == "servings":
                out_file.write_text("partial", encoding="utf-8")
                raise subprocess.CalledProcessError(1, cmd=["bin"], stderr="err")
            out_file.write_text(_SAMPLE_CSV[export_type], encoding="utf-8")

        with patch.object(downloader, "_run_export", side_effect=fail_first):
            downloader.download_all()

        tmp_files = list(downloader.provider_dir.glob("*.tmp.csv"))
        assert tmp_files == []

    def test_partial_failure_adds_warning(self, downloader):
        def fake_run_export(export_type, start, end, out_file):
            if export_type == "servings":
                raise subprocess.CalledProcessError(1, cmd=["bin"], stderr="auth error")
            out_file.write_text(_SAMPLE_CSV[export_type], encoding="utf-8")

        with patch.object(downloader, "_run_export", side_effect=fake_run_export):
            result = downloader.download_all()

        assert result.success is False
        assert any("servings" in w for w in result.warnings)
        for export_type in _EXPORT_TYPES:
            if export_type != "servings":
                assert export_type in result.items_downloaded

    def test_days_back_zero_uses_full_history(self, tmp_path):
        d = _make_downloader(tmp_path, days_back=0)
        d._binary.touch()

        captured = {}

        def fake_run_export(export_type, start, end, out_file):
            captured[export_type] = start
            out_file.write_text(_SAMPLE_CSV[export_type], encoding="utf-8")

        with patch.object(d, "_run_export", side_effect=fake_run_export):
            d.download_all()

        assert captured["servings"] == date(2000, 1, 1)

    def test_days_back_controls_start_date(self, tmp_path):
        days = 7
        d = _make_downloader(tmp_path, days_back=days)
        d._binary.touch()

        captured = {}

        def fake_run_export(export_type, start, end, out_file):
            captured[export_type] = start
            out_file.write_text(_SAMPLE_CSV[export_type], encoding="utf-8")

        with patch.object(d, "_run_export", side_effect=fake_run_export):
            d.download_all()

        assert captured["biometrics"] == date.today() - timedelta(days=days)

    def test_ensure_binary_called(self, downloader):
        with self._patch_run_export(downloader):
            with patch.object(downloader, "_ensure_binary") as mock_ensure:
                downloader.download_all()
        mock_ensure.assert_called_once()

    def test_all_export_types_attempted(self, downloader):
        called_types = []

        def fake_run_export(export_type, start, end, out_file):
            called_types.append(export_type)
            out_file.write_text(_SAMPLE_CSV[export_type], encoding="utf-8")

        with patch.object(downloader, "_run_export", side_effect=fake_run_export):
            downloader.download_all()

        assert set(called_types) == set(_EXPORT_TYPES)


# ---------------------------------------------------------------------------
# Sample CSV content matching real downloaded files
# ---------------------------------------------------------------------------
_SAMPLE_BIOMETRICS = (
    "Day,Group,Metric,Unit,Amount\n"
    "2026-02-01,Uncategorized,Recovery (Garmin),%,73.0\n"
    "2026-02-01,Uncategorized,Weight (Garmin),kg,83.524\n"
)
_SAMPLE_DAILY_NUTRITION = (
    "Date,Energy (kcal),Protein (g),Carbs (g),Fat (g),Completed\n"
    "2026-02-01,,,,, false\n"
    "2026-02-02,2100.0,120.0,250.0,70.0,true\n"
)
_SAMPLE_EXERCISES = (
    "Day,Group,Exercise,Minutes,Calories Burned\n"
    "2026-02-02,Uncategorized,Daily Activity (Garmin),107.0,-527.00\n"
    "2026-02-02,Uncategorized,Skating ws (Garmin),68.83,-275.85\n"
)
_SAMPLE_NOTES = "Day,Group,Note\n"
_SAMPLE_SERVINGS = (
    "Day,Group,Food Name,Amount,Energy (kcal),Protein (g),Category\n"
    '2026-03-13,Lunch,Lumberjack Burger,1.00 full recipe,1204.10,53.89,""\n'
    '2026-03-13,Uncategorized,French Fries,150.00 g,293.24,2.90,"Vegetables"\n'
)

_SAMPLE_CSV = {
    "servings": _SAMPLE_SERVINGS,
    "daily-nutrition": _SAMPLE_DAILY_NUTRITION,
    "exercises": _SAMPLE_EXERCISES,
    "biometrics": _SAMPLE_BIOMETRICS,
    "notes": _SAMPLE_NOTES,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_zip_bytes(exe_name: str = _BINARY_NAME) -> bytes:
    """Build an in-memory zip containing a fake .exe."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(exe_name, b"fake binary content")
    return buf.getvalue()


def _make_downloader(tmp_path: Path, days_back: int = 30) -> CronometerDownloader:
    return CronometerDownloader(
        username="test@example.com",
        password="secret",
        data_dir=tmp_path,
        days_back=days_back,
    )


# ---------------------------------------------------------------------------
# TestCronometerDownloaderInit
# ---------------------------------------------------------------------------


class TestCronometerDownloaderInit:
    def test_provider_constant(self, tmp_path):
        d = _make_downloader(tmp_path)
        assert d.PROVIDER == "cronometer"

    def test_binary_path_inside_provider_dir(self, tmp_path):
        d = _make_downloader(tmp_path)
        assert d._binary == d.provider_dir / "bin" / _BINARY_NAME

    def test_directories_created_on_init(self, tmp_path):
        d = _make_downloader(tmp_path)
        assert d.provider_dir.exists()
        assert (d.provider_dir / "bin").exists()

    def test_implements_data_provider_protocol(self, tmp_path):
        d = _make_downloader(tmp_path)
        assert isinstance(d, DataProvider)


# ---------------------------------------------------------------------------
# TestFromConfig
# ---------------------------------------------------------------------------


class TestFromConfig:
    def test_creates_instance_from_config(self, tmp_path):
        cfg = CronometerConfig(
            cronometer_email="me@example.com",
            cronometer_password="pw",
            data_dir=tmp_path,
            days_back=14,
        )
        d = CronometerDownloader.from_config(cfg)
        assert d.username == "me@example.com"
        assert d.password == "pw"
        assert d.days_back == 14

    def test_data_dir_passed_through(self, tmp_path):
        cfg = CronometerConfig(
            cronometer_email="a@b.com",
            cronometer_password="x",
            data_dir=tmp_path,
        )
        d = CronometerDownloader.from_config(cfg)
        assert d.provider_dir.parent == tmp_path


# ---------------------------------------------------------------------------
# TestEnsureBinary
# ---------------------------------------------------------------------------


class TestEnsureBinary:
    def test_skips_download_if_binary_exists(self, tmp_path):
        d = _make_downloader(tmp_path)
        d._binary.touch()

        with patch("src.lib.providers.cronometer.downloader.requests.get") as mock_get:
            d._ensure_binary()
            mock_get.assert_not_called()

    def test_downloads_and_extracts_binary(self, tmp_path):
        d = _make_downloader(tmp_path)

        mock_response = MagicMock()
        mock_response.content = _make_zip_bytes(_BINARY_NAME)

        with patch(
            "src.lib.providers.cronometer.downloader.requests.get",
            return_value=mock_response,
        ):
            d._ensure_binary()

        assert d._binary.exists()
        mock_response.raise_for_status.assert_called_once()

    def test_raises_if_zip_contains_no_exe(self, tmp_path):
        d = _make_downloader(tmp_path)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", "no exe here")

        mock_response = MagicMock()
        mock_response.content = buf.getvalue()

        with patch(
            "src.lib.providers.cronometer.downloader.requests.get",
            return_value=mock_response,
        ):
            with pytest.raises(RuntimeError, match="No .exe found"):
                d._ensure_binary()

    def test_handles_nested_exe_path_in_zip(self, tmp_path):
        """Binary may be in a subdirectory inside the zip."""
        d = _make_downloader(tmp_path)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(f"subdir/{_BINARY_NAME}", b"fake binary")

        mock_response = MagicMock()
        mock_response.content = buf.getvalue()

        with patch(
            "src.lib.providers.cronometer.downloader.requests.get",
            return_value=mock_response,
        ):
            d._ensure_binary()

        assert d._binary.exists()


# ---------------------------------------------------------------------------
# TestRunExport
# ---------------------------------------------------------------------------


class TestRunExport:
    def _make_downloader_with_fake_binary(self, tmp_path: Path) -> CronometerDownloader:
        d = _make_downloader(tmp_path)
        d._binary.touch()
        return d

    def test_calls_subprocess_with_correct_args(self, tmp_path):
        d = self._make_downloader_with_fake_binary(tmp_path)
        start = date(2026, 2, 1)
        end = date(2026, 3, 13)
        out_file = tmp_path / "out.csv"

        with patch("src.lib.providers.cronometer.downloader.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            d._run_export("servings", start, end, out_file)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == str(d._binary)
        assert "-u" in cmd and "test@example.com" in cmd
        assert "-t" in cmd and "servings" in cmd
        assert "-s" in cmd and "2026-02-01T00:00:00Z" in cmd
        assert "-e" in cmd and "2026-03-13T00:00:00Z" in cmd
        assert "-o" in cmd and str(out_file) in cmd

    def test_raises_on_nonzero_exit(self, tmp_path):
        d = self._make_downloader_with_fake_binary(tmp_path)
        out_file = tmp_path / "out.csv"

        with patch("src.lib.providers.cronometer.downloader.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["binary"], stderr="invalid credentials"
            )
            with pytest.raises(subprocess.CalledProcessError):
                d._run_export("biometrics", date(2026, 2, 1), date(2026, 3, 13), out_file)

    def test_dates_formatted_as_rfc3339(self, tmp_path):
        d = self._make_downloader_with_fake_binary(tmp_path)
        out_file = tmp_path / "out.csv"

        with patch("src.lib.providers.cronometer.downloader.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            d._run_export("exercises", date(2025, 1, 5), date(2025, 12, 31), out_file)

        cmd = mock_run.call_args[0][0]
        s_idx = cmd.index("-s") + 1
        e_idx = cmd.index("-e") + 1
        assert cmd[s_idx] == "2025-01-05T00:00:00Z"
        assert cmd[e_idx] == "2025-12-31T00:00:00Z"


# ---------------------------------------------------------------------------
# TestDownloadAll
# ---------------------------------------------------------------------------


class TestDownloadAll:
    @pytest.fixture
    def downloader(self, tmp_path):
        d = _make_downloader(tmp_path, days_back=40)
        d._binary.touch()
        return d

    def _write_csv(self, path: Path, export_type: str) -> None:
        path.write_text(_SAMPLE_CSV[export_type], encoding="utf-8")

    def _patch_run_export(self, downloader: CronometerDownloader):
        """Patch _run_export to write a sample CSV file."""
        original = downloader._run_export

        def fake_run_export(export_type, start, end, out_file):
            out_file.write_text(_SAMPLE_CSV[export_type], encoding="utf-8")

        return patch.object(downloader, "_run_export", side_effect=fake_run_export)

    def test_returns_download_result(self, downloader):
        with self._patch_run_export(downloader):
            result = downloader.download_all()
        assert isinstance(result, DownloadResult)

    def test_success_when_all_types_downloaded(self, downloader):
        with self._patch_run_export(downloader):
            result = downloader.download_all()
        assert result.success is True

    def test_all_export_types_in_items_downloaded(self, downloader):
        with self._patch_run_export(downloader):
            result = downloader.download_all()
        for export_type in _EXPORT_TYPES:
            assert export_type in result.items_downloaded

    def test_provider_is_cronometer(self, downloader):
        with self._patch_run_export(downloader):
            result = downloader.download_all()
        assert result.provider == "cronometer"

    def test_data_dir_set_in_result(self, downloader):
        with self._patch_run_export(downloader):
            result = downloader.download_all()
        assert result.data_dir == str(downloader.provider_dir)

    def test_duration_recorded(self, downloader):
        with self._patch_run_export(downloader):
            result = downloader.download_all()
        assert result.duration_seconds >= 0

    def test_cached_files_skipped(self, downloader):
        """Types with max date >= today are marked cached without re-fetching."""
        today = date.today().isoformat()
        for export_type in _EXPORT_TYPES:
            date_col = "Date" if export_type == "daily-nutrition" else "Day"
            _canonical(downloader, export_type).write_text(
                f"{date_col},Val\n{today},x\n", encoding="utf-8"
            )

        with patch.object(downloader, "_run_export") as mock_run:
            result = downloader.download_all()
            mock_run.assert_not_called()

        assert result.items_cached == {t: 1 for t in _EXPORT_TYPES}

    def test_partial_failure_adds_warning(self, downloader):
        """A failed export type is recorded as a warning, not an exception."""
        def fake_run_export(export_type, start, end, out_file):
            if export_type == "servings":
                raise subprocess.CalledProcessError(1, cmd=["bin"], stderr="auth error")
            out_file.write_text(_SAMPLE_CSV[export_type], encoding="utf-8")

        with patch.object(downloader, "_run_export", side_effect=fake_run_export):
            result = downloader.download_all()

        assert result.success is False
        assert any("servings" in w for w in result.warnings)
        # Other types still downloaded
        for export_type in _EXPORT_TYPES:
            if export_type != "servings":
                assert export_type in result.items_downloaded

    def test_days_back_zero_uses_full_history(self, tmp_path):
        d = _make_downloader(tmp_path, days_back=0)
        d._binary.touch()

        captured = {}

        def fake_run_export(export_type, start, end, out_file):
            captured[export_type] = (start, end)
            out_file.write_text(_SAMPLE_CSV[export_type], encoding="utf-8")

        with patch.object(d, "_run_export", side_effect=fake_run_export):
            d.download_all()

        assert captured["servings"][0] == date(2000, 1, 1)

    def test_days_back_controls_start_date(self, tmp_path):
        days = 7
        d = _make_downloader(tmp_path, days_back=days)
        d._binary.touch()

        captured = {}

        def fake_run_export(export_type, start, end, out_file):
            captured[export_type] = (start, end)
            out_file.write_text(_SAMPLE_CSV[export_type], encoding="utf-8")

        with patch.object(d, "_run_export", side_effect=fake_run_export):
            d.download_all()

        expected_start = date.today() - timedelta(days=days)
        assert captured["biometrics"][0] == expected_start

    def test_ensure_binary_called(self, downloader):
        with self._patch_run_export(downloader):
            with patch.object(downloader, "_ensure_binary") as mock_ensure:
                downloader.download_all()
        mock_ensure.assert_called_once()

    def test_all_export_types_attempted(self, downloader):
        called_types = []

        def fake_run_export(export_type, start, end, out_file):
            called_types.append(export_type)
            out_file.write_text(_SAMPLE_CSV[export_type], encoding="utf-8")

        with patch.object(downloader, "_run_export", side_effect=fake_run_export):
            downloader.download_all()

        assert set(called_types) == set(_EXPORT_TYPES)
