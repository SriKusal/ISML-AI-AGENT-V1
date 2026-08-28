"""Tests for configurable quality thresholds (ENH-004)."""

import unittest

from app.services.quality_thresholds import (
    classify_score,
    is_high_quality,
    quality_summary,
    QualityTier,
)


class TestClassifyScore(unittest.TestCase):

    def test_excellent_tier(self):
        result = classify_score(0.95)
        self.assertEqual(result.tier, QualityTier.EXCELLENT)
        self.assertTrue(result.auto_approve)

    def test_exact_excellent_boundary(self):
        result = classify_score(0.90)
        self.assertEqual(result.tier, QualityTier.EXCELLENT)

    def test_high_tier(self):
        result = classify_score(0.85)
        self.assertEqual(result.tier, QualityTier.HIGH)
        self.assertTrue(result.auto_approve)

    def test_exact_high_boundary(self):
        result = classify_score(0.80)
        self.assertEqual(result.tier, QualityTier.HIGH)

    def test_acceptable_tier(self):
        result = classify_score(0.75)
        self.assertEqual(result.tier, QualityTier.ACCEPTABLE)
        self.assertTrue(result.auto_approve)

    def test_exact_acceptable_boundary(self):
        result = classify_score(0.70)
        self.assertEqual(result.tier, QualityTier.ACCEPTABLE)

    def test_review_tier(self):
        result = classify_score(0.60)
        self.assertEqual(result.tier, QualityTier.REVIEW)
        self.assertFalse(result.auto_approve)

    def test_zero_score_review(self):
        result = classify_score(0.0)
        self.assertEqual(result.tier, QualityTier.REVIEW)

    def test_score_above_1_clamped(self):
        result = classify_score(1.5)
        self.assertEqual(result.tier, QualityTier.EXCELLENT)

    def test_negative_score_clamped_to_review(self):
        result = classify_score(-0.5)
        self.assertEqual(result.tier, QualityTier.REVIEW)

    def test_label_contains_tier_info(self):
        result = classify_score(0.92)
        self.assertIn("Excellent", result.label)

    def test_score_preserved_in_result(self):
        result = classify_score(0.83)
        self.assertAlmostEqual(result.score, 0.83, places=2)


class TestIsHighQuality(unittest.TestCase):

    def test_excellent_is_high_quality(self):
        self.assertTrue(is_high_quality(0.92))

    def test_high_is_high_quality(self):
        self.assertTrue(is_high_quality(0.82))

    def test_acceptable_is_not_high_quality(self):
        self.assertFalse(is_high_quality(0.75))

    def test_review_is_not_high_quality(self):
        self.assertFalse(is_high_quality(0.50))

    def test_exact_threshold_is_high_quality(self):
        self.assertTrue(is_high_quality(0.80))


class TestQualitySummary(unittest.TestCase):

    def test_empty_returns_zeros(self):
        result = quality_summary([])
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["auto_approve_rate"], 0.0)

    def test_all_excellent(self):
        scores = [0.92, 0.95, 0.91]
        result = quality_summary(scores)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["excellent"], 3)
        self.assertEqual(result["auto_approve_rate"], 1.0)

    def test_mixed_tiers(self):
        scores = [0.95, 0.85, 0.75, 0.60]
        result = quality_summary(scores)
        self.assertEqual(result["excellent"], 1)
        self.assertEqual(result["high"], 1)
        self.assertEqual(result["acceptable"], 1)
        self.assertEqual(result["review"], 1)
        # 3 out of 4 auto-approved
        self.assertAlmostEqual(result["auto_approve_rate"], 0.75, places=2)

    def test_total_matches_input_length(self):
        scores = [0.7, 0.8, 0.9, 0.6, 0.5]
        result = quality_summary(scores)
        self.assertEqual(result["total"], 5)

    def test_buckets_sum_to_total(self):
        scores = [0.95, 0.82, 0.72, 0.55, 0.88]
        result = quality_summary(scores)
        bucket_sum = (result["excellent"] + result["high"] +
                      result["acceptable"] + result["review"])
        self.assertEqual(bucket_sum, result["total"])
