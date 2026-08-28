"""Database persistence service for workflow results.

ENH-002: Extended observability — duration_ms, validated/rejected/persisted/
         embeddings counts, retry_count, knowledge_retrieved flag.
ENH-003: URL normalization applied before DB uniqueness check.
ENH-007: LLM token counts extracted from provider response.
ENH-010: Resource lifecycle status set to "evaluated" on creation.
ENH-011: availability_status set to "unverified" on creation.
ENH-013: Batch embedding generation using asyncio.gather.
"""

from typing import Optional
import asyncio
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories import (
    DomainRepository,
    CourseRepository,
    TopicRepository,
    ResourceRepository,
    EvaluationRepository,
    EmbeddingRepository,
    SearchQueryRepository,
    WorkflowRunRepository,
)
from app.agents.state import ResourceIntelligenceState
from app.services.embedding_service import EmbeddingService
from app.services.resource_validator import normalize_url
from app.logging import get_logger

logger = get_logger("app.services.db_persistence")


def _extract_token_counts(provider_response: Optional[dict]) -> tuple[int, int, int]:
    """Extract (prompt_tokens, completion_tokens, total_tokens) from a provider response.

    Handles both Gemini and OpenAI/DeepSeek response formats.
    Returns (0, 0, 0) if usage data is absent.
    """
    if not isinstance(provider_response, dict):
        return 0, 0, 0

    # OpenAI / DeepSeek format
    if "usage" in provider_response:
        usage = provider_response["usage"]
        prompt = int(usage.get("prompt_tokens", 0) or 0)
        completion = int(usage.get("completion_tokens", 0) or 0)
        total = int(usage.get("total_tokens", prompt + completion) or 0)
        return prompt, completion, total

    # Gemini format — usageMetadata
    if "usageMetadata" in provider_response:
        meta = provider_response["usageMetadata"]
        prompt = int(meta.get("promptTokenCount", 0) or 0)
        completion = int(meta.get("candidatesTokenCount", 0) or 0)
        total = int(meta.get("totalTokenCount", prompt + completion) or 0)
        return prompt, completion, total

    return 0, 0, 0


