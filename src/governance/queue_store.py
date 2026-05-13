"""
Parikshak Operational Governance — Queue Store
===============================================
JSON-file-backed persistent store for approval queues.
Immutable append-only log + current state.
No in-memory-only state — everything is persisted.
Thread-safe via file locking.
"""
import json
import os
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class QueueStore:
    """
    Persistent queue store backed by JSON files.

    Storage layout:
        state_dir/
            queue_state.json       # current queue entries (keyed by queue_entry_id)
            approval_log.json      # append-only approval events
            observability_log.json # append-only observability events

    All writes are atomic (write to temp, rename).
    Thread-safe via a reentrant lock.
    """

    def __init__(self, state_dir: str):
        self._state_dir = state_dir
        os.makedirs(state_dir, exist_ok=True)

        self._queue_file = os.path.join(state_dir, "queue_state.json")
        self._approval_log_file = os.path.join(state_dir, "approval_log.json")
        self._observability_log_file = os.path.join(state_dir, "observability_log.json")
        self._lock = threading.RLock()

        # Initialize files if they don't exist
        self._ensure_file(self._queue_file, {"entries": {}, "insertion_order": []})
        self._ensure_file(self._approval_log_file, {"events": []})
        self._ensure_file(self._observability_log_file, {"events": []})

    def _ensure_file(self, path: str, default: Dict) -> None:
        """Create file with default content if it doesn't exist."""
        if not os.path.exists(path):
            self._write_json(path, default)

    def _read_json(self, path: str) -> Dict:
        """Read JSON file atomically."""
        with self._lock:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

    def _write_json(self, path: str, data: Dict) -> None:
        """Write JSON file atomically (write to temp, rename)."""
        with self._lock:
            temp_path = path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # Atomic rename (on Windows, need to remove first)
            if os.path.exists(path):
                os.remove(path)
            os.rename(temp_path, path)

    # ── Queue Entry Operations ────────────────────────────────────────────

    def add_entry(self, entry: Dict[str, Any]) -> None:
        """Add a queue entry. Deterministic ordering via insertion_order list."""
        with self._lock:
            state = self._read_json(self._queue_file)
            entry_id = entry["queue_entry_id"]

            if entry_id in state["entries"]:
                raise ValueError(f"HARD FAIL: Duplicate queue_entry_id: {entry_id}")

            state["entries"][entry_id] = entry
            state["insertion_order"].append(entry_id)
            self._write_json(self._queue_file, state)

    def update_entry_status(self, queue_entry_id: str, new_status: str) -> None:
        """Update the status of a queue entry."""
        with self._lock:
            state = self._read_json(self._queue_file)

            if queue_entry_id not in state["entries"]:
                raise ValueError(f"HARD FAIL: queue_entry_id not found: {queue_entry_id}")

            state["entries"][queue_entry_id]["queue_status"] = new_status
            self._write_json(self._queue_file, state)

    def get_entry(self, queue_entry_id: str) -> Optional[Dict[str, Any]]:
        """Get a single queue entry by ID."""
        with self._lock:
            state = self._read_json(self._queue_file)
            return state["entries"].get(queue_entry_id)

    def get_entry_by_trace_id(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get a queue entry by trace_id."""
        with self._lock:
            state = self._read_json(self._queue_file)
            for entry in state["entries"].values():
                if entry["trace_id"] == trace_id:
                    return entry
            return None

    def get_entries_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all entries with a given status, in deterministic insertion order."""
        with self._lock:
            state = self._read_json(self._queue_file)
            result = []
            for entry_id in state["insertion_order"]:
                entry = state["entries"].get(entry_id)
                if entry and entry["queue_status"] == status:
                    result.append(entry)
            return result

    def get_all_entries_ordered(self) -> List[Dict[str, Any]]:
        """Get all entries in deterministic insertion order."""
        with self._lock:
            state = self._read_json(self._queue_file)
            return [
                state["entries"][eid]
                for eid in state["insertion_order"]
                if eid in state["entries"]
            ]

    def get_entry_count(self) -> int:
        """Get total number of queue entries."""
        with self._lock:
            state = self._read_json(self._queue_file)
            return len(state["entries"])

    # ── Approval Log Operations ───────────────────────────────────────────

    def append_approval_event(self, event: Dict[str, Any]) -> None:
        """Append an approval event to the immutable log. NEVER modifies existing entries."""
        with self._lock:
            log = self._read_json(self._approval_log_file)
            log["events"].append(event)
            self._write_json(self._approval_log_file, log)

    def get_approval_events(self, queue_entry_id: str = None, trace_id: str = None) -> List[Dict[str, Any]]:
        """Get approval events filtered by queue_entry_id or trace_id."""
        with self._lock:
            log = self._read_json(self._approval_log_file)
            events = log["events"]

            if queue_entry_id:
                events = [e for e in events if e["queue_entry_id"] == queue_entry_id]
            if trace_id:
                events = [e for e in events if e["trace_id"] == trace_id]

            return events

    def get_all_approval_events(self) -> List[Dict[str, Any]]:
        """Get all approval events in append order."""
        with self._lock:
            log = self._read_json(self._approval_log_file)
            return log["events"]

    def get_approval_event_count(self) -> int:
        """Get total count of approval events."""
        with self._lock:
            log = self._read_json(self._approval_log_file)
            return len(log["events"])

    # ── Observability Log Operations ──────────────────────────────────────

    def append_observability_event(self, event: Dict[str, Any]) -> None:
        """Append an observability event. NEVER modifies existing entries."""
        with self._lock:
            log = self._read_json(self._observability_log_file)
            log["events"].append(event)
            self._write_json(self._observability_log_file, log)

    def get_observability_events(self, trace_id: str = None, event_type: str = None) -> List[Dict[str, Any]]:
        """Get observability events filtered by trace_id or event_type."""
        with self._lock:
            log = self._read_json(self._observability_log_file)
            events = log["events"]

            if trace_id:
                events = [e for e in events if e["trace_id"] == trace_id]
            if event_type:
                events = [e for e in events if e["event_type"] == event_type]

            return events

    def get_all_observability_events(self) -> List[Dict[str, Any]]:
        """Get all observability events in append order."""
        with self._lock:
            log = self._read_json(self._observability_log_file)
            return log["events"]

    # ── State Reset (for testing) ─────────────────────────────────────────

    def reset(self) -> None:
        """Reset all state. For testing purposes only."""
        with self._lock:
            self._write_json(self._queue_file, {"entries": {}, "insertion_order": []})
            self._write_json(self._approval_log_file, {"events": []})
            self._write_json(self._observability_log_file, {"events": []})
