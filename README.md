# Parikshak Operational Governance

Operational governance layer for the Parikshak deterministic task evaluation system.
Provides human-governed approval workflows, replay visibility, audit reconstruction,
and observability hardening.

**This is NOT a capability expansion.** This layer sits downstream of the deterministic
traversal engine and enforces operational governance without modifying routing, evaluation,
or task selection logic.

## Architecture

```
Upstream Pipeline (Ishan)
    |
    v
[Pipeline Output - 7-field contract]
    |
    v
GOVERNANCE ORCHESTRATOR
    |
    +-- Contract Monitor (validates 7-field contract)
    +-- Observability Emitter (structured event logs)
    |
    v
APPROVAL QUEUE (PENDING_REVIEW)
    |
    +-- APPROVE --> APPROVED queue --> Assignment Visibility
    +-- REJECT  --> REJECTED queue --> Rejection Reasoning
    +-- HOLD    --> ESCALATED queue --> Senior Review
    |
    v
REPLAY ENGINE (trace_id lookup)
    |
    v
AUDIT RECONSTRUCTOR (human-readable lifecycle report)
```

## Expected Flow

```
Submission --> Evaluation --> Deterministic Traversal
    --> Human Approval Queue --> Approval Decision
    --> Assignment Visibility --> Bucket Persistence
    --> Replay Visibility --> Audit Reconstruction
```

## Components

| Component | Purpose |
|-----------|---------|
| `governance_orchestrator.py` | Single entry point for governance operations |
| `approval_queue.py` | FIFO queue with 4 statuses: PENDING_REVIEW, APPROVED, REJECTED, ESCALATED |
| `approval_engine.py` | APPROVE/REJECT/HOLD actions with mandatory reasoning |
| `approval_log.py` | Immutable append-only approval event log |
| `queue_store.py` | JSON-file-backed persistent storage (thread-safe) |
| `replay_engine.py` | Trace-based lifecycle reconstruction |
| `audit_reconstructor.py` | Human-readable audit reports |
| `observability.py` | Structured event emitter (no silent failures) |
| `contract_monitor.py` | 7-field contract validation |

## 7-Field Output Contract

Every pipeline output must contain exactly these 7 fields:

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

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run full governance demonstration
python main.py

# Run all tests (81 tests)
python -m pytest tests/ -v
```

## Project Structure

```
src/
    governance/
        governance_orchestrator.py   # Single entry point
        approval_queue.py            # Queue management
        approval_engine.py           # Approval actions
        approval_log.py              # Immutable log
        queue_store.py               # Persistent storage
    audit/
        replay_engine.py             # Replay by trace_id
        audit_reconstructor.py       # Audit reports
    observability/
        observability.py             # Structured event logs
        contract_monitor.py          # Contract validation
    models/
        governance_models.py         # Data models & constants
tests/
    test_approval_queue.py           # 15 tests
    test_approval_engine.py          # 18 tests
    test_replay.py                   # 14 tests
    test_observability.py            # 22 tests
    test_determinism.py              # 7 tests
    test_concurrent.py               # 5 tests
data/
    governance_state/                # Runtime state (queues, logs)
outputs/                             # Execution outputs
review_packets/
    REVIEW_PACKET.md                 # Review documentation
```

## Governance Rules

1. **No automatic assignment release** - every submission requires explicit human approval
2. **Approval reason mandatory** - empty reason = HARD FAIL
3. **Immutable audit log** - append-only, never modified
4. **Trace continuity** - trace_id flows unchanged through entire lifecycle
5. **No silent failures** - every event emits structured observability log
6. **Deterministic ordering** - FIFO queue, insertion order preserved
7. **No hidden state** - all state persisted to JSON files

## Integration Map

| Owner | Responsibility |
|-------|---------------|
| Ishan Shirode | Deterministic traversal engine, graph integrity, replay-safe routing |
| SriSatya (this repo) | Operational governance, approval workflows, observability, audit |
| Raj Prajapati | Downstream assignment visibility, execution-chain participation |
| Vinayak Tiwari | Operational testing, replay correctness validation |

## Constraints Preserved

- Deterministic traversal: untouched (upstream)
- DB-only routing: untouched (upstream)
- Immutable trace propagation: trace_id unchanged through governance
- Replay-safe outputs: all state reconstructable from trace_id
- Strict contract discipline: 7-field contract enforced at governance boundary
- No hidden authority layers: all state explicit and visible
