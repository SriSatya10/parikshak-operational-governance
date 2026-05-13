"""
Parikshak Operational Governance — Replay Tests
=================================================
Tests: replay by trace_id, execution timeline, rejection reasoning,
       failure route visibility.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.governance.queue_store import QueueStore
from src.governance.approval_queue import ApprovalQueue
from src.governance.approval_engine import ApprovalEngine
from src.audit.replay_engine import ReplayEngine
from src.audit.audit_reconstructor import AuditReconstructor
from src.observability.observability import ObservabilityEmitter


@pytest.fixture
def replay_env(tmp_path):
    store = QueueStore(str(tmp_path / "state"))
    queue = ApprovalQueue(store)
    engine = ApprovalEngine(store)
    replay = ReplayEngine(store)
    auditor = AuditReconstructor(replay)
    emitter = ObservabilityEmitter(store)
    return store, queue, engine, replay, auditor, emitter


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


class TestReplayEngine:
    """Phase 3: Replay & Audit Visibility tests."""

    def test_replay_by_trace_id(self, replay_env):
        store, queue, engine, replay, auditor, emitter = replay_env
        queue.enqueue(_make_output(trace_id="TRACE-001"))
        result = replay.replay_by_trace_id("TRACE-001")
        assert result is not None
        assert result["trace_id"] == "TRACE-001"
        assert result["queue_entry"] is not None

    def test_replay_not_found(self, replay_env):
        store, queue, engine, replay, auditor, emitter = replay_env
        assert replay.replay_by_trace_id("NONEXISTENT") is None

    def test_replay_with_approval(self, replay_env):
        store, queue, engine, replay, auditor, emitter = replay_env
        queue.enqueue(_make_output(trace_id="TRACE-001"))
        engine.approve("QE-S1", "op1", "Approved")
        result = replay.replay_by_trace_id("TRACE-001")
        assert result["lifecycle_complete"] is True
        assert len(result["approval_events"]) == 1

    def test_replay_lifecycle_incomplete(self, replay_env):
        store, queue, engine, replay, auditor, emitter = replay_env
        queue.enqueue(_make_output(trace_id="TRACE-001"))
        result = replay.replay_by_trace_id("TRACE-001")
        assert result["lifecycle_complete"] is False

    def test_execution_timeline(self, replay_env):
        store, queue, engine, replay, auditor, emitter = replay_env
        emitter.emit_submission("TRACE-001", "S1")
        queue.enqueue(_make_output(trace_id="TRACE-001"))
        emitter.emit_queue_entry("TRACE-001", "QE-S1", "PENDING_REVIEW")
        engine.approve("QE-S1", "op1", "Approved")

        timeline = replay.get_execution_timeline("TRACE-001")
        assert len(timeline) >= 2
        # Should be chronologically sorted
        for i in range(len(timeline) - 1):
            assert timeline[i]["timestamp"] <= timeline[i+1]["timestamp"]

    def test_graph_traversal_visibility(self, replay_env):
        store, queue, engine, replay, auditor, emitter = replay_env
        trace = ["TASK_001", "TASK_002", "TASK_003"]
        queue.enqueue(_make_output(trace_id="TRACE-001"),
                      graph_traversal_trace=trace)
        result = replay.get_graph_traversal("TRACE-001")
        assert result == trace

    def test_rejection_reasoning(self, replay_env):
        store, queue, engine, replay, auditor, emitter = replay_env
        queue.enqueue(_make_output(trace_id="TRACE-001"))
        engine.reject("QE-S1", "op1", "Schema check failed")
        result = replay.get_rejection_reasoning("TRACE-001")
        assert result is not None
        assert len(result["rejection_events"]) == 1
        assert result["rejection_events"][0]["reason"] == "Schema check failed"

    def test_rejection_reasoning_not_rejected(self, replay_env):
        store, queue, engine, replay, auditor, emitter = replay_env
        queue.enqueue(_make_output(trace_id="TRACE-001"))
        engine.approve("QE-S1", "op1", "Approved")
        assert replay.get_rejection_reasoning("TRACE-001") is None

    def test_failure_route_visibility(self, replay_env):
        store, queue, engine, replay, auditor, emitter = replay_env
        queue.enqueue(_make_output(
            trace_id="TRACE-F1", result="FAIL",
            ft="schema_violation", task="NONE",
        ))
        result = replay.get_failure_route("TRACE-F1")
        assert result is not None
        assert result["failure_type"] == "schema_violation"
        assert result["evaluation_result"] == "FAIL"

    def test_failure_route_on_pass(self, replay_env):
        store, queue, engine, replay, auditor, emitter = replay_env
        queue.enqueue(_make_output(trace_id="TRACE-001"))
        assert replay.get_failure_route("TRACE-001") is None


class TestAuditReconstructor:
    """Phase 3: Audit reconstruction tests."""

    def test_audit_report_generation(self, replay_env):
        store, queue, engine, replay, auditor, emitter = replay_env
        queue.enqueue(_make_output(trace_id="TRACE-001"),
                      graph_traversal_trace=["TASK_001", "TASK_002"])
        engine.approve("QE-S1", "op1", "Validated")

        report = auditor.reconstruct("TRACE-001")
        assert report is not None
        assert "TRACE-001" in report
        assert "TASK_001" in report
        assert "APPROVED" in report or "APPROVE" in report
        assert "op1" in report

    def test_audit_report_not_found(self, replay_env):
        store, queue, engine, replay, auditor, emitter = replay_env
        assert auditor.reconstruct("NONEXISTENT") is None

    def test_audit_dict(self, replay_env):
        store, queue, engine, replay, auditor, emitter = replay_env
        queue.enqueue(_make_output(trace_id="TRACE-001"))
        engine.approve("QE-S1", "op1", "OK")

        d = auditor.reconstruct_dict("TRACE-001")
        assert d["trace_id"] == "TRACE-001"
        assert d["lifecycle_complete"] is True
        assert d["queue_status"] == "APPROVED"
        assert len(d["approval_events"]) == 1

    def test_audit_shows_rejection_chain(self, replay_env):
        store, queue, engine, replay, auditor, emitter = replay_env
        queue.enqueue(_make_output(trace_id="TRACE-001"))
        engine.reject("QE-S1", "op1", "Invalid data")

        report = auditor.reconstruct("TRACE-001")
        assert "REJECT" in report
        assert "Invalid data" in report
