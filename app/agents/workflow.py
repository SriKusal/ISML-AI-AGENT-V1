"""Workflow node definitions for the ISML Academic Resource Intelligence Agent.

Each node represents a stage in the agent's workflow and operates on the shared state.

Nodes
-----
initialize           — validate inputs
topic_analysis       — extract learning context
knowledge_retrieval  — check DB for existing high-quality resources (ENH-006)
search_strategy      — generate search queries
discover_resources   — multi-source parallel discovery
evaluate_resources   — validate + normalize + score resources (BUG-005/006/007)
rank_resources       — rank, categorize, sequence
build_prompt         — construct LLM prompt
query_provider       — call LLM
parse_response       — extract JSON from LLM text
validate_output      — Pydantic schema validation + repair-retry (BUG-014/016)
complete             — finalize
"""

from typing import Optional
import json

from app.agents.state import ResourceIntelligenceState, AgentPhase, ResourceIntelligenceOutput
from app.config import settings
from app.services.provider_factory import LLMProviderFactory
from app.services.resource_discovery import ResourceDiscoveryEngine
from app.services.resource_evaluation import ResourceScoringEngine
from app.services.resource_ranking import ResourceRankingEngine, RecommendationEngine
from app.services.resource_validator import ResourceValidator
from app.services.output_validator import validate_output
from prompts import SYSTEM_PROMPT_TEMPLATE, TASK_PROMPT_TEMPLATE
from app.logging import get_logger, NodeTimer

logger = get_logger("app.agents.workflow")


