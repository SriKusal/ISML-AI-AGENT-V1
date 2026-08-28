# ADR-003: LangGraph-Style Workflow Orchestration

**Date:** 2026-08  
**Status:** Accepted

## Context

The resource intelligence pipeline has many sequential stages (12 nodes). Each node needs to read from and write to shared state. The workflow needs retry loops, conditional branching (knowledge retrieval shortcut), and repair-retry for LLM output.

## Decision

Use a phase-driven state machine pattern: `AgentPhase` enum, `ResourceIntelligenceState` dataclass, and `WorkflowNodes` class. `ResourceIntelligenceGraph` maps phases to node functions. The `execute_workflow()` loop calls nodes until `AgentPhase.COMPLETE`. This is a lightweight implementation of the LangGraph pattern without requiring the LangGraph library itself.

## Consequences

- No external graph library dependency — pure Python, easy to test.
- Each node is a pure function (or async function) that takes state in and returns state out.
- Retry and repair loops are implemented as phase rewinds (set `phase = BUILD_PROMPT` to retry).
- Knowledge retrieval shortcut implemented as a conditional phase jump.
- Adding new nodes requires only adding a new `AgentPhase`, node function, and graph mapping entry.
