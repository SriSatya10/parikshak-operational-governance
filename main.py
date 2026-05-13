"""
Parikshak Operational Governance — Main Entry Point
=====================================================
Full demonstration of the operational governance flow:
  - Multiple submissions through the pipeline
  - Approval/rejection/hold cycles
  - Replay reconstruction proof
  - Determinism proof
  - Observability log output

Usage:
    python main.py
"""
import json
import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(__file__))

from src.governance.governance_orchestrator import GovernanceOrchestrator


# ── Simulated Pipeline Outputs (from upstream integration pipeline) ──────────

PASS_OUTPUTS = [
    {
        "trace_id": "TRACE-001",
        "submission_id": "SUB-001",
        "evaluation_result": "PASS",
        "failure_type": None,
        "selected_task_id": "TASK_001",
        "selection_reason": "Authentication failure detected - route to token validation.",
        "source": "task_graph",
    },
    {
        "trace_id": "TRACE-002",
        "submission_id": "SUB-002",
        "evaluation_result": "PASS",
        "failure_type": None,
        "selected_task_id": "TASK_004",
        "selection_reason": "Invalid API payload - route to request validation.",
        "source": "task_graph",
    },
    {
        "trace_id": "TRACE-003",
        "submission_id": "SUB-003",
        "evaluation_result": "PASS",
        "failure_type": None,
        "selected_task_id": "TASK_006",
        "selection_reason": "Standard processing requested - route to data pipeline.",
        "source": "task_graph",
    },
]

FAIL_OUTPUTS = [
    {
        "trace_id": "TRACE-FAIL-001",
        "submission_id": "SUB-FAIL-001",
        "evaluation_result": "FAIL",
        "failure_type": "schema_violation",
        "selected_task_id": "NONE",
        "selection_reason": "HARD FAIL: product must not be empty.",
        "source": "task_graph",
    },
    {
        "trace_id": "TRACE-FAIL-002",
        "submission_id": "SUB-FAIL-002",
        "evaluation_result": "FAIL",
        "failure_type": "incorrect_logic",
        "selected_task_id": "NONE",
        "selection_reason": "No rule matched for layer='xyz', subsystem='abc'",
        "source": "task_graph",
    },
]

GRAPH_TRACES = {
    "TRACE-001": ["TASK_001", "TASK_002", "TASK_003"],
    "TRACE-002": ["TASK_004", "TASK_005"],
    "TRACE-003": ["TASK_006", "TASK_007"],
}


def print_separator(char="=", width=70):
    print(char * width)


def print_header(title):
    print_separator()
    print(f"  {title}")
    print_separator()


def print_sub_header(title):
    print_separator("-")
    print(f"  {title}")
    print_separator("-")


