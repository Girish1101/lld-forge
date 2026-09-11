import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from models import Problem, Attempt


class IProblemRepository(ABC):
    @abstractmethod
    def get_by_id(self, problem_id: str) -> Optional[Problem]:
        pass

    @abstractmethod
    def list_all(self) -> List[Problem]:
        pass

    @abstractmethod
    def save(self, problem: Problem) -> None:
        pass


class IAttemptRepository(ABC):
    @abstractmethod
    def get_by_id(self, attempt_id: str) -> Optional[Attempt]:
        pass

    @abstractmethod
    def list_by_problem(self, problem_id: str) -> List[Attempt]:
        pass

    @abstractmethod
    def list_by_learner_and_problem(self, learner_id: str, problem_id: str) -> List[Attempt]:
        pass

    @abstractmethod
    def save(self, attempt: Attempt) -> None:
        pass


class InMemoryProblemRepository(IProblemRepository):
    """Thread-safe in-memory problem catalog repository."""
    def __init__(self):
        self._storage: Dict[str, Problem] = {}
        self._lock = threading.Lock()

    def get_by_id(self, problem_id: str) -> Optional[Problem]:
        with self._lock:
            return self._storage.get(problem_id)

    def list_all(self) -> List[Problem]:
        with self._lock:
            return list(self._storage.values())

    def save(self, problem: Problem) -> None:
        with self._lock:
            self._storage[problem.id] = problem


class InMemoryAttemptRepository(IAttemptRepository):
    """Thread-safe in-memory attempt history repository."""
    def __init__(self):
        self._storage: Dict[str, Attempt] = {}
        self._lock = threading.Lock()

    def get_by_id(self, attempt_id: str) -> Optional[Attempt]:
        with self._lock:
            return self._storage.get(attempt_id)

    def list_by_problem(self, problem_id: str) -> List[Attempt]:
        with self._lock:
            return [att for att in self._storage.values() if att.problem_id == problem_id]

    def list_by_learner_and_problem(self, learner_id: str, problem_id: str) -> List[Attempt]:
        with self._lock:
            return [
                att for att in self._storage.values()
                if att.problem_id == problem_id and att.learner_id == learner_id
            ]

    def save(self, attempt: Attempt) -> None:
        with self._lock:
            self._storage[attempt.id] = attempt
