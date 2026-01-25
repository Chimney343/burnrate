"""Tests for the HealthFlattener module."""

import pytest

from src.lib.flattener import HealthFlattener


class TestHealthFlattenerStats:
    """Test suite for flatten_stats method."""

    def test_flatten_stats_extracts_stats_section(self):
        """Test that stats are correctly extracted from nested structure."""
        flattener = HealthFlattener()
        raw_data = [
            {
                "date": "2024-01-15",
                "stats": {
                    "totalSteps": 10000,
                    "totalCalories": 2500,
                    "restingHeartRate": 55,
                },
            }
        ]

        result = flattener.flatten_stats(raw_data)

        assert len(result) == 1
        assert result[0]["date"] == "2024-01-15"
        assert result[0]["totalSteps"] == 10000
        assert result[0]["totalCalories"] == 2500
        assert result[0]["restingHeartRate"] == 55

    def test_flatten_stats_skips_records_without_stats(self):
        """Test that records without stats section are skipped."""
        flattener = HealthFlattener()
        raw_data = [
            {"date": "2024-01-15", "stats": {"totalSteps": 5000}},
            {"date": "2024-01-16"},  # No stats
            {"date": "2024-01-17", "stats": None},  # stats is None
            {"date": "2024-01-18", "stats": {"totalSteps": 8000}},
        ]

        result = flattener.flatten_stats(raw_data)

        assert len(result) == 2
        assert result[0]["date"] == "2024-01-15"
        assert result[1]["date"] == "2024-01-18"

    def test_flatten_stats_empty_input(self):
        """Test flatten_stats with empty list."""
        flattener = HealthFlattener()

        result = flattener.flatten_stats([])

        assert result == []

    def test_flatten_stats_preserves_all_stat_fields(self):
        """Test that all fields in stats are preserved."""
        flattener = HealthFlattener()
        raw_data = [
            {
                "date": "2024-01-15",
                "stats": {
                    "field1": "value1",
                    "field2": 123,
                    "field3": True,
                    "nested": {"a": 1},
                },
            }
        ]

        result = flattener.flatten_stats(raw_data)

        assert result[0]["field1"] == "value1"
        assert result[0]["field2"] == 123
        assert result[0]["field3"] is True
        assert result[0]["nested"] == {"a": 1}


class TestHealthFlattenerHeartRate:
    """Test suite for flatten_heart_rate method."""

    def test_flatten_heart_rate_extracts_data(self):
        """Test that heart rate data is correctly extracted."""
        flattener = HealthFlattener()
        raw_data = [
            {
                "date": "2024-01-15",
                "heart_rate": {
                    "restingHeartRate": 55,
                    "maxHeartRate": 180,
                    "minHeartRate": 45,
                },
            }
        ]

        result = flattener.flatten_heart_rate(raw_data)

        assert len(result) == 1
        assert result[0]["date"] == "2024-01-15"
        assert result[0]["restingHeartRate"] == 55
        assert result[0]["maxHeartRate"] == 180

    def test_flatten_heart_rate_skips_missing_data(self):
        """Test that records without heart_rate are skipped."""
        flattener = HealthFlattener()
        raw_data = [
            {"date": "2024-01-15", "heart_rate": {"rhr": 55}},
            {"date": "2024-01-16"},
            {"date": "2024-01-17", "heart_rate": {"rhr": 58}},
        ]

        result = flattener.flatten_heart_rate(raw_data)

        assert len(result) == 2

    def test_flatten_heart_rate_empty_input(self):
        """Test flatten_heart_rate with empty list."""
        flattener = HealthFlattener()

        result = flattener.flatten_heart_rate([])

        assert result == []


