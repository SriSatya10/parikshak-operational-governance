"""
Parikshak Operational Governance — Governance Orchestrator
============================================================
Single entry point for the operational governance layer.

Flow:
  1. Receive pipeline output from upstream
  2. Validate contract
  3. Emit observability events
  4. Create queue entry (PENDING_REVIEW)
  5. Await human approval decision (via approve/reject/hold)
  6. Record immutable log
  7. Enable replay lookup
"""
import os
from typing import Dict, Any, List, Optional
from src.governance.queue_store import QueueStore
from src.governance.approval_queue import ApprovalQueue
from src.governance.approval_engine import ApprovalEngine
from src.observability.observability import ObservabilityEmitter
from src.observability.contract_monitor import ContractMonitor
from src.audit.replay_engine import ReplayEngine
from src.audit.audit_reconstructor import AuditReconstructor
from src.models.governance_models import PENDING_REVIEW


class GovernanceOrchestrator:
    """
    Single orchestrator for operational governance.
    Manages the full lifecycle from pipeline output to approval decision.
    """

    def __init__(self, state_dir: str = None):
        if state_dir is None:
            state_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "governance_state",
            )

        self._store = QueueStore(state_dir)
        self._queue = ApprovalQueue(self._store)
        self._engine = ApprovalEngine(self._store)
        self._emitter = ObservabilityEmitter(self._store)
        self._monitor = ContractMonitor(self._emitter)
        self._replay = ReplayEngine(self._store)
        self._auditor = AuditReconstructor(self._replay)

    def submit(self, pipeline_output: Dict[str, Any],
               graph_traversal_trace: List[str] = None) -> Dict[str, Any]:
        """
        Submit a pipeline output for governance review.

        1. Validates contract
        2. Emits observability events
        3. Creates queue entry in PENDING_REVIEW

        Returns: queue entry dict.
        Raises: ValueError if contract is violated.
        """
        trace_id = pipeline_output.get("trace_id", "UNKNOWN")
        submission_id = pipeline_output.get("submission_id", "UNKNOWN")

        # Step 1: Emit submission event
        self._emitter.emit_submission(trace_id, submission_id)

        # Step 2: Validate contract
        violations = self._monitor.validate(pipeline_output, trace_id)
        if violations:
            raise ValueError(
                f"HARD FAIL: Contract violations detected: {violations}"
            )

        # Step 3: Emit evaluation event
        self._emitter.emit_evaluation(
            trace_id=trace_id,
            result=pipeline_output["evaluation_result"],
            task_id=pipeline_output["selected_task_id"],
            failure_type=pipeline_output.get("failure_type"),
        )

        # Step 4: Enqueue for review
        entry = self._queue.enqueue(pipeline_output, graph_traversal_trace)

        # Step 5: Emit queue entry event
        self._emitter.emit_queue_entry(
            trace_id, entry.queue_entry_id, PENDING_REVIEW
        )

        return entry.to_dict()

    def approve(self, queue_entry_id: str, approver_id: str,
                reason: str) -> Dict[str, Any]:
        """Approve a queue entry. Emits observability event."""
        result = self._engine.approve(queue_entry_id, approver_id, reason)
        self._emitter.emit_approval(
            result["trace_id"], queue_entry_id, approver_id, reason
        )
        return result

    def reject(self, queue_entry_id: str, approver_id: str,
               reason: str) -> Dict[str, Any]:
        """Reject a queue entry. Emits observability event."""
        result = self._engine.reject(queue_entry_id, approver_id, reason)
        self._emitter.emit_rejection(
            result["trace_id"], queue_entry_id, approver_id, reason
        )
        return result

    def hold(self, queue_entry_id: str, approver_id: str,
             reason: str) -> Dict[str, Any]:
        """Hold/escalate a queue entry. Emits observability event."""
        result = self._engine.hold(queue_entry_id, approver_id, reason)
        self._emitter.emit_escalation(
            result["trace_id"], queue_entry_id, approver_id, reason
        )
        return result

    def replay(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Replay full lifecycle by trace_id."""
        result = self._replay.replay_by_trace_id(trace_id)
        if result is None:
            self._emitter.emit_replay_failure(trace_id, "Trace not found")
        return result

    def reconstruct_audit(self, trace_id: str) -> Optional[str]:
        """Produce human-readable audit report."""
        return self._auditor.reconstruct(trace_id)

    def reconstruct_audit_dict(self, trace_id: str) -> Optional[Dict]:
        """Produce machine-readable audit reconstruction."""
        return self._auditor.reconstruct_dict(trace_id)

    def get_timeline(self, trace_id: str) -> List[Dict[str, Any]]:
        """Get execution timeline for a trace_id."""
        return self._replay.get_execution_timeline(trace_id)

    def get_pending_review(self) -> List[Dict[str, Any]]:
        return self._queue.get_pending_review()

    def get_approved(self) -> List[Dict[str, Any]]:
        return self._queue.get_approved()

    def get_rejected(self) -> List[Dict[str, Any]]:
        return self._queue.get_rejected()

    def get_escalated(self) -> List[Dict[str, Any]]:
        return self._queue.get_escalated()

    def get_queue_counts(self) -> Dict[str, int]:
        return self._queue.get_queue_counts()

    def get_all_observability_events(self) -> List[Dict[str, Any]]:
        return self._emitter.get_all_events()

    def reset(self) -> None:
        """Reset all state. For testing only."""
        self._store.reset()
