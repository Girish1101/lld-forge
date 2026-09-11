import uuid
from typing import List, Optional
from models import Problem, Attempt, SubmissionPayload
from repositories import IProblemRepository, IAttemptRepository
from engine import IEvaluationEngine


class PracticePlatformService:
    """Application Service coordinating repository state and hybrid evaluation execution."""
    def __init__(
        self,
        problem_repo: IProblemRepository,
        attempt_repo: IAttemptRepository,
        engine: IEvaluationEngine
    ):
        self.problem_repo = problem_repo
        self.attempt_repo = attempt_repo
        self.engine = engine

    def list_problems(self) -> List[Problem]:
        return self.problem_repo.list_all()

    def get_problem(self, problem_id: str) -> Optional[Problem]:
        return self.problem_repo.get_by_id(problem_id)

    def get_attempt(self, attempt_id: str) -> Optional[Attempt]:
        return self.attempt_repo.get_by_id(attempt_id)

    def get_problem_history(self, problem_id: str) -> List[Attempt]:
        return self.attempt_repo.list_by_problem(problem_id)

    def get_learner_history(self, learner_id: str, problem_id: str) -> List[Attempt]:
        """Returns attempts scoped to a specific learner + problem pair, sorted by version."""
        attempts = self.attempt_repo.list_by_learner_and_problem(learner_id, problem_id)
        return sorted(attempts, key=lambda a: a.version)

    def start_new_attempt(self, problem_id: str, learner_id: str = "anonymous") -> Attempt:
        problem = self.problem_repo.get_by_id(problem_id)
        if not problem:
            raise ValueError(f"Problem {problem_id} does not exist.")

        attempt_id = f"att_{uuid.uuid4().hex[:8]}"
        attempt = Attempt(attempt_id=attempt_id, problem_id=problem_id, version=1, learner_id=learner_id)
        self.attempt_repo.save(attempt)
        return attempt

    def submit_and_evaluate(self, attempt_id: str, payload: SubmissionPayload) -> Attempt:
        attempt = self.attempt_repo.get_by_id(attempt_id)
        if not attempt:
            raise ValueError(f"Attempt {attempt_id} not found.")

        problem = self.problem_repo.get_by_id(attempt.problem_id)
        if not problem:
            raise ValueError(f"Associated problem {attempt.problem_id} not found.")

        attempt.submit(payload)
        attempt.mark_evaluating()
        self.attempt_repo.save(attempt)

        try:
            feedback = self.engine.run_evaluation(problem, payload)
            attempt.mark_completed(feedback)
        except Exception as exc:
            attempt.mark_failed(str(exc))

        self.attempt_repo.save(attempt)
        return attempt

    def iterate_attempt(self, previous_attempt_id: str) -> Attempt:
        prev_attempt = self.attempt_repo.get_by_id(previous_attempt_id)
        if not prev_attempt:
            raise ValueError(f"Previous attempt {previous_attempt_id} not found.")

        next_attempt_id = f"att_{uuid.uuid4().hex[:8]}"
        new_attempt = prev_attempt.create_next_version(next_attempt_id)
        self.attempt_repo.save(new_attempt)
        return new_attempt
