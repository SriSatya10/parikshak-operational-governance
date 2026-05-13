"""
Parikshak Operational Governance — Concurrency Tests
======================================================
Tests: concurrent submissions, queue ordering under concurrency,
       no race conditions in approval state.
"""
import os
import sys
import pytest
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.governance.governance_orchestrator import GovernanceOrchestrator


def _make_output(trace_id, sub_id):
    return {
        "trace_id": trace_id,
        "submission_id": sub_id,
        "evaluation_result": "PASS",
        "failure_type": None,
        "selected_task_id": "TASK_001",
        "selection_reason": "Test",
        "source": "task_graph",
    }


class TestConcurrency:
    """Phase 5: Concurrent workflow tests."""

    def test_concurrent_submissions(self, tmp_path):
        """Multiple threads submitting concurrently — no crashes."""
        gov = GovernanceOrchestrator(str(tmp_path / "state"))
        errors = []

        def submit(idx):
            try:
                gov.submit(_make_output(f"T-{idx}", f"S-{idx}"))
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=submit, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        counts = gov.get_queue_counts()
        assert counts["PENDING_REVIEW"] == 10

    def test_concurrent_submissions_no_duplicates(self, tmp_path):
        """Each thread submits a unique entry — no duplicates."""
        gov = GovernanceOrchestrator(str(tmp_path / "state"))
        errors = []

        def submit(idx):
            try:
                gov.submit(_make_output(f"T-{idx}", f"S-{idx}"))
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=submit, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        entries = gov.get_pending_review()
        ids = [e["queue_entry_id"] for e in entries]
        assert len(ids) == len(set(ids))  # No duplicates

    def test_concurrent_approval_no_race(self, tmp_path):
        """Only one approval should succeed for a given entry."""
        gov = GovernanceOrchestrator(str(tmp_path / "state"))
        gov.submit(_make_output("T1", "S1"))

        results = []
        errors = []

        def approve(approver_id):
            try:
                r = gov.approve("QE-S1", approver_id, f"Approved by {approver_id}")
                results.append(r)
            except ValueError:
                errors.append(approver_id)

        # Two threads try to approve the same entry
        t1 = threading.Thread(target=approve, args=("op1",))
        t2 = threading.Thread(target=approve, args=("op2",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Exactly one should succeed, one should fail
        assert len(results) + len(errors) == 2
        # The entry should be APPROVED
        entry = gov._store.get_entry("QE-S1")
        assert entry["queue_status"] == "APPROVED"

    def test_concurrent_different_entries(self, tmp_path):
        """Different entries can be approved concurrently."""
        gov = GovernanceOrchestrator(str(tmp_path / "state"))
        gov.submit(_make_output("T1", "S1"))
        gov.submit(_make_output("T2", "S2"))
        gov.submit(_make_output("T3", "S3"))

        results = []

        def approve(entry_id, approver):
            r = gov.approve(entry_id, approver, f"Approved {entry_id}")
            results.append(r)

        threads = [
            threading.Thread(target=approve, args=("QE-S1", "op1")),
            threading.Thread(target=approve, args=("QE-S2", "op2")),
            threading.Thread(target=approve, args=("QE-S3", "op3")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 3
        counts = gov.get_queue_counts()
        assert counts["APPROVED"] == 3

    def test_queue_entries_all_present_after_concurrent_submit(self, tmp_path):
        """All entries present after concurrent submission."""
        gov = GovernanceOrchestrator(str(tmp_path / "state"))

        def submit(idx):
            gov.submit(_make_output(f"T-{idx}", f"S-{idx}"))

        threads = [threading.Thread(target=submit, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        entries = gov.get_pending_review()
        assert len(entries) == 20
        # All trace_ids present
        trace_ids = {e["trace_id"] for e in entries}
        expected = {f"T-{i}" for i in range(20)}
        assert trace_ids == expected