def main():
    # Use temp dir for clean state each run
    state_dir = os.path.join(os.path.dirname(__file__), "data", "governance_state")
    gov = GovernanceOrchestrator(state_dir)
    gov.reset()

    all_results = {}

    print_header("PARIKSHAK OPERATIONAL GOVERNANCE — Full System Run")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 1: Submit pipeline outputs for governance review
    # ═══════════════════════════════════════════════════════════════════════
    print_header("STEP 1: SUBMISSIONS → PENDING_REVIEW QUEUE")

    for output in PASS_OUTPUTS + FAIL_OUTPUTS:
        trace = GRAPH_TRACES.get(output["trace_id"], [])
        entry = gov.submit(output, graph_traversal_trace=trace)
        print(f"  ✓ Queued: {entry['queue_entry_id']:20s} | "
              f"trace={entry['trace_id']:16s} | "
              f"task={entry['selected_task_id']:10s} | "
              f"result={entry['evaluation_result']}")

    counts = gov.get_queue_counts()
    print(f"\n  Queue Counts: {json.dumps(counts)}")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 2: Human Approval Decisions
    # ═══════════════════════════════════════════════════════════════════════
    print_header("STEP 2: HUMAN APPROVAL DECISIONS")

    # Approve first PASS
    r = gov.approve("QE-SUB-001", "operator_01", "Validated against SLA criteria. Token check required.")
    print(f"  ✓ {r['action']:8s} {r['queue_entry_id']} by {r['approver_id']}")

    # Approve second PASS
    r = gov.approve("QE-SUB-002", "operator_01", "API validation confirmed. Route to handler.")
    print(f"  ✓ {r['action']:8s} {r['queue_entry_id']} by {r['approver_id']}")

    # Hold third PASS for escalation
    r = gov.hold("QE-SUB-003", "operator_02", "Requires senior review - data pipeline change.")
    print(f"  ✓ {r['action']:8s} {r['queue_entry_id']} by {r['approver_id']}")

    # Reject first FAIL
    r = gov.reject("QE-SUB-FAIL-001", "operator_01", "Schema violation confirmed. Invalid submission.")
    print(f"  ✓ {r['action']:8s} {r['queue_entry_id']} by {r['approver_id']}")

    # Reject second FAIL
    r = gov.reject("QE-SUB-FAIL-002", "operator_02", "No valid rule match. Submission malformed.")
    print(f"  ✓ {r['action']:8s} {r['queue_entry_id']} by {r['approver_id']}")

    # Now approve the escalated one (senior approved)
    r = gov.approve("QE-SUB-003", "senior_operator", "Reviewed and cleared. Pipeline change acceptable.")
    print(f"  ✓ {r['action']:8s} {r['queue_entry_id']} by {r['approver_id']}")

    counts = gov.get_queue_counts()
    print(f"\n  Final Queue Counts: {json.dumps(counts)}")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 3: Replay Reconstruction
    # ═══════════════════════════════════════════════════════════════════════
    print_header("STEP 3: REPLAY RECONSTRUCTION")

    for trace_id in ["TRACE-001", "TRACE-003", "TRACE-FAIL-001"]:
        print_sub_header(f"Replay: {trace_id}")
        report = gov.reconstruct_audit(trace_id)
        if report:
            print(report)
        else:
            print(f"  [ERROR] Trace {trace_id} not found!")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 4: Execution Timeline
    # ═══════════════════════════════════════════════════════════════════════
    print_header("STEP 4: EXECUTION TIMELINE (TRACE-001)")

    timeline = gov.get_timeline("TRACE-001")
    for i, event in enumerate(timeline, 1):
        etype = event.get("event_type") or event.get("action")
        ts = event["timestamp"]
        print(f"  {i:2d}. [{ts}] {event['type']:14s} | {etype}")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 5: Determinism Proof
    # ═══════════════════════════════════════════════════════════════════════
    print_header("STEP 5: DETERMINISM PROOF")

    print("  Running 5 identical governance cycles...")
    det_results = []

    for run in range(5):
        det_dir = os.path.join(os.path.dirname(__file__), "data", f"det_test_{run}")
        det_gov = GovernanceOrchestrator(det_dir)
        det_gov.reset()

        det_gov.submit(PASS_OUTPUTS[0], graph_traversal_trace=["TASK_001", "TASK_002", "TASK_003"])
        det_gov.approve("QE-SUB-001", "operator_01", "Determinism test approval")
        audit = det_gov.reconstruct_audit_dict("TRACE-001")

        # Extract deterministic fields (exclude timestamps)
        det_fields = {
            "trace_id": audit["trace_id"],
            "submission_id": audit["submission_id"],
            "evaluation_result": audit["evaluation_result"],
            "selected_task_id": audit["selected_task_id"],
            "queue_status": audit["queue_status"],
            "lifecycle_complete": audit["lifecycle_complete"],
            "graph_traversal_trace": audit["graph_traversal_trace"],
        }
        det_results.append(det_fields)
        print(f"  Run {run+1}: status={det_fields['queue_status']} task={det_fields['selected_task_id']} complete={det_fields['lifecycle_complete']}")

        # Clean up
        shutil.rmtree(det_dir, ignore_errors=True)

    if all(r == det_results[0] for r in det_results):
        print("\n  [PASS] DETERMINISM VERIFIED — All 5 runs produced identical governance results.")
    else:
        print("\n  [FAIL] DETERMINISM FAILED — Results differ!")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 6: Observability Log Summary
    # ═══════════════════════════════════════════════════════════════════════
    print_header("STEP 6: OBSERVABILITY LOG SUMMARY")

    all_obs = gov.get_all_observability_events()
    type_counts = {}
    severity_counts = {}
    for e in all_obs:
        t = e["event_type"]
        s = e["severity"]
        type_counts[t] = type_counts.get(t, 0) + 1
        severity_counts[s] = severity_counts.get(s, 0) + 1

    print(f"  Total events: {len(all_obs)}")
    print(f"  By type:     {json.dumps(type_counts, indent=None)}")
    print(f"  By severity: {json.dumps(severity_counts, indent=None)}")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 7: Approval/Rejection Audit Logs
    # ═══════════════════════════════════════════════════════════════════════
    print_header("STEP 7: APPROVAL/REJECTION AUDIT LOG")

    store = gov._store
    all_events = store.get_all_approval_events()
    for evt in all_events:
        print(f"  {evt['event_id']:25s} | {evt['action']:8s} | "
              f"{evt['previous_status']:16s} → {evt['new_status']:12s} | "
              f"by {evt['approver_id']} — \"{evt['reason'][:50]}\"")

    # ═══════════════════════════════════════════════════════════════════════
    # Save all results
    # ═══════════════════════════════════════════════════════════════════════
    output_dir = os.path.join(os.path.dirname(__file__), "outputs")
    os.makedirs(output_dir, exist_ok=True)

    # Save observability log
    obs_path = os.path.join(output_dir, "observability_log.json")
    with open(obs_path, "w", encoding="utf-8") as f:
        json.dump(all_obs, f, indent=2, ensure_ascii=False)

    # Save approval log
    approval_path = os.path.join(output_dir, "approval_audit_log.json")
    with open(approval_path, "w", encoding="utf-8") as f:
        json.dump(all_events, f, indent=2, ensure_ascii=False)

    # Save queue state
    queue_path = os.path.join(output_dir, "queue_state.json")
    all_entries = gov._queue.get_all_entries()
    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, indent=2, ensure_ascii=False)

    # Save audit reconstructions
    audit_path = os.path.join(output_dir, "audit_reconstructions.json")
    audits = {}
    for trace_id in ["TRACE-001", "TRACE-002", "TRACE-003", "TRACE-FAIL-001", "TRACE-FAIL-002"]:
        audits[trace_id] = gov.reconstruct_audit_dict(trace_id)
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audits, f, indent=2, ensure_ascii=False)

    print(f"\n  Saved: {obs_path}")
    print(f"  Saved: {approval_path}")
    print(f"  Saved: {queue_path}")
    print(f"  Saved: {audit_path}")

    print_header("DONE — ALL GOVERNANCE FLOWS COMPLETE")


if __name__ == "__main__":
    main()
