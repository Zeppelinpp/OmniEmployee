#!/usr/bin/env python3
"""Generate experiment code to validate a hypothesis."""

import argparse
import sys
from pathlib import Path


EXPERIMENT_TEMPLATES = {
    "performance": '''#!/usr/bin/env python3
"""Performance experiment: {hypothesis}"""

import time
import statistics
from typing import Callable, Any


def benchmark(func: Callable, iterations: int = {iterations}, warmup: int = 3) -> dict:
    """Benchmark a function's performance."""
    # Warmup runs
    for _ in range(warmup):
        func()
    
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    
    return {{
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "stdev": statistics.stdev(times) if len(times) > 1 else 0,
        "min": min(times),
        "max": max(times),
        "total_runs": iterations
    }}


def format_results(name: str, results: dict) -> str:
    """Format benchmark results."""
    return f"""
{{name}}:
  Mean:   {{results['mean']*1000:.3f}} ms
  Median: {{results['median']*1000:.3f}} ms
  Stdev:  {{results['stdev']*1000:.3f}} ms
  Min:    {{results['min']*1000:.3f}} ms
  Max:    {{results['max']*1000:.3f}} ms
"""


# TODO: Implement your test functions here
def approach_a():
    """First approach to test."""
    # Replace with actual implementation
    pass


def approach_b():
    """Second approach to test."""
    # Replace with actual implementation
    pass


def main():
    print("=" * 60)
    print("EXPERIMENT: {hypothesis}")
    print("=" * 60)
    print()
    
    print("Running benchmarks...")
    print()
    
    results_a = benchmark(approach_a)
    results_b = benchmark(approach_b)
    
    print(format_results("Approach A", results_a))
    print(format_results("Approach B", results_b))
    
    # Compare
    speedup = results_a["mean"] / results_b["mean"] if results_b["mean"] > 0 else 0
    
    print("COMPARISON:")
    if speedup > 1:
        print(f"  Approach B is {{speedup:.2f}}x faster than Approach A")
    elif speedup < 1:
        print(f"  Approach A is {{1/speedup:.2f}}x faster than Approach B")
    else:
        print("  Both approaches have similar performance")
    
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
''',

    "comparison": '''#!/usr/bin/env python3
"""Comparison experiment: {hypothesis}"""

from dataclasses import dataclass
from typing import Any


@dataclass
class TestCase:
    """A single test case."""
    name: str
    input_data: Any
    expected: Any = None


@dataclass 
class Result:
    """Result from a single test."""
    test_name: str
    approach: str
    output: Any
    success: bool
    notes: str = ""


def run_comparison(test_cases: list[TestCase]) -> dict:
    """Run comparison across all test cases."""
    results = {{"approach_a": [], "approach_b": []}}
    
    for case in test_cases:
        # Run approach A
        try:
            output_a = approach_a(case.input_data)
            success_a = output_a == case.expected if case.expected else True
            results["approach_a"].append(Result(
                test_name=case.name,
                approach="A",
                output=output_a,
                success=success_a
            ))
        except Exception as e:
            results["approach_a"].append(Result(
                test_name=case.name,
                approach="A", 
                output=None,
                success=False,
                notes=str(e)
            ))
        
        # Run approach B
        try:
            output_b = approach_b(case.input_data)
            success_b = output_b == case.expected if case.expected else True
            results["approach_b"].append(Result(
                test_name=case.name,
                approach="B",
                output=output_b,
                success=success_b
            ))
        except Exception as e:
            results["approach_b"].append(Result(
                test_name=case.name,
                approach="B",
                output=None,
                success=False,
                notes=str(e)
            ))
    
    return results


# TODO: Implement your approaches here
def approach_a(input_data: Any) -> Any:
    """First approach."""
    # Replace with actual implementation
    return input_data


def approach_b(input_data: Any) -> Any:
    """Second approach."""
    # Replace with actual implementation
    return input_data


def main():
    print("=" * 60)
    print("EXPERIMENT: {hypothesis}")
    print("=" * 60)
    print()
    
    # TODO: Define your test cases
    test_cases = [
        TestCase(name="basic", input_data="test"),
        TestCase(name="edge_case", input_data=""),
        # Add more test cases
    ]
    
    results = run_comparison(test_cases)
    
    print("RESULTS:")
    print()
    
    for approach, approach_results in results.items():
        successes = sum(1 for r in approach_results if r.success)
        print(f"{{approach.upper()}}: {{successes}}/{{len(approach_results)}} passed")
        for r in approach_results:
            status = "✓" if r.success else "✗"
            print(f"  {{status}} {{r.test_name}}: {{r.output}}")
            if r.notes:
                print(f"    Note: {{r.notes}}")
    
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
''',

    "validation": '''#!/usr/bin/env python3
"""Validation experiment: {hypothesis}"""

import json
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class ValidationResult:
    """Result of a validation check."""
    check_name: str
    passed: bool
    expected: Any
    actual: Any
    notes: str = ""


def validate(checks: list[tuple]) -> list[ValidationResult]:
    """Run validation checks.
    
    Args:
        checks: List of (name, expected, actual) tuples
    """
    results = []
    for name, expected, actual in checks:
        passed = expected == actual
        results.append(ValidationResult(
            check_name=name,
            passed=passed,
            expected=expected,
            actual=actual
        ))
    return results


def main():
    print("=" * 60)
    print("VALIDATION: {hypothesis}")
    print("=" * 60)
    print()
    
    # TODO: Define your validation checks
    # Format: (check_name, expected_value, actual_value)
    checks = [
        ("check_1", "expected", get_actual_value_1()),
        ("check_2", 100, get_actual_value_2()),
        # Add more checks
    ]
    
    results = validate(checks)
    
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    
    print(f"RESULTS: {{passed}}/{{total}} checks passed")
    print()
    
    for r in results:
        status = "✓ PASS" if r.passed else "✗ FAIL"
        print(f"{{status}}: {{r.check_name}}")
        if not r.passed:
            print(f"  Expected: {{r.expected}}")
            print(f"  Actual:   {{r.actual}}")
    
    print()
    print("=" * 60)
    
    # Exit with error code if any checks failed
    if passed < total:
        exit(1)


# TODO: Implement functions to get actual values
def get_actual_value_1():
    return "expected"  # Replace with actual implementation


def get_actual_value_2():
    return 100  # Replace with actual implementation


if __name__ == "__main__":
    main()
'''
}


