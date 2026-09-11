import sys
import argparse
from models import Problem, RubricCriterion, SubmissionPayload
from rules import ASTInterfaceValidationRule, ClassSizeCouplingRule, LLMDesignReviewRule, MockLLMAdapter
from engine import HybridEvaluationPipeline
from repositories import InMemoryProblemRepository, InMemoryAttemptRepository
from service import PracticePlatformService
from api import create_http_server


def setup_default_service() -> PracticePlatformService:
    prob_repo = InMemoryProblemRepository()
    att_repo = InMemoryAttemptRepository()

    # Curated Problem 1: Parking Lot Allocation Engine
    parking_lot_problem = Problem(
        id="parking-lot",
        title="Parking Lot Allocation Engine",
        description="Design a flexible parking lot allocation system supporting diverse vehicle types, spot types, and custom allocation strategies.",
        required_interfaces=["Vehicle", "ParkingSpot", "IParkingStrategy"],
        rubric=[
            RubricCriterion("Single Responsibility", 0.35, "Classes must have one reason to change."),
            RubricCriterion("Extensibility", 0.35, "Allow new spot assignment policies without modifying LotController."),
            RubricCriterion("Encapsulation", 0.30, "Protect spot states and prevent direct illegal state mutations.")
        ],
        starter_code="from abc import ABC, abstractmethod\n\nclass Vehicle(ABC):\n    pass\n"
    )
    prob_repo.save(parking_lot_problem)

    # Curated Problem 2: Multi-Elevator Dispatch Controller
    elevator_problem = Problem(
        id="elevator-system",
        title="Multi-Elevator Dispatch Controller",
        description="Design a multi-elevator scheduling and dispatch system optimizing response times across high-rise building floors.",
        required_interfaces=["Elevator", "IDispatchStrategy", "FloorRequest"],
        rubric=[
            RubricCriterion("Strategy Pattern", 0.40, "Decouple elevator dispatch algorithms (LOOK vs SCAN vs SSTF)."),
            RubricCriterion("State Management", 0.30, "Encapsulate elevator direction and motion states cleanly."),
            RubricCriterion("Single Responsibility", 0.30, "Isolate request queue management from physical elevator state.")
        ],
        starter_code="from abc import ABC, abstractmethod\n\nclass Elevator:\n    pass\n"
    )
    prob_repo.save(elevator_problem)

    # Curated Problem 3: Stateful Vending Machine Controller
    vending_problem = Problem(
        id="vending-machine",
        title="Stateful Vending Machine Controller",
        description="Design a vending machine system managing finite state transitions (Idle, HasMoney, Dispensing, OutOfStock) cleanly.",
        required_interfaces=["VendingMachine", "State"],
        rubric=[
            RubricCriterion("State Pattern", 0.40, "Encapsulate states in discrete collaborator classes."),
            RubricCriterion("Encapsulation", 0.30, "Prevent invalid state transitions (e.g. dispensing without funds)."),
            RubricCriterion("Extensibility", 0.30, "Allow adding new item selection or payment states without editing core machine loop.")
        ],
        starter_code="class VendingMachine:\n    pass\n"
    )
    prob_repo.save(vending_problem)

    # Build hybrid evaluation pipeline
    pipeline = HybridEvaluationPipeline(
        deterministic_rules=[ASTInterfaceValidationRule(), ClassSizeCouplingRule()],
        heuristic_rules=[LLMDesignReviewRule(MockLLMAdapter())]
    )

    return PracticePlatformService(prob_repo, att_repo, pipeline)


def run_cli_demo():
    print("===============================================================")
    print("       LLD PRACTICE PLATFORM PROTOTYPE DEMONSTRATION           ")
    print("===============================================================\n")

    service = setup_default_service()

    # Display Problem Catalog
    problems = service.list_problems()
    print(f"[*] Loaded Curated Problem Catalog ({len(problems)} problems available):")
    for p in problems:
        print(f"    - [{p.id}] {p.title} ({len(p.rubric)} Rubric Criteria)")

    # 1. Start Attempt 1 on parking-lot
    attempt = service.start_new_attempt("parking-lot")
    print(f"\n[Created] Attempt ID: {attempt.id} | Problem: {attempt.problem_id} (Version: v{attempt.version})")

    # 2. Learner writes and submits code (Attempt 1: Valid structure)
    learner_code = """
from abc import ABC, abstractmethod

class Vehicle(ABC):
    def __init__(self, license_plate: str):
        self.license_plate = license_plate

class ParkingSpot:
    def __init__(self, spot_id: str):
        self.spot_id = spot_id
        self.occupied = False

class IParkingStrategy(ABC):
    @abstractmethod
    def find_spot(self, spots):
        pass

class NearestFirstStrategy(IParkingStrategy):
    def find_spot(self, spots):
        return next((s for s in spots if not s.occupied), None)
"""
    payload = SubmissionPayload(
        source_code=learner_code,
        language="python",
        pattern_rationale="Used Strategy pattern for spot selection to decouple allocation logic.",
        tradeoffs_rationale="Omitted database persistence to focus on in-memory entity modeling."
    )

    print("\n[Submitting Attempt 1] Running hybrid evaluation pipeline...")
    completed_attempt = service.submit_and_evaluate(attempt.id, payload)

    # 3. View feedback
    feedback = completed_attempt.feedback
    print(f"\n[Status]: {completed_attempt.status.value}")
    print(f"[Score]: {feedback.overall_score}/10.0 (Execution time: {feedback.execution_time_ms}ms)")
    print("\n--- Detailed Rule Feedback ---")
    for critique in feedback.critiques:
        status_symbol = "PASS" if critique.passed else "WARN"
        print(f"[{status_symbol}] {critique.rule_name} (Score: {critique.score}/10.0)")
        print(f"      Summary: {critique.summary}")
        if critique.suggestions:
            for sug in critique.suggestions:
                print(f"      -> Suggestion: {sug}")

    # 4. Fork attempt for revision
    print("\n[Action] Forking attempt for revision v2...")
    v2_attempt = service.iterate_attempt(completed_attempt.id)
    print(f"[Created] Iteration Attempt ID: {v2_attempt.id} (Version: v{v2_attempt.version})")

    # Query history
    history = service.get_problem_history("parking-lot")
    print(f"[History Verified] Total attempts logged for 'parking-lot': {len(history)}")
    print("\n===============================================================")
    print("                     DEMO COMPLETED SUCCESSFULLY               ")
    print("===============================================================")


def start_server(port: int = 8080):
    service = setup_default_service()
    server = create_http_server(service, port=port)
    print(f"[*] LLD Practice Platform REST API server listening on http://localhost:{port}")
    print("[*] Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")


if __name__ == "__main__":
    import os
    env_port = os.environ.get("PORT")
    default_port = int(env_port) if env_port else 8080
    auto_server = bool(env_port)

    parser = argparse.ArgumentParser(description="LLD Practice Platform Engine")
    parser.add_argument("--server", action="store_true", default=auto_server, help="Run HTTP REST API server")
    parser.add_argument("--port", type=int, default=default_port, help="Port for REST API server (default: 8080 or $PORT)")
    args = parser.parse_args()

    if args.server or auto_server:
        start_server(args.port)
    else:
        run_cli_demo()
