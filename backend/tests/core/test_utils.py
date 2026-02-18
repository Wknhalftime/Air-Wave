"""Tests for airwave.core.utils."""

from datetime import datetime, timezone

import pytest

from airwave.core.utils import guess_station_from_filename, parse_flexible_date


class TestParseFlexibleDate:
    """Tests for parse_flexible_date."""

    def test_none_returns_none(self):
        assert parse_flexible_date(None) is None

    def test_empty_string_returns_none(self):
        assert parse_flexible_date("") is None
        assert parse_flexible_date("   ") is None

    def test_none_string_returns_none(self):
        assert parse_flexible_date("none") is None
        assert parse_flexible_date("None") is None
        assert parse_flexible_date("null") is None
        assert parse_flexible_date("nan") is None

    def test_datetime_naive_gets_utc(self):
        dt = datetime(2023, 1, 15, 10, 30, 0)
        result = parse_flexible_date(dt)
        assert result is not None
        assert result.tzinfo is timezone.utc
        assert result.year == 2023 and result.month == 1 and result.day == 15

    def test_datetime_aware_unchanged(self):
        dt = datetime(2023, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = parse_flexible_date(dt)
        assert result == dt

    def test_iso_like_format(self):
        result = parse_flexible_date("2023-01-01 12:00:00")
        assert result is not None
        assert result.year == 2023 and result.month == 1 and result.day == 1
        assert result.hour == 12 and result.minute == 0

    def test_us_format(self):
        result = parse_flexible_date("01/15/2023 10:30:00")
        assert result is not None
        assert result.year == 2023 and result.month == 1 and result.day == 15

    def test_date_only(self):
        result = parse_flexible_date("2023-06-20")
        assert result is not None
        assert result.year == 2023 and result.month == 6 and result.day == 20

    def test_invalid_returns_none(self):
        assert parse_flexible_date("not-a-date") is None
        assert parse_flexible_date("2023-13-45") is None  # Invalid month/day


class TestGuessStationFromFilename:
    """Tests for guess_station_from_filename."""

    def test_empty_returns_unknown(self):
        assert guess_station_from_filename("") == "UNKNOWN"
        assert guess_station_from_filename(None) == "UNKNOWN"

    def test_underscore_takes_first_part(self):
        assert guess_station_from_filename("KROQ_2004.csv") == "KROQ"

    def test_hyphen_takes_first_part(self):
        assert guess_station_from_filename("KIIS-FM Log.csv") == "KIIS"

    def test_space_takes_first_part(self):
        assert guess_station_from_filename("WXYZ 2023 log.csv") == "WXYZ"

    def test_uppercased(self):
        assert guess_station_from_filename("kexp_2023.csv") == "KEXP"

    def test_numeric_returns_unknown(self):
        assert guess_station_from_filename("123_log.csv") == "UNKNOWN"

    def test_simple_basename(self):
        # Implementation takes first part before _/-/space; no extension strip
        assert guess_station_from_filename("WFMU.csv") == "WFMU.CSV"
        assert guess_station_from_filename("WFMU") == "WFMU"
