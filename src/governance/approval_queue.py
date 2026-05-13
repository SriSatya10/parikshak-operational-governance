"""
Parikshak Operational Governance — Approval Queue
==================================================
Deterministic queue manager with four queues:
  - PENDING_REVIEW: awaiting human decision
  - APPROVED: approved for downstream assignment
  - REJECTED: rejected with mandatory reason
  - ESCALATED: flagged for higher authority

Requirements:
  - FIFO ordering (deterministic — insertion order)
  - Full trace visibility on every entry
  - task_id visible on every entry
  - failure_type visible on every entry
  - Replay lookup by trace_id supported
  - No mutable hidden state
"""
from typing import Dict, Any, List, Optional

from src.models.governance_models import (
    QueueEntry,
    PENDING_REVIEW,
    APPROVED,
    REJECTED,
    ESCALATED,
    VALID_QUEUE_STATUSES,
    _utc_now_iso,
)
from src.governance.queue_store import QueueStore


class ApprovalQueue:
    """
    Manages the four approval queues with deterministic FIFO ordering.
    All state is persisted via QueueStore — no hidden in-memory state.
    """

    def __init__(self, store: QueueStore):
        self._store = store

    def enqueue(self, pipeline_output: Dict[str, Any],
                graph_traversal_trace: List[str] = None) -> QueueEntry:
        """
        Enqueue a pipeline output for human review.

        Args:
            pipeline_output: The 7-field contract-compliant output from upstream.
            graph_traversal_trace: Optional traversal trace from state machine.

        Returns:
            The created QueueEntry.

        Raises:
            ValueError: If pipeline_output is missing required fields.
        """
        # ── Validate required fields from pipeline output ────────────────
        required = {"trace_id", "submission_id", "evaluation_result",
                     "failure_type", "selected_task_id", "selection_reason", "source"}
        missing = required - set(pipeline_output.keys())
        if missing:
            raise ValueError(f"HARD FAIL: Pipeline output missing fields: {missing}")

        trace_id = pipeline_output["trace_id"]
        submission_id = pipeline_output["submission_id"]

        if not trace_id or not isinstance(trace_id, str):
            raise ValueError("HARD FAIL: trace_id must be a non-empty string.")
        if not submission_id or not isinstance(submission_id, str):
            raise ValueError("HARD FAIL: submission_id must be a non-empty string.")

        # ── Build deterministic queue entry ──────────────────────────────
        entry = QueueEntry(
            queue_entry_id=f"QE-{submission_id}",
            trace_id=trace_id,
            submission_id=submission_id,
            pipeline_output=pipeline_output,
            queue_status=PENDING_REVIEW,
            enqueued_at=_utc_now_iso(),
            evaluation_result=pipeline_output["evaluation_result"],
            failure_type=pipeline_output.get("failure_type"),
            selected_task_id=pipeline_output["selected_task_id"],
            graph_traversal_trace=graph_traversal_trace or [],
        )

        # ── Persist ──────────────────────────────────────────────────────
        self._store.add_entry(entry.to_dict())

        return entry

    def get_pending_review(self) -> List[Dict[str, Any]]:
        """Get all entries awaiting human review, in FIFO order."""
        return self._store.get_entries_by_status(PENDING_REVIEW)

    def get_approved(self) -> List[Dict[str, Any]]:
        """Get all approved entries, in FIFO order."""
        return self._store.get_entries_by_status(APPROVED)

    def get_rejected(self) -> List[Dict[str, Any]]:
        """Get all rejected entries, in FIFO order."""
        return self._store.get_entries_by_status(REJECTED)

    def get_escalated(self) -> List[Dict[str, Any]]:
        """Get all escalated entries, in FIFO order."""
        return self._store.get_entries_by_status(ESCALATED)

    def get_entry(self, queue_entry_id: str) -> Optional[Dict[str, Any]]:
        """Get a single entry by queue_entry_id."""
        return self._store.get_entry(queue_entry_id)

    def lookup_by_trace_id(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Replay lookup: find entry by trace_id."""
        return self._store.get_entry_by_trace_id(trace_id)

    def get_all_entries(self) -> List[Dict[str, Any]]:
        """Get all entries in deterministic insertion order."""
        return self._store.get_all_entries_ordered()

    def get_queue_counts(self) -> Dict[str, int]:
        """Get count of entries in each queue status."""
        all_entries = self._store.get_all_entries_ordered()
        counts = {s: 0 for s in VALID_QUEUE_STATUSES}
        for entry in all_entries:
            status = entry["queue_status"]
            if status in counts:
                counts[status] += 1
        return counts
