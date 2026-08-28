"""SQLAlchemy ORM models for ISML AI AGENT.

Tables
------
domains             - Top-level subject domains (e.g. "Language Learning")
courses             - Courses within a domain (e.g. "Japanese Language")
topics              - Learning topics within a course (e.g. "Hiragana")
resources           - Discovered educational resources
resource_evaluations - Multi-dimensional quality scores for a resource
resource_embeddings  - pgvector embeddings for semantic search
search_queries      - Logged search queries generated per workflow run
workflow_runs       - Full record of each /intelligence API invocation
"""

import uuid
from typing import Optional

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


# ---------------------------------------------------------------------------
# Resource lifecycle status (ENH-010)
# ---------------------------------------------------------------------------

class ResourceStatus:
    """Resource lifecycle states (ENH-010).

    States progress as:
        DISCOVERED → VALIDATED → EVALUATED → APPROVED → REJECTED/ARCHIVED

    Using plain string constants instead of a DB Enum so we can add states
    without a schema migration.
    """
    DISCOVERED = "discovered"
    VALIDATED = "validated"
    EVALUATED = "evaluated"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    UNAVAILABLE = "unavailable"

    ALL = frozenset({
        DISCOVERED, VALIDATED, EVALUATED, APPROVED,
        REJECTED, ARCHIVED, UNAVAILABLE,
    })
    ACTIVE_STATES = frozenset({DISCOVERED, VALIDATED, EVALUATED, APPROVED})
    EXCLUDED_FROM_SEARCH = frozenset({REJECTED, ARCHIVED, UNAVAILABLE})


# ---------------------------------------------------------------------------
# Domain
# ---------------------------------------------------------------------------

