"""
Parikshak Operational Governance — Observability
==================================================
Structured operational log emitter.
No silent failures allowed. Every event is logged explicitly.

Severity mapping:
  - Contract violations → CRITICAL
  - Graph rejects (no rule match) → ERROR
  - Replay failures (trace not found) → ERROR
  - Escalation events → WARN
  - Approval/rejection → INFO
  - Queue entry → INFO
  - Submission/evaluation → INFO
"""
from typing import Dict, Any
from src.models.governance_models import (
    EVENT_SUBMISSION, EVENT_EVALUATION, EVENT_QUEUE_ENTRY,
    EVENT_APPROVAL, EVENT_REJECTION, EVENT_ESCALATION,
    EVENT_CONTRACT_VIOLATION, EVENT_GRAPH_REJECT, EVENT_REPLAY_FAILURE,
    SEVERITY_INFO, SEVERITY_WARN, SEVERITY_ERROR, SEVERITY_CRITICAL,
    ObservabilityEvent, _utc_now_iso,
)
from src.governance.queue_store import QueueStore


# Event type → default severity mapping
_SEVERITY_MAP = {
    EVENT_SUBMISSION: SEVERITY_INFO,
    EVENT_EVALUATION: SEVERITY_INFO,
    EVENT_QUEUE_ENTRY: SEVERITY_INFO,
    EVENT_APPROVAL: SEVERITY_INFO,
    EVENT_REJECTION: SEVERITY_INFO,
    EVENT_ESCALATION: SEVERITY_WARN,
    EVENT_CONTRACT_VIOLATION: SEVERITY_CRITICAL,
    EVENT_GRAPH_REJECT: SEVERITY_ERROR,
    EVENT_REPLAY_FAILURE: SEVERITY_ERROR,
}


class ObservabilityEmitter:
    """Structured operational log emitter. No silent failures."""

    def __init__(self, store: QueueStore):
        self._store = store

    def emit(self, event_type: str, trace_id: str,
             details: Dict[str, Any] = None,
             severity_override: str = None) -> ObservabilityEvent:
        """
        Emit a structured observability event.
        Severity is auto-determined from event type unless overridden.
        """
        severity = severity_override or _SEVERITY_MAP.get(event_type, SEVERITY_INFO)
        event = ObservabilityEvent(
            event_type=event_type,
            trace_id=trace_id,
            timestamp=_utc_now_iso(),
            severity=severity,
            details=details or {},
        )
        self._store.append_observability_event(event.to_dict())
        return event

    def emit_submission(self, trace_id: str, submission_id: str) -> ObservabilityEvent:
        return self.emit(EVENT_SUBMISSION, trace_id, {
            "submission_id": submission_id,
            "message": f"Submission received: {submission_id}",
        })

    def emit_evaluation(self, trace_id: str, result: str,
                        task_id: str, failure_type: str = None) -> ObservabilityEvent:
        return self.emit(EVENT_EVALUATION, trace_id, {
            "evaluation_result": result,
            "selected_task_id": task_id,
            "failure_type": failure_type,
            "message": f"Evaluation: {result} → {task_id}",
        })

    def emit_queue_entry(self, trace_id: str, queue_entry_id: str,
                         status: str) -> ObservabilityEvent:
        return self.emit(EVENT_QUEUE_ENTRY, trace_id, {
            "queue_entry_id": queue_entry_id,
            "queue_status": status,
            "message": f"Queued: {queue_entry_id} → {status}",
        })

    def emit_approval(self, trace_id: str, queue_entry_id: str,
                       approver_id: str, reason: str) -> ObservabilityEvent:
        return self.emit(EVENT_APPROVAL, trace_id, {
            "queue_entry_id": queue_entry_id,
            "approver_id": approver_id,
            "reason": reason,
            "message": f"APPROVED by {approver_id}",
        })

    def emit_rejection(self, trace_id: str, queue_entry_id: str,
                        approver_id: str, reason: str) -> ObservabilityEvent:
        return self.emit(EVENT_REJECTION, trace_id, {
            "queue_entry_id": queue_entry_id,
            "approver_id": approver_id,
            "reason": reason,
            "message": f"REJECTED by {approver_id}: {reason}",
        })

    def emit_escalation(self, trace_id: str, queue_entry_id: str,
                         approver_id: str, reason: str) -> ObservabilityEvent:
        return self.emit(EVENT_ESCALATION, trace_id, {
            "queue_entry_id": queue_entry_id,
            "approver_id": approver_id,
            "reason": reason,
            "message": f"ESCALATED by {approver_id}: {reason}",
        })

    def emit_contract_violation(self, trace_id: str,
                                 violation: str) -> ObservabilityEvent:
        return self.emit(EVENT_CONTRACT_VIOLATION, trace_id, {
            "violation": violation,
            "message": f"CONTRACT VIOLATION: {violation}",
        })

    def emit_graph_reject(self, trace_id: str, reason: str) -> ObservabilityEvent:
        return self.emit(EVENT_GRAPH_REJECT, trace_id, {
            "reason": reason,
            "message": f"GRAPH REJECT: {reason}",
        })

    def emit_replay_failure(self, trace_id: str, reason: str) -> ObservabilityEvent:
        return self.emit(EVENT_REPLAY_FAILURE, trace_id, {
            "reason": reason,
            "message": f"REPLAY FAILURE: {reason}",
        })

    def get_events_by_trace(self, trace_id: str):
        return self._store.get_observability_events(trace_id=trace_id)

    def get_events_by_type(self, event_type: str):
        return self._store.get_observability_events(event_type=event_type)

    def get_all_events(self):
        return self._store.get_all_observability_events()
