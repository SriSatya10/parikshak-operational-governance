"""
Parikshak Operational Governance — Approval Engine
====================================================
Human approval lock. Three actions: APPROVE, REJECT, HOLD.

Rules:
  - No automatic assignment release
  - Approval mandatory before downstream progression
  - Immutable approval log
  - Approval reason required
  - Must preserve trace continuity
"""
from typing import Dict, Any, Optional
from src.models.governance_models import (
    PENDING_REVIEW, APPROVED, REJECTED, ESCALATED,
    ACTION_APPROVE, ACTION_REJECT, ACTION_HOLD,
    VALID_QUEUE_STATUSES,
)
from src.governance.queue_store import QueueStore
from src.governance.approval_log import ApprovalLog


class ApprovalEngine:
    """
    Human-governed approval engine.
    No automatic release. Every transition requires explicit human action.
    """

    def __init__(self, store: QueueStore):
        self._store = store
        self._log = ApprovalLog(store)

    def approve(self, queue_entry_id: str, approver_id: str, reason: str) -> Dict[str, Any]:
        """
        APPROVE a queue entry. Moves to APPROVED status.
        Only entries in PENDING_REVIEW or ESCALATED can be approved.
        """
        entry = self._get_and_validate_entry(queue_entry_id)
        previous_status = entry["queue_status"]

        if previous_status not in (PENDING_REVIEW, ESCALATED):
            raise ValueError(
                f"HARD FAIL: Cannot APPROVE entry in status '{previous_status}'. "
                f"Must be PENDING_REVIEW or ESCALATED."
            )

        # Record immutable event BEFORE status change
        event = self._log.record_event(
            queue_entry_id=queue_entry_id,
            trace_id=entry["trace_id"],
            action=ACTION_APPROVE,
            approver_id=approver_id,
            reason=reason,
            previous_status=previous_status,
            new_status=APPROVED,
        )

        # Update status
        self._store.update_entry_status(queue_entry_id, APPROVED)

        return {
            "action": ACTION_APPROVE,
            "queue_entry_id": queue_entry_id,
            "trace_id": entry["trace_id"],
            "previous_status": previous_status,
            "new_status": APPROVED,
            "event_id": event.event_id,
            "approver_id": approver_id,
            "reason": reason,
        }

    def reject(self, queue_entry_id: str, approver_id: str, reason: str) -> Dict[str, Any]:
        """
        REJECT a queue entry. Moves to REJECTED status.
        Only entries in PENDING_REVIEW or ESCALATED can be rejected.
        """
        entry = self._get_and_validate_entry(queue_entry_id)
        previous_status = entry["queue_status"]

        if previous_status not in (PENDING_REVIEW, ESCALATED):
            raise ValueError(
                f"HARD FAIL: Cannot REJECT entry in status '{previous_status}'. "
                f"Must be PENDING_REVIEW or ESCALATED."
            )

        event = self._log.record_event(
            queue_entry_id=queue_entry_id,
            trace_id=entry["trace_id"],
            action=ACTION_REJECT,
            approver_id=approver_id,
            reason=reason,
            previous_status=previous_status,
            new_status=REJECTED,
        )

        self._store.update_entry_status(queue_entry_id, REJECTED)

        return {
            "action": ACTION_REJECT,
            "queue_entry_id": queue_entry_id,
            "trace_id": entry["trace_id"],
            "previous_status": previous_status,
            "new_status": REJECTED,
            "event_id": event.event_id,
            "approver_id": approver_id,
            "reason": reason,
        }

    def hold(self, queue_entry_id: str, approver_id: str, reason: str) -> Dict[str, Any]:
        """
        HOLD (escalate) a queue entry. Moves to ESCALATED status.
        Only entries in PENDING_REVIEW can be held/escalated.
        """
        entry = self._get_and_validate_entry(queue_entry_id)
        previous_status = entry["queue_status"]

        if previous_status != PENDING_REVIEW:
            raise ValueError(
                f"HARD FAIL: Cannot HOLD entry in status '{previous_status}'. "
                f"Must be PENDING_REVIEW."
            )

        event = self._log.record_event(
            queue_entry_id=queue_entry_id,
            trace_id=entry["trace_id"],
            action=ACTION_HOLD,
            approver_id=approver_id,
            reason=reason,
            previous_status=previous_status,
            new_status=ESCALATED,
        )

        self._store.update_entry_status(queue_entry_id, ESCALATED)

        return {
            "action": ACTION_HOLD,
            "queue_entry_id": queue_entry_id,
            "trace_id": entry["trace_id"],
            "previous_status": previous_status,
            "new_status": ESCALATED,
            "event_id": event.event_id,
            "approver_id": approver_id,
            "reason": reason,
        }

    def get_approval_history(self, queue_entry_id: str):
        """Get full approval event history for an entry."""
        return self._log.get_events_for_entry(queue_entry_id)

    def get_approval_history_by_trace(self, trace_id: str):
        """Get full approval event history by trace_id."""
        return self._log.get_events_for_trace(trace_id)

    def _get_and_validate_entry(self, queue_entry_id: str) -> Dict[str, Any]:
        """Get entry and validate it exists."""
        if not queue_entry_id or not isinstance(queue_entry_id, str):
            raise ValueError("HARD FAIL: queue_entry_id is MANDATORY.")

        entry = self._store.get_entry(queue_entry_id)
        if entry is None:
            raise ValueError(f"HARD FAIL: Queue entry not found: {queue_entry_id}")

        return entry
