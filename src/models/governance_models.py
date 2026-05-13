"""
Parikshak Operational Governance — Data Models
===============================================
Strict data models for the governance layer.
No dynamic generation. No AI/ML. No randomness.
All IDs are deterministic. All timestamps are explicit.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


# ── Queue Status Constants ────────────────────────────────────────────────────
PENDING_REVIEW = "PENDING_REVIEW"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
ESCALATED = "ESCALATED"

VALID_QUEUE_STATUSES = {PENDING_REVIEW, APPROVED, REJECTED, ESCALATED}

# ── Approval Action Constants ─────────────────────────────────────────────────
ACTION_APPROVE = "APPROVE"
ACTION_REJECT = "REJECT"
ACTION_HOLD = "HOLD"

VALID_ACTIONS = {ACTION_APPROVE, ACTION_REJECT, ACTION_HOLD}

# ── Observability Event Types ─────────────────────────────────────────────────
EVENT_SUBMISSION = "SUBMISSION"
EVENT_EVALUATION = "EVALUATION"
EVENT_QUEUE_ENTRY = "QUEUE_ENTRY"
EVENT_APPROVAL = "APPROVAL"
EVENT_REJECTION = "REJECTION"
EVENT_ESCALATION = "ESCALATION"
EVENT_CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
EVENT_GRAPH_REJECT = "GRAPH_REJECT"
EVENT_REPLAY_FAILURE = "REPLAY_FAILURE"

# ── Severity Levels ───────────────────────────────────────────────────────────
SEVERITY_INFO = "INFO"
SEVERITY_WARN = "WARN"
SEVERITY_ERROR = "ERROR"
SEVERITY_CRITICAL = "CRITICAL"


def _utc_now_iso() -> str:
    """Returns current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@dataclass
class QueueEntry:
    """
    Single entry in the approval queue.
    Every field is explicit — no hidden state.
    """
    queue_entry_id: str             # deterministic: f"QE-{submission_id}"
    trace_id: str                   # from upstream, immutable
    submission_id: str              # from upstream, immutable
    pipeline_output: Dict[str, Any] # full 7-field contract output
    queue_status: str               # PENDING_REVIEW | APPROVED | REJECTED | ESCALATED
    enqueued_at: str                # ISO timestamp
    evaluation_result: str          # PASS or FAIL
    failure_type: Optional[str]     # from pipeline output
    selected_task_id: str           # from pipeline output
    graph_traversal_trace: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "queue_entry_id": self.queue_entry_id,
            "trace_id": self.trace_id,
            "submission_id": self.submission_id,
            "pipeline_output": self.pipeline_output,
            "queue_status": self.queue_status,
            "enqueued_at": self.enqueued_at,
            "evaluation_result": self.evaluation_result,
            "failure_type": self.failure_type,
            "selected_task_id": self.selected_task_id,
            "graph_traversal_trace": self.graph_traversal_trace,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "QueueEntry":
        return QueueEntry(
            queue_entry_id=d["queue_entry_id"],
            trace_id=d["trace_id"],
            submission_id=d["submission_id"],
            pipeline_output=d["pipeline_output"],
            queue_status=d["queue_status"],
            enqueued_at=d["enqueued_at"],
            evaluation_result=d["evaluation_result"],
            failure_type=d.get("failure_type"),
            selected_task_id=d["selected_task_id"],
            graph_traversal_trace=d.get("graph_traversal_trace", []),
        )


@dataclass
class ApprovalEvent:
    """
    Single immutable approval log entry.
    Append-only — never modified after creation.
    """
    event_id: str                   # deterministic: f"EVT-{queue_entry_id}-{seq}"
    queue_entry_id: str
    trace_id: str
    action: str                     # APPROVE | REJECT | HOLD
    approver_id: str
    reason: str                     # mandatory — empty = HARD FAIL
    timestamp: str                  # ISO 8601
    previous_status: str
    new_status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "queue_entry_id": self.queue_entry_id,
            "trace_id": self.trace_id,
            "action": self.action,
            "approver_id": self.approver_id,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ApprovalEvent":
        return ApprovalEvent(
            event_id=d["event_id"],
            queue_entry_id=d["queue_entry_id"],
            trace_id=d["trace_id"],
            action=d["action"],
            approver_id=d["approver_id"],
            reason=d["reason"],
            timestamp=d["timestamp"],
            previous_status=d["previous_status"],
            new_status=d["new_status"],
        )


@dataclass
class ObservabilityEvent:
    """
    Structured operational log event.
    Every event is explicit — no silent failures.
    """
    event_type: str                 # SUBMISSION | EVALUATION | QUEUE_ENTRY | etc.
    trace_id: str
    timestamp: str
    severity: str                   # INFO | WARN | ERROR | CRITICAL
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "severity": self.severity,
            "details": self.details,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ObservabilityEvent":
        return ObservabilityEvent(
            event_type=d["event_type"],
            trace_id=d["trace_id"],
            timestamp=d["timestamp"],
            severity=d["severity"],
            details=d["details"],
        )
