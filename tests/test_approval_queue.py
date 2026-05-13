"""
Parikshak Operational Governance — Approval Queue Tests
=========================================================
Tests: FIFO ordering, all four queue states, trace/task/failure visibility.
"""
import os
import sys
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.governance.queue_store import QueueStore
from src.governance.approval_queue import ApprovalQueue
from src.models.governance_models import PENDING_REVIEW, APPROVED, REJECTED, ESCALATED


@pytest.fixture
def queue_env(tmp_path):
    store = QueueStore(str(tmp_path / "state"))
    queue = ApprovalQueue(store)
    return store, queue


def _make_output(trace_id="T1", sub_id="S1", result="PASS",
                 ft=None, task="TASK_001"):
    return {
        "trace_id": trace_id,
        "submission_id": sub_id,
        "evaluation_result": result,
        "failure_type": ft,
        "selected_task_id": task,
        "selection_reason": "Test reason",
        "source": "task_graph",
    }


class TestApprovalQueue:
    """Phase 1: Approval Queue Layer tests."""

    def test_enqueue_creates_pending_entry(self, queue_env):
        store, queue = queue_env
        entry = queue.enqueue(_make_output())
        assert entry.queue_status == PENDING_REVIEW
        assert entry.queue_entry_id == "QE-S1"
        assert entry.trace_id == "T1"

    def test_enqueue_deterministic_id(self, queue_env):
        store, queue = queue_env
        entry = queue.enqueue(_make_output(sub_id="SUB-123"))
        assert entry.queue_entry_id == "QE-SUB-123"

    def test_fifo_ordering(self, queue_env):
        store, queue = queue_env
        queue.enqueue(_make_output(trace_id="T1", sub_id="S1"))
        queue.enqueue(_make_output(trace_id="T2", sub_id="S2"))
        queue.enqueue(_make_output(trace_id="T3", sub_id="S3"))

        pending = queue.get_pending_review()
        assert len(pending) == 3
        assert pending[0]["trace_id"] == "T1"
        assert pending[1]["trace_id"] == "T2"
        assert pending[2]["trace_id"] == "T3"

    def test_trace_visibility(self, queue_env):
        store, queue = queue_env
        queue.enqueue(_make_output(trace_id="TRACE-XYZ", sub_id="S1"))
        entry = queue.get_entry("QE-S1")
        assert entry["trace_id"] == "TRACE-XYZ"

    def test_task_id_visibility(self, queue_env):
        store, queue = queue_env
        queue.enqueue(_make_output(task="TASK_042"))
        entry = queue.get_entry("QE-S1")
        assert entry["selected_task_id"] == "TASK_042"

    def test_failure_type_visibility(self, queue_env):
        store, queue = queue_env
        queue.enqueue(_make_output(result="FAIL", ft="schema_violation", task="NONE"))
        entry = queue.get_entry("QE-S1")
        assert entry["failure_type"] == "schema_violation"
        assert entry["evaluation_result"] == "FAIL"

    def test_replay_lookup_by_trace_id(self, queue_env):
        store, queue = queue_env
        queue.enqueue(_make_output(trace_id="TRACE-REPLAY", sub_id="S1"))
        found = queue.lookup_by_trace_id("TRACE-REPLAY")
        assert found is not None
        assert found["trace_id"] == "TRACE-REPLAY"

    def test_replay_lookup_not_found(self, queue_env):
        store, queue = queue_env
        found = queue.lookup_by_trace_id("NONEXISTENT")
        assert found is None

    def test_duplicate_entry_fails(self, queue_env):
        store, queue = queue_env
        queue.enqueue(_make_output(sub_id="S1"))
        with pytest.raises(ValueError, match="Duplicate"):
            queue.enqueue(_make_output(sub_id="S1"))

    def test_missing_trace_id_fails(self, queue_env):
        store, queue = queue_env
        output = _make_output()
        output["trace_id"] = ""
        with pytest.raises(ValueError, match="trace_id"):
            queue.enqueue(output)

    def test_missing_fields_fails(self, queue_env):
        store, queue = queue_env
        with pytest.raises(ValueError, match="missing"):
            queue.enqueue({"trace_id": "T1"})

    def test_queue_counts(self, queue_env):
        store, queue = queue_env
        queue.enqueue(_make_output(sub_id="S1"))
        queue.enqueue(_make_output(sub_id="S2"))
        counts = queue.get_queue_counts()
        assert counts[PENDING_REVIEW] == 2
        assert counts[APPROVED] == 0
        assert counts[REJECTED] == 0
        assert counts[ESCALATED] == 0

    def test_graph_traversal_trace_stored(self, queue_env):
        store, queue = queue_env
        trace = ["TASK_001", "TASK_002", "TASK_003"]
        entry = queue.enqueue(_make_output(), graph_traversal_trace=trace)
        assert entry.graph_traversal_trace == trace

    def test_pipeline_output_preserved(self, queue_env):
        store, queue = queue_env
        output = _make_output()
        entry = queue.enqueue(output)
        assert entry.pipeline_output == output

    def test_get_all_entries_ordered(self, queue_env):
        store, queue = queue_env
        for i in range(5):
            queue.enqueue(_make_output(trace_id=f"T{i}", sub_id=f"S{i}"))
        entries = queue.get_all_entries()
        assert len(entries) == 5
        for i in range(5):
            assert entries[i]["trace_id"] == f"T{i}"
