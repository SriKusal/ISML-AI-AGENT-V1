"""Resource ranking and recommendation engine.

Ranks and recommends resources based on multi-dimensional scores.
Provides categorized recommendations for different learning scenarios.
"""

from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

from app.services.resource_evaluation import ComprehensiveResourceScore
from app.logging import get_logger

logger = get_logger("app.services.resource_ranking")


class ResourceCategory(str, Enum):
    """Resource category for learning sequence."""
    FOUNDATION = "foundation"  # Foundational concepts
    PRACTICE = "practice"  # Hands-on practice
    MASTERY = "mastery"  # Advanced mastery
    REFERENCE = "reference"  # Reference materials
    ASSESSMENT = "assessment"  # Assessment tools


@dataclass
class RankedResource:
    """A ranked resource with placement information."""
    
    rank: int
    resource_id: str
    title: str
    url: str
    resource_type: str
    composite_score: float
    category: ResourceCategory
    reason: str  # Why this resource is recommended
    score_breakdown: dict = field(default_factory=dict)


class ResourceRankingEngine:
    """Engine for ranking and recommending resources."""
    
    @staticmethod
    def categorize_resource(
        scored_resource: ComprehensiveResourceScore,
    ) -> ResourceCategory:
        """Categorize a resource for learning sequence.
        
        Args:
            scored_resource: Scored resource object
            
        Returns:
            ResourceCategory for the resource
        """
        composite = scored_resource.composite_score
        relevance = scored_resource.relevance.overall_score
        quality = scored_resource.educational_quality.overall_score
        
        resource_type = scored_resource.resource_type.lower()
        
        # Foundation: high relevance, beginner-friendly, comprehensive
        if relevance > 0.8 and quality > 0.75 and composite > 0.75:
            return ResourceCategory.FOUNDATION
        
        # Practice: high engagement, interactive, skill-focused
        if resource_type in ['video', 'article'] and quality > 0.7:
            return ResourceCategory.PRACTICE
        
        # Mastery: very high quality, advanced content
        if quality > 0.85 and composite > 0.80:
            return ResourceCategory.MASTERY
        
        # Reference: good credibility, comprehensive
        if scored_resource.credibility.overall_score > 0.8:
            return ResourceCategory.REFERENCE
        
        # Assessment: for self-testing
        if 'quiz' in scored_resource.title.lower() or 'exercise' in scored_resource.title.lower():
            return ResourceCategory.ASSESSMENT
        
        # Default to reference
        return ResourceCategory.REFERENCE
    
    @staticmethod
    def generate_recommendation_reason(
        scored_resource: ComprehensiveResourceScore,
        category: ResourceCategory,
    ) -> str:
        """Generate a human-readable recommendation reason.
        
        Args:
            scored_resource: Scored resource object
            category: Resource category
            
        Returns:
            Recommendation reason string
        """
        strengths = []
        
        if scored_resource.relevance.overall_score > 0.85:
            strengths.append("highly relevant to learning objectives")
        elif scored_resource.relevance.overall_score > 0.75:
            strengths.append("well-aligned with topic")
        
        if scored_resource.educational_quality.overall_score > 0.85:
            strengths.append("excellent educational quality")
        elif scored_resource.educational_quality.overall_score > 0.75:
            strengths.append("strong pedagogical approach")
        
        if scored_resource.credibility.overall_score > 0.85:
            strengths.append("highly credible source")
        
        if scored_resource.learning_effectiveness.overall_score > 0.80:
            strengths.append("proven learning effectiveness")
        
        if not strengths:
            strengths = ["relevant content", "suitable for learning"]
        
        reason = f"{category.value.capitalize()} resource: {', '.join(strengths[:2])}"
        return reason
    
    @staticmethod
    def rank_resources(
        scored_resources: list[ComprehensiveResourceScore],
        sort_strategy: str = "composite",
    ) -> list[RankedResource]:
        """Rank resources using specified strategy.
        
        Args:
            scored_resources: List of scored resources
            sort_strategy: Sorting strategy (composite, relevance, quality, credibility)
            
        Returns:
            List of ranked resources sorted by strategy
        """
        logger.info(f"Ranking {len(scored_resources)} resources using {sort_strategy} strategy")
        
        # Sort based on strategy
        if sort_strategy == "composite":
            sorted_resources = sorted(
                scored_resources,
                key=lambda r: r.composite_score,
                reverse=True
            )
        elif sort_strategy == "relevance":
            sorted_resources = sorted(
                scored_resources,
                key=lambda r: r.relevance.overall_score,
                reverse=True
            )
        elif sort_strategy == "quality":
            sorted_resources = sorted(
                scored_resources,
                key=lambda r: r.educational_quality.overall_score,
                reverse=True
            )
        elif sort_strategy == "credibility":
            sorted_resources = sorted(
                scored_resources,
                key=lambda r: r.credibility.overall_score,
                reverse=True
            )
        else:
            sorted_resources = sorted(
                scored_resources,
                key=lambda r: r.composite_score,
                reverse=True
            )
        
        # Create ranked resources with metadata
        ranked = []
        for rank, scored in enumerate(sorted_resources, 1):
            category = ResourceRankingEngine.categorize_resource(scored)
            reason = ResourceRankingEngine.generate_recommendation_reason(scored, category)
            
            ranked.append(RankedResource(
                rank=rank,
                resource_id=scored.resource_id,
                title=scored.title,
                url=scored.url,
                resource_type=scored.resource_type,
                composite_score=scored.composite_score,
                category=category,
                reason=reason,
                score_breakdown={
                    "relevance": scored.relevance.overall_score,
                    "educational_quality": scored.educational_quality.overall_score,
                    "credibility": scored.credibility.overall_score,
                    "learning_effectiveness": scored.learning_effectiveness.overall_score,
                },
            ))
        
        logger.info(f"Ranked {len(ranked)} resources")
        return ranked


