"""Resource quality evaluation framework for educational resources.

Implements multi-dimensional scoring for:
- Relevance to learning objectives
- Educational quality and effectiveness
- Source credibility
- Learning effectiveness indicators
"""

from typing import Optional
from dataclasses import dataclass, field

from app.logging import get_logger

logger = get_logger("app.services.resource_evaluation")


@dataclass
class RelevanceScore:
    """Relevance scoring for a resource against learning objectives."""
    
    topic_match: float = 0.0  # 0-1: How well the resource matches the topic
    keyword_match: float = 0.0  # 0-1: Keyword/concept alignment
    learning_objective_coverage: float = 0.0  # 0-1: Covers learning objectives
    difficulty_alignment: float = 0.0  # 0-1: Matches difficulty level
    
    overall_score: float = field(init=False)
    
    def __post_init__(self):
        """Calculate overall relevance score."""
        weights = {
            'topic_match': 0.3,
            'keyword_match': 0.25,
            'learning_objective_coverage': 0.25,
            'difficulty_alignment': 0.2,
        }
        self.overall_score = (
            self.topic_match * weights['topic_match'] +
            self.keyword_match * weights['keyword_match'] +
            self.learning_objective_coverage * weights['learning_objective_coverage'] +
            self.difficulty_alignment * weights['difficulty_alignment']
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "topic_match": round(self.topic_match, 3),
            "keyword_match": round(self.keyword_match, 3),
            "learning_objective_coverage": round(self.learning_objective_coverage, 3),
            "difficulty_alignment": round(self.difficulty_alignment, 3),
            "overall": round(self.overall_score, 3),
        }


@dataclass
class EducationalQualityScore:
    """Educational quality scoring for a resource."""
    
    content_accuracy: float = 0.0  # 0-1: Factual correctness
    pedagogical_effectiveness: float = 0.0  # 0-1: Teaching methodology
    engagement_level: float = 0.0  # 0-1: Student engagement potential
    comprehensiveness: float = 0.0  # 0-1: Content coverage
    clarity: float = 0.0  # 0-1: Explanation clarity
    interactivity: float = 0.0  # 0-1: Interactive elements
    
    overall_score: float = field(init=False)
    
    def __post_init__(self):
        """Calculate overall educational quality score."""
        weights = {
            'content_accuracy': 0.25,
            'pedagogical_effectiveness': 0.20,
            'engagement_level': 0.15,
            'comprehensiveness': 0.15,
            'clarity': 0.15,
            'interactivity': 0.10,
        }
        self.overall_score = (
            self.content_accuracy * weights['content_accuracy'] +
            self.pedagogical_effectiveness * weights['pedagogical_effectiveness'] +
            self.engagement_level * weights['engagement_level'] +
            self.comprehensiveness * weights['comprehensiveness'] +
            self.clarity * weights['clarity'] +
            self.interactivity * weights['interactivity']
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "content_accuracy": round(self.content_accuracy, 3),
            "pedagogical_effectiveness": round(self.pedagogical_effectiveness, 3),
            "engagement_level": round(self.engagement_level, 3),
            "comprehensiveness": round(self.comprehensiveness, 3),
            "clarity": round(self.clarity, 3),
            "interactivity": round(self.interactivity, 3),
            "overall": round(self.overall_score, 3),
        }


@dataclass
class CredibilityScore:
    """Source credibility scoring."""
    
    source_authority: float = 0.0  # 0-1: Authority in domain
    publication_reputation: float = 0.0  # 0-1: Publication credibility
    author_expertise: float = 0.0  # 0-1: Author credentials
    peer_review_status: float = 0.0  # 0-1: Peer review/verification
    currency: float = 0.0  # 0-1: Content freshness
    
    overall_score: float = field(init=False)
    
    def __post_init__(self):
        """Calculate overall credibility score."""
        weights = {
            'source_authority': 0.25,
            'publication_reputation': 0.25,
            'author_expertise': 0.20,
            'peer_review_status': 0.20,
            'currency': 0.10,
        }
        self.overall_score = (
            self.source_authority * weights['source_authority'] +
            self.publication_reputation * weights['publication_reputation'] +
            self.author_expertise * weights['author_expertise'] +
            self.peer_review_status * weights['peer_review_status'] +
            self.currency * weights['currency']
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "source_authority": round(self.source_authority, 3),
            "publication_reputation": round(self.publication_reputation, 3),
            "author_expertise": round(self.author_expertise, 3),
            "peer_review_status": round(self.peer_review_status, 3),
            "currency": round(self.currency, 3),
            "overall": round(self.overall_score, 3),
        }


