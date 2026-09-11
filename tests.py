import unittest
import json
import threading
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Dict, Any

from models import (
    Attempt, AttemptStatus, Problem, RubricCriterion,
    SubmissionPayload, EvaluationFeedback, EvaluationCritique
)
from rules import (
    ASTStructuralAnalyzer, ASTInterfaceValidationRule, ClassSizeCouplingRule,
    LLMDesignReviewRule, ILLMAdapter, MockLLMAdapter
)
from engine import HybridEvaluationPipeline
from repositories import InMemoryProblemRepository, InMemoryAttemptRepository
from service import PracticePlatformService
from api import create_http_server
from main import setup_default_service


class TestAttemptDomainTransitions(unittest.TestCase):
    def setUp(self):
        self.attempt = Attempt(attempt_id="att_test_001", problem_id="parking-lot", version=1)
        self.payload = SubmissionPayload(
            source_code="class Vehicle: pass",
            language="python",
            pattern_rationale="Basic model",
            tradeoffs_rationale="In-memory only"
        )

    def test_initial_state_is_draft(self):
        self.assertEqual(self.attempt.status, AttemptStatus.DRAFT)
        self.assertEqual(self.attempt.version, 1)
        self.assertIsNone(self.attempt.submission)
        self.assertIsNone(self.attempt.feedback)

    def test_valid_submission_lifecycle(self):
        # DRAFT -> SUBMITTED
        self.attempt.submit(self.payload)
        self.assertEqual(self.attempt.status, AttemptStatus.SUBMITTED)
        self.assertIsNotNone(self.attempt.submission)

        # SUBMITTED -> EVALUATING
        self.attempt.mark_evaluating()
        self.assertEqual(self.attempt.status, AttemptStatus.EVALUATING)

        # EVALUATING -> COMPLETED
        feedback = EvaluationFeedback(
            overall_score=8.5,
            deterministic_passed=True,
            critiques=[]
        )
        self.attempt.mark_completed(feedback)
        self.assertEqual(self.attempt.status, AttemptStatus.COMPLETED)
        self.assertEqual(self.attempt.feedback.overall_score, 8.5)

    def test_prevent_evaluating_from_draft(self):
        """Cannot jump directly from DRAFT to EVALUATING without submission."""
        with self.assertRaises(ValueError):
            self.attempt.mark_evaluating()

    def test_prevent_submission_when_already_evaluating(self):
        """Attempt in evaluation cannot accept duplicate submissions."""
        self.attempt.submit(self.payload)
        self.attempt.mark_evaluating()
        with self.assertRaises(ValueError):
            self.attempt.submit(self.payload)

    def test_mark_failed_sets_status_and_records_reason(self):
        self.attempt.submit(self.payload)
        self.attempt.mark_evaluating()
        self.attempt.mark_failed("Evaluation service unreachable.")
        self.assertEqual(self.attempt.status, AttemptStatus.FAILED)
        self.assertEqual(self.attempt.feedback.failure_reason, "Evaluation service unreachable.")
        self.assertFalse(self.attempt.feedback.deterministic_passed)

    def test_version_forking_increments_counter(self):
        child_attempt = self.attempt.create_next_version(new_attempt_id="att_test_002")
        self.assertEqual(child_attempt.version, 2)
        self.assertEqual(child_attempt.problem_id, self.attempt.problem_id)
        self.assertEqual(child_attempt.status, AttemptStatus.DRAFT)


class FailingLLMAdapter(ILLMAdapter):
    """Simulates network timeout or upstream 500 error from an LLM API provider."""
    def analyze_design(self, problem_description: str, code: str, rationale: str) -> Dict[str, Any]:
        raise TimeoutError("Upstream LLM provider did not respond within deadline.")


