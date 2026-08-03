#!/usr/bin/env python
"""Test Day 3 workflow execution."""

import asyncio
from app.agents import (
    ResourceIntelligenceState,
    AgentPhase,
    create_resource_intelligence_graph,
)


async def test_workflow():
    # Create state
    state = ResourceIntelligenceState(
        domain="language_learning",
        course="French A1",
        topic="Greetings",
        difficulty_level="Beginner",
        provider="gemini",
        model="gemini-3.5-flash"
    )
    
    print("=" * 70)
    print("TESTING DAY 3 WORKFLOW")
    print("=" * 70)
    print(f"\n✓ Initial state created")
    print(f"  Domain: {state.domain}")
    print(f"  Course: {state.course}")
    print(f"  Topic: {state.topic}")
    print(f"  Phase: {state.phase.value}")
    
    # Create graph
    graph = create_resource_intelligence_graph()
    print(f"\n✓ Graph created with {len(graph.get_node_functions())} nodes")
    print(f"  Nodes: {', '.join(graph.get_node_functions().keys())}")
    
    # Execute workflow
    print("\n" + "=" * 70)
    print("EXECUTING WORKFLOW")
    print("=" * 70)
    
    max_iterations = 50
    iteration = 0
    
    while state.phase != AgentPhase.COMPLETE and iteration < max_iterations:
        iteration += 1
        node_name = graph.get_next_node(state)
        node_func = graph.get_node_functions().get(node_name)
        
        print(f"\n[{iteration}] Executing: {node_name} (phase: {state.phase.value})")
        
        # Check if node is async
        if asyncio.iscoroutinefunction(node_func):
            state = await node_func(state)
        else:
            state = node_func(state)
        
        # Print state updates
        if state.topic_understanding:
            print(f"    → Topic understood with {len(state.topic_understanding)} fields")
        if state.search_queries:
            print(f"    → Search queries generated: {len(state.search_queries)}")
            print(f"    → Samples: {state.search_queries[:2]}")
        if state.messages:
            print(f"    → Message: {state.messages[-1]}")
    
    print("\n" + "=" * 70)
    print("WORKFLOW COMPLETED")
    print("=" * 70)
    print(f"\n✓ Final Phase: {state.phase.value}")
    print(f"✓ Attempts: {state.attempt_count}")
    print(f"✓ Errors: {len(state.validation_errors)}")
    print(f"✓ Messages: {len(state.messages)}")
    
    print("\n--- Topic Understanding ---")
    if state.topic_understanding:
        for key, value in state.topic_understanding.items():
            if isinstance(value, list):
                val_str = ", ".join(value[:2]) + ("..." if len(value) > 2 else "")
                print(f"  {key}: {val_str}")
            else:
                print(f"  {key}: {value}")
    
    print("\n--- Search Queries Generated ---")
    for i, query in enumerate(state.search_queries[:8], 1):
        print(f"  {i}. {query}")
    if len(state.search_queries) > 8:
        print(f"  ... and {len(state.search_queries) - 8} more")
    
    print("\n--- Messages Log ---")
    for msg in state.messages:
        print(f"  • {msg}")
    
    if state.validation_errors:
        print("\n--- Errors ---")
        for err in state.validation_errors:
            print(f"  ✗ {err}")
    else:
        print("\n✓ No errors!")
    
    return state


if __name__ == "__main__":
    asyncio.run(test_workflow())