class RecommendationEngine:
    """Engine for generating learning recommendations."""
    
    @staticmethod
    def generate_learning_sequence(
        ranked_resources: list[RankedResource],
    ) -> dict:
        """Generate recommended learning sequence from ranked resources.
        
        Args:
            ranked_resources: List of ranked resources
            
        Returns:
            Learning sequence organized by category
        """
        logger.info("Generating learning sequence from ranked resources")
        
        sequence = {
            ResourceCategory.FOUNDATION: [],
            ResourceCategory.PRACTICE: [],
            ResourceCategory.MASTERY: [],
            ResourceCategory.REFERENCE: [],
            ResourceCategory.ASSESSMENT: [],
        }
        
        # Categorize resources
        for resource in ranked_resources:
            category = resource.category
            sequence[category].append({
                "rank": resource.rank,
                "title": resource.title,
                "url": resource.url,
                "type": resource.resource_type,
                "score": resource.composite_score,
                "reason": resource.reason,
            })
        
        # Sort within categories by score
        for category in sequence:
            sequence[category].sort(key=lambda r: r['score'], reverse=True)
        
        # Build recommended order
        recommended_order = []
        
        # 1. Foundation first (strongest resources)
        recommended_order.extend(sequence[ResourceCategory.FOUNDATION][:3])
        
        # 2. Then practice resources
        recommended_order.extend(sequence[ResourceCategory.PRACTICE][:4])
        
        # 3. Reference materials for context
        recommended_order.extend(sequence[ResourceCategory.REFERENCE][:2])
        
        # 4. Assessment for validation
        recommended_order.extend(sequence[ResourceCategory.ASSESSMENT][:2])
        
        # 5. Mastery for deep learning
        recommended_order.extend(sequence[ResourceCategory.MASTERY][:2])
        
        logger.info(f"Generated learning sequence with {len(recommended_order)} recommended resources")
        
        return {
            "learning_sequence": recommended_order,
            "by_category": {
                category.value: resources
                for category, resources in sequence.items()
                if resources
            },
            "total_recommendations": len(recommended_order),
        }
    
    @staticmethod
    def generate_personalized_recommendations(
        ranked_resources: list[RankedResource],
        difficulty_level: str = "Beginner",
        preferred_type: Optional[str] = None,
    ) -> dict:
        """Generate personalized recommendations based on learner profile.
        
        Args:
            ranked_resources: List of ranked resources
            difficulty_level: Beginner, Intermediate, Advanced
            preferred_type: Preferred resource type (video, pdf, article, etc.)
            
        Returns:
            Personalized recommendations
        """
        logger.info(f"Generating personalized recommendations for {difficulty_level} level")
        
        # Filter by difficulty level (simple heuristic)
        filtered = ranked_resources
        
        # Filter by preferred type if specified
        if preferred_type:
            type_filtered = [r for r in filtered if preferred_type.lower() in r.resource_type.lower()]
            if type_filtered:
                filtered = type_filtered
        
        # Get top recommendations by category
        recommendations = {
            "essential": [],
            "recommended": [],
            "supplementary": [],
        }
        
        # Essential: high-ranked, high-quality resources
        for resource in filtered[:5]:
            if resource.composite_score > 0.80:
                recommendations["essential"].append({
                    "title": resource.title,
                    "url": resource.url,
                    "type": resource.resource_type,
                    "why": resource.reason,
                })
        
        # Recommended: good quality resources
        for resource in filtered[5:10]:
            if resource.composite_score > 0.70:
                recommendations["recommended"].append({
                    "title": resource.title,
                    "url": resource.url,
                    "type": resource.resource_type,
                    "why": resource.reason,
                })
        
        # Supplementary: additional resources
        for resource in filtered[10:15]:
            if resource.composite_score > 0.60:
                recommendations["supplementary"].append({
                    "title": resource.title,
                    "url": resource.url,
                    "type": resource.resource_type,
                    "why": resource.reason,
                })
        
        logger.info(f"Generated personalized recommendations: {len(recommendations['essential'])} essential, {len(recommendations['recommended'])} recommended")
        
        return recommendations
    
    @staticmethod
    def generate_summary_statistics(
        ranked_resources: list[RankedResource],
    ) -> dict:
        """Generate summary statistics about ranked resources.
        
        Args:
            ranked_resources: List of ranked resources
            
        Returns:
            Summary statistics
        """
        if not ranked_resources:
            return {
                "total_resources": 0,
                "average_score": 0.0,
                "by_type": {},
                "by_category": {},
                "score_distribution": {},
            }
        
        scores = [r.composite_score for r in ranked_resources]
        
        # Score distribution
        distribution = {
            "excellent (0.85+)": len([s for s in scores if s >= 0.85]),
            "good (0.70-0.84)": len([s for s in scores if 0.70 <= s < 0.85]),
            "fair (0.55-0.69)": len([s for s in scores if 0.55 <= s < 0.70]),
            "poor (<0.55)": len([s for s in scores if s < 0.55]),
        }
        
        # By type
        by_type = {}
        for resource in ranked_resources:
            rtype = resource.resource_type
            if rtype not in by_type:
                by_type[rtype] = 0
            by_type[rtype] += 1
        
        # By category
        by_category = {}
        for resource in ranked_resources:
            cat = resource.category.value
            if cat not in by_category:
                by_category[cat] = 0
            by_category[cat] += 1
        
        return {
            "total_resources": len(ranked_resources),
            "average_score": round(sum(scores) / len(scores), 3),
            "highest_score": round(max(scores), 3),
            "lowest_score": round(min(scores), 3),
            "by_type": by_type,
            "by_category": by_category,
            "score_distribution": distribution,
        }