class TestEvaluationPipelineStrategies(unittest.TestCase):
    def setUp(self):
        self.problem = Problem(
            id="parking-lot",
            title="Parking Lot Design",
            description="Design an extensible parking system.",
            required_interfaces=["Vehicle", "ParkingSpot"],
            rubric=[],
            starter_code=""
        )

    def test_ast_structural_analyzer_utility(self):
        code = """
class Vehicle: pass
class ParkingSpot(Vehicle): pass
class GodObject:
    def m1(self): pass
    def m2(self): pass
    def m3(self): pass
"""
        classes = ASTStructuralAnalyzer.extract_declared_classes(code)
        self.assertEqual(classes, {"Vehicle", "ParkingSpot", "GodObject"})

        inheritance = ASTStructuralAnalyzer.inspect_inheritance(code)
        self.assertEqual(inheritance.get("ParkingSpot"), ["Vehicle"])

        monoliths = ASTStructuralAnalyzer.detect_monolithic_classes(code, max_methods=2)
        self.assertEqual(monoliths, ["GodObject"])

    def test_syntax_error_halts_early_without_running_heuristic(self):
        """A broken syntax string must fail fast and bypass heuristic evaluation."""
        pipeline = HybridEvaluationPipeline(
            deterministic_rules=[ASTInterfaceValidationRule()],
            heuristic_rules=[LLMDesignReviewRule(MockLLMAdapter())]
        )
        broken_payload = SubmissionPayload(
            source_code="def broken_syntax( pass",  # Syntax error
            language="python",
            pattern_rationale="N/A",
            tradeoffs_rationale="N/A"
        )

        feedback = pipeline.run_evaluation(self.problem, broken_payload)

        self.assertFalse(feedback.deterministic_passed)
        self.assertEqual(feedback.overall_score, 0.0)
        self.assertIn("Syntax error halts evaluation pipeline.", feedback.failure_reason)
        self.assertEqual(len(feedback.critiques), 1)
        self.assertEqual(feedback.critiques[0].rule_name, "Syntax & Parse Validation")

    def test_missing_required_interfaces_reduces_score(self):
        rule = ASTInterfaceValidationRule()
        partial_code = "class Vehicle:\n    pass\n"  # ParkingSpot missing
        payload = SubmissionPayload(
            source_code=partial_code,
            language="python",
            pattern_rationale="",
            tradeoffs_rationale=""
        )

        critique = rule.evaluate(self.problem, payload)
        self.assertFalse(critique.passed)
        self.assertIn("ParkingSpot", critique.summary)
        self.assertLess(critique.score, 10.0)

    def test_class_size_coupling_rule_detects_god_class(self):
        rule = ClassSizeCouplingRule()
        methods = "\n".join([f"    def method_{i}(self): pass" for i in range(11)])
        god_class_code = f"class MonolithLot:\n{methods}\n"
        payload = SubmissionPayload(
            source_code=god_class_code,
            language="python",
            pattern_rationale="",
            tradeoffs_rationale=""
        )

        critique = rule.evaluate(self.problem, payload)
        self.assertFalse(critique.passed)
        self.assertIn("MonolithLot", critique.summary)

    def test_graceful_degradation_on_llm_failure(self):
        """If the LLM fails or times out, deterministic feedback is preserved."""
        pipeline = HybridEvaluationPipeline(
            deterministic_rules=[ASTInterfaceValidationRule()],
            heuristic_rules=[LLMDesignReviewRule(FailingLLMAdapter())]
        )
        valid_payload = SubmissionPayload(
            source_code="class Vehicle:\n    pass\nclass ParkingSpot:\n    pass\n",
            language="python",
            pattern_rationale="Clean division of concerns",
            tradeoffs_rationale="None"
        )

        feedback = pipeline.run_evaluation(self.problem, valid_payload)

        self.assertTrue(feedback.deterministic_passed)
        ast_critique = next(c for c in feedback.critiques if c.rule_name == "Required Abstractions Check")
        llm_critique = next(c for c in feedback.critiques if "Heuristic Evaluation" in c.rule_name)

        self.assertTrue(ast_critique.passed)
        self.assertFalse(llm_critique.passed)
        self.assertIn("temporary fault", llm_critique.summary)