class WorkflowNodes:
    """Collection of node functions for the LangGraph workflow."""

    # ------------------------------------------------------------------
    # initialize
    # ------------------------------------------------------------------

    @staticmethod
    def initialize_node(state: ResourceIntelligenceState) -> ResourceIntelligenceState:
        """Initialize the workflow state and validate input."""
        logger.info(
            "Initializing workflow: domain=%s, course=%s, topic=%s, difficulty=%s",
            state.domain, state.course, state.topic, state.difficulty_level
        )

        if not all([state.domain, state.course, state.topic]):
            state.add_error("Missing required fields: domain, course, or topic")
            state.phase = AgentPhase.COMPLETE
            return state

        state.add_message("Workflow initialized with valid inputs")
        state.phase = AgentPhase.TOPIC_ANALYSIS
        state.increment_attempt()
        return state

    # ------------------------------------------------------------------
    # topic_analysis
    # ------------------------------------------------------------------

    @staticmethod
    def topic_analysis_node(state: ResourceIntelligenceState) -> ResourceIntelligenceState:
        """Analyze the learning topic and extract context."""
        logger.info("Analyzing topic: %s in course: %s", state.topic, state.course)

        try:
            topic_context = {
                "domain": state.domain,
                "course": state.course,
                "topic": state.topic,
                "difficulty_level": state.difficulty_level,
                "related_concepts": [],
                "learning_objectives": [],
                "required_skills": [],
                "assessment_criteria": [],
            }

            if "language" in state.domain.lower():
                topic_context["related_concepts"] = [
                    "vocabulary", "grammar", "pronunciation", "comprehension"
                ]
                topic_context["learning_objectives"] = [
                    f"Understand {state.topic} in {state.course}",
                    f"Practice {state.topic} communication",
                    "Build cultural awareness",
                ]
                topic_context["required_skills"] = [
                    "listening", "speaking", "reading", "writing"
                ]
                topic_context["assessment_criteria"] = [
                    "accuracy", "fluency", "comprehension", "cultural appropriateness"
                ]

            state.topic_understanding = topic_context
            state.add_message("Topic analysis completed: extracted learning context")
            state.phase = AgentPhase.KNOWLEDGE_RETRIEVAL
        except Exception as exc:
            state.add_error(f"Failed to analyze topic: {exc}")
            state.phase = AgentPhase.COMPLETE

        return state

    # ------------------------------------------------------------------
    # knowledge_retrieval  (ENH-006)
    # ------------------------------------------------------------------

    @staticmethod
    async def knowledge_retrieval_node(
        state: ResourceIntelligenceState,
    ) -> ResourceIntelligenceState:
        """Check the database for sufficient existing high-quality resources.

        ENH-006: If enough high-quality resources already exist for this
        topic/difficulty, populate discovered_resources from the DB and skip
        the expensive discovery → LLM pipeline (jump straight to evaluate).

        The threshold is configurable via:
          KNOWLEDGE_RETRIEVAL_MIN_RESOURCES  (default 5)
          KNOWLEDGE_RETRIEVAL_MIN_SCORE      (default 0.65)

        If retrieval fails (DB not available) the node fails gracefully and
        proceeds to search_strategy as normal.
        """
        logger.info(
            "Knowledge retrieval check for: %s / %s (%s)",
            state.course, state.topic, state.difficulty_level,
        )

        min_resources = settings.KNOWLEDGE_RETRIEVAL_MIN_RESOURCES
        min_score = settings.KNOWLEDGE_RETRIEVAL_MIN_SCORE

        try:
            from database.connection import async_session_factory
            from database.models import Resource, Topic, Course, Domain
            from sqlalchemy import select

            async with async_session_factory() as session:
                # Resolve topic by name
                result = await session.execute(
                    select(Topic)
                    .join(Course, Course.id == Topic.course_id)
                    .join(Domain, Domain.id == Course.domain_id)
                    .where(
                        Domain.name == state.domain,
                        Course.name == state.course,
                        Topic.name == state.topic,
                        Topic.difficulty_level == state.difficulty_level,
                    )
                )
                db_topic = result.scalar_one_or_none()

                if db_topic is None:
                    logger.info("No existing topic record — proceeding to discovery")
                    state.phase = AgentPhase.SEARCH_STRATEGY
                    return state

                # Count high-quality resources for this topic
                result = await session.execute(
                    select(Resource).where(
                        Resource.topic_id == db_topic.id,
                        Resource.is_active.is_(True),
                        Resource.composite_score >= min_score,
                    ).order_by(Resource.composite_score.desc())
                )
                existing = list(result.scalars().all())
                count = len(existing)
                state.existing_resources_count = count

                if count >= min_resources:
                    # Sufficient knowledge exists — convert DB rows to resource dicts
                    resource_dicts = [
                        {
                            "title": r.title,
                            "url": r.url or "",
                            "resource_type": r.resource_type,
                            "source": r.source or "",
                            "language": r.language,
                            "difficulty_level": r.difficulty_level or state.difficulty_level,
                            "summary": r.summary or "",
                            "keywords": r.keywords or [],
                            "author": r.author or "",
                            "publication_date": r.publication_date or "",
                            "estimated_study_time": r.estimated_study_time,
                            "credibility_score": r.credibility_score,
                        }
                        for r in existing
                    ]
                    state.discovered_resources = {"_existing_knowledge": resource_dicts}
                    state.knowledge_retrieved = True
                    state.add_message(
                        f"Knowledge retrieval: found {count} existing high-quality resources "
                        f"(threshold: {min_resources}) — skipping discovery pipeline"
                    )
                    logger.info(
                        "Knowledge retrieval hit: %d resources found, skipping discovery",
                        count,
                    )
                    # Jump straight to evaluate (skip search_strategy + discover)
                    state.phase = AgentPhase.EVALUATE_RESOURCES
                else:
                    logger.info(
                        "Knowledge retrieval miss: only %d/%d qualifying resources — "
                        "proceeding to full discovery",
                        count, min_resources,
                    )
                    state.add_message(
                        f"Knowledge retrieval: {count}/{min_resources} resources found "
                        "— running full discovery"
                    )
                    state.phase = AgentPhase.SEARCH_STRATEGY

        except Exception as exc:
            # DB unavailable or any other error — fail gracefully, continue normally
            logger.warning(
                "Knowledge retrieval check failed (non-fatal): %s — proceeding to discovery",
                exc,
            )
            state.phase = AgentPhase.SEARCH_STRATEGY

        return state

    # ------------------------------------------------------------------
    # search_strategy
    # ------------------------------------------------------------------

    @staticmethod
    def search_strategy_node(state: ResourceIntelligenceState) -> ResourceIntelligenceState:
        """Generate intelligent search queries based on topic understanding."""
        logger.info("Generating search strategy for: %s", state.topic)

        try:
            queries = []
            topic = state.topic
            course = state.course
            domain = state.domain
            difficulty = state.difficulty_level.lower()

            queries.append(f"{topic} {course}")
            queries.append(f"{topic} {difficulty} tutorial")
            queries.append(f"{topic} video {difficulty}")
            queries.append(f"{topic} guide PDF")
            queries.append(f"{topic} worksheet practice")
            queries.append(f"{topic} pronunciation audio")

            if "language" in domain.lower():
                language = course.split()[-1] if " " in course else course
                queries.append(f"{language} {topic} beginner")
                queries.append(f"{language} {topic} vocabulary")
                queries.append(f"{language} {topic} conversation")
                queries.append(f"{topic} listening comprehension")
                queries.append(f"{topic} speaking practice")

            queries.append(f"learn {topic}")
            queries.append(f"{topic} learning resources")
            queries.append(f"{topic} study materials")

            seen = set()
            unique_queries = []
            for q in queries:
                if q.lower() not in seen:
                    seen.add(q.lower())
                    unique_queries.append(q)

            state.search_queries = unique_queries
            state.add_message(
                f"Search strategy generated: {len(unique_queries)} query variations"
            )
            state.phase = AgentPhase.DISCOVER_RESOURCES
        except Exception as exc:
            state.add_error(f"Failed to generate search strategy: {exc}")
            state.phase = AgentPhase.COMPLETE

        return state

    # ------------------------------------------------------------------
    # discover_resources
    # ------------------------------------------------------------------

    @staticmethod
    async def discover_resources_node(
        state: ResourceIntelligenceState,
    ) -> ResourceIntelligenceState:
        """Discover resources from multiple sources using search queries."""
        logger.info("Discovering resources for topic: %s", state.topic)

        try:
            with NodeTimer(logger, "discover_resources"):
                engine = ResourceDiscoveryEngine()
                discovered = await engine.discover_all(
                    search_queries=state.search_queries,
                    max_results_per_source=3,
                )
                resources_dict = {}
                total_resources = 0
                for query, resources in discovered.items():
                    resources_dict[query] = [r.to_dict() for r in resources]
                    total_resources += len(resources)

            state.discovered_resources = resources_dict
            state.add_message(
                f"Resource discovery completed: {total_resources} resources found "
                f"across {len(state.search_queries)} queries"
            )
            state.phase = AgentPhase.EVALUATE_RESOURCES
        except Exception as exc:
            state.add_error(f"Failed to discover resources: {exc}")
            state.phase = AgentPhase.COMPLETE

        return state

    # ------------------------------------------------------------------
    # evaluate_resources  (BUG-005, BUG-006, BUG-007)
    # ------------------------------------------------------------------

    @staticmethod
    def evaluate_resources_node(
        state: ResourceIntelligenceState,
    ) -> ResourceIntelligenceState:
        """Validate, normalize, deduplicate, and evaluate discovered resources.

        Validation (BUG-005 / BUG-006 / BUG-007) runs as a pre-filter:
        - Required fields checked (title, url, resource_type, source).
        - URLs normalized (lowercase host, strip tracking params, no fragment).
        - SSRF / private-hostname URLs rejected.
        - Duplicate URLs (after normalization) skipped.
        Only valid, unique resources proceed to multi-dimensional scoring.
        """
        total_count = sum(len(r) for r in state.discovered_resources.values())
        logger.info(
            "Validating and evaluating %d discovered resources", total_count,
            extra={"resources_count": total_count},
        )

        try:
            with NodeTimer(logger, "evaluate_resources"):
                # Flatten all resources from all queries
                all_resources: list[dict] = []
                for resources in state.discovered_resources.values():
                    all_resources.extend(resources)

                # Validate, normalize, deduplicate
                validator = ResourceValidator()
                validated_resources: list[dict] = []
                for resource, result in validator.validate_batch(all_resources):
                    if result.is_valid:
                        validated_resources.append(resource)
                    else:
                        logger.info(
                            "Resource rejected: title='%s' reason='%s'",
                            resource.get("title", "?"), result.rejection_reason,
                        )

                vstats = validator.stats
                state.validated_count = vstats["accepted"]
                state.rejected_count = vstats["rejected"]
                state.validation_stats = vstats

                logger.info(
                    "Validation complete: %d accepted, %d rejected out of %d",
                    vstats["accepted"], vstats["rejected"], vstats["total"],
                )

                # Score each validated resource
                evaluated_resources: list[dict] = []
                scoring_engine = ResourceScoringEngine()
                for resource in validated_resources:
                    try:
                        scored = scoring_engine.score_resource(
                            resource, state.topic_understanding
                        )
                        evaluated_resources.append(scored.to_dict())
                    except Exception as exc:
                        logger.warning(
                            "Failed to score resource '%s': %s",
                            resource.get("title", "Unknown"), exc,
                        )

            state.evaluated_resources = evaluated_resources
            state.add_message(
                f"Validated {vstats['accepted']}/{vstats['total']} resources "
                f"({vstats['rejected']} rejected); evaluated {len(evaluated_resources)} "
                "across 4 scoring dimensions"
            )
            state.phase = AgentPhase.RANK_RESOURCES
        except Exception as exc:
            state.add_error(f"Failed to evaluate resources: {exc}")
            state.phase = AgentPhase.COMPLETE

        return state

    # ------------------------------------------------------------------
    # rank_resources
    # ------------------------------------------------------------------

    @staticmethod
    def rank_resources_node(
        state: ResourceIntelligenceState,
    ) -> ResourceIntelligenceState:
        """Rank resources and generate learning recommendations."""
        logger.info("Ranking %d evaluated resources", len(state.evaluated_resources))

        try:
            from app.services.resource_evaluation import (
                ComprehensiveResourceScore,
                RelevanceScore,
                EducationalQualityScore,
                CredibilityScore,
                LearningEffectivenessScore,
            )

            scored_objects = []
            for eval_resource in state.evaluated_resources:
                rel_dict = eval_resource["relevance"]
                relevance = RelevanceScore(
                    topic_match=rel_dict["topic_match"],
                    keyword_match=rel_dict["keyword_match"],
                    learning_objective_coverage=rel_dict["learning_objective_coverage"],
                    difficulty_alignment=rel_dict["difficulty_alignment"],
                )

                edu_dict = eval_resource["educational_quality"]
                educational_quality = EducationalQualityScore(
                    content_accuracy=edu_dict["content_accuracy"],
                    pedagogical_effectiveness=edu_dict["pedagogical_effectiveness"],
                    engagement_level=edu_dict["engagement_level"],
                    comprehensiveness=edu_dict["comprehensiveness"],
                    clarity=edu_dict["clarity"],
                    interactivity=edu_dict["interactivity"],
                )

                cred_dict = eval_resource["credibility"]
                credibility = CredibilityScore(
                    source_authority=cred_dict["source_authority"],
                    publication_reputation=cred_dict["publication_reputation"],
                    author_expertise=cred_dict["author_expertise"],
                    peer_review_status=cred_dict["peer_review_status"],
                    currency=cred_dict["currency"],
                )

                eff_dict = eval_resource["learning_effectiveness"]
                learning_effectiveness = LearningEffectivenessScore(
                    skill_development=eff_dict["skill_development"],
                    knowledge_retention=eff_dict["knowledge_retention"],
                    practical_applicability=eff_dict["practical_applicability"],
                    motivation_factor=eff_dict["motivation_factor"],
                    assessment_compatibility=eff_dict["assessment_compatibility"],
                )

                scored = ComprehensiveResourceScore(
                    resource_id=eval_resource["resource_id"],
                    title=eval_resource["title"],
                    resource_type=eval_resource["resource_type"],
                    url=eval_resource["url"],
                    relevance=relevance,
                    educational_quality=educational_quality,
                    credibility=credibility,
                    learning_effectiveness=learning_effectiveness,
                )
                scored_objects.append(scored)

            ranking_engine = ResourceRankingEngine()
            ranked = ranking_engine.rank_resources(scored_objects, sort_strategy="composite")

            state.ranked_resources = [
                {
                    "rank": r.rank,
                    "resource_id": r.resource_id,
                    "title": r.title,
                    "url": r.url,
                    "type": r.resource_type,
                    "composite_score": round(r.composite_score, 3),
                    "category": r.category.value,
                    "reason": r.reason,
                    "scores": r.score_breakdown,
                }
                for r in ranked
            ]

            recommendation_engine = RecommendationEngine()
            learning_seq = recommendation_engine.generate_learning_sequence(ranked)
            state.learning_sequence = learning_seq.get("learning_sequence", [])

            recommendations = recommendation_engine.generate_personalized_recommendations(
                ranked, difficulty_level=state.difficulty_level
            )
            state.recommendations = recommendations

            state.add_message(
                f"Ranked {len(ranked)} resources and generated learning sequence "
                f"with {len(state.learning_sequence)} recommendations"
            )
            state.phase = AgentPhase.BUILD_PROMPT
        except Exception as exc:
            logger.error("Failed to rank resources: %s", exc)
            state.add_error(f"Failed to rank resources: {exc}")
            state.phase = AgentPhase.COMPLETE

        return state

    # ------------------------------------------------------------------
    # build_prompt
    # ------------------------------------------------------------------

    @staticmethod
    def build_prompt_node(
        state: ResourceIntelligenceState,
    ) -> ResourceIntelligenceState:
        """Build system and task prompts from templates."""
        logger.info("Building prompts for topic: %s", state.topic)

        try:
            state.system_prompt = SYSTEM_PROMPT_TEMPLATE

            # If a previous validation produced errors, prepend a repair fragment
            repair_fragment = getattr(state, "_repair_fragment", "")

            task_prompt = TASK_PROMPT_TEMPLATE.format(
                domain=state.domain,
                course=state.course,
                topic=state.topic,
                difficulty_level=state.difficulty_level,
            )

            if repair_fragment:
                task_prompt = repair_fragment + "\n\n" + task_prompt
                logger.info("Repair fragment prepended to task prompt")

            state.task_prompt = task_prompt
            state.full_prompt = f"{state.system_prompt}\n\n{state.task_prompt}"

            state.add_message("Prompts built successfully")
            state.phase = AgentPhase.QUERY_PROVIDER
        except Exception as exc:
            state.add_error(f"Failed to build prompts: {exc}")
            state.phase = AgentPhase.COMPLETE

        return state

    # ------------------------------------------------------------------
    # query_provider
    # ------------------------------------------------------------------

    @staticmethod
    async def query_provider_node(
        state: ResourceIntelligenceState,
    ) -> ResourceIntelligenceState:
        """Send the full prompt to the selected LLM provider."""
        logger.info("Querying provider: %s", state.provider)

        try:
            provider = LLMProviderFactory.create(state.provider)
            model = state.model or ""

            response = await provider.generate_text(state.full_prompt, model)
            state.provider_response = response

            state.add_message(f"Provider response received from {state.provider}")
            state.phase = AgentPhase.PARSE_RESPONSE
        except Exception as exc:
            state.provider_error = str(exc)
            state.add_error(f"Provider request failed: {exc}")

            if state.should_retry():
                state.add_message(f"Retry attempt {state.attempt_count + 1}")
                state.increment_attempt()
                state.phase = AgentPhase.BUILD_PROMPT
            else:
                state.phase = AgentPhase.COMPLETE

        return state

    # ------------------------------------------------------------------
    # parse_response
    # ------------------------------------------------------------------

    @staticmethod
    def parse_response_node(
        state: ResourceIntelligenceState,
    ) -> ResourceIntelligenceState:
        """Parse the provider response into structured JSON."""
        logger.info("Parsing provider response")

        if not state.provider_response:
            state.add_error("No provider response to parse")
            state.phase = AgentPhase.COMPLETE
            return state

        try:
            response_data = state.provider_response
            text_content = ""

            if isinstance(response_data, dict) and "candidates" in response_data:
                content = response_data["candidates"][0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    text_content = parts[0].get("text", "")
            elif isinstance(response_data, dict) and "choices" in response_data:
                choice = response_data["choices"][0]
                text_content = choice.get("message", {}).get("content", "")
            else:
                state.add_error("Unexpected provider response format")
                state.phase = AgentPhase.COMPLETE
                return state

            # Strip markdown code fences
            stripped = text_content.strip()
            if stripped.startswith("```"):
                lines = stripped.splitlines()
                lines = lines[1:] if lines else lines
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                stripped = "\n".join(lines).strip()

            try:
                state.parsed_output = json.loads(stripped)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r"\{.*\}", stripped, re.DOTALL)
                if json_match:
                    state.parsed_output = json.loads(json_match.group())
                else:
                    raise

            state.add_message("Response parsed successfully")
            state.phase = AgentPhase.VALIDATE_OUTPUT

        except json.JSONDecodeError as exc:
            logger.warning("JSON parse failed: %s — retrying if attempts remain", exc)
            state.add_error(f"Failed to parse JSON response: {exc}")
            if state.should_retry():
                state.increment_attempt()
                state.phase = AgentPhase.BUILD_PROMPT
                state.add_message(
                    f"Retrying after JSON parse failure (attempt {state.attempt_count})"
                )
            else:
                state.phase = AgentPhase.COMPLETE
        except Exception as exc:
            state.add_error(f"Failed to parse response: {exc}")
            state.phase = AgentPhase.COMPLETE

        return state

    # ------------------------------------------------------------------
    # validate_output  (BUG-014, BUG-016)
    # ------------------------------------------------------------------

    @staticmethod
    def validate_output_node(
        state: ResourceIntelligenceState,
    ) -> ResourceIntelligenceState:
        """Validate the parsed output against the Pydantic OutputSchema.

        BUG-014: Uses Pydantic models instead of manual key-presence checks.
        BUG-016: On schema failure, if retries remain, builds a repair prompt
                 and rewinds to BUILD_PROMPT so the LLM can correct its output.

        Normalization (alias handling) runs first so the Pydantic validator
        operates on canonical field names.
        """
        logger.info("Validating parsed output")

        if not state.parsed_output:
            state.add_error("No parsed output to validate")
            state.phase = AgentPhase.COMPLETE
            return state

        try:
            output = state.parsed_output

            # ----------------------------------------------------------
            # Normalization — handle known LLM output aliases
            # ----------------------------------------------------------
            if "task" not in output:
                if all(k in output for k in ("domain", "course", "topic")):
                    output["task"] = {
                        "domain": output.get("domain"),
                        "course": output.get("course"),
                        "topic": output.get("topic"),
                        "difficulty_level": output.get("difficulty_level"),
                    }
                else:
                    output["task"] = {
                        "domain": state.domain,
                        "course": state.course,
                        "topic": state.topic,
                        "difficulty_level": state.difficulty_level,
                    }

            # Ensure task has required sub-fields from state if missing
            task = output["task"]
            if not task.get("domain"):
                task["domain"] = state.domain
            if not task.get("course"):
                task["course"] = state.course
            if not task.get("topic"):
                task["topic"] = state.topic
            if not task.get("difficulty_level"):
                task["difficulty_level"] = state.difficulty_level

            _ranked_aliases = [
                "ranked_resource_ids", "ranked_list",
                "resource_ranking", "ranking_order",
            ]
            if "ranked_resources" not in output:
                for alias in _ranked_aliases:
                    if alias in output:
                        output["ranked_resources"] = output.pop(alias)
                        break

            if "ranked_resources" not in output:
                resources = output.get("resources", [])
                if resources and isinstance(resources, list):
                    def _rank_key(r):
                        return r.get("ranking") or r.get("rank") or 999
                    sorted_resources = sorted(resources, key=_rank_key)
                    output["ranked_resources"] = [
                        r.get("id") or r.get("resource_id", f"res_{i}")
                        for i, r in enumerate(sorted_resources)
                    ]

            _seq_aliases = [
                "recommended_learning_sequence", "recommended_sequence",
                "learning_path", "study_sequence", "suggested_sequence",
            ]
            if "learning_sequence" not in output:
                for alias in _seq_aliases:
                    if alias in output:
                        output["learning_sequence"] = output.pop(alias)
                        break

            if "learning_sequence" not in output:
                ranked = output.get("ranked_resources", [])
                output["learning_sequence"] = [
                    {"step": i + 1, "resource_id": rid, "reason": "Recommended resource"}
                    for i, rid in enumerate(ranked[:10])
                ]

            for step in output.get("learning_sequence", []):
                if isinstance(step, dict):
                    if "reasoning" in step and "reason" not in step:
                        step["reason"] = step.pop("reasoning")
                    if "instructions" in step and "reason" not in step:
                        step["reason"] = step.pop("instructions")
                    # Ensure step has required int field
                    if "step" not in step:
                        step["step"] = 1

            state.parsed_output = output

            # ----------------------------------------------------------
            # Pydantic schema validation (BUG-014)
            # ----------------------------------------------------------
            validation_result = validate_output(output)

            if validation_result.valid:
                state.is_valid = True
                state.add_message("Output validation passed (Pydantic schema)")
                state.phase = AgentPhase.COMPLETE
            else:
                # Schema validation failed
                for err in validation_result.errors:
                    state.add_error(f"Schema validation: {err}")

                logger.warning(
                    "Output schema validation failed (%d errors): %s",
                    len(validation_result.errors),
                    "; ".join(validation_result.errors[:3]),
                )

                # BUG-016: repair-retry — if retries remain, rewind to BUILD_PROMPT
                if state.should_retry():
                    repair_fragment = validation_result.repair_prompt_fragment()
                    # Stash on state so build_prompt_node can prepend it
                    state._repair_fragment = repair_fragment  # type: ignore[attr-defined]
                    state.increment_attempt()
                    state.phase = AgentPhase.BUILD_PROMPT
                    state.add_message(
                        f"Schema validation failed — repair retry "
                        f"(attempt {state.attempt_count})"
                    )
                    logger.info(
                        "Triggering repair-retry after schema failure "
                        "(attempt %d/%d)",
                        state.attempt_count, state.max_retries,
                    )
                else:
                    state.add_message(
                        f"Schema validation failed after max retries "
                        f"({len(validation_result.errors)} errors)"
                    )
                    state.phase = AgentPhase.COMPLETE

        except Exception as exc:
            state.add_error(f"Validation check failed: {exc}")
            state.phase = AgentPhase.COMPLETE

        return state

    # ------------------------------------------------------------------
    # complete
    # ------------------------------------------------------------------

    @staticmethod
    def complete_node(
        state: ResourceIntelligenceState,
    ) -> ResourceIntelligenceState:
        """Finalize the workflow and prepare output."""
        logger.info(
            "Workflow complete. valid=%s errors=%d attempts=%d "
            "resources=%d ranked=%d validated=%d rejected=%d retrieved=%s",
            state.is_valid,
            len(state.validation_errors),
            state.attempt_count,
            len(state.evaluated_resources),
            len(state.ranked_resources),
            state.validated_count,
            state.rejected_count,
            state.knowledge_retrieved,
            extra={
                "phase": "complete",
                "resources_count": len(state.ranked_resources),
            },
        )
        return state
