# ADR-002: PostgreSQL + pgvector for Storage and Semantic Search

**Date:** 2026-08  
**Status:** Accepted

## Context

Educational resources need to be persisted with rich metadata, multi-dimensional quality scores, and embeddings for semantic search. We need a single storage tier that handles both structured queries and vector similarity search.

## Decision

Use PostgreSQL as the primary database with the pgvector extension for embedding storage. SQLAlchemy async ORM for structured access. pgvector's HNSW index for fast cosine similarity queries. Gemini `text-embedding-004` (768 dimensions) as the embedding model.

## Consequences

- Single storage tier reduces operational complexity.
- pgvector HNSW index provides sub-100ms semantic search for millions of vectors.
- No separate vector database (Pinecone, Weaviate) required — reduces costs and infra complexity.
- Embeddings and structured data co-located — semantic search results include full resource metadata in one query.
