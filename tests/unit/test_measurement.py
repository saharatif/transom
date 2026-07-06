"""Unit tests for backend/rag/measurement.py — the deterministic
inch-measurement comparison that stabilized the RAG agent's yes/no
conclusions (BUGS.md #20).
"""
from backend.rag.measurement import (
    compare_measurement_to_sources, extract_inch_measurements)


class TestExtractInchMeasurements:
    def test_fraction(self):
        assert extract_inch_measurements("a 1/8 inch crack") == [0.125]

    def test_fraction_of_an_inch_phrasing(self):
        assert extract_inch_measurements("shall not exceed 1/32 of an inch") == [1 / 32]

    def test_decimal_and_hyphenated(self):
        assert extract_inch_measurements("a 0.25 inch gap and a 2-inch pipe") == [0.25, 2.0]

    def test_fraction_not_double_counted_as_decimal(self):
        # The "8" in "1/8 inch" must not also parse as "8 inches".
        assert extract_inch_measurements("1/8 inch") == [0.125]

    def test_order_of_appearance_preserved(self):
        text = "1/2 inch here, then 1/4 inch there"
        assert extract_inch_measurements(text) == [0.5, 0.25]

    def test_zero_denominator_skipped(self):
        assert extract_inch_measurements("1/0 inch") == []

    def test_no_measurements(self):
        assert extract_inch_measurements("Is the roof covered?") == []


class TestCompareMeasurementToSources:
    SOURCE = "Cracks in drywall shall not exceed 1/32 of an inch in width."

    def test_measurement_exceeds_threshold(self):
        result = compare_measurement_to_sources(
            "Is a 1/8 inch crack in the drywall covered?", self.SOURCE)
        assert result == {
            "measured_inches": 0.125,
            "threshold_inches": 1 / 32,
            "exceeds_threshold": True,
        }

    def test_measurement_within_threshold(self):
        result = compare_measurement_to_sources(
            "Is a 1/64 inch crack covered?", self.SOURCE)
        assert result["exceeds_threshold"] is False

    def test_no_measurement_in_question_returns_none(self):
        assert compare_measurement_to_sources("Is the roof covered?", self.SOURCE) is None

    def test_multiple_question_measurements_returns_none(self):
        q = "Is a 1/8 inch or 1/4 inch crack covered?"
        assert compare_measurement_to_sources(q, self.SOURCE) is None

    def test_ambiguous_thresholds_with_no_matching_subject_returns_none(self):
        # No sentence mentions both subjects and no keyword narrows to a
        # single value -> stay out of it and let the LLM reason unaided.
        sources = ("Foundations shall not deflect more than 1/16 of an inch. "
                   "Trim gaps shall not exceed 1/4 of an inch.")
        assert compare_measurement_to_sources(
            "Is a 1/8 inch crack in the drywall covered?", sources) is None

    def test_mixed_thresholds_narrowed_by_subject_keywords(self):
        # Replicates the real retrieval for the drywall-crack question
        # (BUGS.md #33): the context mixes a stucco crack limit (1/8"),
        # ceiling-bow tolerances (1/2" within a 32-inch measurement),
        # crowning (1/4") and the actual drywall crack limit (1/32").
        # Only the sentence mentioning BOTH "crack" and "drywall" holds
        # the right threshold.
        sources = (
            "Stucco shall not have cracks that equal or exceed 1/8 of an inch in width. "
            "A ceiling made of drywall shall not have bows or depressions that equal or "
            "exceed 1/2 of an inch out of line within a 32-inch measurement. "
            "A drywall surface shall not crack such that any crack equals or exceeds "
            "1/32 of an inch in width at any point along the length of the crack. "
            "Crowning at a drywall joint shall not equal or exceed 1/4 of an inch.")
        result = compare_measurement_to_sources(
            "Is a 1/8 inch crack in the drywall covered?", sources)
        assert result == {
            "measured_inches": 0.125,
            "threshold_inches": 1 / 32,
            "exceeds_threshold": True,
        }

    def test_mixed_thresholds_within_tolerance_direction(self):
        sources = (
            "Stucco shall not have cracks that equal or exceed 1/8 of an inch in width. "
            "A drywall surface shall not crack such that any crack equals or exceeds "
            "1/32 of an inch in width.")
        result = compare_measurement_to_sources(
            "Is a 1/64 inch crack in the drywall covered?", sources)
        assert result["exceeds_threshold"] is False

    def test_repeated_identical_threshold_still_compares(self):
        sources = ("shall not exceed 1/32 of an inch ... the 1/32 inch "
                   "standard applies during the warranty period")
        result = compare_measurement_to_sources("Is a 1/8 inch crack covered?", sources)
        assert result["exceeds_threshold"] is True