class TestHealthFlattenerBodyComposition:
    """Test suite for flatten_body_composition method."""

    def test_flatten_body_composition_extracts_total_average(self):
        """Test that totalAverage weight data is extracted."""
        flattener = HealthFlattener()
        raw_data = [
            {
                "date": "2024-01-15",
                "body_composition": {
                    "startDate": "2024-01-15",
                    "endDate": "2024-01-15",
                    "totalAverage": {
                        "weight": 75.5,
                        "bmi": 23.5,
                        "bodyFat": 18.5,
                        "bodyWater": 55.0,
                        "boneMass": 3.2,
                        "muscleMass": 35.0,
                        "physiqueRating": 5,
                        "visceralFat": 8,
                        "metabolicAge": 30,
                    },
                },
            }
        ]

        result = flattener.flatten_body_composition(raw_data)

        assert len(result) == 1
        assert result[0]["date"] == "2024-01-15"
        assert result[0]["weight"] == 75.5
        assert result[0]["bmi"] == 23.5
        assert result[0]["bodyFat"] == 18.5
        assert result[0]["muscleMass"] == 35.0
        assert result[0]["startDate"] == "2024-01-15"
        assert result[0]["endDate"] == "2024-01-15"

    def test_flatten_body_composition_handles_missing_total_average(self):
        """Test handling when totalAverage is missing."""
        flattener = HealthFlattener()
        raw_data = [
            {
                "date": "2024-01-15",
                "body_composition": {
                    "startDate": "2024-01-15",
                    "endDate": "2024-01-15",
                    # No totalAverage
                },
            }
        ]

        result = flattener.flatten_body_composition(raw_data)

        assert len(result) == 1
        assert result[0]["date"] == "2024-01-15"
        assert result[0]["startDate"] == "2024-01-15"
        assert "weight" not in result[0]

    def test_flatten_body_composition_skips_missing_section(self):
        """Test that records without body_composition are skipped."""
        flattener = HealthFlattener()
        raw_data = [
            {"date": "2024-01-15", "body_composition": {"totalAverage": {"weight": 75}}},
            {"date": "2024-01-16"},
            {"date": "2024-01-17", "body_composition": None},
        ]

        result = flattener.flatten_body_composition(raw_data)

        assert len(result) == 1
        assert result[0]["date"] == "2024-01-15"

    def test_flatten_body_composition_empty_input(self):
        """Test flatten_body_composition with empty list."""
        flattener = HealthFlattener()

        result = flattener.flatten_body_composition([])

        assert result == []

    def test_flatten_body_composition_partial_total_average(self):
        """Test handling partial totalAverage data."""
        flattener = HealthFlattener()
        raw_data = [
            {
                "date": "2024-01-15",
                "body_composition": {
                    "totalAverage": {
                        "weight": 75.5,
                        # Only weight, other fields missing
                    },
                },
            }
        ]

        result = flattener.flatten_body_composition(raw_data)

        assert result[0]["weight"] == 75.5
        assert result[0].get("bmi") is None
        assert result[0].get("bodyFat") is None


class TestHealthFlattenerMultipleRecords:
    """Test processing multiple records."""

    @pytest.mark.parametrize(
        "method_name,section_key",
        [
            ("flatten_stats", "stats"),
            ("flatten_heart_rate", "heart_rate"),
            ("flatten_body_composition", "body_composition"),
        ],
    )
    def test_processes_multiple_records(self, method_name, section_key):
        """Test that all methods correctly process multiple records."""
        flattener = HealthFlattener()
        
        if section_key == "body_composition":
            section_data = {"totalAverage": {"weight": 75}}
        else:
            section_data = {"value": 100}
        
        raw_data = [
            {"date": f"2024-01-{i:02d}", section_key: section_data}
            for i in range(1, 11)
        ]

        method = getattr(flattener, method_name)
        result = method(raw_data)

        assert len(result) == 10
        for i, row in enumerate(result):
            assert row["date"] == f"2024-01-{i+1:02d}"


class TestHealthFlattenerEdgeCases:
    """Test edge cases and error handling."""

    def test_stats_is_not_dict(self):
        """Test handling when stats is wrong type."""
        flattener = HealthFlattener()
        raw_data = [
            {"date": "2024-01-15", "stats": "invalid"},
            {"date": "2024-01-16", "stats": ["list", "data"]},
            {"date": "2024-01-17", "stats": 123},
        ]

        result = flattener.flatten_stats(raw_data)

        assert result == []

    def test_missing_date_in_record(self):
        """Test handling when date is missing."""
        flattener = HealthFlattener()
        raw_data = [{"stats": {"totalSteps": 5000}}]

        result = flattener.flatten_stats(raw_data)

        assert len(result) == 1
        assert result[0].get("date") is None
        assert result[0]["totalSteps"] == 5000

    def test_flattener_is_reusable(self):
        """Test that a single flattener instance can be reused."""
        flattener = HealthFlattener()
        
        data1 = [{"date": "2024-01-15", "stats": {"steps": 1000}}]
        data2 = [{"date": "2024-01-16", "stats": {"steps": 2000}}]

        result1 = flattener.flatten_stats(data1)
        result2 = flattener.flatten_stats(data2)

        assert result1[0]["steps"] == 1000
        assert result2[0]["steps"] == 2000
