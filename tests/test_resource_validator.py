"""Tests for resource validation, URL normalization, and deduplication.

Covers BUG-005, BUG-006, BUG-007.
"""

import unittest

from app.services.resource_validator import (
    ResourceValidator,
    ValidationResult,
    normalize_url,
)


# ---------------------------------------------------------------------------
# URL normalization tests
# ---------------------------------------------------------------------------

class TestNormalizeUrl(unittest.TestCase):

    # --- Basic normalization ---

    def test_trailing_slash_removed(self):
        self.assertEqual(
            normalize_url("https://example.com/page/"),
            "https://example.com/page",
        )

    def test_root_slash_preserved(self):
        result = normalize_url("https://example.com/")
        self.assertIn("example.com", result)

    def test_hostname_lowercased(self):
        result = normalize_url("https://EXAMPLE.COM/page")
        self.assertIn("example.com", result)
        self.assertNotIn("EXAMPLE", result)

    def test_scheme_lowercased(self):
        result = normalize_url("HTTPS://example.com/page")
        self.assertTrue(result.startswith("https://"))

    def test_fragment_stripped(self):
        result = normalize_url("https://example.com/page#section")
        self.assertNotIn("#", result)

    def test_utm_params_removed(self):
        result = normalize_url(
            "https://example.com/page?utm_source=google&utm_medium=cpc&content=real"
        )
        self.assertNotIn("utm_source", result)
        self.assertNotIn("utm_medium", result)
        self.assertIn("content=real", result)

    def test_fbclid_removed(self):
        result = normalize_url("https://example.com/page?fbclid=abc123")
        self.assertIsNotNone(result)
        self.assertNotIn("fbclid", result)

    def test_gclid_removed(self):
        result = normalize_url("https://example.com/page?gclid=xyz")
        self.assertNotIn("gclid", result)

    def test_semantic_query_param_preserved(self):
        """YouTube video ID must NOT be stripped."""
        result = normalize_url("https://www.youtube.com/watch?v=abc123")
        self.assertIn("v=abc123", result)

    def test_page_param_preserved(self):
        result = normalize_url("https://example.com/articles?page=2")
        self.assertIn("page=2", result)

    def test_missing_scheme_adds_https(self):
        result = normalize_url("example.com/page")
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith("https://"))

    def test_empty_string_returns_none(self):
        self.assertIsNone(normalize_url(""))

    def test_none_returns_none(self):
        self.assertIsNone(normalize_url(None))

    def test_whitespace_only_returns_none(self):
        self.assertIsNone(normalize_url("   "))

    # --- SSRF / scheme protection ---

    def test_ftp_scheme_rejected(self):
        self.assertIsNone(normalize_url("ftp://example.com/file.pdf"))

    def test_file_scheme_rejected(self):
        self.assertIsNone(normalize_url("file:///etc/passwd"))

    def test_localhost_rejected(self):
        self.assertIsNone(normalize_url("http://localhost/admin"))

    def test_loopback_127_rejected(self):
        self.assertIsNone(normalize_url("http://127.0.0.1/secret"))

    def test_private_10_range_rejected(self):
        self.assertIsNone(normalize_url("http://10.0.0.1/internal"))

    def test_private_192_168_rejected(self):
        self.assertIsNone(normalize_url("http://192.168.1.1/router"))

    def test_private_172_16_rejected(self):
        self.assertIsNone(normalize_url("http://172.16.0.1/vpn"))

    def test_link_local_169_254_rejected(self):
        self.assertIsNone(normalize_url("http://169.254.169.254/metadata"))

    def test_public_url_accepted(self):
        result = normalize_url("https://www.youtube.com/watch?v=test123")
        self.assertIsNotNone(result)

    def test_http_public_url_accepted(self):
        result = normalize_url("http://example.com/resource")
        self.assertIsNotNone(result)

    # --- Equivalence after normalization ---

    def test_utm_variant_same_as_clean(self):
        """Two URLs differing only by tracking params normalize to the same value."""
        clean = normalize_url("https://example.com/article")
        tracked = normalize_url(
            "https://example.com/article?utm_source=newsletter&utm_medium=email"
        )
        self.assertEqual(clean, tracked)

    def test_trailing_slash_variant_same(self):
        a = normalize_url("https://example.com/page")
        b = normalize_url("https://example.com/page/")
        self.assertEqual(a, b)


# ---------------------------------------------------------------------------
# ResourceValidator tests
# ---------------------------------------------------------------------------

def _make_resource(**overrides):
    """Return a minimal valid resource dict."""
    base = {
        "title": "Test Resource",
        "url": "https://example.com/resource",
        "resource_type": "video",
        "source": "youtube",
        "language": "English",
        "difficulty_level": "Beginner",
        "summary": "A great tutorial",
        "keywords": ["tutorial", "beginner"],
    }
    base.update(overrides)
    return base


