"""
Parikshak Operational Governance — Audit Reconstructor
=======================================================
Full audit reconstruction — produces human-readable reports.
Operator can reconstruct entire lifecycle from trace_id alone.
"""
from typing import Dict, Any, Optional
from src.audit.replay_engine import ReplayEngine


class AuditReconstructor:
    """Produces human-readable audit reports from trace_id."""

    def __init__(self, replay_engine: ReplayEngine):
        self._replay = replay_engine

    def reconstruct(self, trace_id: str) -> Optional[str]:
        """
        Produce a full audit reconstruction report for a trace_id.
        Returns a human-readable string or None if trace not found.
        """
        replay = self._replay.replay_by_trace_id(trace_id)
        if replay is None:
            return None

        entry = replay["queue_entry"]
        lines = [
            "=" * 60,
            "  AUDIT RECONSTRUCTION REPORT",
            "=" * 60,
            f"  TRACE:        {entry['trace_id']}",
            f"  SUBMISSION:   {entry['submission_id']}",
            f"  EVALUATION:   {entry['evaluation_result']}",
            f"  FAILURE TYPE: {entry['failure_type'] or 'N/A'}",
            f"  TASK:         {entry['selected_task_id']}",
        ]

        # Graph traversal
        traversal = entry.get("graph_traversal_trace", [])
        if traversal:
            lines.append(f"  TRAVERSAL:    {' → '.join(traversal)}")
        else:
            lines.append("  TRAVERSAL:    N/A")

        # Queue info
        lines.append(f"  QUEUED:       {entry['enqueued_at']} ({entry['queue_status']})")

        # Approval events
        approval_events = replay.get("approval_events", [])
        if approval_events:
            lines.append("")
            lines.append("  APPROVAL HISTORY:")
            for evt in approval_events:
                lines.append(
                    f"    {evt['action']:8s} {evt['timestamp']} by {evt['approver_id']} "
                    f"— \"{evt['reason']}\""
                )
                lines.append(
                    f"             {evt['previous_status']} → {evt['new_status']}"
                )
        else:
            lines.append("  APPROVAL:     No decisions recorded yet.")

        # Lifecycle status
        lines.append("")
        if replay["lifecycle_complete"]:
            lines.append(f"  STATUS:       LIFECYCLE COMPLETE ({entry['queue_status']})")
        else:
            lines.append(f"  STATUS:       LIFECYCLE IN PROGRESS ({entry['queue_status']})")

        lines.append("=" * 60)
        return "\n".join(lines)

    def reconstruct_dict(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """
        Produce a structured audit reconstruction dict for a trace_id.
        Machine-readable companion to reconstruct().
        """
        replay = self._replay.replay_by_trace_id(trace_id)
        if replay is None:
            return None

        entry = replay["queue_entry"]
        return {
            "trace_id": entry["trace_id"],
            "submission_id": entry["submission_id"],
            "evaluation_result": entry["evaluation_result"],
            "failure_type": entry["failure_type"],
            "selected_task_id": entry["selected_task_id"],
            "graph_traversal_trace": entry.get("graph_traversal_trace", []),
            "queue_status": entry["queue_status"],
            "enqueued_at": entry["enqueued_at"],
            "approval_events": replay.get("approval_events", []),
            "observability_events": replay.get("observability_events", []),
            "lifecycle_complete": replay["lifecycle_complete"],
        }
