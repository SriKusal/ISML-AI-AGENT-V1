# ADR-001: LLM Provider Abstraction

**Date:** 2026-08  
**Status:** Accepted

## Context

The system needs to call different LLM providers (Gemini, DeepSeek, and potentially others). Business logic should not be coupled to any specific provider.

## Decision

Define `BaseLLMProvider` as an ABC with a single method `generate_text(prompt, model) -> dict`. All providers implement this interface. `LLMProviderFactory.create(provider_name)` returns the correct implementation. The workflow depends only on the interface — zero provider-specific code in `workflow.py`.

## Consequences

- Switching providers requires only changing the `provider` field in the API request.
- Adding a new provider (OpenAI, Claude, Llama) requires implementing one class and one factory case.
- Provider-specific retry configs can be set per-provider without affecting business logic.
