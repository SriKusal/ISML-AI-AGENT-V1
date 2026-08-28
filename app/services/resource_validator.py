"""Resource validation, metadata normalization, and URL-based deduplication.

Addresses BUG-005, BUG-006, BUG-007.

Responsibilities
----------------
1. URL normalization  — strip tracking params, trailing slash, lowercase hostname,
   remove fragment, canonicalize scheme so that equivalent URLs are treated as one.
2. Metadata validation — reject resources that are missing required fields or have
   obviously malformed values.
3. In-run deduplication — maintain a seen-URL set across a batch so duplicate
   resources from multiple search queries do not proceed to evaluation.
4. Structured rejection logging — every rejected resource is logged with a clear reason.

Design decisions
----------------
- Implemented as a single stateless utility class so it can be called from any
  workflow node or service without introducing a new dependency layer.
- URL normalization is conservative: it only removes well-known tracking parameters
  (utm_*, fbclid, gclid, ref, source) that carry no semantic information for
  educational resources. Query parameters that may affect content (e.g. page=, id=,
  v= for YouTube) are preserved.
- No new workflow node is created; the validator is called inside
  evaluate_resources_node as a pre-filter, keeping the node graph unchanged.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import (
    ParseResult,
    parse_qsl,
    urlencode,
    urlparse,
    urlunparse,
)

from app.logging import get_logger

logger = get_logger("app.services.resource_validator")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# URL schemes considered safe for educational resources
ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

# Tracking / analytics query-string keys that carry no semantic content
_TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "utm_id", "utm_reader", "utm_name",
        "fbclid", "gclid", "msclkid", "twclid",
        "ref", "referral", "source", "origin",
        "_ga", "_gl",
    }
)

# Required fields every resource must have before entering evaluation
_REQUIRED_FIELDS: tuple[str, ...] = ("title", "url", "resource_type", "source")

# SSRF / private-network hostname patterns to block
_PRIVATE_HOST_RE = re.compile(
    r"^("
    r"localhost"
    r"|127\.\d+\.\d+\.\d+"
    r"|0\.0\.0\.0"
    r"|10\.\d+\.\d+\.\d+"
    r"|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+"
    r"|192\.168\.\d+\.\d+"
    r"|169\.254\.\d+\.\d+"          # link-local / AWS metadata
    r"|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+"  # CGNAT
    r"|::1"
    r"|fc[0-9a-f][0-9a-f]:"         # ULA IPv6
    r"|fd[0-9a-f][0-9a-f]:"
    r")$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Outcome of validating a single resource."""

    is_valid: bool
    normalized_url: Optional[str]
    rejection_reason: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# URL normalizer
# ---------------------------------------------------------------------------

def normalize_url(raw_url: str) -> Optional[str]:
    """Return a canonical URL string, or None if the URL is fundamentally malformed.

    Normalization steps
    -------------------
    1. Strip leading/trailing whitespace.
    2. Enforce lowercase scheme and hostname.
    3. Reject non-HTTP(S) schemes.
    4. Reject private / loopback / cloud-metadata hostnames (SSRF protection).
    5. Remove well-known tracking query parameters.
    6. Remove URL fragment (``#section``).
    7. Remove trailing slash from path (except bare root ``/``).
    """
    if not raw_url or not isinstance(raw_url, str):
        return None

    url = raw_url.strip()
    if not url:
        return None

    # Lowercase the string before scheme detection so HTTPS:// is handled correctly
    url_lower = url.lower()

    # Add scheme if missing so urlparse works correctly
    if not url_lower.startswith(("http://", "https://", "ftp://", "file://")):
        url = "https://" + url

    try:
        parsed: ParseResult = urlparse(url)
    except Exception:
        return None

    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        return None

    netloc = parsed.netloc.lower()
    if not netloc:
        return None

    # Require at least one dot in the hostname (rejects bare words like "notaurl")
    hostname_for_dot_check = netloc.split(":")[0]
    if "." not in hostname_for_dot_check and hostname_for_dot_check != "localhost":
        return None

    # Strip port from SSRF check (check hostname only)
    hostname = netloc.split(":")[0]
    if _PRIVATE_HOST_RE.match(hostname):
        logger.debug("SSRF protection: blocked private hostname '%s'", hostname)
        return None

    # Remove tracking parameters from query string
    original_qs = parse_qsl(parsed.query, keep_blank_values=True)
    filtered_qs = [
        (k, v) for k, v in original_qs if k.lower() not in _TRACKING_PARAMS
    ]
    clean_query = urlencode(filtered_qs)

    # Normalize path: remove trailing slash unless it's the root path
    path = parsed.path
    if path.endswith("/") and len(path) > 1:
        path = path.rstrip("/")

    # Reconstruct — drop fragment entirely
    normalized = urlunparse((scheme, netloc, path, "", clean_query, ""))
    return normalized


