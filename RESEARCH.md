# Research Note: Low-Level Design Practice — Learner Gaps & Product Direction

## 1. The Learner Problem

Low-Level Design (LLD) sits between algorithmic problem-solving and high-level system architecture. In technical interviews and professional growth, it measures how an engineer thinks about **object modelling**, **responsibility boundaries**, **side-effect isolation**, and **extensibility trade-offs** — not just whether code runs.

The core learner friction point is a feedback vacuum. Unlike algorithmic problems (where test cases provide binary pass/fail signals in seconds), an LLD submission produces a class diagram or code skeleton that could be valid in several different ways. Without a knowledgeable reviewer, a learner cannot distinguish:

- A deliberate design decision from an accidental one
- Appropriate coupling from avoidable coupling
- A valid alternative pattern from a fundamentally flawed abstraction

The result: learners repeatedly produce solutions without ever understanding **why** one design is preferable to another, and they cannot self-diagnose.

---

## 2. Existing Approaches & Gaps

### 2.1 Canonical Blog Posts & Video Tutorials
*(e.g., GeeksForGeeks "Design a Parking Lot", YouTube interview prep channels)*

| Mechanism | Gap |
|-----------|-----|
| Walkthrough of a single reference solution to canonical prompts (Parking Lot, Chess, ATM) | Promotes a **single "correct" answer**. Fails to teach evaluation of alternatives (e.g., Strategy vs. State vs. conditional table). Learner cannot verify whether their divergence is valid or flawed. |

### 2.2 Unconstrained AI Chatbots (ChatGPT, Claude, Gemini)
*(Learner pastes arbitrary class definitions and asks "is my design good?")*

| Mechanism | Gap |
|-----------|-----|
| Free-form conversational critique | Unbounded **sycophancy** ("Great design! Very clean."). No structured rubric. Hallucinates requirements not in the problem. Cannot track improvement across attempts. No enforcement of baseline domain contracts. |

### 2.3 UML / Diagramming Tools (Mermaid, PlantUML, Excalidraw, Lucidchart)
*(Learner draws class diagrams manually)*

| Mechanism | Gap |
|-----------|-----|
| Free-form visual structure capture | **No semantic validation** of domain contracts or design trade-offs. Tools cannot tell whether an arrow represents valid inheritance or a misapplied association. No feedback on SOLID violations. |

### 2.4 Competitive Coding Platforms (LeetCode, HackerRank, AlgoExpert)
*(Some offer "OOP Design" question categories)*

| Mechanism | Gap |
|-----------|-----|
| Curated problem sets, community solutions, video editorial | OOP design problems on these platforms are typically evaluated via hand-rolled test cases, not design quality metrics. There is **no rubric for coupling, cohesion, or extensibility**. "Passing" a test is not equivalent to "good design." |

### 2.5 Structurizr / Architecture Review Tools
*(Enterprise architecture tools for C4/arc42 diagrams)*

| Mechanism | Gap |
|-----------|-----|
| Formal modelling languages for architecture | Designed for enterprise HLD/system context diagrams, not object-level design review. Overkill and inaccessible for individual learner practice. No feedback engine. |

---

## 3. Key Gaps Identified

1. **No machine-verifiable baseline contracts.** Existing tools cannot confirm that a submission actually declares the domain abstractions required by a problem (e.g., `IParkingStrategy`, `State`).
2. **Feedback is not rubric-driven.** Neither AI chatbots nor diagramming tools evaluate submissions against consistent, weighted criteria (SRP, extensibility, coupling thresholds).
3. **No iterative progress tracking.** Learners have no way to see whether their v2 design improved over v1 on specific dimensions.
4. **No rationale requirement.** Without forcing a learner to explain *why* they chose a pattern, it is impossible to distinguish a deliberate architectural decision from accidental code structure.
5. **Feedback latency.** Getting human expert feedback on an LLD submission requires scheduling a mock interview — a high-friction, low-frequency process.

---

## 4. Product Direction

The MVP implements a **Contract-First, Hybrid Evaluation Practice Engine** addressing all five gaps:

1. **Bounded Problem Contracts.** Each problem defines explicit required interfaces/classes (e.g., `Vehicle`, `ParkingSpot`, `IParkingStrategy`). The evaluator verifies these deterministically via Python AST before any qualitative review runs.
2. **Hybrid Evaluation Pipeline.** A two-stage pipeline runs fast deterministic AST checks (syntax, required abstractions, God Object detection) before invoking a multi-signal heuristic scorer that evaluates 10 design dimensions (abstraction depth, GoF patterns, SRP proxies, rationale quality, class decomposition).
3. **Mandatory Design Rationale.** Submissions require `pattern_rationale` and `tradeoffs_rationale` text. The evaluator analyses keyword richness, SOLID vocabulary density, and length — penalising empty or vague rationales.
4. **Versioned Attempt History.** Every submission is a version (`v1`, `v2`, …) on an attempt lineage. Learners can compare scores across iterations and see whether a refactor improved or regressed specific design criteria.
5. **Resilient Evaluation.** If the heuristic evaluator is unavailable (timeout, API error), deterministic checks remain valid and are returned — the learner is never left with a broken, orphaned submission.

### Product Hypothesis
> A learner who receives **criterion-specific, rubric-driven feedback tied to their own rationale** — rather than a generic score or a single reference solution — will develop stronger design intuition faster, because they can trace each critique back to a specific structural choice they made.