class DatabasePersistenceService:
    """Persists a completed workflow run to the database."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.domain_repo = DomainRepository(session)
        self.course_repo = CourseRepository(session)
        self.topic_repo = TopicRepository(session)
        self.resource_repo = ResourceRepository(session)
        self.eval_repo = EvaluationRepository(session)
        self.embedding_repo = EmbeddingRepository(session)
        self.search_repo = SearchQueryRepository(session)
        self.run_repo = WorkflowRunRepository(session)
        self.embedding_service = EmbeddingService()

    async def persist(
        self,
        state: ResourceIntelligenceState,
        start_time: Optional[float] = None,
    ) -> uuid.UUID:
        """Persist all workflow results. Returns the WorkflowRun ID."""
        run_id: Optional[uuid.UUID] = None
        topic_id: Optional[uuid.UUID] = None

        # ENH-007: extract token counts
        prompt_tokens, completion_tokens, total_tokens = _extract_token_counts(
            state.provider_response
        )

        # ENH-002: compute duration
        duration_ms: Optional[int] = None
        if start_time is not None:
            duration_ms = int((time.perf_counter() - start_time) * 1000)

        try:
            # 1. Resolve Domain / Course / Topic
            domain, _ = await self.domain_repo.get_or_create(name=state.domain)
            course, _ = await self.course_repo.get_or_create(
                domain_id=domain.id, name=state.course
            )
            topic, _ = await self.topic_repo.get_or_create(
                course_id=course.id,
                name=state.topic,
                difficulty_level=state.difficulty_level,
                topic_understanding=state.topic_understanding or None,
            )
            topic_id = topic.id
            logger.info("Resolved domain=%s course=%s topic=%s",
                        domain.id, course.id, topic.id)

            # 2. Create WorkflowRun record
            run = await self.run_repo.create(
                domain=state.domain,
                course=state.course,
                topic_name=state.topic,
                difficulty_level=state.difficulty_level,
                provider=state.provider,
                model=state.model,
                topic_id=topic_id,
            )
            run_id = run.id

            # 3. Save SearchQuery records
            if state.search_queries:
                results_counts = {
                    q: len(state.discovered_resources.get(q, []))
                    for q in state.search_queries
                }
                queries = await self.search_repo.bulk_create(
                    topic_id=topic_id,
                    query_texts=state.search_queries,
                    workflow_run_id=run_id,
                )
                for sq in queries:
                    count = results_counts.get(sq.query_text, 0)
                    if count:
                        sq.results_count = count
                logger.info("Saved %d search queries", len(queries))

            # 4. Collect unique resources
            resources_saved = 0
            evals_saved = 0
            embeddings_saved = 0

            eval_lookup: dict[str, dict] = {
                r["resource_id"]: r for r in state.evaluated_resources
            }
            rank_lookup: dict[str, dict] = {
                r["resource_id"]: r for r in state.ranked_resources
            }

            seen_urls: set[str] = set()
            resource_rows: list[tuple[dict, str, dict]] = []

            for _query, resources in state.discovered_resources.items():
                for res_dict in resources:
                    raw_url = res_dict.get("url", "")
                    url = normalize_url(raw_url) or raw_url
                    if url and url in seen_urls:
                        continue
                    if url:
                        seen_urls.add(url)
                    resource_internal_id = (
                        f"{res_dict.get('source', 'unknown')}_"
                        f"{hash(url) % 10000}"
                    )
                    rank_info = rank_lookup.get(resource_internal_id, {})
                    resource_rows.append((res_dict, url, rank_info))

            # ENH-013: Batch-generate embeddings in parallel
            texts = [self.embedding_service._build_text(r) for r, _, _ in resource_rows]
            async def _none():
                return None
            embedding_tasks = [
                self.embedding_service.embed_text(t) if t else _none()
                for t in texts
            ]
            try:
                embedding_vectors = await asyncio.gather(
                    *embedding_tasks, return_exceptions=True
                )
            except Exception:
                embedding_vectors = [None] * len(resource_rows)

            # 5. Persist resources + evaluations + pre-computed embeddings
            for idx, (res_dict, url, rank_info) in enumerate(resource_rows):
                resource_internal_id = (
                    f"{res_dict.get('source', 'unknown')}_"
                    f"{hash(url) % 10000}"
                )
                try:
                    # Savepoint per resource — a constraint violation on one
                    # row does not roll back the entire session.
                    async with self.session.begin_nested():
                        db_resource = await self.resource_repo.create(
                            topic_id=topic_id,
                            title=res_dict.get("title", "Untitled"),
                            resource_type=res_dict.get("resource_type", "unknown"),
                            url=url or None,
                            source=res_dict.get("source"),
                            author=res_dict.get("author"),
                            language=res_dict.get("language", "English"),
                            summary=res_dict.get("summary"),
                            keywords=res_dict.get("keywords"),
                            difficulty_level=res_dict.get("difficulty_level"),
                            estimated_study_time=res_dict.get("estimated_study_time", 0),
                            publication_date=res_dict.get("publication_date"),
                            credibility_score=res_dict.get("credibility_score", 0.5),
                            category=rank_info.get("category"),
                            rank=rank_info.get("rank"),
                            composite_score=rank_info.get("composite_score", 0.0),
                            status="evaluated",
                            availability_status="unverified",
                        )
                        resources_saved += 1

                        eval_dict = eval_lookup.get(resource_internal_id)
                        if eval_dict:
                            kwargs = EvaluationRepository.from_score_dict(
                                resource_id=db_resource.id,
                                score_dict=eval_dict,
                            )
                            await self.eval_repo.create(**kwargs)
                            evals_saved += 1

                        # Store pre-computed embedding vector
                        vector = embedding_vectors[idx] if idx < len(embedding_vectors) else None
                        if isinstance(vector, Exception):
                            vector = None
                        if vector:
                            await self.embedding_repo.upsert(
                                resource_id=db_resource.id,
                                embedding=vector,
                                model_name=self.embedding_service.model,
                            )
                            embeddings_saved += 1

                except Exception as exc:
                    logger.warning(
                        "Skipped resource '%s': %s",
                        res_dict.get("title", "?"), exc,
                    )

            logger.info(
                "Saved %d resources, %d evaluations, %d embeddings",
                resources_saved, evals_saved, embeddings_saved,
            )

            # 6. Complete the WorkflowRun record with full observability data
            await self.run_repo.complete(
                run_id=run_id,
                success=state.is_valid,
                final_phase=state.phase.value,
                attempt_count=state.attempt_count,
                resources_discovered=sum(
                    len(v) for v in state.discovered_resources.values()
                ),
                resources_evaluated=len(state.evaluated_resources),
                resources_ranked=len(state.ranked_resources),
                resources_validated=getattr(state, "validated_count", 0),
                resources_rejected=getattr(state, "rejected_count", 0),
                resources_persisted=resources_saved,
                embeddings_generated=embeddings_saved,
                retry_count=max(0, state.attempt_count - 1),
                duration_ms=duration_ms,
                knowledge_retrieved=getattr(state, "knowledge_retrieved", False),
                llm_prompt_tokens=prompt_tokens or None,
                llm_completion_tokens=completion_tokens or None,
                llm_total_tokens=total_tokens or None,
                messages=state.messages,
                errors=state.validation_errors,
                parsed_output=state.parsed_output,
            )

            logger.info(
                "WorkflowRun %s persisted (duration=%sms tokens=%s "
                "persisted=%d embeddings=%d)",
                run_id, duration_ms, total_tokens,
                resources_saved, embeddings_saved,
            )

        except Exception as exc:
            logger.error("DB persistence failed: %s", exc, exc_info=True)

        return run_id
