# AI Usage Reflection

This document details key architectural decisions made using AI assistants (ChatGPT, Claude, Gemini, Cursor) during the design of this prototype, strictly adhering to the "AI suggested → Action Taken → Engineering Rationale" format.

---

### Decision 1: Submission Format (Visual Diagrams vs. Code Skeletons + Rationale)
* **AI Suggested:** Use an integrated Mermaid.js diagram editor where the learner draws class diagrams, and have an LLM parse the raw Mermaid text.
* **Action Taken:** **Rejected.**
* **Engineering Rationale:** Parsing Mermaid markdown via an LLM introduces double non-determinism: an imprecise visual representation translated through probabilistic text inference. Using Python code skeletons allows exact, deterministic Abstract Syntax Tree (AST) validation for contracts, reducing the LLM's role strictly to qualitative architectural review.

---

### Decision 2: Static Analysis Approach (Regex Linting vs. AST Parsing)
* **AI Suggested:** Use regular expressions (`re.search(r'class (\w+)')`) to detect class definitions and method signatures.
* **Action Taken:** **Rejected.**
* **Engineering Rationale:** Regex parsing of source code is fragile against valid syntax variations (line breaks, type hints, multi-line signatures, docstrings). Using Python's native `ast` module (`ASTStructuralAnalyzer`) guarantees syntactically correct introspection of classes, inheritance topologies, and method counts.

---

### Decision 3: Pipeline Failure Modes & Error Handling (Hard Fail vs. Graceful Degradation)
* **AI Suggested:** Block the submission call until both static checks and the LLM response return, throwing an unhandled error or failing the attempt completely if the LLM API times out.
* **Action Taken:** **Modified (Partially Rejected).**
* **Engineering Rationale:** Maintained fast-failing for unparseable Python syntax errors (preventing token waste), but implemented graceful degradation for LLM API timeouts or 5xx faults. If the LLM service fails or times out, the attempt still transitions to `COMPLETED` with valid deterministic static feedback preserved and a clear warning attached.

---

### Decision 4: Attempt History & Lineage Model (Overwrite vs. Explicit Version Forking)
* **AI Suggested:** Overwrite the current attempt record on every re-submission to keep the storage schema simple.
* **Action Taken:** **Rejected.**
* **Engineering Rationale:** Overwriting attempt records eliminates historical progress tracking, making it impossible to evaluate learner improvement over time. Implemented an explicit `create_next_version()` factory method on `Attempt` to maintain version lineage (`v1 -> v2 -> v3`), enabling delta comparisons across submission iterations.
