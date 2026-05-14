"""
Parikshak Evaluation Engine — Runner
=====================================
Single entry point for the evaluation layer.

Flow:
  1. Receive pipeline output from upstream (Ishan)
  2. Emit submission observability event
  3. Validate against 7-field contract
  4. Emit evaluation observability event
  5. Return deterministic 7-field dictionary to upstream
"""
import os
from typing import Dict, Any, List
from src.evaluation_engine.event_store import EventStore
from src.evaluation_engine.observability import ObservabilityEmitter
from src.evaluation_engine.contract_monitor import ContractMonitor


class EvaluationRunner:
    """
    Pure deterministic evaluation runner.
    Takes output, validates contract, ensures observability, and returns.
    """

    def __init__(self, state_dir: str = None):
        if state_dir is None:
            state_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "governance_state",
            )

        self._store = EventStore(state_dir)
        self._emitter = ObservabilityEmitter(self._store)
        self._monitor = ContractMonitor(self._emitter)

    def evaluate(self, pipeline_output: Dict[str, Any],
                 graph_traversal_trace: List[str] = None) -> Dict[str, Any]:
        """
        Evaluate a pipeline output.

        1. Emits submission event
        2. Validates 7-field contract
        3. Emits evaluation event
        4. Returns the validated output

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

        # Step 4: Return valid 7-field output unmodified
        return pipeline_output

    def get_all_observability_events(self) -> List[Dict[str, Any]]:
        return self._emitter.get_all_events()

    def reset(self) -> None:
        """Reset all state. For testing only."""
        self._store.reset()