class TestEndToEndAttemptLifecycle(unittest.TestCase):
    def setUp(self):
        self.service = setup_default_service()

    def test_three_seeded_problems_exist(self):
        problems = self.service.list_problems()
        self.assertEqual(len(problems), 3)
        ids = [p.id for p in problems]
        self.assertIn("parking-lot", ids)
        self.assertIn("elevator-system", ids)
        self.assertIn("vending-machine", ids)
        for p in problems:
            self.assertGreaterEqual(len(p.rubric), 3)

    def test_full_practice_and_revision_loop(self):
        # 1. Start Attempt 1
        att1 = self.service.start_new_attempt("vending-machine")
        self.assertEqual(att1.version, 1)

        # 2. Submit initial flawed implementation (missing State interface)
        sub1 = SubmissionPayload(
            source_code="class VendingMachine:\n    def __init__(self):\n        self.state = 'IDLE'\n",
            language="python",
            pattern_rationale="Used raw string flags for state control.",
            tradeoffs_rationale="Simpler than full State Pattern."
        )
        evaluated_att1 = self.service.submit_and_evaluate(att1.id, sub1)
        self.assertEqual(evaluated_att1.status, AttemptStatus.COMPLETED)
        self.assertFalse(evaluated_att1.feedback.deterministic_passed)

        # 3. Create iteration Attempt 2
        att2 = self.service.iterate_attempt(evaluated_att1.id)
        self.assertEqual(att2.version, 2)
        self.assertEqual(att2.status, AttemptStatus.DRAFT)

        # 4. Submit improved solution matching all contracts
        sub2 = SubmissionPayload(
            source_code="""
from abc import ABC, abstractmethod

class State(ABC):
    @abstractmethod
    def insert_coin(self): pass

class VendingMachine:
    def __init__(self, state: State):
        self.state = state
""",
            language="python",
            pattern_rationale="Refactored to Strategy/State pattern to isolate state transitions.",
            tradeoffs_rationale="Added class count for decoupling."
        )
        evaluated_att2 = self.service.submit_and_evaluate(att2.id, sub2)
        self.assertEqual(evaluated_att2.status, AttemptStatus.COMPLETED)
        self.assertTrue(evaluated_att2.feedback.deterministic_passed)
        self.assertGreater(evaluated_att2.feedback.overall_score, evaluated_att1.feedback.overall_score)

        # 5. Query history for the problem
        history = self.service.get_problem_history("vending-machine")
        self.assertEqual(len(history), 2)
        versions = [a.version for a in history]
        self.assertIn(1, versions)
        self.assertIn(2, versions)


class TestRESTAPIController(unittest.TestCase):
    """Integration test suite for HTTP REST API Controller (api.py)."""
    @classmethod
    def setUpClass(cls):
        cls.service = setup_default_service()
        cls.port = 8899
        cls.server = create_http_server(cls.service, port=cls.port)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _post(self, path: str, payload: dict) -> dict:
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _get(self, path: str) -> dict:
        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"}, method="GET")
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_get_problems_endpoint(self):
        res = self._get("/api/problems")
        self.assertIn("problems", res)
        self.assertEqual(len(res["problems"]), 3)

    def test_start_submit_iterate_history_api_flow(self):
        # 1. Start attempt via POST /api/attempts
        create_res = self._post("/api/attempts", {"problem_id": "parking-lot"})
        self.assertIn("attempt_id", create_res)
        attempt_id = create_res["attempt_id"]
        self.assertEqual(create_res["version"], 1)

        # 2. Submit solution via POST /api/attempts/<id>/submit
        sub_res = self._post(f"/api/attempts/{attempt_id}/submit", {
            "source_code": "class Vehicle: pass\nclass ParkingSpot: pass\nclass IParkingStrategy: pass",
            "language": "python",
            "pattern_rationale": "Strategy Pattern",
            "tradeoffs_rationale": "In-memory"
        })
        self.assertEqual(sub_res["status"], "COMPLETED")
        self.assertTrue(sub_res["deterministic_passed"])

        # 3. Iterate attempt via POST /api/attempts/<id>/iterate
        iter_res = self._post(f"/api/attempts/{attempt_id}/iterate", {})
        self.assertIn("attempt_id", iter_res)
        self.assertEqual(iter_res["version"], 2)

        # 4. Get history via GET /api/problems/parking-lot/history
        hist_res = self._get("/api/problems/parking-lot/history")
        self.assertIn("history", hist_res)
        self.assertGreaterEqual(len(hist_res["history"]), 2)


if __name__ == "__main__":
    unittest.main()