@dataclass
class LearningEffectivenessScore:
    """Learning effectiveness scoring based on indicators."""
    
    skill_development: float = 0.0  # 0-1: Supports skill building
    knowledge_retention: float = 0.0  # 0-1: Aids long-term retention
    practical_applicability: float = 0.0  # 0-1: Real-world relevance
    motivation_factor: float = 0.0  # 0-1: Learner motivation impact
    assessment_compatibility: float = 0.0  # 0-1: Works with assessment
    
    overall_score: float = field(init=False)
    
    def __post_init__(self):
        """Calculate overall learning effectiveness score."""
        weights = {
            'skill_development': 0.25,
            'knowledge_retention': 0.25,
            'practical_applicability': 0.20,
            'motivation_factor': 0.15,
            'assessment_compatibility': 0.15,
        }
        self.overall_score = (
            self.skill_development * weights['skill_development'] +
            self.knowledge_retention * weights['knowledge_retention'] +
            self.practical_applicability * weights['practical_applicability'] +
            self.motivation_factor * weights['motivation_factor'] +
            self.assessment_compatibility * weights['assessment_compatibility']
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "skill_development": round(self.skill_development, 3),
            "knowledge_retention": round(self.knowledge_retention, 3),
            "practical_applicability": round(self.practical_applicability, 3),
            "motivation_factor": round(self.motivation_factor, 3),
            "assessment_compatibility": round(self.assessment_compatibility, 3),
            "overall": round(self.overall_score, 3),
        }


@dataclass
class ComprehensiveResourceScore:
    """Comprehensive multi-dimensional score for a resource."""
    
    resource_id: str
    title: str
    resource_type: str
    url: str
    
    relevance: RelevanceScore = field(default_factory=RelevanceScore)
    educational_quality: EducationalQualityScore = field(default_factory=EducationalQualityScore)
    credibility: CredibilityScore = field(default_factory=CredibilityScore)
    learning_effectiveness: LearningEffectivenessScore = field(default_factory=LearningEffectivenessScore)
    
    composite_score: float = field(init=False)
    
    def __post_init__(self):
        """Calculate composite score."""
        weights = {
            'relevance': 0.30,
            'educational_quality': 0.30,
            'credibility': 0.25,
            'learning_effectiveness': 0.15,
        }
        self.composite_score = (
            self.relevance.overall_score * weights['relevance'] +
            self.educational_quality.overall_score * weights['educational_quality'] +
            self.credibility.overall_score * weights['credibility'] +
            self.learning_effectiveness.overall_score * weights['learning_effectiveness']
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "resource_id": self.resource_id,
            "title": self.title,
            "resource_type": self.resource_type,
            "url": self.url,
            "relevance": self.relevance.to_dict(),
            "educational_quality": self.educational_quality.to_dict(),
            "credibility": self.credibility.to_dict(),
            "learning_effectiveness": self.learning_effectiveness.to_dict(),
            "composite_score": round(self.composite_score, 3),
        }


