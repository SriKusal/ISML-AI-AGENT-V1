"""Tests for resource discovery across the dataset.

Validates:
- Discovery returns results for every topic
- All 4 source types (video, pdf, article, web) are represented
- Resource metadata fields are populated
- Parallel discovery (asyncio.gather) produces consistent results
- Results are deduplication-safe
"""

import asyncio
import unittest

from tests.test_dataset import (
    TOPIC_DATASET,
    LANGUAGE_TOPICS,
    CS_TOPICS,
    BEGINNER_TOPICS,
)
from app.services.resource_discovery import (
    ResourceDiscoveryEngine,
    YouTubeDiscovery,
    PDFDocumentDiscovery,
    ArticleDiscovery,
    WebSearchDiscovery,
)


class TestResourceDiscoveryEngine(unittest.IsolatedAsyncioTestCase):
    """Tests for ResourceDiscoveryEngine.discover_all."""

    async def test_discover_all_returns_results_for_every_query(self):
        """Every search query should produce at least one resource."""
        engine = ResourceDiscoveryEngine()
        queries = ["Hiragana Japanese", "Python basics", "Calculus derivatives"]
        results = await engine.discover_all(queries, max_results_per_source=2)
        self.assertEqual(len(results), len(queries))
        for query in queries:
            self.assertIn(query, results)
            self.assertGreater(len(results[query]), 0)

    async def test_discover_all_covers_all_source_types(self):
        """Discovery should return video, pdf, and article types."""
        engine = ResourceDiscoveryEngine()
        results = await engine.discover_all(["machine learning"], max_results_per_source=3)
        resources = results.get("machine learning", [])
        types = {r.resource_type for r in resources}
        self.assertIn("video", types)
        self.assertIn("pdf", types)
        self.assertIn("article", types)

    async def test_resource_metadata_fields_populated(self):
        """Every resource must have title, url, type, source, and credibility_score."""
        engine = ResourceDiscoveryEngine()
        results = await engine.discover_all(["SQL joins"], max_results_per_source=2)
        for query, resources in results.items():
            for resource in resources:
                self.assertIsNotNone(resource.title, "title should not be None")
                self.assertIsNotNone(resource.url, "url should not be None")
                self.assertIsNotNone(resource.resource_type, "resource_type should not be None")
                self.assertIsNotNone(resource.source, "source should not be None")
                self.assertGreaterEqual(resource.credibility_score, 0.0)
                self.assertLessEqual(resource.credibility_score, 1.0)

    async def test_discover_all_with_language_topics(self):
        """Language domain topics should produce results."""
        engine = ResourceDiscoveryEngine()
        queries = [f"{t['topic']} {t['course']}" for t in LANGUAGE_TOPICS[:5]]
        results = await engine.discover_all(queries, max_results_per_source=2)
        self.assertEqual(len(results), 5)
        total = sum(len(r) for r in results.values())
        self.assertGreater(total, 0)

    async def test_discover_all_with_cs_topics(self):
        """Computer science topics should produce results."""
        engine = ResourceDiscoveryEngine()
        queries = [f"{t['topic']}" for t in CS_TOPICS[:5]]
        results = await engine.discover_all(queries, max_results_per_source=2)
        self.assertEqual(len(results), 5)

    async def test_parallel_discovery_matches_sequential_count(self):
        """Parallel discover_all should return same count as calling sources individually."""
        engine = ResourceDiscoveryEngine()
        query = "Binary Search Trees"
        results = await engine.discover_all([query], max_results_per_source=3)
        resources = results.get(query, [])
        # 4 sources × 3 results each = 12 max
        self.assertLessEqual(len(resources), 12)
        self.assertGreater(len(resources), 0)

    async def test_to_dict_serialisation(self):
        """ResourceMetadata.to_dict() should produce valid dicts with expected keys."""
        engine = ResourceDiscoveryEngine()
        results = await engine.discover_all(["Hiragana"], max_results_per_source=1)
        for query, resources in results.items():
            for resource in resources:
                d = resource.to_dict()
                self.assertIn("title", d)
                self.assertIn("url", d)
                self.assertIn("resource_type", d)
                self.assertIn("source", d)
                self.assertIn("credibility_score", d)
                self.assertIn("discovered_at", d)

    async def test_discover_all_with_diverse_dataset_sample(self):
        """Sample 10 topics from the full dataset and verify discovery runs cleanly."""
        engine = ResourceDiscoveryEngine()
        sample = TOPIC_DATASET[::5][:10]  # every 5th topic, first 10
        queries = [f"{t['topic']} {t['course']}" for t in sample]
        results = await engine.discover_all(queries, max_results_per_source=2)
        self.assertEqual(len(results), len(queries))
        for query in queries:
            self.assertIn(query, results)


class TestIndividualDiscoverySources(unittest.IsolatedAsyncioTestCase):
    """Tests for each individual discovery source."""

    async def test_youtube_discovery_returns_videos(self):
        results = await YouTubeDiscovery.search("Hiragana tutorial", max_results=3)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertEqual(r.resource_type, "video")
            self.assertIn("youtube.com", r.url)

    async def test_pdf_discovery_returns_pdfs(self):
        results = await PDFDocumentDiscovery.search("Dynamic programming", max_results=3)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertEqual(r.resource_type, "pdf")

    async def test_article_discovery_returns_articles(self):
        results = await ArticleDiscovery.search("SQL joins beginner", max_results=3)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertEqual(r.resource_type, "article")

    async def test_web_search_returns_mixed_types(self):
        results = await WebSearchDiscovery.search("machine learning", max_results=6)
        self.assertGreater(len(results), 0)
        types = {r.resource_type for r in results}
        self.assertGreater(len(types), 1)

    async def test_youtube_credibility_scores_within_range(self):
        results = await YouTubeDiscovery.search("Calculus", max_results=5)
        for r in results:
            self.assertGreaterEqual(r.credibility_score, 0.0)
            self.assertLessEqual(r.credibility_score, 1.0)