# ---------------------------------------------------------------------------
# Resource validator
# ---------------------------------------------------------------------------

class ResourceValidator:
    """Validates and normalizes discovered resources before evaluation.

    Usage
    -----
    Create one instance per workflow run and call ``validate(resource)`` for
    each resource dict.  The instance maintains a ``seen_urls`` set to detect
    within-run duplicates after normalization.
    """

    def __init__(self) -> None:
        # Normalized URLs seen in this validation pass (in-run deduplication)
        self._seen_urls: set[str] = set()
        self._total: int = 0
        self._accepted: int = 0
        self._rejected: int = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def validate(self, resource: dict) -> ValidationResult:
        """Validate a single resource dict.

        Returns
        -------
        ValidationResult with is_valid, normalized_url, and optional
        rejection_reason / warnings.
        """
        self._total += 1
        title = resource.get("title", "?")

        # 1. Required field check
        missing = [f for f in _REQUIRED_FIELDS if not resource.get(f)]
        if missing:
            self._rejected += 1
            reason = f"Missing required fields: {', '.join(missing)}"
            logger.debug("Resource rejected ('%s'): %s", title, reason)
            return ValidationResult(is_valid=False, normalized_url=None, rejection_reason=reason)

        # 2. URL normalization + SSRF protection
        raw_url: str = resource.get("url", "")
        norm_url = normalize_url(raw_url)
        if norm_url is None:
            self._rejected += 1
            reason = f"Invalid or unsafe URL: '{raw_url}'"
            logger.debug("Resource rejected ('%s'): %s", title, reason)
            return ValidationResult(is_valid=False, normalized_url=None, rejection_reason=reason)

        # 3. In-run duplicate detection (after normalization)
        if norm_url in self._seen_urls:
            self._rejected += 1
            reason = f"Duplicate URL (already seen): '{norm_url}'"
            logger.debug("Resource rejected ('%s'): %s", title, reason)
            return ValidationResult(is_valid=False, normalized_url=norm_url, rejection_reason=reason)

        self._seen_urls.add(norm_url)

        # 4. Soft-field warnings (don't reject — just log)
        warnings: list[str] = []
        if not resource.get("summary"):
            warnings.append("Empty summary")
        if not resource.get("language"):
            warnings.append("Missing language")
        if not resource.get("difficulty_level"):
            warnings.append("Missing difficulty_level")
        if not resource.get("keywords"):
            warnings.append("No keywords")
        if warnings:
            logger.debug(
                "Resource '%s' accepted with warnings: %s",
                title, "; ".join(warnings),
            )

        self._accepted += 1
        return ValidationResult(is_valid=True, normalized_url=norm_url, warnings=warnings)

    def validate_batch(
        self, resources: list[dict]
    ) -> list[tuple[dict, ValidationResult]]:
        """Validate a list of resources, returning (resource, result) pairs.

        The resource dict is updated in-place with the normalized URL when
        validation passes.
        """
        results = []
        for resource in resources:
            result = self.validate(resource)
            if result.is_valid and result.normalized_url:
                # Update the dict's URL to the normalized form so downstream
                # services and the DB uniqueness constraint see the same URL.
                resource["url"] = result.normalized_url
            results.append((resource, result))
        return results

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict:
        """Return validation statistics for the current pass."""
        return {
            "total": self._total,
            "accepted": self._accepted,
            "rejected": self._rejected,
        }

    def reset(self) -> None:
        """Reset state for a new validation pass."""
        self._seen_urls.clear()
        self._total = 0
        self._accepted = 0
        self._rejected = 0
