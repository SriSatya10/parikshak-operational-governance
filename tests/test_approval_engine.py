"""
Parikshak Operational Governance — Approval Engine Tests
==========================================================
Tests: APPROVE/REJECT/HOLD actions, reason mandatory,
       immutable log, trace continuity.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.governance.queue_store import QueueStore
from src.governance.approval_queue import ApprovalQueue
from src.governance.approval_engine import ApprovalEngine
from src.models.governance_models import (
    PENDING_REVIEW, APPROVED, REJECTED, ESCALATED,
)


@pytest.fixture
def engine_env(tmp_path):
    store = QueueStore(str(tmp_path / "state"))
    queue = ApprovalQueue(store)
    engine = ApprovalEngine(store)
    return store, queue, engine


def _make_output(sub_id="S1", trace_id="T1"):
    return {
        "trace_id": trace_id,
        "submission_id": sub_id,
        "evaluation_result": "PASS",
        "failure_type": None,
        "selected_task_id": "TASK_001",
        "selection_reason": "Test",
        "source": "task_graph",
    }


class TestApprovalEngine:
    """Phase 2: Human Approval Lock tests."""

    def test_approve_success(self, engine_env):
        store, queue, engine = engine_env
        queue.enqueue(_make_output())
        result = engine.approve("QE-S1", "op1", "Approved after review")
        assert result["action"] == "APPROVE"
        assert result["new_status"] == APPROVED
        entry = store.get_entry("QE-S1")
        assert entry["queue_status"] == APPROVED

    def test_reject_success(self, engine_env):
        store, queue, engine = engine_env
        queue.enqueue(_make_output())
        result = engine.reject("QE-S1", "op1", "Rejected - invalid")
        assert result["action"] == "REJECT"
        assert result["new_status"] == REJECTED
        entry = store.get_entry("QE-S1")
        assert entry["queue_status"] == REJECTED

    def test_hold_success(self, engine_env):
        store, queue, engine = engine_env
        queue.enqueue(_make_output())
        result = engine.hold("QE-S1", "op1", "Needs senior review")
        assert result["action"] == "HOLD"
        assert result["new_status"] == ESCALATED
        entry = store.get_entry("QE-S1")
        assert entry["queue_status"] == ESCALATED

    def test_approve_from_escalated(self, engine_env):
        store, queue, engine = engine_env
        queue.enqueue(_make_output())
        engine.hold("QE-S1", "op1", "Escalating")
        result = engine.approve("QE-S1", "senior", "Senior approved")
        assert result["new_status"] == APPROVED
        assert result["previous_status"] == ESCALATED

    def test_reject_from_escalated(self, engine_env):
        store, queue, engine = engine_env
        queue.enqueue(_make_output())
        engine.hold("QE-S1", "op1", "Escalating")
        result = engine.reject("QE-S1", "senior", "Senior rejected")
        assert result["new_status"] == REJECTED

    def test_empty_reason_fails(self, engine_env):
        store, queue, engine = engine_env
        queue.enqueue(_make_output())
        with pytest.raises(ValueError, match="reason"):
            engine.approve("QE-S1", "op1", "")

    def test_whitespace_reason_fails(self, engine_env):
        store, queue, engine = engine_env
        queue.enqueue(_make_output())
        with pytest.raises(ValueError, match="reason"):
            engine.approve("QE-S1", "op1", "   ")

    def test_empty_approver_fails(self, engine_env):
        store, queue, engine = engine_env
        queue.enqueue(_make_output())
        with pytest.raises(ValueError, match="approver_id"):
            engine.approve("QE-S1", "", "Good reason")

    def test_cannot_approve_already_approved(self, engine_env):
        store, queue, engine = engine_env
        queue.enqueue(_make_output())
        engine.approve("QE-S1", "op1", "First approval")
        with pytest.raises(ValueError, match="Cannot APPROVE"):
            engine.approve("QE-S1", "op1", "Second approval")

    def test_cannot_reject_already_rejected(self, engine_env):
        store, queue, engine = engine_env
        queue.enqueue(_make_output())
        engine.reject("QE-S1", "op1", "First rejection")
        with pytest.raises(ValueError, match="Cannot REJECT"):
            engine.reject("QE-S1", "op1", "Second rejection")

    def test_cannot_hold_already_approved(self, engine_env):
        store, queue, engine = engine_env
        queue.enqueue(_make_output())
        engine.approve("QE-S1", "op1", "Approved")
        with pytest.raises(ValueError, match="Cannot HOLD"):
            engine.hold("QE-S1", "op1", "Trying to hold")

    def test_nonexistent_entry_fails(self, engine_env):
        store, queue, engine = engine_env
        with pytest.raises(ValueError, match="not found"):
            engine.approve("QE-FAKE", "op1", "Testing")

    def test_immutable_log_records(self, engine_env):
        store, queue, engine = engine_env
        queue.enqueue(_make_output())
        engine.approve("QE-S1", "op1", "Approved reason")
        events = engine.get_approval_history("QE-S1")
        assert len(events) == 1
        assert events[0]["action"] == "APPROVE"
        assert events[0]["approver_id"] == "op1"
        assert events[0]["reason"] == "Approved reason"

    def test_trace_continuity(self, engine_env):
        store, queue, engine = engine_env
        queue.enqueue(_make_output(trace_id="TRACE-XYZ"))
        engine.approve("QE-S1", "op1", "Trace test")
        events = engine.get_approval_history("QE-S1")
        assert events[0]["trace_id"] == "TRACE-XYZ"

    def test_trace_lookup_in_approval_history(self, engine_env):
        store, queue, engine = engine_env
        queue.enqueue(_make_output(trace_id="TRACE-ABC"))
        engine.approve("QE-S1", "op1", "Test")
        events = engine.get_approval_history_by_trace("TRACE-ABC")
        assert len(events) == 1
        assert events[0]["trace_id"] == "TRACE-ABC"

    def test_multiple_events_for_escalation_flow(self, engine_env):
        store, queue, engine = engine_env
        queue.enqueue(_make_output())
        engine.hold("QE-S1", "op1", "Needs review")
        engine.approve("QE-S1", "senior", "Senior approved")
        events = engine.get_approval_history("QE-S1")
        assert len(events) == 2
        assert events[0]["action"] == "HOLD"
        assert events[1]["action"] == "APPROVE"

    def test_event_id_is_deterministic(self, engine_env):
        store, queue, engine = engine_env
        queue.enqueue(_make_output())
        engine.approve("QE-S1", "op1", "Test")
        events = engine.get_approval_history("QE-S1")
        assert events[0]["event_id"] == "EVT-QE-S1-001"

    def test_no_automatic_release(self, engine_env):
        """Verify that enqueueing does NOT auto-approve."""
        store, queue, engine = engine_env
        queue.enqueue(_make_output())
        entry = store.get_entry("QE-S1")
        assert entry["queue_status"] == PENDING_REVIEW
        # No approval events should exist
        events = engine.get_approval_history("QE-S1")
        assert len(events) == 0