class ResourceScoringEngine:
    """Engine for scoring resources across multiple dimensions."""
    
    @staticmethod
    def score_relevance(
        resource: dict,
        topic_understanding: dict,
    ) -> RelevanceScore:
        """Score resource relevance against learning objectives.
        
        Args:
            resource: Resource metadata dictionary
            topic_understanding: Learning context with objectives and concepts
            
        Returns:
            RelevanceScore with dimension scores
        """
        logger.debug(f"Scoring relevance for: {resource.get('title', 'Unknown')}")
        
        title_lower = resource.get('title', '').lower()
        topic_lower = topic_understanding.get('topic', '').lower()
        keywords = [kw.lower() for kw in resource.get('keywords', [])]
        
        # Topic match
        topic_match = 0.9 if topic_lower in title_lower else (
            0.7 if topic_lower in ' '.join(keywords) else 0.5
        )
        
        # Keyword match
        topic_keywords = topic_understanding.get('related_concepts', [])
        keyword_overlap = sum(1 for kw in topic_keywords if kw.lower() in ' '.join(keywords).lower())
        keyword_match = min(1.0, (keyword_overlap / max(len(topic_keywords), 1)) * 0.8 + 0.2)
        
        # Learning objective coverage
        objectives = topic_understanding.get('learning_objectives', [])
        objective_coverage = 0.7 if any(obj.lower() in title_lower for obj in objectives) else 0.5
        
        # Difficulty alignment
        resource_difficulty = resource.get('difficulty_level', 'Unknown').lower()
        context_difficulty = topic_understanding.get('difficulty_level', 'Beginner').lower()
        difficulty_match = 0.9 if resource_difficulty == context_difficulty else (
            0.7 if resource_difficulty in ['beginner', 'intermediate', 'advanced'] else 0.5
        )
        
        return RelevanceScore(
            topic_match=topic_match,
            keyword_match=keyword_match,
            learning_objective_coverage=objective_coverage,
            difficulty_alignment=difficulty_match,
        )
    
    @staticmethod
    def score_educational_quality(resource: dict) -> EducationalQualityScore:
        """Score resource educational quality based on metadata indicators.
        
        Args:
            resource: Resource metadata dictionary
            
        Returns:
            EducationalQualityScore with dimension scores
        """
        logger.debug(f"Scoring educational quality for: {resource.get('title', 'Unknown')}")
        
        resource_type = resource.get('resource_type', '').lower()
        source = resource.get('source', '').lower()
        summary = resource.get('summary', '').lower()
        
        # Content accuracy (higher for academic sources)
        accuracy = 0.9 if 'scholar' in source or 'academic' in source else (
            0.85 if 'khan' in source or 'edx' in source or 'coursera' in source else 0.7
        )
        
        # Pedagogical effectiveness
        pedagogy = 0.85 if resource_type == 'video' else (
            0.80 if resource_type == 'article' else (
                0.75 if resource_type == 'pdf' else 0.6
            )
        )
        
        # Engagement level
        engagement = 0.9 if resource_type == 'video' else (
            0.75 if resource_type == 'article' else 0.6
        )
        
        # Comprehensiveness
        comprehensiveness = 0.8 if resource.get('estimated_study_time', 0) >= 20 else (
            0.7 if resource.get('estimated_study_time', 0) >= 10 else 0.5
        )
        
        # Clarity
        clarity = 0.8 if 'tutorial' in summary or 'guide' in summary or 'learn' in summary else 0.6
        
        # Interactivity
        interactivity = 0.85 if 'interactive' in summary or resource_type == 'video' else 0.5
        
        return EducationalQualityScore(
            content_accuracy=accuracy,
            pedagogical_effectiveness=pedagogy,
            engagement_level=engagement,
            comprehensiveness=comprehensiveness,
            clarity=clarity,
            interactivity=interactivity,
        )
    
    @staticmethod
    def score_credibility(resource: dict) -> CredibilityScore:
        """Score source credibility based on source reputation and indicators.
        
        Args:
            resource: Resource metadata dictionary
            
        Returns:
            CredibilityScore with dimension scores
        """
        logger.debug(f"Scoring credibility for: {resource.get('title', 'Unknown')}")
        
        source = resource.get('source', '').lower()
        credibility_base = resource.get('credibility_score', 0.5)
        
        # Source authority
        authority_map = {
            'scholar': 0.95,
            'khan': 0.95,
            'edx': 0.95,
            'coursera': 0.90,
            'youtube': 0.70,
            'medium': 0.65,
            'wikipedia': 0.75,
        }
        authority = next(
            (v for k, v in authority_map.items() if k in source),
            credibility_base
        )
        
        # Publication reputation
        reputation = 0.9 if source in ['scholar', 'khan', 'edx', 'coursera'] else (
            0.75 if source in ['wikipedia', 'youtube'] else 0.6
        )
        
        # Author expertise (higher for academic/institutional sources)
        author = resource.get('author', '')
        expertise = 0.85 if any(org in author.lower() for org in ['academy', 'institute', 'university']) else 0.6
        
        # Peer review status
        peer_review = 0.95 if 'scholar' in source else (
            0.80 if source in ['edx', 'coursera'] else 0.5
        )
        
        # Currency (freshness)
        import datetime
        pub_date_str = resource.get('publication_date', '')
        try:
            pub_date = datetime.datetime.strptime(pub_date_str, '%Y-%m-%d')
            days_old = (datetime.datetime.now() - pub_date).days
            currency = 0.95 if days_old < 180 else (
                0.80 if days_old < 365 else (
                    0.65 if days_old < 730 else 0.5
                )
            )
        except:
            currency = 0.6
        
        return CredibilityScore(
            source_authority=authority,
            publication_reputation=reputation,
            author_expertise=expertise,
            peer_review_status=peer_review,
            currency=currency,
        )
    
    @staticmethod
    def score_learning_effectiveness(resource: dict) -> LearningEffectivenessScore:
        """Score learning effectiveness indicators.
        
        Args:
            resource: Resource metadata dictionary
            
        Returns:
            LearningEffectivenessScore with dimension scores
        """
        logger.debug(f"Scoring learning effectiveness for: {resource.get('title', 'Unknown')}")
        
        resource_type = resource.get('resource_type', '').lower()
        summary = resource.get('summary', '').lower()
        study_time = resource.get('estimated_study_time', 15)
        
        # Skill development
        skill_dev = 0.9 if any(x in summary for x in ['practice', 'exercise', 'interactive']) else 0.6
        
        # Knowledge retention
        retention = 0.85 if resource_type == 'video' else (
            0.80 if resource_type == 'article' else 0.7
        )
        
        # Practical applicability
        practical = 0.9 if any(x in summary for x in ['practical', 'real-world', 'example', 'application']) else 0.5
        
        # Motivation factor
        motivation = 0.85 if resource_type == 'video' else (
            0.75 if resource_type == 'article' else 0.6
        )
        
        # Assessment compatibility
        assessment = 0.9 if any(x in summary for x in ['quiz', 'exercise', 'assessment', 'test']) else (
            0.7 if resource_type in ['pdf', 'article'] else 0.5
        )
        
        return LearningEffectivenessScore(
            skill_development=skill_dev,
            knowledge_retention=retention,
            practical_applicability=practical,
            motivation_factor=motivation,
            assessment_compatibility=assessment,
        )
    
    @staticmethod
    def score_resource(
        resource: dict,
        topic_understanding: dict,
    ) -> ComprehensiveResourceScore:
        """Generate comprehensive score for a resource.
        
        Args:
            resource: Resource metadata dictionary
            topic_understanding: Learning context
            
        Returns:
            ComprehensiveResourceScore with all dimension scores
        """
        logger.info(f"Comprehensive scoring for: {resource.get('title', 'Unknown')}")
        
        # Generate unique resource ID
        resource_id = f"{resource.get('source', 'unknown')}_{hash(resource.get('url', '')) % 10000}"
        
        return ComprehensiveResourceScore(
            resource_id=resource_id,
            title=resource.get('title', 'Unknown'),
            resource_type=resource.get('resource_type', 'unknown'),
            url=resource.get('url', ''),
            relevance=ResourceScoringEngine.score_relevance(resource, topic_understanding),
            educational_quality=ResourceScoringEngine.score_educational_quality(resource),
            credibility=ResourceScoringEngine.score_credibility(resource),
            learning_effectiveness=ResourceScoringEngine.score_learning_effectiveness(resource),
        )
