"""
Parikshak Operational Governance — Observability Tests
========================================================
Tests: structured log emission, contract violation visibility,
       no silent failures.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.governance.queue_store import QueueStore
from src.observability.observability import ObservabilityEmitter
from src.observability.contract_monitor import ContractMonitor
from src.models.governance_models import (
    EVENT_SUBMISSION, EVENT_EVALUATION, EVENT_QUEUE_ENTRY,
    EVENT_APPROVAL, EVENT_REJECTION, EVENT_ESCALATION,
    EVENT_CONTRACT_VIOLATION, EVENT_GRAPH_REJECT, EVENT_REPLAY_FAILURE,
    SEVERITY_INFO, SEVERITY_WARN, SEVERITY_ERROR, SEVERITY_CRITICAL,
)


@pytest.fixture
def obs_env(tmp_path):
    store = QueueStore(str(tmp_path / "state"))
    emitter = ObservabilityEmitter(store)
    monitor = ContractMonitor(emitter)
    return store, emitter, monitor


class TestObservabilityEmitter:
    """Phase 4: Observability Hardening tests."""

    def test_emit_submission(self, obs_env):
        store, emitter, monitor = obs_env
        event = emitter.emit_submission("T1", "S1")
        assert event.event_type == EVENT_SUBMISSION
        assert event.severity == SEVERITY_INFO
        assert event.trace_id == "T1"

    def test_emit_evaluation(self, obs_env):
        store, emitter, monitor = obs_env
        event = emitter.emit_evaluation("T1", "PASS", "TASK_001")
        assert event.event_type == EVENT_EVALUATION
        assert event.severity == SEVERITY_INFO

    def test_emit_queue_entry(self, obs_env):
        store, emitter, monitor = obs_env
        event = emitter.emit_queue_entry("T1", "QE-S1", "PENDING_REVIEW")
        assert event.event_type == EVENT_QUEUE_ENTRY

    def test_emit_approval(self, obs_env):
        store, emitter, monitor = obs_env
        event = emitter.emit_approval("T1", "QE-S1", "op1", "Approved")
        assert event.event_type == EVENT_APPROVAL
        assert event.severity == SEVERITY_INFO

    def test_emit_rejection(self, obs_env):
        store, emitter, monitor = obs_env
        event = emitter.emit_rejection("T1", "QE-S1", "op1", "Rejected")
        assert event.event_type == EVENT_REJECTION
        assert event.severity == SEVERITY_INFO

    def test_emit_escalation_is_warn(self, obs_env):
        store, emitter, monitor = obs_env
        event = emitter.emit_escalation("T1", "QE-S1", "op1", "Needs review")
        assert event.event_type == EVENT_ESCALATION
        assert event.severity == SEVERITY_WARN

    def test_emit_contract_violation_is_critical(self, obs_env):
        store, emitter, monitor = obs_env
        event = emitter.emit_contract_violation("T1", "Missing field")
        assert event.event_type == EVENT_CONTRACT_VIOLATION
        assert event.severity == SEVERITY_CRITICAL

    def test_emit_graph_reject_is_error(self, obs_env):
        store, emitter, monitor = obs_env
        event = emitter.emit_graph_reject("T1", "No rule matched")
        assert event.event_type == EVENT_GRAPH_REJECT
        assert event.severity == SEVERITY_ERROR

    def test_emit_replay_failure_is_error(self, obs_env):
        store, emitter, monitor = obs_env
        event = emitter.emit_replay_failure("T1", "Trace not found")
        assert event.event_type == EVENT_REPLAY_FAILURE
        assert event.severity == SEVERITY_ERROR

    def test_events_persisted(self, obs_env):
        store, emitter, monitor = obs_env
        emitter.emit_submission("T1", "S1")
        emitter.emit_evaluation("T1", "PASS", "TASK_001")
        events = emitter.get_all_events()
        assert len(events) == 2

    def test_filter_by_trace(self, obs_env):
        store, emitter, monitor = obs_env
        emitter.emit_submission("T1", "S1")
        emitter.emit_submission("T2", "S2")
        events = emitter.get_events_by_trace("T1")
        assert len(events) == 1
        assert events[0]["trace_id"] == "T1"

    def test_filter_by_type(self, obs_env):
        store, emitter, monitor = obs_env
        emitter.emit_submission("T1", "S1")
        emitter.emit_evaluation("T1", "PASS", "TASK_001")
        events = emitter.get_events_by_type(EVENT_SUBMISSION)
        assert len(events) == 1

    def test_event_has_timestamp(self, obs_env):
        store, emitter, monitor = obs_env
        event = emitter.emit_submission("T1", "S1")
        assert event.timestamp is not None
        assert "Z" in event.timestamp

    def test_event_details_populated(self, obs_env):
        store, emitter, monitor = obs_env
        event = emitter.emit_submission("T1", "S1")
        assert "submission_id" in event.details
        assert event.details["submission_id"] == "S1"


class TestContractMonitor:
    """Phase 4: Contract monitoring tests."""

    def test_valid_pass_output(self, obs_env):
        store, emitter, monitor = obs_env
        output = {
            "trace_id": "T1", "submission_id": "S1",
            "evaluation_result": "PASS", "failure_type": None,
            "selected_task_id": "TASK_001",
            "selection_reason": "OK", "source": "task_graph",
        }
        violations = monitor.validate(output)
        assert violations == []

    def test_valid_fail_output(self, obs_env):
        store, emitter, monitor = obs_env
        output = {
            "trace_id": "T1", "submission_id": "S1",
            "evaluation_result": "FAIL",
            "failure_type": "schema_violation",
            "selected_task_id": "NONE",
            "selection_reason": "Bad", "source": "task_graph",
        }
        violations = monitor.validate(output)
        assert violations == []

    def test_missing_field_detected(self, obs_env):
        store, emitter, monitor = obs_env
        output = {"trace_id": "T1", "submission_id": "S1"}
        violations = monitor.validate(output)
        assert len(violations) > 0

    def test_extra_field_detected(self, obs_env):
        store, emitter, monitor = obs_env
        output = {
            "trace_id": "T1", "submission_id": "S1",
            "evaluation_result": "PASS", "failure_type": None,
            "selected_task_id": "TASK_001",
            "selection_reason": "OK", "source": "task_graph",
            "extra_field": "bad",
        }
        violations = monitor.validate(output)
        assert any("Unexpected" in v for v in violations)

    def test_pass_with_failure_type_detected(self, obs_env):
        store, emitter, monitor = obs_env
        output = {
            "trace_id": "T1", "submission_id": "S1",
            "evaluation_result": "PASS",
            "failure_type": "schema_violation",
            "selected_task_id": "TASK_001",
            "selection_reason": "OK", "source": "task_graph",
        }
        violations = monitor.validate(output)
        assert any("PASS" in v for v in violations)

    def test_fail_without_failure_type_detected(self, obs_env):
        store, emitter, monitor = obs_env
        output = {
            "trace_id": "T1", "submission_id": "S1",
            "evaluation_result": "FAIL", "failure_type": None,
            "selected_task_id": "NONE",
            "selection_reason": "Bad", "source": "task_graph",
        }
        violations = monitor.validate(output)
        assert any("FAIL" in v for v in violations)

    def test_wrong_source_detected(self, obs_env):
        store, emitter, monitor = obs_env
        output = {
            "trace_id": "T1", "submission_id": "S1",
            "evaluation_result": "PASS", "failure_type": None,
            "selected_task_id": "TASK_001",
            "selection_reason": "OK", "source": "wrong_source",
        }
        violations = monitor.validate(output)
        assert any("source" in v.lower() for v in violations)

    def test_violations_emit_critical_events(self, obs_env):
        store, emitter, monitor = obs_env
        output = {"trace_id": "T1"}
        monitor.validate(output, "T1")
        events = emitter.get_events_by_type(EVENT_CONTRACT_VIOLATION)
        assert len(events) > 0
        assert all(e["severity"] == SEVERITY_CRITICAL for e in events)
