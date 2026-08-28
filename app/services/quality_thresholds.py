"""Configurable quality threshold service (ENH-004).

Provides a single source of truth for quality tier classification.
Thresholds are read from Settings so they can be changed via environment
variables without code changes.

Scale: 0-1  (matching ResourceScoringEngine's composite_score output).

Tiers (default values, all overridable via env vars):
  EXCELLENT   ≥ 0.90   — auto-approve, surface prominently
  HIGH        ≥ 0.80   — auto-approve
  ACCEPTABLE  ≥ 0.70   — accept with note
  REVIEW      < 0.70   — flag for human review / soft-reject in automated flow
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass

from app.config import settings


class QualityTier(str, Enum):
    EXCELLENT = "excellent"
    HIGH = "high"
    ACCEPTABLE = "acceptable"
    REVIEW = "review"


@dataclass(frozen=True)
class QualityAssessment:
    """Result of classifying a resource's composite score."""
    score: float
    tier: QualityTier
    label: str          # human-readable label
    auto_approve: bool  # whether the resource should be approved without human review


def classify_score(composite_score: float) -> QualityAssessment:
    """Classify a 0-1 composite score into a quality tier.

    Parameters
    ----------
    composite_score : float
        The composite score produced by ResourceScoringEngine (0-1).

    Returns
    -------
    QualityAssessment with tier, label, and auto_approve flag.
    """
    s = max(0.0, min(1.0, composite_score))  # clamp to [0, 1]

    if s >= settings.QUALITY_THRESHOLD_EXCELLENT:
        return QualityAssessment(
            score=s,
            tier=QualityTier.EXCELLENT,
            label=f"Excellent (≥{settings.QUALITY_THRESHOLD_EXCELLENT:.0%})",
            auto_approve=True,
        )
    if s >= settings.QUALITY_THRESHOLD_HIGH:
        return QualityAssessment(
            score=s,
            tier=QualityTier.HIGH,
            label=f"High Quality (≥{settings.QUALITY_THRESHOLD_HIGH:.0%})",
            auto_approve=True,
        )
    if s >= settings.QUALITY_THRESHOLD_ACCEPTABLE:
        return QualityAssessment(
            score=s,
            tier=QualityTier.ACCEPTABLE,
            label=f"Acceptable (≥{settings.QUALITY_THRESHOLD_ACCEPTABLE:.0%})",
            auto_approve=True,
        )
    return QualityAssessment(
        score=s,
        tier=QualityTier.REVIEW,
        label=f"Needs Review (<{settings.QUALITY_THRESHOLD_ACCEPTABLE:.0%})",
        auto_approve=False,
    )


def is_high_quality(composite_score: float) -> bool:
    """Return True if the score meets the HIGH or EXCELLENT threshold."""
    return composite_score >= settings.QUALITY_THRESHOLD_HIGH


def quality_summary(scores: list[float]) -> dict:
    """Return a distribution summary for a list of composite scores."""
    if not scores:
        return {
            "total": 0,
            "excellent": 0,
            "high": 0,
            "acceptable": 0,
            "review": 0,
            "auto_approve_rate": 0.0,
        }

    buckets: dict[str, int] = {
        "excellent": 0, "high": 0, "acceptable": 0, "review": 0
    }
    for s in scores:
        tier = classify_score(s).tier.value
        buckets[tier] += 1

    approved = buckets["excellent"] + buckets["high"] + buckets["acceptable"]
    return {
        "total": len(scores),
        **buckets,
        "auto_approve_rate": round(approved / len(scores), 3),
    }
