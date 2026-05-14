"""
Parikshak Operational Governance — Event Store
===============================================
JSON-file-backed persistent store for observability logs.
Immutable append-only log.
Thread-safe via file locking.
"""
import json
import os
import threading
from typing import Dict, Any, List


class EventStore:
    """
    Persistent store backed by JSON files.

    Storage layout:
        state_dir/
            observability_log.json # append-only observability events

    All writes are atomic (write to temp, rename).
    Thread-safe via a reentrant lock.
    """

    def __init__(self, state_dir: str):
        self._state_dir = state_dir
        os.makedirs(state_dir, exist_ok=True)

        self._observability_log_file = os.path.join(state_dir, "observability_log.json")
        self._lock = threading.RLock()

        # Initialize files if they don't exist
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
            self._write_json(self._observability_log_file, {"events": []})
