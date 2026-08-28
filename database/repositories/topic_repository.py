"""CRUD repository for the Topic model."""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Topic
from app.logging import get_logger

logger = get_logger("database.repositories.topic")


class TopicRepository:
    """All database operations for the topics table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        course_id: uuid.UUID,
        name: str,
        difficulty_level: str = "Beginner",
        description: Optional[str] = None,
        topic_understanding: Optional[dict] = None,
    ) -> Topic:
        """Create and persist a new topic."""
        topic = Topic(
            course_id=course_id,
            name=name,
            difficulty_level=difficulty_level,
            description=description,
            topic_understanding=topic_understanding,
        )
        self.session.add(topic)
        await self.session.flush()
        logger.info("Created topic: %s (level=%s)", name, difficulty_level)
        return topic

    async def get_or_create(
        self,
        course_id: uuid.UUID,
        name: str,
        difficulty_level: str = "Beginner",
        description: Optional[str] = None,
        topic_understanding: Optional[dict] = None,
    ) -> tuple[Topic, bool]:
        """Return existing topic or create a new one."""
        existing = await self.get_by_course_name_level(course_id, name, difficulty_level)
        if existing:
            return existing, False
        topic = await self.create(
            course_id, name, difficulty_level, description, topic_understanding
        )
        return topic, True

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(self, topic_id: uuid.UUID) -> Optional[Topic]:
        """Fetch a topic by primary key."""
        result = await self.session.execute(
            select(Topic).where(Topic.id == topic_id)
        )
        return result.scalar_one_or_none()

    async def get_by_course_name_level(
        self, course_id: uuid.UUID, name: str, difficulty_level: str
    ) -> Optional[Topic]:
        """Fetch a topic by unique (course_id, name, difficulty_level)."""
        result = await self.session.execute(
            select(Topic).where(
                Topic.course_id == course_id,
                Topic.name == name,
                Topic.difficulty_level == difficulty_level,
            )
        )
        return result.scalar_one_or_none()

    async def get_all_by_course(
        self, course_id: uuid.UUID, active_only: bool = True
    ) -> list[Topic]:
        """Return all topics for a course."""
        stmt = select(Topic).where(Topic.course_id == course_id)
        if active_only:
            stmt = stmt.where(Topic.is_active.is_(True))
        result = await self.session.execute(stmt.order_by(Topic.name))
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update(
        self,
        topic_id: uuid.UUID,
        name: Optional[str] = None,
        difficulty_level: Optional[str] = None,
        description: Optional[str] = None,
        topic_understanding: Optional[dict] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Topic]:
        """Update fields on an existing topic."""
        topic = await self.get_by_id(topic_id)
        if not topic:
            return None
        if name is not None:
            topic.name = name
        if difficulty_level is not None:
            topic.difficulty_level = difficulty_level
        if description is not None:
            topic.description = description
        if topic_understanding is not None:
            topic.topic_understanding = topic_understanding
        if is_active is not None:
            topic.is_active = is_active
        await self.session.flush()
        return topic

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, topic_id: uuid.UUID) -> bool:
        """Hard-delete a topic."""
        topic = await self.get_by_id(topic_id)
        if not topic:
            return False
        await self.session.delete(topic)
        await self.session.flush()
        return True

    async def soft_delete(self, topic_id: uuid.UUID) -> bool:
        """Mark a topic as inactive."""
        result = await self.update(topic_id, is_active=False)
        return result is not None
