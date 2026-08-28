"""CRUD repository for the Domain model."""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Domain
from app.logging import get_logger

logger = get_logger("database.repositories.domain")


class DomainRepository:
    """All database operations for the domains table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(self, name: str, description: Optional[str] = None) -> Domain:
        """Create and persist a new domain."""
        domain = Domain(name=name, description=description)
        self.session.add(domain)
        await self.session.flush()
        logger.info("Created domain: %s", name)
        return domain

    async def get_or_create(self, name: str, description: Optional[str] = None) -> tuple[Domain, bool]:
        """Return existing domain or create a new one.

        Returns
        -------
        (domain, created) where created is True if a new row was inserted.
        """
        existing = await self.get_by_name(name)
        if existing:
            return existing, False
        domain = await self.create(name, description)
        return domain, True

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(self, domain_id: uuid.UUID) -> Optional[Domain]:
        """Fetch a domain by primary key."""
        result = await self.session.execute(
            select(Domain).where(Domain.id == domain_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[Domain]:
        """Fetch a domain by exact name match."""
        result = await self.session.execute(
            select(Domain).where(Domain.name == name)
        )
        return result.scalar_one_or_none()

    async def get_all(self, active_only: bool = True) -> list[Domain]:
        """Return all domains, optionally filtering to active only."""
        stmt = select(Domain)
        if active_only:
            stmt = stmt.where(Domain.is_active.is_(True))
        result = await self.session.execute(stmt.order_by(Domain.name))
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update(
        self,
        domain_id: uuid.UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Domain]:
        """Update fields on an existing domain. Returns None if not found."""
        domain = await self.get_by_id(domain_id)
        if not domain:
            return None
        if name is not None:
            domain.name = name
        if description is not None:
            domain.description = description
        if is_active is not None:
            domain.is_active = is_active
        await self.session.flush()
        return domain

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, domain_id: uuid.UUID) -> bool:
        """Hard-delete a domain by ID. Returns True if deleted."""
        domain = await self.get_by_id(domain_id)
        if not domain:
            return False
        await self.session.delete(domain)
        await self.session.flush()
        logger.info("Deleted domain: %s", domain_id)
        return True

    async def soft_delete(self, domain_id: uuid.UUID) -> bool:
        """Mark a domain as inactive without removing the row."""
        result = await self.update(domain_id, is_active=False)
        return result is not None