class TestResourceValidatorMissingFields(unittest.TestCase):

    def test_missing_title_rejected(self):
        r = _make_resource(title="")
        v = ResourceValidator()
        result = v.validate(r)
        self.assertFalse(result.is_valid)
        self.assertIn("title", result.rejection_reason)

    def test_missing_url_rejected(self):
        r = _make_resource(url="")
        v = ResourceValidator()
        result = v.validate(r)
        self.assertFalse(result.is_valid)

    def test_missing_resource_type_rejected(self):
        r = _make_resource(resource_type="")
        v = ResourceValidator()
        result = v.validate(r)
        self.assertFalse(result.is_valid)
        self.assertIn("resource_type", result.rejection_reason)

    def test_missing_source_rejected(self):
        r = _make_resource(source="")
        v = ResourceValidator()
        result = v.validate(r)
        self.assertFalse(result.is_valid)

    def test_valid_resource_accepted(self):
        r = _make_resource()
        v = ResourceValidator()
        result = v.validate(r)
        self.assertTrue(result.is_valid)
        self.assertIsNotNone(result.normalized_url)

    def test_optional_fields_missing_gives_warnings(self):
        r = _make_resource(summary="", language="", keywords=[])
        v = ResourceValidator()
        result = v.validate(r)
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)


class TestResourceValidatorUrlNormalization(unittest.TestCase):

    def test_url_is_normalized_in_result(self):
        r = _make_resource(url="https://EXAMPLE.COM/resource/?utm_source=google")
        v = ResourceValidator()
        result = v.validate(r)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.normalized_url, "https://example.com/resource")

    def test_url_in_dict_is_updated_after_validate_batch(self):
        r = _make_resource(url="https://EXAMPLE.COM/resource/?utm_source=google")
        v = ResourceValidator()
        pairs = v.validate_batch([r])
        # Resource dict must be updated in-place with normalized URL
        self.assertEqual(r["url"], "https://example.com/resource")

    def test_invalid_url_rejected(self):
        r = _make_resource(url="not-a-url-at-all!!!###")
        v = ResourceValidator()
        result = v.validate(r)
        self.assertFalse(result.is_valid)

    def test_localhost_url_rejected(self):
        r = _make_resource(url="http://localhost:8080/api")
        v = ResourceValidator()
        result = v.validate(r)
        self.assertFalse(result.is_valid)

    def test_private_ip_url_rejected(self):
        r = _make_resource(url="http://192.168.1.100/resource")
        v = ResourceValidator()
        result = v.validate(r)
        self.assertFalse(result.is_valid)

    def test_ftp_url_rejected(self):
        r = _make_resource(url="ftp://files.example.com/doc.pdf")
        v = ResourceValidator()
        result = v.validate(r)
        self.assertFalse(result.is_valid)


class TestResourceValidatorDeduplication(unittest.TestCase):

    def test_exact_duplicate_rejected(self):
        v = ResourceValidator()
        r1 = _make_resource(url="https://example.com/resource")
        r2 = _make_resource(title="Duplicate", url="https://example.com/resource")
        v.validate(r1)
        result2 = v.validate(r2)
        self.assertFalse(result2.is_valid)
        self.assertIn("Duplicate", result2.rejection_reason)

    def test_tracking_param_variant_is_duplicate(self):
        v = ResourceValidator()
        r1 = _make_resource(url="https://example.com/resource")
        r2 = _make_resource(title="Same with UTM",
                             url="https://example.com/resource?utm_source=email")
        v.validate(r1)
        result2 = v.validate(r2)
        self.assertFalse(result2.is_valid)

    def test_trailing_slash_variant_is_duplicate(self):
        v = ResourceValidator()
        r1 = _make_resource(url="https://example.com/resource")
        r2 = _make_resource(title="Same trailing slash",
                             url="https://example.com/resource/")
        v.validate(r1)
        result2 = v.validate(r2)
        self.assertFalse(result2.is_valid)

    def test_different_urls_both_accepted(self):
        v = ResourceValidator()
        r1 = _make_resource(url="https://example.com/resource-a")
        r2 = _make_resource(title="Resource B", url="https://example.com/resource-b")
        res1 = v.validate(r1)
        res2 = v.validate(r2)
        self.assertTrue(res1.is_valid)
        self.assertTrue(res2.is_valid)

    def test_reset_clears_seen_urls(self):
        v = ResourceValidator()
        r = _make_resource()
        v.validate(r)
        v.reset()
        result = v.validate(r)
        self.assertTrue(result.is_valid)

    def test_stats_match_outcome(self):
        v = ResourceValidator()
        resources = [
            _make_resource(url=f"https://example.com/resource-{i}") for i in range(5)
        ]
        # Add a duplicate
        resources.append(_make_resource(url="https://example.com/resource-0"))
        # Add one with missing title
        resources.append({"url": "https://example.com/other", "resource_type": "video",
                           "source": "web", "title": ""})
        pairs = v.validate_batch(resources)
        stats = v.stats
        self.assertEqual(stats["total"], 7)
        self.assertEqual(stats["accepted"], 5)
        self.assertEqual(stats["rejected"], 2)


class TestResourceValidatorBatch(unittest.TestCase):

    def test_batch_filters_invalids(self):
        v = ResourceValidator()
        resources = [
            _make_resource(url=f"https://example.com/r{i}") for i in range(3)
        ]
        resources.append(_make_resource(url="http://localhost/bad"))
        pairs = v.validate_batch(resources)
        valid = [r for r, result in pairs if result.is_valid]
        self.assertEqual(len(valid), 3)

    def test_batch_normalizes_all_valid_urls(self):
        v = ResourceValidator()
        resources = [
            _make_resource(url=f"https://EXAMPLE.COM/r{i}/?utm_source=test")
            for i in range(3)
        ]
        v.validate_batch(resources)
        for r in resources:
            self.assertTrue(r["url"].startswith("https://example.com"))
            self.assertNotIn("utm_source", r["url"])