class Domain(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Top-level subject domain (e.g. 'Language Learning', 'Computer Science').

    Relationships
    -------------
    courses : list[Course]  — all courses under this domain
    """

    __tablename__ = "domains"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    courses: Mapped[list["Course"]] = relationship(
        "Course", back_populates="domain", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Domain id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Course
# ---------------------------------------------------------------------------

class Course(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A course within a domain (e.g. 'Japanese Language').

    Relationships
    -------------
    domain  : Domain        — parent domain
    topics  : list[Topic]   — topics under this course
    """

    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("domain_id", "name", name="uq_courses_domain_name"),
    )

    domain_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("domains.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    domain: Mapped["Domain"] = relationship("Domain", back_populates="courses")
    topics: Mapped[list["Topic"]] = relationship(
        "Topic", back_populates="course", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Course id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Topic
# ---------------------------------------------------------------------------

class Topic(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A learning topic within a course (e.g. 'Hiragana').

    Relationships
    -------------
    course          : Course            — parent course
    resources       : list[Resource]    — resources discovered for this topic
    search_queries  : list[SearchQuery] — queries generated for this topic
    workflow_runs   : list[WorkflowRun] — workflow runs triggered for this topic
    """

    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("course_id", "name", "difficulty_level", name="uq_topics_course_name_level"),
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    difficulty_level: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Beginner"
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON: related_concepts, learning_objectives, required_skills, assessment_criteria
    topic_understanding: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    course: Mapped["Course"] = relationship("Course", back_populates="topics")
    resources: Mapped[list["Resource"]] = relationship(
        "Resource", back_populates="topic", cascade="all, delete-orphan"
    )
    search_queries: Mapped[list["SearchQuery"]] = relationship(
        "SearchQuery", back_populates="topic", cascade="all, delete-orphan"
    )
    workflow_runs: Mapped[list["WorkflowRun"]] = relationship(
        "WorkflowRun", back_populates="topic", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Topic id={self.id} name={self.name!r} level={self.difficulty_level!r}>"


# ---------------------------------------------------------------------------
# Resource
# ---------------------------------------------------------------------------

class Resource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An educational resource discovered for a topic.

    Relationships
    -------------
    topic       : Topic                     — associated learning topic
    evaluation  : ResourceEvaluation | None — quality scores
    embedding   : ResourceEmbedding | None  — pgvector embedding
    """

    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint("topic_id", "url", name="uq_resources_topic_url"),
    )

    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Core metadata
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resource_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # video, pdf, article, course, book
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(50), nullable=False, default="English")
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON list of keyword strings
    keywords: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Educational metadata
    difficulty_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    modality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    audience_level: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    estimated_effort: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    estimated_study_time: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Discovery metadata
    publication_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    credibility_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    # foundation, practice, advanced, supplementary, assessment
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Ranking
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    composite_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Lifecycle (ENH-010)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ResourceStatus.DISCOVERED, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Freshness (ENH-011)
    last_verified_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    availability_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Content hash for stronger idempotency (ENH-003)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    topic: Mapped["Topic"] = relationship("Topic", back_populates="resources")
    evaluation: Mapped[Optional["ResourceEvaluation"]] = relationship(
        "ResourceEvaluation", back_populates="resource",
        uselist=False, cascade="all, delete-orphan"
    )
    embedding: Mapped[Optional["ResourceEmbedding"]] = relationship(
        "ResourceEmbedding", back_populates="resource",
        uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Resource id={self.id} title={self.title!r} type={self.resource_type!r}>"


# ---------------------------------------------------------------------------
# ResourceEvaluation
# ---------------------------------------------------------------------------

class ResourceEvaluation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Multi-dimensional quality evaluation scores for a resource.

    One-to-one with Resource.

    Score dimensions mirror ResourceScoringEngine:
    - relevance      (topic_match, keyword_match, objective_coverage, difficulty_alignment)
    - quality        (accuracy, pedagogy, engagement, comprehensiveness, clarity, interactivity)
    - credibility    (authority, reputation, expertise, peer_review, currency)
    - effectiveness  (skill_dev, retention, practical, motivation, assessment_compat)
    """

    __tablename__ = "resource_evaluations"

    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )

    # --- Relevance scores ---
    relevance_topic_match: Mapped[float] = mapped_column(Float, default=0.0)
    relevance_keyword_match: Mapped[float] = mapped_column(Float, default=0.0)
    relevance_objective_coverage: Mapped[float] = mapped_column(Float, default=0.0)
    relevance_difficulty_alignment: Mapped[float] = mapped_column(Float, default=0.0)
    relevance_overall: Mapped[float] = mapped_column(Float, default=0.0)

    # --- Educational quality scores ---
    quality_content_accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    quality_pedagogical_effectiveness: Mapped[float] = mapped_column(Float, default=0.0)
    quality_engagement_level: Mapped[float] = mapped_column(Float, default=0.0)
    quality_comprehensiveness: Mapped[float] = mapped_column(Float, default=0.0)
    quality_clarity: Mapped[float] = mapped_column(Float, default=0.0)
    quality_interactivity: Mapped[float] = mapped_column(Float, default=0.0)
    quality_overall: Mapped[float] = mapped_column(Float, default=0.0)

    # --- Credibility scores ---
    credibility_source_authority: Mapped[float] = mapped_column(Float, default=0.0)
    credibility_publication_reputation: Mapped[float] = mapped_column(Float, default=0.0)
    credibility_author_expertise: Mapped[float] = mapped_column(Float, default=0.0)
    credibility_peer_review_status: Mapped[float] = mapped_column(Float, default=0.0)
    credibility_currency: Mapped[float] = mapped_column(Float, default=0.0)
    credibility_overall: Mapped[float] = mapped_column(Float, default=0.0)

    # --- Learning effectiveness scores ---
    effectiveness_skill_development: Mapped[float] = mapped_column(Float, default=0.0)
    effectiveness_knowledge_retention: Mapped[float] = mapped_column(Float, default=0.0)
    effectiveness_practical_applicability: Mapped[float] = mapped_column(Float, default=0.0)
    effectiveness_motivation_factor: Mapped[float] = mapped_column(Float, default=0.0)
    effectiveness_assessment_compatibility: Mapped[float] = mapped_column(Float, default=0.0)
    effectiveness_overall: Mapped[float] = mapped_column(Float, default=0.0)

    # Composite score
    composite_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Raw LLM rationale stored as JSON (optional)
    rationale: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationship
    resource: Mapped["Resource"] = relationship("Resource", back_populates="evaluation")

    def __repr__(self) -> str:
        return f"<ResourceEvaluation resource_id={self.resource_id} composite={self.composite_score:.3f}>"


# ---------------------------------------------------------------------------
# ResourceEmbedding
# ---------------------------------------------------------------------------

class ResourceEmbedding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """pgvector embedding for a resource — enables semantic similarity search.

    One-to-one with Resource.
    Dimension 1536 matches OpenAI text-embedding-3-small.
    Change EMBEDDING_DIM if using a different model.
    """

    __tablename__ = "resource_embeddings"

    EMBEDDING_DIM = 3072  # gemini-embedding-001 output dimension

    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )

    # pgvector column — stores the dense embedding vector
    embedding: Mapped[Optional[list]] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )

    # Which model produced this embedding
    model_name: Mapped[str] = mapped_column(
        String(100), nullable=False, default="text-embedding-3-small"
    )

    # Relationship
    resource: Mapped["Resource"] = relationship("Resource", back_populates="embedding")

    def __repr__(self) -> str:
        return f"<ResourceEmbedding resource_id={self.resource_id} model={self.model_name!r}>"


# ---------------------------------------------------------------------------
# SearchQuery
# ---------------------------------------------------------------------------

class SearchQuery(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A search query generated by the search_strategy_node for a topic.

    Tracks which queries were used and how many results each produced.

    Relationships
    -------------
    topic        : Topic       — the topic this query was generated for
    workflow_run : WorkflowRun — the run that generated this query
    """

    __tablename__ = "search_queries"

    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    workflow_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True, index=True
    )

    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    results_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    topic: Mapped["Topic"] = relationship("Topic", back_populates="search_queries")
    workflow_run: Mapped[Optional["WorkflowRun"]] = relationship(
        "WorkflowRun", back_populates="search_queries"
    )

    def __repr__(self) -> str:
        return f"<SearchQuery id={self.id} query={self.query_text!r}>"


# ---------------------------------------------------------------------------
# WorkflowRun
# ---------------------------------------------------------------------------

class WorkflowRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Full record of a single /api/v1/resources/intelligence invocation.

    Captures input, all workflow phases, provider used, success/failure,
    and the final parsed LLM output for audit and replay purposes.

    Relationships
    -------------
    topic          : Topic              — topic this run was for
    search_queries : list[SearchQuery]  — queries generated in this run
    """

    __tablename__ = "workflow_runs"

    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True, index=True
    )

    # Input parameters
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    course: Mapped[str] = mapped_column(String(255), nullable=False)
    topic_name: Mapped[str] = mapped_column(String(255), nullable=False)
    difficulty_level: Mapped[str] = mapped_column(String(50), nullable=False, default="Beginner")
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="gemini")
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Outcome
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    final_phase: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Counts
    resources_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resources_evaluated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resources_ranked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Extended observability counts (ENH-002)
    resources_validated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resources_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resources_persisted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embeddings_generated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    knowledge_retrieved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # LLM cost tracking (ENH-007) — nullable so rows created before this feature still load
    llm_prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    llm_completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    llm_total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Logs stored as JSON arrays
    messages: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    errors: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Final LLM output (parsed JSON)
    parsed_output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    topic: Mapped[Optional["Topic"]] = relationship("Topic", back_populates="workflow_runs")
    search_queries: Mapped[list["SearchQuery"]] = relationship(
        "SearchQuery", back_populates="workflow_run"
    )

    def __repr__(self) -> str:
        return (
            f"<WorkflowRun id={self.id} topic={self.topic_name!r} "
            f"provider={self.provider!r} success={self.success}>"
        )
