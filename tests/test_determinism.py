"""
Parikshak Operational Governance — Determinism Tests
======================================================
Proves: same input + same graph state = same operational result.
"""
import os
import sys
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.governance.governance_orchestrator import GovernanceOrchestrator


def _make_output(trace_id="T1", sub_id="S1"):
    return {
        "trace_id": trace_id,
        "submission_id": sub_id,
        "evaluation_result": "PASS",
        "failure_type": None,
        "selected_task_id": "TASK_001",
        "selection_reason": "Auth failure - token validation.",
        "source": "task_graph",
    }


def _make_fail_output(trace_id="TF1", sub_id="SF1"):
    return {
        "trace_id": trace_id,
        "submission_id": sub_id,
        "evaluation_result": "FAIL",
        "failure_type": "schema_violation",
        "selected_task_id": "NONE",
        "selection_reason": "HARD FAIL: product must not be empty.",
        "source": "task_graph",
    }


class TestDeterminism:
    """Phase 5: Deterministic governance tests."""

    def test_same_input_same_queue_entry(self, tmp_path):
        """Same pipeline output → same queue entry (excluding timestamps)."""
        results = []
        for i in range(5):
            gov = GovernanceOrchestrator(str(tmp_path / f"run_{i}"))
            entry = gov.submit(_make_output(), ["TASK_001", "TASK_002"])
            # Compare deterministic fields only
            det = {
                "queue_entry_id": entry["queue_entry_id"],
                "trace_id": entry["trace_id"],
                "submission_id": entry["submission_id"],
                "evaluation_result": entry["evaluation_result"],
                "failure_type": entry["failure_type"],
                "selected_task_id": entry["selected_task_id"],
                "queue_status": entry["queue_status"],
                "graph_traversal_trace": entry["graph_traversal_trace"],
            }
            results.append(det)

        assert all(r == results[0] for r in results)

    def test_same_approval_same_result(self, tmp_path):
        """Same approval action → same result (excluding timestamps)."""
        results = []
        for i in range(5):
            gov = GovernanceOrchestrator(str(tmp_path / f"run_{i}"))
            gov.submit(_make_output())
            result = gov.approve("QE-S1", "op1", "Approved")
            det = {
                "action": result["action"],
                "queue_entry_id": result["queue_entry_id"],
                "trace_id": result["trace_id"],
                "previous_status": result["previous_status"],
                "new_status": result["new_status"],
                "approver_id": result["approver_id"],
                "reason": result["reason"],
            }
            results.append(det)

        assert all(r == results[0] for r in results)

    def test_same_rejection_same_result(self, tmp_path):
        results = []
        for i in range(5):
            gov = GovernanceOrchestrator(str(tmp_path / f"run_{i}"))
            gov.submit(_make_output())
            result = gov.reject("QE-S1", "op1", "Rejected reason")
            det = {
                "action": result["action"],
                "new_status": result["new_status"],
                "reason": result["reason"],
            }
            results.append(det)

        assert all(r == results[0] for r in results)

    def test_same_audit_reconstruction(self, tmp_path):
        """Same lifecycle → same audit dict (excluding timestamps)."""
        results = []
        for i in range(5):
            gov = GovernanceOrchestrator(str(tmp_path / f"run_{i}"))
            gov.submit(_make_output(), ["TASK_001", "TASK_002", "TASK_003"])
            gov.approve("QE-S1", "op1", "OK")
            audit = gov.reconstruct_audit_dict("T1")
            det = {
                "trace_id": audit["trace_id"],
                "submission_id": audit["submission_id"],
                "evaluation_result": audit["evaluation_result"],
                "selected_task_id": audit["selected_task_id"],
                "queue_status": audit["queue_status"],
                "lifecycle_complete": audit["lifecycle_complete"],
                "graph_traversal_trace": audit["graph_traversal_trace"],
            }
            results.append(det)

        assert all(r == results[0] for r in results)

    def test_fail_output_determinism(self, tmp_path):
        results = []
        for i in range(5):
            gov = GovernanceOrchestrator(str(tmp_path / f"run_{i}"))
            entry = gov.submit(_make_fail_output())
            det = {
                "queue_entry_id": entry["queue_entry_id"],
                "evaluation_result": entry["evaluation_result"],
                "failure_type": entry["failure_type"],
                "selected_task_id": entry["selected_task_id"],
            }
            results.append(det)

        assert all(r == results[0] for r in results)

    def test_queue_ordering_determinism(self, tmp_path):
        """Multiple submissions in same order → same queue order."""
        results = []
        for i in range(3):
            gov = GovernanceOrchestrator(str(tmp_path / f"run_{i}"))
            gov.submit(_make_output(trace_id="T1", sub_id="S1"))
            gov.submit(_make_output(trace_id="T2", sub_id="S2"))
            gov.submit(_make_output(trace_id="T3", sub_id="S3"))
            pending = gov.get_pending_review()
            order = [e["trace_id"] for e in pending]
            results.append(order)

        assert all(r == results[0] for r in results)

    def test_escalation_flow_determinism(self, tmp_path):
        results = []
        for i in range(5):
            gov = GovernanceOrchestrator(str(tmp_path / f"run_{i}"))
            gov.submit(_make_output())
            gov.hold("QE-S1", "op1", "Needs review")
            gov.approve("QE-S1", "senior", "Senior approved")
            audit = gov.reconstruct_audit_dict("T1")
            det = {
                "queue_status": audit["queue_status"],
                "lifecycle_complete": audit["lifecycle_complete"],
                "num_events": len(audit["approval_events"]),
            }
            results.append(det)

        assert all(r == results[0] for r in results)
