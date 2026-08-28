"""CRUD repository for the ResourceEmbedding model (pgvector)."""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import ResourceEmbedding
from app.logging import get_logger

logger = get_logger("database.repositories.embedding")


class EmbeddingRepository:
    """All database operations for the resource_embeddings table.

    Handles storage and semantic similarity queries using pgvector.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Create / Upsert
    # ------------------------------------------------------------------

    async def upsert(
        self,
        resource_id: uuid.UUID,
        embedding: list[float],
        model_name: str = "text-embedding-3-small",
    ) -> ResourceEmbedding:
        """Create or replace the embedding for a resource."""
        existing = await self.get_by_resource_id(resource_id)
        if existing:
            existing.embedding = embedding
            existing.model_name = model_name
            await self.session.flush()
            return existing

        record = ResourceEmbedding(
            resource_id=resource_id,
            embedding=embedding,
            model_name=model_name,
        )
        self.session.add(record)
        await self.session.flush()
        logger.debug("Upserted embedding for resource_id=%s", resource_id)
        return record

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_resource_id(
        self, resource_id: uuid.UUID
    ) -> Optional[ResourceEmbedding]:
        """Fetch the embedding record for a resource."""
        result = await self.session.execute(
            select(ResourceEmbedding).where(
                ResourceEmbedding.resource_id == resource_id
            )
        )
        return result.scalar_one_or_none()

    async def find_similar(
        self,
        query_embedding: list[float],
        limit: int = 10,
        min_similarity: float = 0.5,
        topic_id: Optional[str] = None,
    ) -> list[dict]:
        """Find resources semantically similar to the query embedding.

        Uses pgvector cosine distance operator (<=>).
        Joins with the resources table to return full resource metadata.

        Parameters
        ----------
        query_embedding : list[float]  — Query vector to search against
        limit           : int          — Max results to return
        min_similarity  : float        — Minimum cosine similarity 0-1
        topic_id        : str | None   — Optional filter by topic UUID

        Returns
        -------
        List of dicts with full resource metadata + similarity score.
        """
        from sqlalchemy import text as sa_text

        max_distance = 1.0 - min_similarity

        topic_filter = "AND r.topic_id = CAST(:topic_id AS uuid)" if topic_id else ""

        raw_sql = sa_text(f"""
            SELECT
                r.id            AS resource_id,
                r.title,
                r.url,
                r.resource_type,
                r.source,
                r.summary,
                r.category,
                r.rank,
                r.composite_score,
                r.difficulty_level,
                r.estimated_study_time,
                re.model_name,
                1 - (re.embedding <=> CAST(:query AS vector)) AS similarity
            FROM resource_embeddings re
            JOIN resources r ON r.id = re.resource_id
            WHERE re.embedding <=> CAST(:query AS vector) <= :max_dist
              AND r.is_active = true
              {topic_filter}
            ORDER BY re.embedding <=> CAST(:query AS vector)
            LIMIT :limit
        """)

        params = {
            "query": str(query_embedding),
            "max_dist": max_distance,
            "limit": limit,
        }
        if topic_id:
            params["topic_id"] = topic_id

        result = await self.session.execute(raw_sql, params)
        rows = result.fetchall()

        return [
            {
                "resource_id": str(row.resource_id),
                "title": row.title,
                "url": row.url,
                "resource_type": row.resource_type,
                "source": row.source,
                "summary": row.summary,
                "category": row.category,
                "rank": row.rank,
                "composite_score": round(float(row.composite_score or 0), 3),
                "difficulty_level": row.difficulty_level,
                "estimated_study_time": row.estimated_study_time,
                "embedding_model": row.model_name,
                "similarity": round(float(row.similarity), 4),
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_by_resource_id(self, resource_id: uuid.UUID) -> bool:
        """Delete the embedding for a resource."""
        record = await self.get_by_resource_id(resource_id)
        if not record:
            return False
        await self.session.delete(record)
        await self.session.flush()
        return True
