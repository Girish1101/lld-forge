# LLD-Forge: Low-Level Design Practice & Evaluation Engine

[![GitHub Repo](https://img.shields.io/badge/GitHub-lld--forge-blue?logo=github)](https://github.com/Girish1101/lld-forge)
[![Tests Passing](https://img.shields.io/badge/Tests-15%2F15%20Passing-brightgreen)](https://github.com/Girish1101/lld-forge)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Girish1101/lld-forge)

A low-level design practice engine built in Python. Features a full **learner-facing web UI**, a hybrid evaluation pipeline combining deterministic AST structural validation with a rich multi-signal heuristic design reviewer, and per-learner attempt history.

> **GitHub Repository:** [https://github.com/Girish1101/lld-forge](https://github.com/Girish1101/lld-forge)

> **Offline Transcript & Specification Reference:**
> All original assignment brief requirements, design questions, class hierarchies, method signatures, and checkpoint handoff blocks are fully embedded in [`TRANSCRIPT_SPEC.md`](TRANSCRIPT_SPEC.md). Any AI assistant or evaluator can verify complete compliance offline without requiring external Google sign-in access.

## Features
* **Web UI (SPA):** Full interactive learner frontend — problem catalog → code editor → feedback panel → attempt history. Run `python main.py --server` and open `http://localhost:8080`.
* **Learner Identity:** Attempts are scoped to a `learner_id` (set in the UI header). History is filterable per-learner per-problem.
* **Contract-First Evaluation:** Verifies mandatory domain abstractions via AST static analysis before running heuristic checks.
* **Rich Heuristic Scoring:** `MockLLMAdapter` evaluates 10 independent design signals — abstract base classes, GoF patterns (Strategy, Factory, State, Observer), inheritance depth, docstring coverage, SRP naming proxies, rationale keyword richness, and class decomposition quality.
* **Resilient Evaluation Pipeline:** Fallback mechanisms preserve deterministic results if external LLM services time out or fail.
* **Attempt Versioning:** Supports iterative refinement with version lineage (`v1 → v2 → v3`), carrying `learner_id` across iterations.
* **HTTP REST API Controller:** Standalone REST API using Python standard library `http.server`.
* **Zero External Infrastructure:** Runs without external brokers or dependencies using standard Python 3.10+.

## Project Layout
```text
├── models.py            # Domain aggregates (Problem, Attempt, Feedback, Rubric)
├── rules.py             # ASTStructuralAnalyzer, Strategy rules, 10-signal MockLLMAdapter
├── engine.py            # HybridEvaluationPipeline orchestration & state machine
├── repositories.py      # Thread-safe in-memory repository contracts + list_by_learner_and_problem
├── service.py           # Application service coordinator + get_learner_history()
├── api.py               # HTTP REST API Controller + static file server (serves index.html)
├── main.py              # CLI demonstration runner & REST API server entrypoint
├── static/
│   └── index.html       # Full learner SPA (practice loop UI)
├── tests.py             # Unit, strategy, lifecycle, and API test suites (15 tests)
├── TRANSCRIPT_SPEC.md   # Offline transcript, assignment brief, & technical specification
├── RESEARCH.md          # Learner friction points, tool gap analysis, & product direction
├── DESIGN.md            # Architecture, domain models, pipeline strategy, & trade-offs
├── AI_USAGE.md          # AI usage reflection (4 key engineering decisions)
└── CHECKPOINTS.md       # Incremental checkpoint verification log (Sections 1.0 to 5.0)
```

## Running the Prototype

The prototype has no third-party package dependencies and runs on Python 3.10+.

### 1. Run the interactive Web UI + REST API Server:
```bash
python main.py --server --port 8080
```
Then open **http://localhost:8080** in your browser.

The learner practice loop:
1. **Choose a problem** from the catalog (Parking Lot, Elevator, Vending Machine)
2. **Write Python code** in the editor (starter code pre-loaded)
3. **Fill in rationale** — pattern choices and trade-offs
4. **Submit** → see score, per-rule critiques, and actionable suggestions
5. **Iterate** → fork to v2 and refine your design
6. **View history** → compare scores across versions, scoped to your learner ID

### 2. Run the CLI demo:
```bash
python main.py
```

### 3. Run the test suite:
```bash
python -m unittest tests.py -v
```

## REST API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serve learner SPA (index.html) |
| `GET` | `/api/problems` | List problem catalog (3 curated problems with rubrics) |
| `GET` | `/api/problems/<id>` | Get single problem detail |
| `POST` | `/api/attempts` | Start new attempt `{"problem_id": "...", "learner_id": "..."}` |
| `POST` | `/api/attempts/<id>/submit` | Submit code + rationale, run hybrid evaluation |
| `POST` | `/api/attempts/<id>/iterate` | Fork attempt into next version (carries learner_id) |
| `GET` | `/api/attempts/<id>` | Get attempt state and feedback |
| `GET` | `/api/history` | Learner-scoped history `?learner_id=<id>&problem_id=<id>` |
| `GET` | `/api/problems/<id>/history` | Global problem history |

## Limitations
* **In-Memory Storage:** Data resides in single-process memory repositories (`InMemoryProblemRepository`, `InMemoryAttemptRepository`). State is reset upon process restart (production would swap repositories for PostgreSQL/SQLite via `IProblemRepository` and `IAttemptRepository`).
* **Mock LLM Adapter:** Uses a 10-signal `MockLLMAdapter` to evaluate design quality deterministically without requiring paid API keys. Swap in a real LLM by implementing `ILLMAdapter` with any provider.
* **No Authentication / Authorization:** Uses a plain text `learner_id` field. Production would replace this with JWT auth or session tokens.
* **Fixed Timeout Budget:** Evaluation pipeline uses a global fixed execution timeout (8.0 seconds) rather than per-problem configurable time budgets.
