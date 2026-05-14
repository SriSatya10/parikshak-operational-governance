"""
Parikshak Operational Governance — Data Models
===============================================
Strict data models for the evaluation layer.
No dynamic generation. No AI/ML. No randomness.
"""
from dataclasses import dataclass
from typing import Dict, Any
from datetime import datetime, timezone


# ── Observability Event Types ─────────────────────────────────────────────────
EVENT_SUBMISSION = "SUBMISSION"
EVENT_EVALUATION = "EVALUATION"
EVENT_CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
EVENT_GRAPH_REJECT = "GRAPH_REJECT"

# ── Severity Levels ───────────────────────────────────────────────────────────
SEVERITY_INFO = "INFO"
SEVERITY_WARN = "WARN"
SEVERITY_ERROR = "ERROR"
SEVERITY_CRITICAL = "CRITICAL"


def _utc_now_iso() -> str:
    """Returns current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@dataclass
class ObservabilityEvent:
    """
    Structured operational log event.
    Every event is explicit — no silent failures.
    """
    event_type: str                 # SUBMISSION | EVALUATION | etc.
    trace_id: str
    timestamp: str
    severity: str                   # INFO | WARN | ERROR | CRITICAL
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "severity": self.severity,
            "details": self.details,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ObservabilityEvent":
        return ObservabilityEvent(
            event_type=d["event_type"],
            trace_id=d["trace_id"],
            timestamp=d["timestamp"],
            severity=d["severity"],
            details=d["details"],
        )
