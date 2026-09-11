import ast
from abc import ABC, abstractmethod
from typing import Dict, List, Set, Any, Optional
from models import Problem, SubmissionPayload, EvaluationCritique


class ASTStructuralAnalyzer:
    """Static utility inspecting Python code structure via standard library AST."""
    @staticmethod
    def extract_declared_classes(source_code: str) -> Set[str]:
        try:
            tree = ast.parse(source_code)
            return {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        except SyntaxError:
            return set()

    @staticmethod
    def inspect_inheritance(source_code: str) -> Dict[str, List[str]]:
        """Maps declared class names to their base class names."""
        try:
            tree = ast.parse(source_code)
            inheritance_map = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    bases = [base.id for base in node.bases if isinstance(base, ast.Name)]
                    inheritance_map[node.name] = bases
            return inheritance_map
        except SyntaxError:
            return {}

    @staticmethod
    def detect_monolithic_classes(source_code: str, max_methods: int = 8) -> List[str]:
        """Detects classes exceeding method count thresholds (God Object antipattern)."""
        try:
            tree = ast.parse(source_code)
            monoliths = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    if len(methods) > max_methods:
                        monoliths.append(node.name)
            return monoliths
        except SyntaxError:
            return []


class IDeterministicRule(ABC):
    """Executes fast, zero-cost structural/syntax analysis."""
    @abstractmethod
    def evaluate(self, problem: Problem, submission: SubmissionPayload) -> EvaluationCritique:
        pass


class IHeuristicRule(ABC):
    """Executes cognitive analysis (LLM or rule-based inference)."""
    @abstractmethod
    def evaluate(self, problem: Problem, submission: SubmissionPayload) -> EvaluationCritique:
        pass


class ILLMAdapter(ABC):
    """Interface for LLM provider adapters."""
    @abstractmethod
    def analyze_design(self, problem_description: str, code: str, rationale: str) -> Dict[str, Any]:
        pass


class ASTInterfaceValidationRule(IDeterministicRule):
    """Verifies all mandatory domain interfaces/classes are declared in the code."""
    def evaluate(self, problem: Problem, submission: SubmissionPayload) -> EvaluationCritique:
        try:
            ast.parse(submission.source_code)
        except SyntaxError as e:
            return EvaluationCritique(
                rule_name="Syntax & Parse Validation",
                passed=False,
                score=0.0,
                summary=f"Code failed to parse: {str(e)}",
                suggestions=["Fix Python syntax errors before architectural review."]
            )

        declared_classes = ASTStructuralAnalyzer.extract_declared_classes(submission.source_code)
        missing = set(problem.required_interfaces) - declared_classes

        if missing:
            return EvaluationCritique(
                rule_name="Required Abstractions Check",
                passed=False,
                score=max(0.0, 10.0 - (len(missing) * 3.0)),
                summary=f"Missing essential domain contracts: {', '.join(sorted(list(missing)))}",
                suggestions=[f"Implement the '{name}' class or interface as specified." for name in sorted(list(missing))]
            )

        return EvaluationCritique(
            rule_name="Required Abstractions Check",
            passed=True,
            score=10.0,
            summary="All required domain interfaces and classes are present.",
            suggestions=[]
        )


class ClassSizeCouplingRule(IDeterministicRule):
    """Catches 'God Object' antipatterns via method/line-count thresholds."""
    def evaluate(self, problem: Problem, submission: SubmissionPayload) -> EvaluationCritique:
        monoliths = ASTStructuralAnalyzer.detect_monolithic_classes(submission.source_code, max_methods=10)

        if monoliths:
            return EvaluationCritique(
                rule_name="Class Cohesion & SRP Check",
                passed=False,
                score=5.0,
                summary=f"High method count detected in: {monoliths}.",
                suggestions=["Decompose large classes with >10 methods into smaller collaborators."]
            )

        return EvaluationCritique(
            rule_name="Class Cohesion & SRP Check",
            passed=True,
            score=10.0,
            summary="Class sizes align with Single Responsibility guidelines.",
            suggestions=[]
        )


class MockLLMAdapter(ILLMAdapter):
    """
    Rich multi-signal heuristic adapter for offline / CI environments.
    Scores 10 independent design signals across SOLID principles,
    GoF patterns, coupling metrics, and rationale quality.
    """
    def analyze_design(self, problem_description: str, code: str, rationale: str) -> Dict[str, Any]:
        signals: list[tuple[float, str]] = []  # (score_contribution, suggestion)
        suggestions: list[str] = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"score": 0.0, "critique": "Code could not be parsed.", "actionable_suggestions": ["Fix syntax errors first."]}

        class_nodes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        all_methods: list[ast.FunctionDef] = []
        for cls in class_nodes:
            all_methods += [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

        # Signal 1: Has abstract base classes (Interface Segregation / abstraction)
        has_abc = any(
            any(isinstance(b, ast.Name) and b.id in ("ABC", "ABCMeta") for b in cls.bases)
            for cls in class_nodes
        )
        if has_abc:
            signals.append((1.5, ""))
        else:
            suggestions.append("Introduce abstract base classes (ABC) to define explicit domain contracts.")
            signals.append((0.0, ""))

        # Signal 2: Strategy Pattern (composition + callable strategy)
        has_strategy = "Strategy" in code or "strategy" in rationale.lower() or "IDispatch" in code or "IPark" in code
        if has_strategy:
            signals.append((1.2, ""))
        else:
            suggestions.append("Consider a Strategy interface to decouple variable algorithms (e.g., allocation, dispatch).")
            signals.append((0.5, ""))

        # Signal 3: Factory Pattern
        has_factory = "Factory" in code or "factory" in rationale.lower() or "create_" in code
        if has_factory:
            signals.append((0.8, ""))
        else:
            suggestions.append("Apply a Factory Method to centralise object creation and decouple construction from use.")
            signals.append((0.3, ""))

        # Signal 4: State Pattern keywords
        has_state = "State" in code or "state" in rationale.lower() or "transition" in rationale.lower()
        if has_state:
            signals.append((0.8, ""))
        else:
            suggestions.append("Encapsulate distinct lifecycle states into dedicated State classes to prevent conditional bloat.")
            signals.append((0.2, ""))

        # Signal 5: Observer Pattern
        has_observer = any(kw in code for kw in ("Observer", "Listener", "subscribe", "notify", "publish"))
        if has_observer:
            signals.append((0.5, ""))
        else:
            signals.append((0.2, ""))

        # Signal 6: Inheritance depth — penalise deep chains (>2 levels)
        base_classes = {cls.name for cls in class_nodes}
        deep_classes = []
        for cls in class_nodes:
            depth = 0
            current_bases = [b.id for b in cls.bases if isinstance(b, ast.Name)]
            while any(b in base_classes for b in current_bases):
                depth += 1
                new_bases = []
                for b in current_bases:
                    for c in class_nodes:
                        if c.name == b:
                            new_bases += [x.id for x in c.bases if isinstance(x, ast.Name)]
                current_bases = new_bases
                if depth > 5:
                    break
            if depth > 2:
                deep_classes.append(cls.name)
        if deep_classes:
            signals.append((0.3, ""))
            suggestions.append(f"Deep inheritance detected in {deep_classes}. Prefer composition over inheritance.")
        else:
            signals.append((0.8, ""))

        # Signal 7: Presence of docstrings on classes
        documented_classes = sum(
            1 for cls in class_nodes
            if cls.body and isinstance(cls.body[0], ast.Expr) and isinstance(cls.body[0].value, ast.Constant)
        )
        doc_ratio = documented_classes / max(len(class_nodes), 1)
        if doc_ratio >= 0.5:
            signals.append((0.6, ""))
        else:
            signals.append((0.2, ""))
            suggestions.append("Add docstrings to primary domain classes to clarify their responsibilities.")

        # Signal 8: SRP proxy — no class name containing 'Manager' doing everything
        god_names = [cls.name for cls in class_nodes if any(w in cls.name for w in ("Manager", "Handler", "Util", "Helper"))]
        if god_names:
            signals.append((0.4, ""))
            suggestions.append(f"Avoid ambiguous class names like {god_names}; name classes after their single cohesive responsibility.")
        else:
            signals.append((0.8, ""))

        # Signal 9: Design rationale quality (length + keyword richness)
        rationale_combined = (rationale or "").lower()
        design_keywords = ["solid", "srp", "open", "closed", "pattern", "decouple", "cohesion", "coupling",
                           "abstraction", "encapsul", "interface", "polymorphi", "trade"]
        keyword_hits = sum(1 for kw in design_keywords if kw in rationale_combined)
        rationale_score = min(1.0, len(rationale_combined) / 200) * 0.5 + min(1.0, keyword_hits / 4) * 0.5
        signals.append((rationale_score * 1.0, ""))
        if keyword_hits < 2:
            suggestions.append("Enrich your design rationale — explain SOLID principles, coupling trade-offs, and pattern selection rationale explicitly.")

        # Signal 10: Number of classes — reward decomposition, penalise monolith or over-engineering
        n_classes = len(class_nodes)
        if n_classes == 0:
            signals.append((0.0, ""))
            suggestions.append("Define at least one domain class before submitting.")
        elif 2 <= n_classes <= 10:
            signals.append((1.0, ""))
        elif n_classes > 10:
            signals.append((0.6, ""))
            suggestions.append("Many classes detected. Ensure each has a single clear responsibility; avoid over-engineering.")
        else:  # 1 class
            signals.append((0.4, ""))
            suggestions.append("Consider decomposing into multiple collaborating classes to model distinct domain concepts.")

        raw_total = sum(s for s, _ in signals)
        max_possible = 1.5 + 1.2 + 0.8 + 0.8 + 0.5 + 0.8 + 0.6 + 0.8 + 1.0 + 1.0
        normalised = round((raw_total / max_possible) * 10.0, 2)
        score = max(0.0, min(10.0, normalised))

        if score >= 8.0:
            critique = "Strong design: good abstraction boundaries, clear responsibilities, and deliberate pattern usage."
        elif score >= 6.0:
            critique = "Solid foundation with identifiable domain entities. Some coupling or responsibility gaps remain."
        elif score >= 4.0:
            critique = "Partial design: core entities present but abstractions are underspecified or responsibilities blurred."
        else:
            critique = "Design needs significant restructuring: missing abstractions, high coupling, or insufficient decomposition."

        return {
            "score": score,
            "critique": critique,
            "actionable_suggestions": suggestions if suggestions else ["Architecture meets primary SOLID criteria — consider edge cases and extensibility."],
        }


class StructuredPromptBuilder:
    @staticmethod
    def build_prompt(problem_description: str, code: str, rationale: str) -> str:
        return f"""You are an expert Low-Level System Design Evaluator.
Analyze the user's code and design rationale against the problem description.

Problem Context:
{problem_description}

Learner Code:
{code}

Learner Rationale:
{rationale}

Respond STRICTLY with valid JSON following this schema:
{{
  "score": <float between 0.0 and 10.0>,
  "critique": "<concise structural critique focusing on SOLID principles and coupling>",
  "actionable_suggestions": ["<suggestion 1>", "<suggestion 2>"]
}}
"""


class LLMDesignReviewRule(IHeuristicRule):
    """Queries an LLM provider adapter to evaluate design trade-offs and rationale."""
    def __init__(self, llm_adapter: ILLMAdapter):
        self.llm_adapter = llm_adapter

    def evaluate(self, problem: Problem, submission: SubmissionPayload) -> EvaluationCritique:
        result = self.llm_adapter.analyze_design(
            problem_description=problem.description,
            code=submission.source_code,
            rationale=submission.pattern_rationale
        )
        return EvaluationCritique(
            rule_name="LLM Heuristic Design & SOLID Review",
            passed=result["score"] >= 6.0,
            score=result["score"],
            summary=result["critique"],
            suggestions=result.get("actionable_suggestions", [])
        )
