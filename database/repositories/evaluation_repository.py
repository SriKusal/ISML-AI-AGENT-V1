"""CRUD repository for the ResourceEvaluation model."""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import ResourceEvaluation
from app.logging import get_logger

logger = get_logger("database.repositories.evaluation")


class EvaluationRepository:
    """All database operations for the resource_evaluations table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        resource_id: uuid.UUID,
        # Relevance
        relevance_topic_match: float = 0.0,
        relevance_keyword_match: float = 0.0,
        relevance_objective_coverage: float = 0.0,
        relevance_difficulty_alignment: float = 0.0,
        relevance_overall: float = 0.0,
        # Quality
        quality_content_accuracy: float = 0.0,
        quality_pedagogical_effectiveness: float = 0.0,
        quality_engagement_level: float = 0.0,
        quality_comprehensiveness: float = 0.0,
        quality_clarity: float = 0.0,
        quality_interactivity: float = 0.0,
        quality_overall: float = 0.0,
        # Credibility
        credibility_source_authority: float = 0.0,
        credibility_publication_reputation: float = 0.0,
        credibility_author_expertise: float = 0.0,
        credibility_peer_review_status: float = 0.0,
        credibility_currency: float = 0.0,
        credibility_overall: float = 0.0,
        # Effectiveness
        effectiveness_skill_development: float = 0.0,
        effectiveness_knowledge_retention: float = 0.0,
        effectiveness_practical_applicability: float = 0.0,
        effectiveness_motivation_factor: float = 0.0,
        effectiveness_assessment_compatibility: float = 0.0,
        effectiveness_overall: float = 0.0,
        # Composite
        composite_score: float = 0.0,
        rationale: Optional[dict] = None,
    ) -> ResourceEvaluation:
        """Create and persist a full evaluation for a resource."""
        evaluation = ResourceEvaluation(
            resource_id=resource_id,
            relevance_topic_match=relevance_topic_match,
            relevance_keyword_match=relevance_keyword_match,
            relevance_objective_coverage=relevance_objective_coverage,
            relevance_difficulty_alignment=relevance_difficulty_alignment,
            relevance_overall=relevance_overall,
            quality_content_accuracy=quality_content_accuracy,
            quality_pedagogical_effectiveness=quality_pedagogical_effectiveness,
            quality_engagement_level=quality_engagement_level,
            quality_comprehensiveness=quality_comprehensiveness,
            quality_clarity=quality_clarity,
            quality_interactivity=quality_interactivity,
            quality_overall=quality_overall,
            credibility_source_authority=credibility_source_authority,
            credibility_publication_reputation=credibility_publication_reputation,
            credibility_author_expertise=credibility_author_expertise,
            credibility_peer_review_status=credibility_peer_review_status,
            credibility_currency=credibility_currency,
            credibility_overall=credibility_overall,
            effectiveness_skill_development=effectiveness_skill_development,
            effectiveness_knowledge_retention=effectiveness_knowledge_retention,
            effectiveness_practical_applicability=effectiveness_practical_applicability,
            effectiveness_motivation_factor=effectiveness_motivation_factor,
            effectiveness_assessment_compatibility=effectiveness_assessment_compatibility,
            effectiveness_overall=effectiveness_overall,
            composite_score=composite_score,
            rationale=rationale,
        )
        self.session.add(evaluation)
        await self.session.flush()
        logger.debug("Created evaluation for resource_id=%s (composite=%.3f)", resource_id, composite_score)
        return evaluation

    @classmethod
    def from_score_dict(cls, resource_id: uuid.UUID, score_dict: dict) -> dict:
        """Map a ComprehensiveResourceScore.to_dict() output to constructor kwargs.

        Use this to bridge the scoring engine output directly to create().
        """
        rel = score_dict.get("relevance", {})
        edu = score_dict.get("educational_quality", {})
        cred = score_dict.get("credibility", {})
        eff = score_dict.get("learning_effectiveness", {})
        return {
            "resource_id": resource_id,
            "relevance_topic_match": rel.get("topic_match", 0.0),
            "relevance_keyword_match": rel.get("keyword_match", 0.0),
            "relevance_objective_coverage": rel.get("learning_objective_coverage", 0.0),
            "relevance_difficulty_alignment": rel.get("difficulty_alignment", 0.0),
            "relevance_overall": rel.get("overall", 0.0),
            "quality_content_accuracy": edu.get("content_accuracy", 0.0),
            "quality_pedagogical_effectiveness": edu.get("pedagogical_effectiveness", 0.0),
            "quality_engagement_level": edu.get("engagement_level", 0.0),
            "quality_comprehensiveness": edu.get("comprehensiveness", 0.0),
            "quality_clarity": edu.get("clarity", 0.0),
            "quality_interactivity": edu.get("interactivity", 0.0),
            "quality_overall": edu.get("overall", 0.0),
            "credibility_source_authority": cred.get("source_authority", 0.0),
            "credibility_publication_reputation": cred.get("publication_reputation", 0.0),
            "credibility_author_expertise": cred.get("author_expertise", 0.0),
            "credibility_peer_review_status": cred.get("peer_review_status", 0.0),
            "credibility_currency": cred.get("currency", 0.0),
            "credibility_overall": cred.get("overall", 0.0),
            "effectiveness_skill_development": eff.get("skill_development", 0.0),
            "effectiveness_knowledge_retention": eff.get("knowledge_retention", 0.0),
            "effectiveness_practical_applicability": eff.get("practical_applicability", 0.0),
            "effectiveness_motivation_factor": eff.get("motivation_factor", 0.0),
            "effectiveness_assessment_compatibility": eff.get("assessment_compatibility", 0.0),
            "effectiveness_overall": eff.get("overall", 0.0),
            "composite_score": score_dict.get("composite_score", 0.0),
        }

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_resource_id(
        self, resource_id: uuid.UUID
    ) -> Optional[ResourceEvaluation]:
        """Fetch the evaluation for a specific resource."""
        result = await self.session.execute(
            select(ResourceEvaluation).where(
                ResourceEvaluation.resource_id == resource_id
            )
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def upsert(
        self, resource_id: uuid.UUID, **fields
    ) -> ResourceEvaluation:
        """Create or update the evaluation for a resource."""
        evaluation = await self.get_by_resource_id(resource_id)
        if not evaluation:
            evaluation = ResourceEvaluation(resource_id=resource_id)
            self.session.add(evaluation)
        for key, value in fields.items():
            if hasattr(evaluation, key):
                setattr(evaluation, key, value)
        await self.session.flush()
        return evaluation

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_by_resource_id(self, resource_id: uuid.UUID) -> bool:
        """Delete evaluation for a resource."""
        evaluation = await self.get_by_resource_id(resource_id)
        if not evaluation:
            return False
        await self.session.delete(evaluation)
        await self.session.flush()
        return True
