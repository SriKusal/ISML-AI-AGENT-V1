"""CRUD repository for the Course model."""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Course
from app.logging import get_logger

logger = get_logger("database.repositories.course")


class CourseRepository:
    """All database operations for the courses table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        domain_id: uuid.UUID,
        name: str,
        description: Optional[str] = None,
    ) -> Course:
        """Create and persist a new course under a domain."""
        course = Course(domain_id=domain_id, name=name, description=description)
        self.session.add(course)
        await self.session.flush()
        logger.info("Created course: %s (domain_id=%s)", name, domain_id)
        return course

    async def get_or_create(
        self,
        domain_id: uuid.UUID,
        name: str,
        description: Optional[str] = None,
    ) -> tuple[Course, bool]:
        """Return existing course or create a new one."""
        existing = await self.get_by_domain_and_name(domain_id, name)
        if existing:
            return existing, False
        course = await self.create(domain_id, name, description)
        return course, True

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(self, course_id: uuid.UUID) -> Optional[Course]:
        """Fetch a course by primary key."""
        result = await self.session.execute(
            select(Course).where(Course.id == course_id)
        )
        return result.scalar_one_or_none()

    async def get_by_domain_and_name(
        self, domain_id: uuid.UUID, name: str
    ) -> Optional[Course]:
        """Fetch a course by domain + name (unique constraint)."""
        result = await self.session.execute(
            select(Course).where(
                Course.domain_id == domain_id,
                Course.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def get_all_by_domain(
        self, domain_id: uuid.UUID, active_only: bool = True
    ) -> list[Course]:
        """Return all courses for a domain."""
        stmt = select(Course).where(Course.domain_id == domain_id)
        if active_only:
            stmt = stmt.where(Course.is_active.is_(True))
        result = await self.session.execute(stmt.order_by(Course.name))
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update(
        self,
        course_id: uuid.UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Course]:
        """Update fields on an existing course."""
        course = await self.get_by_id(course_id)
        if not course:
            return None
        if name is not None:
            course.name = name
        if description is not None:
            course.description = description
        if is_active is not None:
            course.is_active = is_active
        await self.session.flush()
        return course

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, course_id: uuid.UUID) -> bool:
        """Hard-delete a course."""
        course = await self.get_by_id(course_id)
        if not course:
            return False
        await self.session.delete(course)
        await self.session.flush()
        return True

    async def soft_delete(self, course_id: uuid.UUID) -> bool:
        """Mark a course as inactive."""
        result = await self.update(course_id, is_active=False)
        return result is not None
