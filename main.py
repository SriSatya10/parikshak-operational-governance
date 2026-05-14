"""
Parikshak Evaluation Engine — Main Entry Point
=====================================================
Full demonstration of the evaluation engine flow:
  - Validates 7-field contract
  - Emits observability logs
  - Rejects malformed outputs (contract violation)

Usage:
    python main.py
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.evaluation_engine.evaluation_runner import EvaluationRunner


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
]

MALFORMED_OUTPUTS = [
    {
        "trace_id": "TRACE-BAD-001",
        "submission_id": "SUB-BAD-001",
        "evaluation_result": "PASS",
        "failure_type": "schema_violation", # Invalid: PASS cannot have failure_type
        "selected_task_id": "TASK_001",
        "selection_reason": "Bad.",
        "source": "wrong_source",           # Invalid source
    }
]


def print_separator(char="=", width=70):
    print(char * width)


def print_header(title):
    print_separator()
    print(f"  {title}")
    print_separator()


def main():
    # Use temp dir for clean state each run
    state_dir = os.path.join(os.path.dirname(__file__), "data", "evaluation_state")
    runner = EvaluationRunner(state_dir)
    runner.reset()

    print_header("PARIKSHAK EVALUATION ENGINE — Full System Run")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 1: Process Valid Outputs
    # ═══════════════════════════════════════════════════════════════════════
    print_header("STEP 1: EVALUATE VALID OUTPUTS")

    for output in PASS_OUTPUTS + FAIL_OUTPUTS:
        try:
            entry = runner.evaluate(output)
            print(f"  [PASS] Evaluated: trace={entry['trace_id']:16s} | "
                  f"task={entry['selected_task_id']:10s} | "
                  f"result={entry['evaluation_result']}")
        except ValueError as e:
            print(f"  [FAIL] Rejected: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 2: Process Malformed Outputs (Contract Violation)
    # ═══════════════════════════════════════════════════════════════════════
    print_header("STEP 2: EVALUATE MALFORMED OUTPUTS (CONTRACT ENFORCEMENT)")

    for output in MALFORMED_OUTPUTS:
        try:
            runner.evaluate(output)
            print(f"  [PASS] Evaluated: trace={output['trace_id']}")
        except ValueError as e:
            print(f"  [FAIL] Rejected (Expected): {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 3: Observability Log Summary
    # ═══════════════════════════════════════════════════════════════════════
    print_header("STEP 3: OBSERVABILITY LOG SUMMARY")

    all_obs = runner.get_all_observability_events()
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
    # Save all results
    # ═══════════════════════════════════════════════════════════════════════
    output_dir = os.path.join(os.path.dirname(__file__), "outputs")
    os.makedirs(output_dir, exist_ok=True)

    # Save observability log
    obs_path = os.path.join(output_dir, "observability_log.json")
    with open(obs_path, "w", encoding="utf-8") as f:
        json.dump(all_obs, f, indent=2, ensure_ascii=False)

    print(f"\n  Saved: {obs_path}")

    print_header("DONE — ALL EVALUATION FLOWS COMPLETE")


if __name__ == "__main__":
    main()
