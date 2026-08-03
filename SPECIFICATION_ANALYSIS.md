# ISML Academic Resource Intelligence Agent - Specification Analysis

## 📋 Complete Specification Summary

This is **NOT a chatbot**. It's an **autonomous educational research assistant** that must:

1. **Understand** learning topics (domain, course, topic, difficulty level)
2. **Discover** educational resources (video, PDF, article, audio)
3. **Extract** structured metadata from each resource
4. **Evaluate** quality using 8 criteria (relevance, accuracy, clarity, pedagogy, credibility, accessibility, practicality, learning effectiveness)
5. **Rank** resources by quality score (0-100)
6. **Categorize** into learning types (foundation, practice, advanced, supplementary, assessment)
7. **Sequence** recommended study order
8. **Store** knowledge in searchable resource library

---

## 🔄 The Complete Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│ INPUT: { domain, course, topic, difficulty_level, provider }   │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ 1. UNDERSTAND: Analyze topic requirements                       │
│    - Extract language, level, communication objectives          │
│    - Identify related vocabulary, grammar, skills               │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. DISCOVER: Search for resources across categories             │
│    - Videos (YouTube, educational channels)                     │
│    - Documents (PDFs, worksheets, study notes)                  │
│    - Articles (blogs, learning websites)                        │
│    - Audio (pronunciation, listening practice)                  │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. EXTRACT: Structured metadata from each resource              │
│    - Title, URL, type, source, language, difficulty             │
│    - Summary, keywords, author, publication date                │
│    - Estimated study time, content scope                        │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. EVALUATE: Quality assessment (0-100 score)                   │
│    Criteria:                                                    │
│    1. Relevance: Does it match the topic?                       │
│    2. Educational Value: Teaches clearly?                       │
│    3. Accuracy: Academically correct?                           │
│    4. Beginner Friendliness: Suitable for level?                │
│    5. Content Completeness: Covers the topic?                   │
│    6. Language Quality: Understandable?                         │
│    7. Source Credibility: Trustworthy?                          │
│    8. Learning Effectiveness: Can student learn?                │
│    → Produces: quality_score (0-100)                            │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. RANK: Sort by quality score                                  │
│    Resource A: 94                                               │
│    Resource B: 88                                               │
│    Resource C: 82                                               │
│    (Prioritize educational effectiveness, not popularity)       │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. CATEGORIZE: Organize into learning structure                 │
│    - Core Learning, Practice, Revision                          │
│    - Pronunciation, Grammar, Vocabulary                         │
│    - Listening, Speaking, Assessment                            │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. SEQUENCE: Recommend study order                              │
│    1. Video Introduction                                        │
│    2. Vocabulary PDF                                            │
│    3. Pronunciation Audio                                       │
│    4. Practice Worksheet                                        │
│    5. Conversation Video                                        │
│    6. Revision Notes                                            │
│    (Transforms discovery into guided learning experience)       │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ 8. STORE: Save to resource library                              │
│    - All metadata, quality scores, embeddings                   │
│    - Tags, keywords, curriculum mapping                         │
│    - Enable semantic search for future queries                  │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ OUTPUT: Structured JSON with resources + learning sequence      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Expected Input/Output

### Input (JSON)
```json
{
  "domain": "language_learning",
  "course": "French A1",
  "topic": "Greetings",
  "difficulty_level": "Beginner",
  "provider": "gemini",
  "model": "gemini-3.5-flash"
}
```

### Output (JSON)
```json
{
  "task": {
    "domain": "language_learning",
    "course": "French A1",
    "topic": "Greetings",
    "difficulty_level": "Beginner"
  },
  "summary": {
    "total_resources": 12,
    "high_quality_resources": 8,
    "average_score": 87
  },
  "resources": [
    {
      "id": "resource_001",
      "title": "French Greetings for Beginners",
      "source": "YouTube - Language Learning Channel",
      "type": "video",
      "url": "https://...",
      "summary": "Introduction to common greetings...",
      "difficulty": "beginner",
      "modality": "visual",
      "effort": "15 minutes",
      "category": "foundation",
      "scores": {
        "relevance": 9,
        "clarity": 9,
        "accuracy": 9,
        "pedagogy": 9,
        "credibility": 8,
        "accessibility": 9,
        "practicality": 8,
        "overall": 94
      }
    }
    // ... more resources
  ],
  "ranked_resources": ["resource_001", "resource_003", "resource_005"],
  "learning_sequence": [
    {
      "step": 1,
      "resource_id": "resource_001",
      "title": "Watch French Greetings Video",
      "type": "video",
      "duration": "15 minutes"
    },
    // ... more steps
  ],
  "recommendations": {
    "next_topic": "French Common Phrases",
    "prerequisite_mastery": 85
  }
}
```

---

## 🏗️ Current Development Status (Days 1-3)

### ✅ COMPLETED (Days 1-2)
- [x] FastAPI project structure with middleware & logging
- [x] Multi-provider LLM abstraction (Gemini, DeepSeek)
- [x] LLM provider factory pattern
- [x] Production-ready prompt templates
  - SYSTEM_PROMPT_TEMPLATE: Agent role, evaluation criteria, ranking logic, categorization rules
  - TASK_PROMPT_TEMPLATE: 4 placeholders (domain, course, topic, difficulty_level)
  - OUTPUT_JSON_TEMPLATE: Complete schema specification
- [x] /api/v1/resources/intelligence endpoint
- [x] Error handling (HTTP 429, 503, 502)

### 🔄 IN PROGRESS (Day 3)
- [x] LangGraph state model (ResourceIntelligenceState)
- [x] Workflow node definitions (6 phases)
- [x] Graph orchestration logic
- [ ] Wire workflow into FastAPI endpoint
- [ ] Make provider calls async-compatible

