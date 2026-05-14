# Parikshak Evaluation Engine

**Canonical Ownership:** `/evaluation_engine` → Sri Satya

Deterministic task evaluation layer for the TANTRA workflow.
Provides evaluation correctness, deterministic failure classification, schema discipline, replay-safe observability logs, and strict contract continuity.

**This is purely an evaluation layer.** It does NOT own:
- Traversal authority
- Governance approval or routing
- Operational override logic
- Assignment release
- Workflow orchestration

## Architecture
```
Upstream Pipeline (Ishan)
    |
    v
[Pipeline Output - 7-field contract]
    |
    v
EVALUATION RUNNER (evaluate())
    |
    +-- Contract Monitor (validates 7-field contract)
    +-- Observability Emitter (structured event logs)
    |
    v
RETURNS VALIDATED OUTPUT TO PIPELINE
```

## 7-Field Output Contract
Every pipeline output must strictly contain exactly these 7 fields. Any deviation results in a HARD FAIL.

```json
{
    "trace_id": "TRACE-001",
    "submission_id": "SUB-001",
    "evaluation_result": "PASS",
    "failure_type": null,
    "selected_task_id": "TASK_001",
    "selection_reason": "Authentication failure detected",
    "source": "task_graph"
}
```

## Project Structure
```
src/
    evaluation_engine/
        evaluation_runner.py       # Single entry point
        contract_monitor.py        # 7-field contract validation
        observability.py           # Structured event logs
        event_store.py             # JSON persistent storage for logs
        evaluation_models.py       # Data models
tests/
    test_determinism.py            # Validates strict mathematical determinism
    test_observability.py          # Validates logging and no silent failures
    test_concurrent.py             # Thread-safety tests
```

## Quick Start
```bash
# Run full evaluation demonstration
python main.py

# Run tests
pytest tests/ -v
```

## Evaluation Rules
1. **Deterministic guarantees** - Same input always yields the exact same evaluation result. No hidden probabilistic behavior.
2. **Schema Integrity** - Empty fields or malformed dictionaries throw a CRITICAL failure immediately.
3. **No silent failures** - Every state change emits a structured observability log.
4. **Trace continuity** - `trace_id` is propagated exactly as received from upstream to ensure replay-safe output compatibility.
