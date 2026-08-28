# ADR-005: Knowledge Retrieval Before Discovery

**Date:** 2026-08  
**Status:** Accepted

## Context

Running the full discovery → LLM pipeline on every request for the same topic is expensive (LLM tokens, search overhead) and slow. The database already contains high-quality evaluated resources from previous runs.

## Decision

Add a `KNOWLEDGE_RETRIEVAL` phase immediately after `TOPIC_ANALYSIS`. Query the DB for existing resources matching (domain, course, topic, difficulty_level) with `composite_score ≥ KNOWLEDGE_RETRIEVAL_MIN_SCORE`. If at least `KNOWLEDGE_RETRIEVAL_MIN_RESOURCES` qualifying resources exist, populate `discovered_resources` from the DB and jump to `EVALUATE_RESOURCES`, skipping search, discovery, prompt construction, and LLM call entirely.

Both thresholds are configurable via env vars. If the DB is unavailable, the node fails gracefully and falls through to normal discovery.

## Consequences

- Repeated requests for the same topic use existing knowledge instead of re-running the full pipeline.
- Reduces LLM costs and latency significantly after the first run.
- Quality of retrieved resources depends on the composite score threshold — low threshold may return stale results.
- Combines well with the response cache for maximum cost reduction.
