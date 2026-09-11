# LLD Practice Platform - Self-Contained Shared Conversation & Full Technical Specification

> **Note for AI Assistants & Reviewers:**
> This document is a complete, self-contained, offline transcript and specification of the LLD Practice Platform 2-Day Engineering Assignment created during the Gemini session (`https://share.gemini.google/hYFVdWHjin0g`). It contains all original requirements, design questions, class hierarchies, method signatures, strategy patterns, state machines, test suites, and checkpoint handoff blocks so that any system or LLM can verify full compliance without needing external Google sign-in credentials.

---

## Part 1: Handoff Protocol & Checkpoint System Rules

### Managing Large Tasks Across AIs
To hand off work across multiple AI sessions without repeating content or losing context, the project uses an **Incremental Master Outline & Checkpoint Protocol**:

1. **Rigid Structure:** An exhaustive, numbered skeleton of the entire project is defined upfront.
2. **Checkpoint Block:** Every handoff includes a structured status block:
```text
[PROJECT HANDOFF CHECKPOINT]
Project Title: LLD Practice Platform - 2-Day Engineering MVP
Master Outline: Sections 1.0 through 5.4

--- CURRENT STATUS ---
Completed Sections:
- [Section X.X Name] (Done)

Last Generated Ending:
"...last 2-3 sentences of previous section..."

--- YOUR TASK ---
1. Pick up exactly at Section [Y.Y Name].
2. Output an updated [PROJECT HANDOFF CHECKPOINT] when done.
```
3. **Overlap Anchor:** Pastes the final 2-3 sentences of previous output into the handoff prompt to maintain seamless context stitching.

---

## Part 2: LLD Practice Platform 2-Day Engineering Assignment Brief

### 1. Challenge & Background
Design and build a small practice experience that helps a learner practice Low-Level Design (LLD), submit a solution, and receive useful, explainable feedback.
LLD practice is easy to start but difficult to evaluate. A learner can design a Parking Lot, Elevator, or Vending Machine and still be unsure whether the responsibilities, abstractions, relationships, and trade-offs are actually good.

### 2. Practice Loop Journey
`Choose problem → Think / design → Submit → Get feedback → Review → Try again`

### 3. MVP Expected Outcomes
* **Problem:** A small set of LLD problems with clear requirements and enough context to attempt them.
* **Practice:** A learner can start an attempt and work on a solution (Interface-driven code + design rationale).
* **Submission:** Learner submits a solution and views status (`DRAFT` -> `SUBMITTED` -> `EVALUATING` -> `COMPLETED`/`FAILED`).
* **Feedback:** Platform provides useful, criterion-based feedback combining deterministic static checks and heuristic design reviews.
* **History:** Learner can view previous attempts (`v1`, `v2`, `v3`) to support revision and progress tracking.
* **Core Design:** Domain behavior represented with clear classes, interfaces, and responsibilities.

### 4. Main Design Questions (All 5 Questions Answered)
1. *What does a learner actually need to provide for an LLD practice attempt to be meaningful?* (`SubmissionPayload` with code + rationale).
2. *What makes feedback useful when there can be more than one valid LLD solution?* (Criterion-based rubrics rather than canonical matching).
3. *Which parts of evaluation should be deterministic, and which parts benefit from an LLM?* (Deterministic AST checks vs qualitative LLM reviews).
4. *How would your design accommodate another evaluation approach or another submission format later?* (Composite Strategy Pattern rules & payload extension points).
5. *What should happen if evaluation takes time or fails?* (Fast-fail on syntax errors, bounded execution timeout, graceful degradation to partial feedback on LLM timeouts/errors).

### 5. Scope Boundary
Focus strictly on LLD/domain-design concerns (classes, objects, responsibilities, interfaces, behavior, relationships, patterns, extensibility). Avoid microservices, Kafka/Celery, Kubernetes, or multi-region HLD infrastructure.

### 6. Deliverable List
* **Research Note (`RESEARCH.md`):** Learner problem, existing tools, gaps, product direction.
* **Design Note (`DESIGN.md`):** MVP overview, user flow, key classes/interfaces, evaluation approach, 5 design questions answered, submission format choice rationale, trade-offs.
* **Working Prototype (`models.py`, `rules.py`, `engine.py`, `repositories.py`, `service.py`, `api.py`, `main.py`):** End-to-end flow from problem selection to feedback and attempt history.
* **Tests (`tests.py`):** Unit, strategy, lifecycle, and HTTP REST API controller test suites.
* **README.md + AI_USAGE.md:** Setup guide, project layout, limitations, and 4 AI usage decisions (`AI suggested → Action Taken → Engineering Rationale`).

---

## Part 3: Verbatim Checkpoint Section Executions (1.0 to 5.0)

### Section 1.0: Problem Research & MVP Scope
* **1.1 Learner Friction Points:** Ambiguous problem definitions, "One True Solution" fallacy, feedback void, superficial chatbot reviews.
* **1.2 Scope Inclusions:** Curated catalog (`parking-lot`, `elevator-system`, `vending-machine`), hybrid evaluator, attempt versioning, failure resiliency.
* **1.3 Submission Payload Schema:**
```json
{
  "problemId": "parking-lot",
  "attemptId": "att_9f83a21b",
  "sourceCode": {
    "language": "python",
    "files": [{"filename": "models.py", "content": "class Vehicle: pass"}]
  },
  "rationale": {
    "patternChoices": "Used Strategy Pattern for parking allocation to decouple LotController.",
    "tradeOffsConsidered": "Omitted persistent DB in favor of in-memory thread-safe registry."
  }
}
```

