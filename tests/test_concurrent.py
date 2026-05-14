"""
Parikshak Evaluation Engine — Concurrency Tests
======================================================
Tests: concurrent evaluations and safe writes to observability log.
"""
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.evaluation_engine.evaluation_runner import EvaluationRunner


def _make_output(trace_id, sub_id):
    return {
        "trace_id": trace_id,
        "submission_id": sub_id,
        "evaluation_result": "PASS",
        "failure_type": None,
        "selected_task_id": "TASK_001",
        "selection_reason": "Test",
        "source": "task_graph",
    }


class TestConcurrency:
    """Concurrent evaluation tests."""

    def test_concurrent_evaluations(self, tmp_path):
        """Multiple threads evaluating concurrently — no crashes, logs properly appended."""
        runner = EvaluationRunner(str(tmp_path / "state"))
        errors = []

        def submit(idx):
            try:
                runner.evaluate(_make_output(f"T-{idx}", f"S-{idx}"))
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=submit, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        events = runner.get_all_observability_events()
        # Each evaluation produces 2 events: SUBMISSION and EVALUATION
        assert len(events) == 40
