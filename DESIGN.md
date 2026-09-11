# Design Note: Architecture, Domain Modeling, & Key Trade-Offs

## 1. Domain Entities & Responsibilities
The domain model prioritizes clean separation of concerns and deterministic state transitions:
* `Problem`: Read-only aggregate root defining required interfaces, grading rubrics, and starter code.
* `Attempt`: Mutable aggregate root managing the learner's journey (`DRAFT` -> `SUBMITTED` -> `EVALUATING` -> `COMPLETED`/`FAILED`). Handles version forking (`v1 -> v2`).
* `SubmissionPayload`: Immutable value object capturing source code and the learner's design rationale text (`pattern_rationale` and `tradeoffs_rationale`).
* `EvaluationFeedback`: Structured feedback containing individual rule critiques, execution metrics, and an overall weighted score.

## 2. Explicit Decision: Submission Format Selection
* **Named Decision:** Python Source Code + Text Rationale (`SubmissionPayload`).
* **Selected Choice Rationale:** Code-only (Python) submissions were chosen over visual diagrams or mixed canvas formats because code allows exact, machine-parseable Abstract Syntax Tree (AST) validation of domain contracts, class sizes, and inheritance topologies before calling qualitative LLMs. Visual diagrams introduce parsing ambiguities and require unreliable OCR/vision models.
* **Documented Future Extension Point:** The system can accommodate visual diagrams or mixed formats in future iterations by defining alternative payload schemas (e.g., `DiagramSubmissionPayload`) and adding specialized rule implementations (e.g., a Mermaid diagram AST parser) without altering the core `HybridEvaluationPipeline` or `Attempt` aggregate.

## 3. Extensible Evaluation Pipeline (Strategy Pattern)
The evaluation engine decouples rule execution via composite strategies:
* `IDeterministicRule`: Zero-cost static checks executing Python AST parsing (e.g., `ASTInterfaceValidationRule`, `ClassSizeCouplingRule` leveraging `ASTStructuralAnalyzer`). Fails fast on syntax errors before downstream steps run.
* `IHeuristicRule`: Evaluates subjective criteria (SOLID adherence, trade-offs, coupling). Implemented via `LLMDesignReviewRule`, which consumes an `ILLMAdapter`.

Adding a new evaluation rule (e.g., a linter, type checker, or PlantUML generator) requires implementing `IDeterministicRule` or `IHeuristicRule` and registering it with `HybridEvaluationPipeline` without changing core orchestrator logic.

## 4. Design Questions Answered

### Question 1: What does a learner actually need to provide for an LLD practice attempt to be meaningful?
A learner must provide a **`SubmissionPayload` combining code implementation and explicit design rationale text**. Code alone does not reveal whether a pattern was chosen deliberately or by accident. The mandatory rationale block (`pattern_rationale` and `tradeoffs_rationale`) forces the learner to articulate their architectural choices (e.g., "Used Strategy Pattern for parking allocation to decouple LotController"), enabling the evaluator to compare intended design against actual code topology.

### Question 2: What makes feedback useful when there can be more than one valid LLD solution?
Feedback must be **criterion-based and rubric-driven rather than binary "pass/fail" or single canonical matching**. Low-Level Design inherently has multiple valid object topologies (e.g., Strategy Pattern vs. State Pattern vs. Rule Engine). The platform evaluates submissions against foundational design principles (Single Responsibility, Interface Segregation, Encapsulation, Cohesion) using structured rubrics, highlighting specific trade-offs rather than forcing a single rigid reference implementation.

### Question 3: Which parts of evaluation should be deterministic, and which parts benefit from an LLM?
* **Deterministic Checks (Python AST):** Syntax validation, verification of mandatory domain interfaces/classes (`ASTInterfaceValidationRule`), and God Object / class size threshold detection (`ClassSizeCouplingRule`). These checks are 100% deterministic, instant, and zero-cost, halting execution early on invalid syntax to prevent token waste.
* **LLM / Heuristic Review:** Qualitative analysis of pattern trade-offs, SOLID principle adherence, coupling subtlety, and alignment between stated rationale and code implementation (`LLMDesignReviewRule`). The LLM operates strictly within a bounded JSON schema.

### Question 4: How would your design accommodate another evaluation approach or another submission format later?
* **Adding Evaluation Rules:** Implement `IDeterministicRule` or `IHeuristicRule` and register the instance into `HybridEvaluationPipeline` (Open/Closed Principle). Core orchestration logic remains unchanged.
* **Adding Submission Formats:** Expand `SubmissionPayload` or introduce sub-types (e.g., `DiagramSubmissionPayload`). Rules inspect the payload type and execute specialized analyzers (e.g., a Mermaid diagram parser rule implementing `IDeterministicRule`).

### Question 5: What should happen if evaluation takes time or fails?
The evaluation pipeline implements a **resilient state machine with fast-failing and graceful degradation**:
1. **Syntax Failures (Fast Fail):** If Python code contains syntax parsing errors, the pipeline immediately halts at Step 1 (`IDeterministicRule`), setting status to `FAILED` with score `0.0`. It does NOT invoke or bill downstream LLM rules.
2. **Execution Time Budget & Timeouts:** The pipeline enforces a bounded timeout budget (`timeout_seconds=8.0`). If heuristic evaluation exceeds this budget, the pipeline logs a timeout critique and proceeds.
3. **Graceful LLM Degradation:** If an external LLM provider times out, returns malformed JSON, or throws HTTP 5xx errors, the pipeline catches the exception, attaches a warning critique ("LLM Evaluator Unavailable"), and completes the attempt with full deterministic AST feedback intact rather than blocking or corrupting the learner's attempt.

## 5. Key Design Trade-Offs & Decisions

| Decision | Selected Approach | Alternative Rejected | Rationale |
| :--- | :--- | :--- | :--- |
| **Submission Input** | Code Skeletons + Rationale Text | Visual UML / Diagramming | AST analysis on code is deterministic, testable, and machine-parseable. Pure diagrams introduce parsing ambiguities. |
| **System Boundary** | In-Memory / Monolithic Thread-Safe Repos | Microservices + Message Broker (Celery/RabbitMQ) | Keeps focus on object-oriented domain design rather than distributed systems infrastructure, fitting the 2-day timeline. |
| **LLM Resilience** | Bounded Execution + Degraded Fallback | Unbounded Retries / Blocking Calls | Prevents orphaned `EVALUATING` states. If the LLM times out, deterministic feedback is returned rather than failing the attempt. |
