"""
Parikshak Operational Governance — Replay Engine
==================================================
Replay-by-trace_id lookup. Reconstructs full lifecycle.
Goal: operator should reconstruct lifecycle from trace_id alone.
"""
from typing import Dict, Any, List, Optional
from src.governance.queue_store import QueueStore


class ReplayEngine:
    """Replay engine for trace_id-based lifecycle reconstruction."""

    def __init__(self, store: QueueStore):
        self._store = store

    def replay_by_trace_id(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """
        Reconstruct full lifecycle from submission to approval decision.
        Returns None if trace_id not found.
        """
        if not trace_id or not isinstance(trace_id, str):
            return None

        entry = self._store.get_entry_by_trace_id(trace_id)
        if entry is None:
            return None

        approval_events = self._store.get_approval_events(trace_id=trace_id)
        observability_events = self._store.get_observability_events(trace_id=trace_id)

        return {
            "trace_id": trace_id,
            "queue_entry": entry,
            "approval_events": approval_events,
            "observability_events": observability_events,
            "lifecycle_complete": entry["queue_status"] in ("APPROVED", "REJECTED"),
        }

    def get_execution_timeline(self, trace_id: str) -> List[Dict[str, Any]]:
        """
        Ordered list of all events for a trace_id.
        Combines observability events and approval events in chronological order.
        """
        if not trace_id:
            return []

        obs_events = self._store.get_observability_events(trace_id=trace_id)
        approval_events = self._store.get_approval_events(trace_id=trace_id)

        timeline = []
        for e in obs_events:
            timeline.append({
                "type": "observability",
                "event_type": e["event_type"],
                "timestamp": e["timestamp"],
                "severity": e["severity"],
                "details": e.get("details", {}),
            })
        for e in approval_events:
            timeline.append({
                "type": "approval",
                "action": e["action"],
                "timestamp": e["timestamp"],
                "approver_id": e["approver_id"],
                "reason": e["reason"],
                "previous_status": e["previous_status"],
                "new_status": e["new_status"],
            })

        # Sort by timestamp for chronological order
        timeline.sort(key=lambda x: x["timestamp"])
        return timeline

    def get_graph_traversal(self, trace_id: str) -> Optional[List[str]]:
        """Get the graph traversal path for a trace_id."""
        entry = self._store.get_entry_by_trace_id(trace_id)
        if entry is None:
            return None
        return entry.get("graph_traversal_trace", [])

    def get_rejection_reasoning(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """If rejected, return the full rejection chain."""
        entry = self._store.get_entry_by_trace_id(trace_id)
        if entry is None:
            return None

        if entry["queue_status"] != "REJECTED":
            return None

        rejection_events = [
            e for e in self._store.get_approval_events(trace_id=trace_id)
            if e["action"] == "REJECT"
        ]

        return {
            "trace_id": trace_id,
            "queue_entry_id": entry["queue_entry_id"],
            "selected_task_id": entry["selected_task_id"],
            "rejection_events": rejection_events,
            "final_status": entry["queue_status"],
        }

    def get_failure_route(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """If evaluation failed, show the failure details."""
        entry = self._store.get_entry_by_trace_id(trace_id)
        if entry is None:
            return None

        if entry["evaluation_result"] != "FAIL":
            return None

        return {
            "trace_id": trace_id,
            "evaluation_result": "FAIL",
            "failure_type": entry["failure_type"],
            "selected_task_id": entry["selected_task_id"],
            "selection_reason": entry["pipeline_output"].get("selection_reason", ""),
            "graph_traversal_trace": entry.get("graph_traversal_trace", []),
        }
