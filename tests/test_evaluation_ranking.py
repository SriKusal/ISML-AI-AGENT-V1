"""Tests for resource evaluation and ranking across the dataset.

Validates:
- Scores are in 0-1 range for all dimensions
- Composite score is correctly calculated from sub-scores
- Ranking preserves order (rank 1 >= rank 2 >= ...)
- All resource categories are assignable
- Learning sequence is generated correctly
- Recommendations are non-empty for any scored set
- Score consistency across multiple topics
"""

import unittest

from tests.test_dataset import TOPIC_DATASET, LANGUAGE_TOPICS, CS_TOPICS
from app.services.resource_evaluation import (
    ResourceScoringEngine,
    RelevanceScore,
    EducationalQualityScore,
    CredibilityScore,
    LearningEffectivenessScore,
    ComprehensiveResourceScore,
)
from app.services.resource_ranking import (
    ResourceRankingEngine,
    RecommendationEngine,
    ResourceCategory,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def make_resource(
    title="Test Resource",
    resource_type="video",
    source="youtube",
    summary="A comprehensive tutorial guide for learning this topic",
    difficulty_level="Beginner",
    estimated_study_time=20,
    credibility_score=0.8,
    keywords=None,
    url="https://youtube.com/test",
    publication_date="2026-01-01",
):
    return {
        "title": title,
        "url": url,
        "resource_type": resource_type,
        "source": source,
        "summary": summary,
        "difficulty_level": difficulty_level,
        "estimated_study_time": estimated_study_time,
        "credibility_score": credibility_score,
        "keywords": keywords or ["tutorial", "beginner", "learning"],
        "author": "Educational Hub",
        "publication_date": publication_date,
    }


def make_topic_understanding(
    topic="Hiragana",
    domain="Language Learning",
    course="Japanese Language",
    difficulty_level="Beginner",
):
    return {
        "domain": domain,
        "course": course,
        "topic": topic,
        "difficulty_level": difficulty_level,
        "related_concepts": ["vocabulary", "grammar", "pronunciation"],
        "learning_objectives": [f"Understand {topic}", f"Practice {topic}"],
        "required_skills": ["listening", "reading"],
        "assessment_criteria": ["accuracy", "fluency"],
    }


# ---------------------------------------------------------------------------
# Score dimension tests
# ---------------------------------------------------------------------------

class TestRelevanceScore(unittest.TestCase):

    def test_scores_in_range(self):
        resource = make_resource(title="Hiragana beginner guide")
        topic = make_topic_understanding()
        score = ResourceScoringEngine.score_relevance(resource, topic)
        self.assertGreaterEqual(score.overall_score, 0.0)
        self.assertLessEqual(score.overall_score, 1.0)
        for val in [score.topic_match, score.keyword_match,
                    score.learning_objective_coverage, score.difficulty_alignment]:
            self.assertGreaterEqual(val, 0.0)
            self.assertLessEqual(val, 1.0)

    def test_topic_in_title_gives_high_topic_match(self):
        resource = make_resource(title="Hiragana Complete Tutorial")
        topic = make_topic_understanding(topic="Hiragana")
        score = ResourceScoringEngine.score_relevance(resource, topic)
        self.assertGreaterEqual(score.topic_match, 0.85)

    def test_topic_not_in_title_gives_lower_score(self):
        resource = make_resource(title="Generic Educational Video")
        topic = make_topic_understanding(topic="Hiragana")
        score = ResourceScoringEngine.score_relevance(resource, topic)
        self.assertLessEqual(score.topic_match, 0.8)

    def test_difficulty_alignment_when_matching(self):
        resource = make_resource(difficulty_level="Beginner")
        topic = make_topic_understanding(difficulty_level="Beginner")
        score = ResourceScoringEngine.score_relevance(resource, topic)
        self.assertGreaterEqual(score.difficulty_alignment, 0.85)

    def test_to_dict_has_all_keys(self):
        resource = make_resource()
        topic = make_topic_understanding()
        score = ResourceScoringEngine.score_relevance(resource, topic)
        d = score.to_dict()
        for key in ["topic_match", "keyword_match", "learning_objective_coverage",
                    "difficulty_alignment", "overall"]:
            self.assertIn(key, d)


class TestEducationalQualityScore(unittest.TestCase):

    def test_video_gets_high_engagement(self):
        resource = make_resource(resource_type="video")
        score = ResourceScoringEngine.score_educational_quality(resource)
        self.assertGreaterEqual(score.engagement_level, 0.85)

    def test_academic_source_gets_high_accuracy(self):
        resource = make_resource(source="scholar")
        score = ResourceScoringEngine.score_educational_quality(resource)
        self.assertGreaterEqual(score.content_accuracy, 0.85)

    def test_scores_in_range(self):
        for rtype in ["video", "pdf", "article"]:
            resource = make_resource(resource_type=rtype)
            score = ResourceScoringEngine.score_educational_quality(resource)
            self.assertGreaterEqual(score.overall_score, 0.0)
            self.assertLessEqual(score.overall_score, 1.0)

    def test_guide_summary_gets_high_clarity(self):
        resource = make_resource(summary="A clear guide to understanding this topic")
        score = ResourceScoringEngine.score_educational_quality(resource)
        self.assertGreaterEqual(score.clarity, 0.75)


class TestCredibilityScore(unittest.TestCase):

    def test_scholar_source_gets_high_authority(self):
        resource = make_resource(source="google_scholar")
        score = ResourceScoringEngine.score_credibility(resource)
        self.assertGreaterEqual(score.source_authority, 0.90)

    def test_scores_in_range(self):
        for source in ["youtube", "medium", "khan", "edx", "wikipedia"]:
            resource = make_resource(source=source)
            score = ResourceScoringEngine.score_credibility(resource)
            self.assertGreaterEqual(score.overall_score, 0.0)
            self.assertLessEqual(score.overall_score, 1.0)

    def test_recent_publication_gets_high_currency(self):
        resource = make_resource(publication_date="2026-06-01")
        score = ResourceScoringEngine.score_credibility(resource)
        self.assertGreaterEqual(score.currency, 0.90)

    def test_old_publication_gets_lower_currency(self):
        resource = make_resource(publication_date="2020-01-01")
        score = ResourceScoringEngine.score_credibility(resource)
        self.assertLessEqual(score.currency, 0.70)


class TestLearningEffectivenessScore(unittest.TestCase):

    def test_video_gets_high_retention(self):
        resource = make_resource(resource_type="video")
        score = ResourceScoringEngine.score_learning_effectiveness(resource)
        self.assertGreaterEqual(score.knowledge_retention, 0.80)

    def test_scores_in_range(self):
        resource = make_resource()
        score = ResourceScoringEngine.score_learning_effectiveness(resource)
        self.assertGreaterEqual(score.overall_score, 0.0)
        self.assertLessEqual(score.overall_score, 1.0)


# ---------------------------------------------------------------------------
# ComprehensiveResourceScore tests
# ---------------------------------------------------------------------------

class TestComprehensiveResourceScore(unittest.TestCase):

    def test_composite_score_calculated_correctly(self):
        """Composite score must equal weighted sum of sub-scores."""
        relevance = RelevanceScore(
            topic_match=0.9, keyword_match=0.8,
            learning_objective_coverage=0.7, difficulty_alignment=0.9
        )
        quality = EducationalQualityScore(
            content_accuracy=0.8, pedagogical_effectiveness=0.75,
            engagement_level=0.9, comprehensiveness=0.7,
            clarity=0.8, interactivity=0.85
        )
        credibility = CredibilityScore(
            source_authority=0.95, publication_reputation=0.9,
            author_expertise=0.8, peer_review_status=0.95, currency=0.9
        )
        effectiveness = LearningEffectivenessScore(
            skill_development=0.8, knowledge_retention=0.85,
            practical_applicability=0.7, motivation_factor=0.85,
            assessment_compatibility=0.6
        )
        score = ComprehensiveResourceScore(
            resource_id="test_1", title="Test", resource_type="video",
            url="https://test.com",
            relevance=relevance, educational_quality=quality,
            credibility=credibility, learning_effectiveness=effectiveness,
        )
        expected = round(
            relevance.overall_score * 0.30 +
            quality.overall_score * 0.30 +
            credibility.overall_score * 0.25 +
            effectiveness.overall_score * 0.15,
            3,
        )
        self.assertAlmostEqual(score.composite_score, expected, places=2)

    def test_composite_score_in_range(self):
        resource = make_resource()
        topic = make_topic_understanding()
        score = ResourceScoringEngine.score_resource(resource, topic)
        self.assertGreaterEqual(score.composite_score, 0.0)
        self.assertLessEqual(score.composite_score, 1.0)

    def test_to_dict_has_all_sections(self):
        resource = make_resource()
        topic = make_topic_understanding()
        score = ResourceScoringEngine.score_resource(resource, topic)
        d = score.to_dict()
        for key in ["resource_id", "title", "resource_type", "url",
                    "relevance", "educational_quality", "credibility",
                    "learning_effectiveness", "composite_score"]:
            self.assertIn(key, d)


# ---------------------------------------------------------------------------
# Scoring across full dataset sample
# ---------------------------------------------------------------------------

class TestScoringAcrossDataset(unittest.TestCase):

    def test_all_topics_produce_valid_scores(self):
        """Scoring should succeed for every topic in the dataset."""
        engine = ResourceScoringEngine()
        errors = []
        for topic_data in TOPIC_DATASET:
            resource = make_resource(
                title=f"{topic_data['topic']} tutorial",
                difficulty_level=topic_data["difficulty_level"],
            )
            topic = make_topic_understanding(
                topic=topic_data["topic"],
                domain=topic_data["domain"],
                course=topic_data["course"],
                difficulty_level=topic_data["difficulty_level"],
            )
            try:
                score = engine.score_resource(resource, topic)
                assert 0.0 <= score.composite_score <= 1.0
            except Exception as exc:
                errors.append(f"{topic_data['topic']}: {exc}")
        self.assertEqual(errors, [], f"Scoring failed for: {errors}")

    def test_higher_credibility_source_outscores_lower(self):
        """Scholar source should score higher credibility than medium."""
        topic = make_topic_understanding()
        scholar = make_resource(source="scholar", resource_type="pdf")
        medium = make_resource(source="medium", resource_type="article")
        s1 = ResourceScoringEngine.score_credibility(scholar)
        s2 = ResourceScoringEngine.score_credibility(medium)
        self.assertGreater(s1.overall_score, s2.overall_score)


# ---------------------------------------------------------------------------
# Ranking tests
# ---------------------------------------------------------------------------

class TestResourceRankingEngine(unittest.TestCase):

    def _make_scored_resources(self, n=10):
        """Build n ComprehensiveResourceScore objects with varying scores."""
        import random
        random.seed(42)
        scored = []
        for i in range(n):
            r = RelevanceScore(
                topic_match=random.uniform(0.5, 0.9),
                keyword_match=random.uniform(0.4, 0.9),
                learning_objective_coverage=random.uniform(0.5, 0.8),
                difficulty_alignment=random.uniform(0.6, 0.95),
            )
            q = EducationalQualityScore(
                content_accuracy=random.uniform(0.6, 0.95),
                pedagogical_effectiveness=random.uniform(0.5, 0.9),
                engagement_level=random.uniform(0.5, 0.9),
                comprehensiveness=random.uniform(0.5, 0.8),
                clarity=random.uniform(0.5, 0.85),
                interactivity=random.uniform(0.4, 0.85),
            )
            c = CredibilityScore(
                source_authority=random.uniform(0.5, 0.95),
                publication_reputation=random.uniform(0.5, 0.9),
                author_expertise=random.uniform(0.5, 0.85),
                peer_review_status=random.uniform(0.4, 0.95),
                currency=random.uniform(0.5, 0.95),
            )
            e = LearningEffectivenessScore(
                skill_development=random.uniform(0.5, 0.9),
                knowledge_retention=random.uniform(0.5, 0.9),
                practical_applicability=random.uniform(0.4, 0.9),
                motivation_factor=random.uniform(0.5, 0.9),
                assessment_compatibility=random.uniform(0.4, 0.9),
            )
            scored.append(ComprehensiveResourceScore(
                resource_id=f"res_{i}",
                title=f"Resource {i}",
                resource_type="video" if i % 2 == 0 else "article",
                url=f"https://test.com/resource_{i}",
                relevance=r,
                educational_quality=q,
                credibility=c,
                learning_effectiveness=e,
            ))
        return scored

    def test_ranking_preserves_descending_order(self):
        """rank 1 should have the highest composite score."""
        scored = self._make_scored_resources(20)
        ranked = ResourceRankingEngine.rank_resources(scored)
        scores = [r.composite_score for r in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_ranking_assigns_sequential_ranks(self):
        scored = self._make_scored_resources(10)
        ranked = ResourceRankingEngine.rank_resources(scored)
        for i, r in enumerate(ranked, 1):
            self.assertEqual(r.rank, i)

    def test_all_categories_are_valid_enum_values(self):
        scored = self._make_scored_resources(20)
        ranked = ResourceRankingEngine.rank_resources(scored)
        valid_categories = {c.value for c in ResourceCategory}
        for r in ranked:
            self.assertIn(r.category.value, valid_categories)

    def test_each_ranked_resource_has_reason(self):
        scored = self._make_scored_resources(5)
        ranked = ResourceRankingEngine.rank_resources(scored)
        for r in ranked:
            self.assertTrue(len(r.reason) > 0)

    def test_ranking_by_relevance_strategy(self):
        scored = self._make_scored_resources(10)
        ranked = ResourceRankingEngine.rank_resources(scored, sort_strategy="relevance")
        relevance_scores = [r.score_breakdown["relevance"] for r in ranked]
        self.assertEqual(relevance_scores, sorted(relevance_scores, reverse=True))

    def test_ranking_by_credibility_strategy(self):
        scored = self._make_scored_resources(10)
        ranked = ResourceRankingEngine.rank_resources(scored, sort_strategy="credibility")
        cred_scores = [r.score_breakdown["credibility"] for r in ranked]
        self.assertEqual(cred_scores, sorted(cred_scores, reverse=True))

    def test_score_breakdown_has_all_dimensions(self):
        scored = self._make_scored_resources(3)
        ranked = ResourceRankingEngine.rank_resources(scored)
        for r in ranked:
            for dim in ["relevance", "educational_quality", "credibility", "learning_effectiveness"]:
                self.assertIn(dim, r.score_breakdown)


# ---------------------------------------------------------------------------
# Recommendation engine tests
# ---------------------------------------------------------------------------

class TestRecommendationEngine(unittest.TestCase):

    def _get_ranked(self, n=20):
        import random
        random.seed(99)
        scored = []
        for i in range(n):
            r = RelevanceScore(
                topic_match=random.uniform(0.5, 0.9),
                keyword_match=random.uniform(0.4, 0.9),
                learning_objective_coverage=random.uniform(0.5, 0.8),
                difficulty_alignment=random.uniform(0.6, 0.95),
            )
            q = EducationalQualityScore(
                content_accuracy=random.uniform(0.6, 0.95),
                pedagogical_effectiveness=random.uniform(0.5, 0.9),
                engagement_level=random.uniform(0.5, 0.9),
                comprehensiveness=random.uniform(0.5, 0.8),
                clarity=random.uniform(0.5, 0.85),
                interactivity=random.uniform(0.4, 0.85),
            )
            c = CredibilityScore(
                source_authority=random.uniform(0.5, 0.95),
                publication_reputation=random.uniform(0.5, 0.9),
                author_expertise=random.uniform(0.5, 0.85),
                peer_review_status=random.uniform(0.4, 0.95),
                currency=random.uniform(0.5, 0.95),
            )
            e = LearningEffectivenessScore(
                skill_development=random.uniform(0.5, 0.9),
                knowledge_retention=random.uniform(0.5, 0.9),
                practical_applicability=random.uniform(0.4, 0.9),
                motivation_factor=random.uniform(0.5, 0.9),
                assessment_compatibility=random.uniform(0.4, 0.9),
            )
            scored.append(ComprehensiveResourceScore(
                resource_id=f"res_{i}", title=f"Resource {i}",
                resource_type="video" if i % 3 == 0 else "article",
                url=f"https://test.com/{i}",
                relevance=r, educational_quality=q,
                credibility=c, learning_effectiveness=e,
            ))
        return ResourceRankingEngine.rank_resources(scored)

    def test_learning_sequence_is_non_empty(self):
        ranked = self._get_ranked()
        result = RecommendationEngine.generate_learning_sequence(ranked)
        self.assertGreater(result["total_recommendations"], 0)
        self.assertGreater(len(result["learning_sequence"]), 0)

    def test_learning_sequence_has_required_fields(self):
        ranked = self._get_ranked()
        result = RecommendationEngine.generate_learning_sequence(ranked)
        for item in result["learning_sequence"]:
            self.assertIn("title", item)
            self.assertIn("url", item)
            self.assertIn("score", item)

    def test_personalized_recommendations_non_empty(self):
        ranked = self._get_ranked()
        recs = RecommendationEngine.generate_personalized_recommendations(ranked)
        total = (len(recs["essential"]) + len(recs["recommended"]) +
                 len(recs["supplementary"]))
        self.assertGreater(total, 0)

    def test_summary_statistics_correct_total(self):
        ranked = self._get_ranked(15)
        stats = RecommendationEngine.generate_summary_statistics(ranked)
        self.assertEqual(stats["total_resources"], 15)
        self.assertGreater(stats["average_score"], 0.0)
        self.assertGreaterEqual(stats["highest_score"], stats["average_score"])
        self.assertLessEqual(stats["lowest_score"], stats["average_score"])

    def test_summary_statistics_empty_input(self):
        stats = RecommendationEngine.generate_summary_statistics([])
        self.assertEqual(stats["total_resources"], 0)
        self.assertEqual(stats["average_score"], 0.0)
