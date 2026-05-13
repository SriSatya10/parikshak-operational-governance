"""
Parikshak Operational Governance — Approval Log
=================================================
Immutable append-only approval event log.
NEVER modifies existing entries. Append-only.
"""
from typing import Dict, Any, List
from src.models.governance_models import (
    ApprovalEvent, VALID_ACTIONS, _utc_now_iso,
)
from src.governance.queue_store import QueueStore


class ApprovalLog:
    """Immutable append-only log of all approval decisions."""

    def __init__(self, store: QueueStore):
        self._store = store
        self._seq_counter: Dict[str, int] = {}

    def _next_seq(self, queue_entry_id: str) -> int:
        if queue_entry_id not in self._seq_counter:
            existing = self._store.get_approval_events(queue_entry_id=queue_entry_id)
            self._seq_counter[queue_entry_id] = len(existing)
        self._seq_counter[queue_entry_id] += 1
        return self._seq_counter[queue_entry_id]

    def record_event(self, queue_entry_id: str, trace_id: str, action: str,
                     approver_id: str, reason: str, previous_status: str,
                     new_status: str) -> ApprovalEvent:
        """Record an immutable approval event. Reason is MANDATORY."""
        if not reason or not isinstance(reason, str) or not reason.strip():
            raise ValueError("HARD FAIL: Approval reason is MANDATORY. Cannot be empty.")
        if action not in VALID_ACTIONS:
            raise ValueError(f"HARD FAIL: Invalid action '{action}'. Must be one of: {VALID_ACTIONS}")
        if not approver_id or not isinstance(approver_id, str) or not approver_id.strip():
            raise ValueError("HARD FAIL: approver_id is MANDATORY. Cannot be empty.")
        if not queue_entry_id or not isinstance(queue_entry_id, str):
            raise ValueError("HARD FAIL: queue_entry_id is MANDATORY.")
        if not trace_id or not isinstance(trace_id, str):
            raise ValueError("HARD FAIL: trace_id is MANDATORY for approval event.")

        seq = self._next_seq(queue_entry_id)
        event = ApprovalEvent(
            event_id=f"EVT-{queue_entry_id}-{seq:03d}",
            queue_entry_id=queue_entry_id,
            trace_id=trace_id,
            action=action,
            approver_id=approver_id,
            reason=reason,
            timestamp=_utc_now_iso(),
            previous_status=previous_status,
            new_status=new_status,
        )
        self._store.append_approval_event(event.to_dict())
        return event

    def get_events_for_entry(self, queue_entry_id: str) -> List[Dict[str, Any]]:
        return self._store.get_approval_events(queue_entry_id=queue_entry_id)

    def get_events_for_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        return self._store.get_approval_events(trace_id=trace_id)

    def get_all_events(self) -> List[Dict[str, Any]]:
        return self._store.get_all_approval_events()

    def get_event_count(self) -> int:
        return self._store.get_approval_event_count()
