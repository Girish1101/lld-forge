from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AttemptStatus(Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class RubricCriterion:
    name: str  # e.g., "Single Responsibility", "Extensibility"
    weight: float
    description: str


@dataclass(frozen=True)
class Problem:
    id: str
    title: str
    description: str
    required_interfaces: List[str]
    rubric: List[RubricCriterion]
    starter_code: str


@dataclass(frozen=True)
class SubmissionPayload:
    source_code: str
    language: str
    pattern_rationale: str
    tradeoffs_rationale: str


@dataclass(frozen=True)
class EvaluationCritique:
    rule_name: str
    passed: bool
    score: float  # 0.0 to 10.0
    summary: str
    suggestions: List[str]


@dataclass
class EvaluationFeedback:
    overall_score: float
    deterministic_passed: bool
    critiques: List[EvaluationCritique]
    evaluated_at: datetime = field(default_factory=utc_now)
    execution_time_ms: int = 0
    failure_reason: Optional[str] = None


class Attempt:
    def __init__(self, attempt_id: str, problem_id: str, version: int = 1, learner_id: str = "anonymous"):
        self.id: str = attempt_id
        self.problem_id: str = problem_id
        self.version: int = version
        self.learner_id: str = learner_id
        self.status: AttemptStatus = AttemptStatus.DRAFT
        self.submission: Optional[SubmissionPayload] = None
        self.feedback: Optional[EvaluationFeedback] = None
        self.created_at: datetime = utc_now()
        self.updated_at: datetime = utc_now()

    def submit(self, payload: SubmissionPayload) -> None:
        if self.status in [AttemptStatus.EVALUATING, AttemptStatus.COMPLETED]:
            raise ValueError(f"Cannot submit attempt in {self.status.value} state.")
        self.submission = payload
        self.status = AttemptStatus.SUBMITTED
        self.updated_at = utc_now()

    def mark_evaluating(self) -> None:
        if self.status != AttemptStatus.SUBMITTED:
            raise ValueError("Attempt must be SUBMITTED before EVALUATING.")
        self.status = AttemptStatus.EVALUATING
        self.updated_at = utc_now()

    def mark_completed(self, feedback: EvaluationFeedback) -> None:
        self.feedback = feedback
        self.status = AttemptStatus.COMPLETED
        self.updated_at = utc_now()

    def mark_failed(self, reason: str) -> None:
        self.status = AttemptStatus.FAILED
        self.feedback = EvaluationFeedback(
            overall_score=0.0,
            deterministic_passed=False,
            critiques=[],
            failure_reason=reason
        )
        self.updated_at = utc_now()

    def create_next_version(self, new_attempt_id: str) -> "Attempt":
        """Forks the current attempt into an incremental iteration, preserving learner identity."""
        return Attempt(
            attempt_id=new_attempt_id,
            problem_id=self.problem_id,
            version=self.version + 1,
            learner_id=self.learner_id
        )
