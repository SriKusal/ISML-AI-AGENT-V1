"""CRUD repository for the SearchQuery model."""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import SearchQuery
from app.logging import get_logger

logger = get_logger("database.repositories.search_query")


class SearchQueryRepository:
    """All database operations for the search_queries table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        topic_id: uuid.UUID,
        query_text: str,
        results_count: int = 0,
        workflow_run_id: Optional[uuid.UUID] = None,
    ) -> SearchQuery:
        """Create and persist a search query record."""
        query = SearchQuery(
            topic_id=topic_id,
            query_text=query_text,
            results_count=results_count,
            workflow_run_id=workflow_run_id,
        )
        self.session.add(query)
        await self.session.flush()
        return query

    async def bulk_create(
        self,
        topic_id: uuid.UUID,
        query_texts: list[str],
        workflow_run_id: Optional[uuid.UUID] = None,
    ) -> list[SearchQuery]:
        """Bulk-create search query records for a topic."""
        queries = [
            SearchQuery(
                topic_id=topic_id,
                query_text=q,
                workflow_run_id=workflow_run_id,
            )
            for q in query_texts
        ]
        self.session.add_all(queries)
        await self.session.flush()
        logger.info("Bulk created %d search queries for topic_id=%s", len(queries), topic_id)
        return queries

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_topic(self, topic_id: uuid.UUID) -> list[SearchQuery]:
        """Return all search queries for a topic."""
        result = await self.session.execute(
            select(SearchQuery)
            .where(SearchQuery.topic_id == topic_id)
            .order_by(SearchQuery.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_workflow_run(
        self, workflow_run_id: uuid.UUID
    ) -> list[SearchQuery]:
        """Return all queries generated in a specific workflow run."""
        result = await self.session.execute(
            select(SearchQuery).where(
                SearchQuery.workflow_run_id == workflow_run_id
            )
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update_results_count(
        self, query_id: uuid.UUID, results_count: int
    ) -> Optional[SearchQuery]:
        """Update the results_count after discovery completes."""
        result = await self.session.execute(
            select(SearchQuery).where(SearchQuery.id == query_id)
        )
        query = result.scalar_one_or_none()
        if not query:
            return None
        query.results_count = results_count
        await self.session.flush()
        return query

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_by_topic(self, topic_id: uuid.UUID) -> int:
        """Delete all search queries for a topic. Returns count deleted."""
        queries = await self.get_by_topic(topic_id)
        for q in queries:
            await self.session.delete(q)
        await self.session.flush()
        return len(queries)
