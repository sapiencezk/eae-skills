#!/usr/bin/env python3
"""
CPU Load Estimator for EcoStruxure Automation Expert Applications

Analyzes ST algorithm complexity, estimates execution time, aggregates resource CPU load.

Exit Codes:
    0: Low load (<70%)
   10: Moderate load (70-90%)
   11: High load (>90%)
    1: Error (parsing failure)
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class ValidationResult:
    """Structured result for script outputs."""
    success: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def exit_code(self) -> int:
        """Calculate exit code based on CPU load."""
        if not self.success:
            return 1

        resource_loads = self.details.get("resource_cpu_load", {})
        if not resource_loads:
            return 0

        max_load = max(
            res["total_load_pct"]
            for res in resource_loads.values()
            if "total_load_pct" in res
        )

        if max_load >= 90:
            return 11  # Critical
        elif max_load >= 70:
            return 10  # Warning
        else:
            return 0  # Safe

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


PLATFORM_FACTORS = {
    "soft-dpac-windows": 1.0,
    "soft-dpac-linux": 0.9,
    "hard-dpac-m262": 1.2,
    "hard-dpac-m251": 1.5,
    "unknown": 1.0
}


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Estimate CPU load for EAE application"
    )
    parser.add_argument("--app-dir", required=True, help="Path to EAE application")
    parser.add_argument("--resource", help="Specific resource (optional)")
    parser.add_argument("--output", help="JSON output path (default: stdout)")
    parser.add_argument(
        "--platform",
        default="unknown",
        choices=list(PLATFORM_FACTORS.keys()),
        help="Target platform"
    )
    return parser.parse_args()


def calculate_cyclomatic_complexity(st_code: str) -> int:
    """Calculate simplified cyclomatic complexity for ST code."""
    decision_keywords = ["IF", "ELSIF", "CASE", "FOR", "WHILE", "REPEAT"]
    complexity = 1

    st_upper = st_code.upper()
    for keyword in decision_keywords:
        complexity += st_upper.count(keyword)

    return complexity


def estimate_execution_time(st_code: str, complexity: int) -> float:
    """
    Estimate execution time in microseconds using heuristics.
    Returns approximate time (±50% accuracy).
    """
    # Count operations
    arithmetic = len(re.findall(r'[\+\-\*/]', st_code))
    logical = len(re.findall(r'\b(AND|OR|XOR|NOT)\b', st_code, re.I))
    comparisons = len(re.findall(r'[<>=]', st_code))
    var_accesses = len(re.findall(r'\b[a-z_][a-z0-9_]*\b', st_code, re.I))

    # Heuristic time estimation
    base_time = complexity * 10  # μs per complexity point
    operation_time = (arithmetic + logical + comparisons) * 1  # μs per operation
    access_time = var_accesses * 0.5  # μs per variable access

    total_time = base_time + operation_time + access_time
    return round(total_time, 1)


def parse_fb_algorithms(filepath: Path) -> List[Dict[str, Any]]:
    """Extract algorithms from .fbt file."""
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except Exception as e:
        return []

    algorithms = []
    fb_name = root.get("Name", "Unknown")

    # Find BasicFB section
    basic_fb = root.find("BasicFB")
    if basic_fb:
        for algo in basic_fb.findall(".//Algorithm"):
            algo_name = algo.get("Name", "Unknown")
            st_code = algo.find("ST")

            if st_code is not None and st_code.text:
                complexity = calculate_cyclomatic_complexity(st_code.text)
                exec_time = estimate_execution_time(st_code.text, complexity)

                algorithms.append({
                    "fb_name": fb_name,
                    "algorithm": algo_name,
                    "complexity": complexity,
                    "estimated_us": exec_time,
                    "st_lines": len(st_code.text.splitlines())
                })

    return algorithms


def estimate_cpu_load(app_dir: Path, platform: str, resource_filter: Optional[str]) -> ValidationResult:
    """Main CPU load estimation function."""
    errors = []
    warnings = []

    fbt_files = list(app_dir.rglob("*.fbt"))
    if not fbt_files:
        return ValidationResult(
            success=False,
            errors=["No .fbt files found"],
            details={}
        )

    print(f"Analyzing {len(fbt_files)} .fbt files", file=sys.stderr)

    # Parse all algorithms
    all_algorithms = []
    for fbt_file in fbt_files:
        algos = parse_fb_algorithms(fbt_file)
        all_algorithms.extend(algos)

    if not all_algorithms:
        warnings.append("No ST algorithms found in application")
        return ValidationResult(
            success=True,
            warnings=warnings,
            details={
                "fb_execution_estimates": {},
                "resource_cpu_load": {},
                "overall_assessment": {
                    "status": "SAFE",
                    "note": "No algorithms to analyze"
                }
            }
        )

    print(f"Found {len(all_algorithms)} ST algorithms", file=sys.stderr)

    # Apply platform factor
    platform_factor = PLATFORM_FACTORS.get(platform, 1.0)

    fb_estimates = {}
    for algo in all_algorithms:
        adjusted_time = algo["estimated_us"] * platform_factor
        fb_estimates[f"{algo['fb_name']}.{algo['algorithm']}"] = {
            "complexity": algo["complexity"],
            "estimated_us": algo["estimated_us"],
            "platform_adjusted_us": round(adjusted_time, 1),
            "platform": platform
        }

    # Simplified resource load calculation (assume 10 Hz execution frequency)
    # In reality, would need event frequency analysis from analyze_event_flow.py
    assumed_frequency_hz = 10
    total_load_us_per_s = sum(
        est["platform_adjusted_us"] * assumed_frequency_hz
        for est in fb_estimates.values()
    )
    cpu_load_pct = (total_load_us_per_s / 1_000_000) * 100

    resource_load = {
        "Resource_Default": {
            "total_load_pct": round(cpu_load_pct, 1),
            "headroom_pct": round(100 - cpu_load_pct, 1),
            "bottleneck_fbs": sorted(
                fb_estimates.keys(),
                key=lambda x: fb_estimates[x]["platform_adjusted_us"],
                reverse=True
            )[:5]
        }
    }

    # Overall assessment
    if cpu_load_pct >= 90:
        status = "CRITICAL"
        recommendation = "High CPU load. Optimize algorithms or distribute to multiple resources."
    elif cpu_load_pct >= 70:
        status = "WARNING"
        recommendation = "Moderate CPU load. Monitor under real load conditions."
    else:
        status = "SAFE"
        recommendation = "Ample CPU headroom available."

    details = {
        "fb_execution_estimates": fb_estimates,
        "resource_cpu_load": resource_load,
        "overall_assessment": {
            "highest_load_resource": "Resource_Default",
            "load_pct": round(cpu_load_pct, 1),
            "status": status,
            "recommendation": recommendation
        },
        "uncertainty_note": "Execution time estimates are heuristic-based and may vary ±50% due to compiler optimizations, cache effects, and OS scheduling.",
        "assumptions": {
            "event_frequency_hz": assumed_frequency_hz,
            "note": "Actual frequency depends on event sources. Use analyze_event_flow.py for precise rates."
        }
    }

    return ValidationResult(success=True, errors=errors, warnings=warnings, details=details)


def main():
    args = parse_arguments()

    app_dir = Path(args.app_dir)
    if not app_dir.exists():
        print(f"Error: Directory not found: {app_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Estimating CPU load for: {app_dir}", file=sys.stderr)
    result = estimate_cpu_load(app_dir, args.platform, args.resource)

    json_output = result.to_json()

    if args.output:
        with open(args.output, "w") as f:
            f.write(json_output)
        print(f"Results written to: {args.output}", file=sys.stderr)
    else:
        print(json_output)

    print(f"Analysis complete. Exit code: {result.exit_code}", file=sys.stderr)
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
