"""CRUD repository for the Resource model."""

import uuid
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Resource
from app.logging import get_logger

logger = get_logger("database.repositories.resource")


class ResourceRepository:
    """All database operations for the resources table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        topic_id: uuid.UUID,
        title: str,
        resource_type: str,
        url: Optional[str] = None,
        source: Optional[str] = None,
        author: Optional[str] = None,
        language: str = "English",
        summary: Optional[str] = None,
        keywords: Optional[list] = None,
        difficulty_level: Optional[str] = None,
        modality: Optional[str] = None,
        audience_level: Optional[str] = None,
        estimated_effort: Optional[str] = None,
        estimated_study_time: int = 0,
        publication_date: Optional[str] = None,
        credibility_score: float = 0.5,
        category: Optional[str] = None,
        rank: Optional[int] = None,
        composite_score: float = 0.0,
        status: str = "discovered",
        availability_status: str = "unverified",
        content_hash: Optional[str] = None,
    ) -> Resource:
        """Create and persist a new resource."""
        resource = Resource(
            topic_id=topic_id,
            title=title,
            resource_type=resource_type,
            url=url,
            source=source,
            author=author,
            language=language,
            summary=summary,
            keywords=keywords,
            difficulty_level=difficulty_level,
            modality=modality,
            audience_level=audience_level,
            estimated_effort=estimated_effort,
            estimated_study_time=estimated_study_time,
            publication_date=publication_date,
            credibility_score=credibility_score,
            category=category,
            rank=rank,
            composite_score=composite_score,
            status=status,
            availability_status=availability_status,
            content_hash=content_hash,
        )
        self.session.add(resource)
        await self.session.flush()
        logger.debug("Created resource: %s (type=%s status=%s)", title, resource_type, status)
        return resource

    async def bulk_create(self, resources: list[dict]) -> list[Resource]:
        """Create multiple resources in one flush.

        Each dict in the list must contain at least topic_id, title,
        and resource_type.
        """
        created = []
        for data in resources:
            resource = Resource(**data)
            self.session.add(resource)
            created.append(resource)
        await self.session.flush()
        logger.info("Bulk created %d resources", len(created))
        return created

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(
        self, resource_id: uuid.UUID, load_evaluation: bool = False
    ) -> Optional[Resource]:
        """Fetch a resource by primary key, optionally loading evaluation."""
        stmt = select(Resource).where(Resource.id == resource_id)
        if load_evaluation:
            stmt = stmt.options(selectinload(Resource.evaluation))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_topic(
        self,
        topic_id: uuid.UUID,
        active_only: bool = True,
        load_evaluation: bool = False,
    ) -> list[Resource]:
        """Return all resources for a topic ordered by rank.

        ENH-010: When active_only=True (default), excludes REJECTED, ARCHIVED,
        and UNAVAILABLE resources from results.
        """
        from database.models import ResourceStatus
        stmt = select(Resource).where(Resource.topic_id == topic_id)
        if active_only:
            stmt = stmt.where(Resource.is_active.is_(True))
            stmt = stmt.where(Resource.status.not_in(ResourceStatus.EXCLUDED_FROM_SEARCH))
        if load_evaluation:
            stmt = stmt.options(selectinload(Resource.evaluation))
        stmt = stmt.order_by(Resource.rank.asc().nullslast(), Resource.composite_score.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_topic_and_url(
        self, topic_id: uuid.UUID, url: str
    ) -> Optional[Resource]:
        """Fetch a resource by unique (topic_id, url) constraint."""
        result = await self.session.execute(
            select(Resource).where(
                and_(Resource.topic_id == topic_id, Resource.url == url)
            )
        )
        return result.scalar_one_or_none()

    async def get_top_ranked(
        self, topic_id: uuid.UUID, limit: int = 10
    ) -> list[Resource]:
        """Return top-ranked resources for a topic by composite score."""
        result = await self.session.execute(
            select(Resource)
            .where(Resource.topic_id == topic_id, Resource.is_active.is_(True))
            .order_by(Resource.composite_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_category(
        self, topic_id: uuid.UUID, category: str
    ) -> list[Resource]:
        """Return resources filtered by pedagogical category."""
        result = await self.session.execute(
            select(Resource)
            .where(
                Resource.topic_id == topic_id,
                Resource.category == category,
                Resource.is_active.is_(True),
            )
            .order_by(Resource.composite_score.desc())
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update(
        self, resource_id: uuid.UUID, **fields
    ) -> Optional[Resource]:
        """Update arbitrary fields on a resource. Returns None if not found."""
        resource = await self.get_by_id(resource_id)
        if not resource:
            return None
        for key, value in fields.items():
            if hasattr(resource, key) and value is not None:
                setattr(resource, key, value)
        await self.session.flush()
        return resource

    async def update_scores(
        self,
        resource_id: uuid.UUID,
        composite_score: float,
        rank: Optional[int] = None,
        category: Optional[str] = None,
    ) -> Optional[Resource]:
        """Update scoring fields after evaluation/ranking phase."""
        return await self.update(
            resource_id,
            composite_score=composite_score,
            rank=rank,
            category=category,
        )

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, resource_id: uuid.UUID) -> bool:
        """Hard-delete a resource."""
        resource = await self.get_by_id(resource_id)
        if not resource:
            return False
        await self.session.delete(resource)
        await self.session.flush()
        return True

    async def soft_delete(self, resource_id: uuid.UUID) -> bool:
        """Mark a resource as inactive."""
        result = await self.update(resource_id, is_active=False)
        return result is not None