### ⏳ PENDING (Days 4-10)

**Day 4 - Resource Discovery**
- [ ] Web search integration (find resources)
- [ ] Resource metadata extraction
- [ ] Handle multiple resource types (video, PDF, article, audio)

**Day 5 - Quality Evaluation**
- [ ] Implement 8-factor quality scoring engine
- [ ] Ranking logic based on quality scores
- [ ] Filtering low-quality resources

**Day 6 - Database Design**
- [ ] PostgreSQL schema design
- [ ] SQLAlchemy ORM models
- [ ] pgvector integration for embeddings

**Day 7 - Knowledge Storage**
- [ ] Embeddings generation
- [ ] Semantic search implementation
- [ ] Resource library retrieval logic

**Day 8 - Production Hardening**
- [ ] Comprehensive logging
- [ ] Error handling & retry logic
- [ ] Performance optimization

**Day 9 - Testing & Validation**
- [ ] Unit tests for all components
- [ ] Edge case handling
- [ ] Duplicate detection
- [ ] Quality validation

**Day 10 - Documentation & Review**
- [ ] Complete documentation
- [ ] Architecture review
- [ ] Code quality review
- [ ] Final demonstration

---

## 🔑 Key Architectural Decisions Needed

### 1. Resource Discovery Strategy
**Question**: How should the agent discover resources?

**Option A**: LLM-driven search
- LLM generates search queries for web search tool
- Uses web search API to find resources
- More flexible, LLM understands context

**Option B**: Pre-defined search patterns
- Deterministic search queries based on topic parameters
- Call web search API directly
- More predictable, faster

**Recommendation**: Likely Option A (agent-driven) to match spec's emphasis on "autonomous research assistant"

### 2. Quality Evaluation Strategy
**Question**: How should quality scores be assigned?

**Option A**: LLM-based evaluation
- For each resource, ask LLM to evaluate against 8 criteria
- LLM generates numerical scores
- More nuanced but slower & expensive

**Option B**: Heuristic-based evaluation
- URL patterns, source credibility lookup
- Keyword matching against evaluation criteria
- Fast but less accurate

**Option C**: Hybrid approach
- Use heuristics for quick filtering
- Use LLM for detailed evaluation of top candidates
- Balanced cost/quality

**Recommendation**: Option C (hybrid) to balance cost and quality per spec's emphasis on evaluation as "most important responsibility"

### 3. Integration with FastAPI
**Question**: How should the workflow integrate with the existing endpoint?

**Current**: Direct prompt → LLM → return JSON
**New**: Endpoint → LangGraph workflow → multiple steps → store → return

**Workflow execution model**:
- Synchronous within HTTP request (return when complete)
- Asynchronous with job ID (return immediately, poll for results)
- Background task (submit job, return later)

**Recommendation**: Synchronous with async/await inside (current endpoint supports it)

---

## 📁 File Structure (Current)

```
app/
├── agents/
│   ├── __init__.py (exports)
│   ├── state.py (ResourceIntelligenceState + AgentPhase) ✓
│   ├── workflow.py (Node functions) ✓
│   └── graph.py (Orchestration logic) ✓
├── api/
│   ├── routes.py (health check)
│   ├── gemini_routes.py
│   ├── deepseek_routes.py
│   ├── llm_routes.py
│   └── resource_routes.py (to be integrated with workflow)
├── services/
│   ├── base.py (BaseLLMProvider)
│   ├── gemini_service.py
│   ├── deepseek_service.py
│   └── provider_factory.py
├── config.py (Settings)
├── logging.py (Logger setup)
└── middleware.py (Request logging)
prompts/
├── system_prompt.py (SYSTEM_PROMPT_TEMPLATE) ✓
├── task_prompt.py (TASK_PROMPT_TEMPLATE) ✓
└── output_schema.py (OUTPUT_JSON_TEMPLATE) ✓
database/ (Day 6 - to be created)
tests/ (Day 9 - to be created)
main.py (Entry point)
```

---

## 🎯 Next Immediate Actions (Day 3 Completion)

1. **Integrate LangGraph into endpoint**
   - Modify `/api/v1/resources/intelligence` to use workflow
   - Convert FastAPI request → ResourceIntelligenceState
   - Execute workflow.get_next_node() in loop until COMPLETE phase
   - Return final parsed_output as JSON response

2. **Make async-compatible**
   - Ensure query_provider_node works with FastAPI's async/await
   - Test with actual Gemini/DeepSeek API

3. **Testing**
   - Verify workflow transitions
   - Verify state persistence through phases
   - Verify error handling and retries

---

## 💡 Key Insights from Specification

1. **This is an Agent, not a prompt hack**: Multiple discrete steps (discover → evaluate → rank → sequence), not one LLM call
2. **Quality is paramount**: Section 5.4 states "most important responsibility" - evaluation engine is critical
3. **Structured knowledge**: Must store all resources with embeddings for future AI agents to use
4. **Educational focus**: Prioritize learning effectiveness over popularity/metrics
5. **Guided experience**: Don't just return links - provide learning sequence
6. **Multi-source**: Must discover across 4+ resource categories (video, document, article, audio)

---

## 📚 Technology Choices (From Spec)

- **Python**: ✓ Already chosen
- **FastAPI**: ✓ Already integrated
- **LangGraph**: Core orchestration framework (in progress)
- **LangChain**: LLM abstraction (to integrate)
- **PostgreSQL**: Resource storage (Day 6)
- **pgvector**: Semantic search (Day 6-7)
- **SQLAlchemy**: ORM (Day 6)
- **Redis**: Caching (optional, Day 8)
- **LLMs**: DeepSeek ✓, Gemini ✓, OpenAI, Claude, Kimi, Llama
