"""
Parikshak Evaluation Engine — Determinism Tests
======================================================
Proves: same input = same evaluation result and contract validation.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.evaluation_engine.evaluation_runner import EvaluationRunner


def _make_output(trace_id="T1", sub_id="S1"):
    return {
        "trace_id": trace_id,
        "submission_id": sub_id,
        "evaluation_result": "PASS",
        "failure_type": None,
        "selected_task_id": "TASK_001",
        "selection_reason": "Auth failure - token validation.",
        "source": "task_graph",
    }


def _make_fail_output(trace_id="TF1", sub_id="SF1"):
    return {
        "trace_id": trace_id,
        "submission_id": sub_id,
        "evaluation_result": "FAIL",
        "failure_type": "schema_violation",
        "selected_task_id": "NONE",
        "selection_reason": "HARD FAIL: product must not be empty.",
        "source": "task_graph",
    }


class TestDeterminism:
    """Deterministic evaluation tests."""

    def test_same_input_same_evaluation_result(self, tmp_path):
        """Same pipeline output → same evaluation result."""
        results = []
        for i in range(5):
            runner = EvaluationRunner(str(tmp_path / f"run_{i}"))
            output = runner.evaluate(_make_output(), ["TASK_001", "TASK_002"])
            det = {
                "trace_id": output["trace_id"],
                "submission_id": output["submission_id"],
                "evaluation_result": output["evaluation_result"],
                "failure_type": output["failure_type"],
                "selected_task_id": output["selected_task_id"],
            }
            results.append(det)

        assert all(r == results[0] for r in results)

    def test_fail_output_determinism(self, tmp_path):
        results = []
        for i in range(5):
            runner = EvaluationRunner(str(tmp_path / f"run_{i}"))
            output = runner.evaluate(_make_fail_output())
            det = {
                "trace_id": output["trace_id"],
                "evaluation_result": output["evaluation_result"],
                "failure_type": output["failure_type"],
                "selected_task_id": output["selected_task_id"],
            }
            results.append(det)

        assert all(r == results[0] for r in results)

    def test_observability_event_determinism(self, tmp_path):
        """Same input produces the same deterministic observability log."""
        results = []
        for i in range(5):
            runner = EvaluationRunner(str(tmp_path / f"run_{i}"))
            runner.evaluate(_make_output())
            events = runner.get_all_observability_events()
            # Extract deterministic fields (ignore timestamp)
            det = [(e["event_type"], e["trace_id"], e["severity"]) for e in events]
            results.append(det)

        assert all(r == results[0] for r in results)