### Section 2.0: Core Low-Level Domain Design Specifications
* **Domain Aggregate Classes (`models.py`):**
  - `AttemptStatus(Enum)`: `DRAFT`, `SUBMITTED`, `EVALUATING`, `COMPLETED`, `FAILED`.
  - `RubricCriterion(frozen)`: `name: str`, `weight: float`, `description: str`.
  - `Problem(frozen)`: `id: str`, `title: str`, `description: str`, `required_interfaces: List[str]`, `rubric: List[RubricCriterion]`, `starter_code: str`.
  - `SubmissionPayload(frozen)`: `source_code: str`, `language: str`, `pattern_rationale: str`, `tradeoffs_rationale: str`.
  - `EvaluationCritique(frozen)`: `rule_name: str`, `passed: bool`, `score: float`, `summary: str`, `suggestions: List[str]`.
  - `EvaluationFeedback`: `overall_score: float`, `deterministic_passed: bool`, `critiques: List[EvaluationCritique]`, `evaluated_at: datetime`, `execution_time_ms: int`, `failure_reason: Optional[str]`.
  - `Attempt`: `id: str`, `problem_id: str`, `version: int`, `status: AttemptStatus`, `submission: Optional[SubmissionPayload]`, `feedback: Optional[EvaluationFeedback]`.
    - Methods: `submit(payload)`, `mark_evaluating()`, `mark_completed(feedback)`, `mark_failed(reason)`, `create_next_version(new_attempt_id)`.
* **Evaluator Strategy Interfaces & Rules (`rules.py`):**
  - `ASTStructuralAnalyzer`: `extract_declared_classes(code)`, `inspect_inheritance(code)`, `detect_monolithic_classes(code, max_methods=8)`.
  - `IDeterministicRule(ABC)`: `evaluate(problem, submission) -> EvaluationCritique`.
  - `IHeuristicRule(ABC)`: `evaluate(problem, submission) -> EvaluationCritique`.
  - `ILLMAdapter(ABC)`: `analyze_design(problem_description, code, rationale) -> Dict[str, Any]`.
  - `ASTInterfaceValidationRule(IDeterministicRule)`: Checks syntax parsing and presence of `problem.required_interfaces`.
  - `ClassSizeCouplingRule(IDeterministicRule)`: Flags classes with >10 methods as God Objects.
  - `MockLLMAdapter(ILLMAdapter)`: Simulates qualitative design reviews deterministically.
  - `StructuredPromptBuilder`: Builds structured JSON prompts for LLM evaluation.
  - `LLMDesignReviewRule(IHeuristicRule)`: Strategy wrapping `ILLMAdapter`.
* **Hybrid Evaluation Engine (`engine.py`):**
  - `HybridEvaluationPipeline`: Runs static deterministic rules first (fast-fails on syntax errors), then runs heuristic LLM rules within `timeout_seconds=8.0`, gracefully degrading if LLM API times out or fails.

### Section 3.0: Implementation, Repositories, Services & Controllers
* **Repository Contracts & In-Memory Implementations (`repositories.py`):**
  - `IProblemRepository`: `get_by_id`, `list_all`, `save`.
  - `IAttemptRepository`: `get_by_id`, `list_by_problem`, `save`.
  - `InMemoryProblemRepository`, `InMemoryAttemptRepository`: Thread-safe using `threading.Lock()`.
* **Application Service (`service.py`):**
  - `PracticePlatformService`: `list_problems()`, `get_problem()`, `get_attempt()`, `get_problem_history()`, `start_new_attempt()`, `submit_and_evaluate()`, `iterate_attempt()`.
* **REST API Controller (`api.py`):**
  - `LLDPracticeHTTPHandler(BaseHTTPRequestHandler)`: REST API endpoints for `/api/problems`, `/api/attempts`, `/api/attempts/<id>/submit`, `/api/attempts/<id>/iterate`, `/api/problems/<id>/history`.
* **CLI Demonstration & Entrypoint (`main.py`):**
  - Seeds 3 curated problems (`parking-lot`, `elevator-system`, `vending-machine`).
  - `run_cli_demo()`: Runs interactive end-to-end demonstration.
  - `--server --port 8080`: Launches HTTP REST API server.

### Section 4.0: Verification & Test Suite Specifications (`tests.py`)
* `TestAttemptDomainTransitions`: Tests attempt lifecycle state machine, invalid state guards, and version incrementing (`v1 -> v2`).
* `TestEvaluationPipelineStrategies`: Tests `ASTStructuralAnalyzer` helper, syntax parse failure fast-failing, missing interface detection, God Object detection, and LLM degradation fallback.
* `TestEndToEndAttemptLifecycle`: Integration test verifying 3 seeded problems existence, initial submission, revision forking (`v1 -> v2`), passing resubmission, and multi-version history tracking.
* `TestRESTAPIController`: Integration tests for HTTP REST API endpoints (`GET /api/problems`, `POST /api/attempts`, `POST /api/attempts/<id>/submit`, `POST /api/attempts/<id>/iterate`, `GET /api/problems/<id>/history`).

### Section 5.0: Documentation Deliverables
* `RESEARCH.md`: Research note detailing learner friction points, tool gaps, and product direction.
* `DESIGN.md`: Architecture note including explicit 5 "Design Questions Answered" section, submission format rationale, and trade-off decisions.
* `AI_USAGE.md`: Reflection detailing 4 decisions in `AI Suggested -> Action Taken -> Engineering Rationale` format.
* `README.md`: Quickstart guide, REST API endpoints, CLI usage, and explicit "Limitations" section.
* `CHECKPOINTS.md`: Checkpoint verification log.

---
*End of Transcript & Specification.*
