import time
from abc import ABC, abstractmethod
from typing import List, Optional
from models import Problem, SubmissionPayload, EvaluationFeedback, EvaluationCritique
from rules import IDeterministicRule, IHeuristicRule


class IEvaluationEngine(ABC):
    """Orchestrates pipeline execution over all configured evaluation rules."""
    @abstractmethod
    def run_evaluation(self, problem: Problem, submission: SubmissionPayload) -> EvaluationFeedback:
        pass


class HybridEvaluationPipeline(IEvaluationEngine):
    """
    Two-stage evaluation engine orchestrating fast deterministic static checks
    followed by cognitive/heuristic LLM reviews with time budgets and graceful fallbacks.
    """
    def __init__(
        self,
        deterministic_rules: List[IDeterministicRule],
        heuristic_rules: List[IHeuristicRule],
        timeout_seconds: float = 8.0
    ):
        self.deterministic_rules = deterministic_rules
        self.heuristic_rules = heuristic_rules
        self.timeout_seconds = timeout_seconds

    def run_evaluation(self, problem: Problem, submission: SubmissionPayload) -> EvaluationFeedback:
        start_time = time.time()
        critiques: List[EvaluationCritique] = []

        # Step 1: Run deterministic static analysis
        deterministic_passed = True
        for rule in self.deterministic_rules:
            critique = rule.evaluate(problem, submission)
            critiques.append(critique)
            if not critique.passed and critique.rule_name == "Syntax & Parse Validation":
                # Critical fail: fast-fail without wasting compute on LLM
                return EvaluationFeedback(
                    overall_score=0.0,
                    deterministic_passed=False,
                    critiques=critiques,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    failure_reason="Syntax error halts evaluation pipeline."
                )
            if not critique.passed:
                deterministic_passed = False

        # Step 2: Run heuristic/LLM rules with timeout & fallback
        for rule in self.heuristic_rules:
            elapsed = time.time() - start_time
            remaining_time = self.timeout_seconds - elapsed

            if remaining_time <= 0:
                critiques.append(EvaluationCritique(
                    rule_name="Heuristic Evaluation (Fallback)",
                    passed=False,
                    score=0.0,
                    summary="Evaluation budget timed out before heuristic analysis finished.",
                    suggestions=["Heuristic feedback was skipped. Deterministic checks remain valid."]
                ))
                break

            try:
                # Execute heuristic / LLM evaluation
                heuristic_critique = rule.evaluate(problem, submission)
                critiques.append(heuristic_critique)
            except Exception as exc:
                # Graceful degradation: failure doesn't crash the learner's attempt
                critiques.append(EvaluationCritique(
                    rule_name="Heuristic Evaluation (Unavailable)",
                    passed=False,
                    score=0.0,
                    summary=f"LLM evaluator encountered a temporary fault: {str(exc)}",
                    suggestions=["Review deterministic checks. You may retry evaluation shortly."]
                ))

        # Step 3: Calculate final weighted score
        valid_scores = [c.score for c in critiques if c.score > 0.0]
        final_score = round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else 0.0

        return EvaluationFeedback(
            overall_score=final_score,
            deterministic_passed=deterministic_passed,
            critiques=critiques,
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
