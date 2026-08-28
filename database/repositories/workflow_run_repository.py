"""CRUD repository for the WorkflowRun model."""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import WorkflowRun
from app.logging import get_logger

logger = get_logger("database.repositories.workflow_run")


class WorkflowRunRepository:
    """All database operations for the workflow_runs table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        domain: str,
        course: str,
        topic_name: str,
        difficulty_level: str = "Beginner",
        provider: str = "gemini",
        model: Optional[str] = None,
        topic_id: Optional[uuid.UUID] = None,
    ) -> WorkflowRun:
        """Create a workflow run record at the start of a request."""
        run = WorkflowRun(
            domain=domain,
            course=course,
            topic_name=topic_name,
            difficulty_level=difficulty_level,
            provider=provider,
            model=model,
            topic_id=topic_id,
        )
        self.session.add(run)
        await self.session.flush()
        logger.info(
            "Created workflow run: id=%s topic=%s provider=%s",
            run.id, topic_name, provider,
        )
        return run

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(self, run_id: uuid.UUID) -> Optional[WorkflowRun]:
        """Fetch a workflow run by primary key."""
        result = await self.session.execute(
            select(WorkflowRun).where(WorkflowRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def get_by_topic_id(
        self, topic_id: uuid.UUID, limit: int = 20
    ) -> list[WorkflowRun]:
        """Return recent workflow runs for a topic."""
        result = await self.session.execute(
            select(WorkflowRun)
            .where(WorkflowRun.topic_id == topic_id)
            .order_by(WorkflowRun.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent(self, limit: int = 50) -> list[WorkflowRun]:
        """Return the most recent workflow runs across all topics."""
        result = await self.session.execute(
            select(WorkflowRun)
            .order_by(WorkflowRun.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_failed_runs(self, limit: int = 50) -> list[WorkflowRun]:
        """Return recent failed workflow runs for debugging."""
        result = await self.session.execute(
            select(WorkflowRun)
            .where(WorkflowRun.success.is_(False))
            .order_by(WorkflowRun.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def complete(
        self,
        run_id: uuid.UUID,
        success: bool,
        final_phase: str,
        attempt_count: int,
        resources_discovered: int = 0,
        resources_evaluated: int = 0,
        resources_ranked: int = 0,
        # ENH-002 extended observability
        resources_validated: int = 0,
        resources_rejected: int = 0,
        resources_persisted: int = 0,
        embeddings_generated: int = 0,
        retry_count: int = 0,
        duration_ms: Optional[int] = None,
        knowledge_retrieved: bool = False,
        # ENH-007 token tracking
        llm_prompt_tokens: Optional[int] = None,
        llm_completion_tokens: Optional[int] = None,
        llm_total_tokens: Optional[int] = None,
        messages: Optional[list] = None,
        errors: Optional[list] = None,
        parsed_output: Optional[dict] = None,
    ) -> Optional[WorkflowRun]:
        """Update a workflow run record when the workflow finishes."""
        run = await self.get_by_id(run_id)
        if not run:
            return None
        run.success = success
        run.final_phase = final_phase
        run.attempt_count = attempt_count
        run.resources_discovered = resources_discovered
        run.resources_evaluated = resources_evaluated
        run.resources_ranked = resources_ranked
        run.resources_validated = resources_validated
        run.resources_rejected = resources_rejected
        run.resources_persisted = resources_persisted
        run.embeddings_generated = embeddings_generated
        run.retry_count = retry_count
        run.duration_ms = duration_ms
        run.knowledge_retrieved = knowledge_retrieved
        run.llm_prompt_tokens = llm_prompt_tokens
        run.llm_completion_tokens = llm_completion_tokens
        run.llm_total_tokens = llm_total_tokens
        run.messages = messages or []
        run.errors = errors or []
        run.parsed_output = parsed_output
        await self.session.flush()
        logger.info("Completed workflow run: id=%s success=%s duration_ms=%s",
                    run_id, success, duration_ms)
        return run

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, run_id: uuid.UUID) -> bool:
        """Hard-delete a workflow run record."""
        run = await self.get_by_id(run_id)
        if not run:
            return False
        await self.session.delete(run)
        await self.session.flush()
        return True