def detect_experiment_type(hypothesis: str) -> str:
    """Detect the best experiment type based on hypothesis."""
    hypothesis_lower = hypothesis.lower()
    
    performance_keywords = ["faster", "slower", "performance", "speed", "benchmark", "latency", "throughput"]
    comparison_keywords = ["vs", "versus", "compare", "better", "worse", "different"]
    validation_keywords = ["is", "are", "should", "must", "verify", "validate", "check"]
    
    if any(kw in hypothesis_lower for kw in performance_keywords):
        return "performance"
    elif any(kw in hypothesis_lower for kw in comparison_keywords):
        return "comparison"
    else:
        return "validation"


def create_experiment(
    hypothesis: str,
    metric: str = "time",
    iterations: int = 10,
    experiment_type: str | None = None
) -> str:
    """Generate experiment code for a hypothesis."""
    if experiment_type is None:
        experiment_type = detect_experiment_type(hypothesis)
    
    if experiment_type not in EXPERIMENT_TEMPLATES:
        experiment_type = "validation"
    
    template = EXPERIMENT_TEMPLATES[experiment_type]
    
    code = template.format(
        hypothesis=hypothesis,
        metric=metric,
        iterations=iterations
    )
    
    return code


def main():
    parser = argparse.ArgumentParser(description="Generate experiment code to validate a hypothesis")
    parser.add_argument("--hypothesis", required=True, help="The hypothesis to test")
    parser.add_argument("--metric", default="time", help="What to measure (default: time)")
    parser.add_argument("--iterations", type=int, default=10, help="Number of test runs (default: 10)")
    parser.add_argument("--type", choices=["performance", "comparison", "validation"], 
                        help="Experiment type (auto-detected if not specified)")
    parser.add_argument("--output", default="experiment.py", help="Output script path")
    
    args = parser.parse_args()
    
    code = create_experiment(
        hypothesis=args.hypothesis,
        metric=args.metric,
        iterations=args.iterations,
        experiment_type=args.type
    )
    
    output_path = Path(args.output)
    output_path.write_text(code)
    output_path.chmod(0o755)
    
    print(f"Experiment script generated: {output_path}")
    print(f"  Hypothesis: {args.hypothesis}")
    print(f"  Type: {args.type or detect_experiment_type(args.hypothesis)}")
    print(f"  Iterations: {args.iterations}")
    print()
    print("Next steps:")
    print(f"  1. Edit {output_path} to implement your test functions")
    print(f"  2. Run: uv run {output_path}")


if __name__ == "__main__":
    main()

