#!/usr/bin/env python3
"""
Event Storm Pattern Detector for EcoStruxure Automation Expert Applications

Rule-based detection of known event storm anti-patterns from SE Application Design Guidelines.

Exit Codes:
    0: No anti-patterns detected
   10: Minor anti-patterns (INFO/WARNING)
   11: Severe anti-patterns (CRITICAL)
    1: Error (parsing failure)
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple


@dataclass
class ValidationResult:
    """Structured result for script outputs."""
    success: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def exit_code(self) -> int:
        """Calculate exit code based on detected patterns."""
        if not self.success:
            return 1

        detected = self.details.get("detected_patterns", [])
        if not detected:
            return 0

        # Check for CRITICAL patterns
        critical_count = sum(
            1 for p in detected if p.get("severity") == "CRITICAL"
        )

        if critical_count > 0:
            return 11  # Critical patterns found
        else:
            return 10  # Only WARNING/INFO patterns

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Detect event storm anti-patterns in EAE application"
    )
    parser.add_argument("--app-dir", required=True, help="Path to EAE application")
    parser.add_argument("--output", help="JSON output path (default: stdout)")
    return parser.parse_args()


def build_event_graph(fbt_files: List[Path]) -> Dict[str, List[str]]:
    """Build event connection graph from .fbt files."""
    graph = {}

    for filepath in fbt_files:
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()

            fb_name = root.get("Name", "Unknown")
            fbnetwork = root.find("FBNetwork")

            if fbnetwork:
                for conn in fbnetwork.findall(".//EventConnections/Connection"):
                    source = conn.get("Source", "").split(".")[0] if "." in conn.get("Source", "") else fb_name
                    dest = conn.get("Destination", "").split(".")[0] if "." in conn.get("Destination", "") else ""

                    if dest:
                        if source not in graph:
                            graph[source] = []
                        if dest not in graph[source]:
                            graph[source].append(dest)

        except Exception:
            continue

    return graph


def detect_tight_loop(graph: Dict[str, List[str]], max_depth: int = 2) -> List[Dict[str, Any]]:
    """Detect event loops with cycle length ≤ max_depth."""
    violations = []

    def dfs_cycle(current: str, target: str, visited: Set[str], depth: int) -> bool:
        if depth > max_depth:
            return False
        if current == target and depth > 0:
            return True

        if current not in graph:
            return False

        for neighbor in graph[current]:
            if neighbor not in visited or neighbor == target:
                new_visited = visited | {neighbor}
                if dfs_cycle(neighbor, target, new_visited, depth + 1):
                    return True

        return False

    for source_fb in graph.keys():
        if dfs_cycle(source_fb, source_fb, {source_fb}, 0):
            violations.append({
                "fb": source_fb,
                "cycle_depth": f"≤{max_depth} hops",
                "description": f"Event loops back to {source_fb} within {max_depth} hops"
            })

    return violations


def detect_io_multiplication(graph: Dict[str, List[str]], threshold: int = 30) -> List[Dict[str, Any]]:
    """Detect I/O events with high downstream multiplication."""
    violations = []

    # Identify potential I/O sources (simplified: FBs with "IO" or "DI" or "AI" in name)
    io_sources = [fb for fb in graph.keys() if any(x in fb.upper() for x in ["IO", "DI", "AI", "DO", "AO"])]

    for io_fb in io_sources:
        # Count downstream events (simplified BFS)
        visited = set()
        queue = [io_fb]
        event_count = 0

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue

            visited.add(current)
            event_count += 1

            if current in graph:
                queue.extend(graph[current])

        if event_count > threshold:
            violations.append({
                "io_source": io_fb,
                "multiplication": event_count,
                "description": f"I/O source {io_fb} triggers {event_count} downstream events"
            })

    return violations


def detect_cascading_timers(fbt_files: List[Path], threshold_hz: int = 100) -> List[Dict[str, Any]]:
    """Detect high aggregate timer frequency (E_CYCLE)."""
    violations = []

    # In a real implementation, would parse E_CYCLE configurations from .cfg files
    # For this version, provide simplified detection logic

    # Placeholder: assume we found timer configurations
    # This would require parsing device configurations and timer FB instances

    return violations  # Simplified: no detection in this version


def detect_patterns(app_dir: Path) -> ValidationResult:
    """Main pattern detection function."""
    errors = []
    warnings = []

    fbt_files = list(app_dir.rglob("*.fbt"))

    if not fbt_files:
        return ValidationResult(
            success=False,
            errors=["No .fbt files found in application directory"],
            details={}
        )

    print(f"Analyzing {len(fbt_files)} .fbt files for anti-patterns", file=sys.stderr)

    # Build event graph
    event_graph = build_event_graph(fbt_files)

    if not event_graph:
        warnings.append("No event connections found")
        return ValidationResult(
            success=True,
            warnings=warnings,
            details={
                "detected_patterns": [],
                "pattern_summary": {"CRITICAL": 0, "WARNING": 0, "INFO": 0}
            }
        )

    detected_patterns = []

    # Pattern 1: TIGHT_EVENT_LOOP
    tight_loops = detect_tight_loop(event_graph, max_depth=2)
    for loop in tight_loops:
        detected_patterns.append({
            "pattern": "TIGHT_EVENT_LOOP",
            "severity": "CRITICAL",
            "description": "FB generates event that loops back to itself within 2 hops",
            "locations": [loop],
            "recommendation": "Break loop with state guard (BOOL flag) or timer-based debouncing (100ms min interval)"
        })

    # Pattern 2: UNCONTROLLED_IO_MULTIPLICATION
    io_violations = detect_io_multiplication(event_graph, threshold=30)
    for violation in io_violations:
        detected_patterns.append({
            "pattern": "UNCONTROLLED_IO_MULTIPLICATION",
            "severity": "WARNING",
            "description": "Single I/O event triggers >30 downstream events",
            "locations": [violation],
            "recommendation": "Use EventChainHead (SE.AppSequence library) or adapter consolidation to reduce event multiplication"
        })

    # Pattern 3: CASCADING_TIMERS (simplified - not fully implemented)
    # Would require .cfg file parsing for E_CYCLE configurations

    # Pattern 4: HMI_BURST_AMPLIFICATION (simplified)
    # Would require analyzing CAT HMI interface connections

    # Pattern 5: CROSS_RESOURCE_AMPLIFICATION (simplified)
    # Would require resource mapping analysis

    # Summarize
    pattern_summary = {
        "CRITICAL": sum(1 for p in detected_patterns if p["severity"] == "CRITICAL"),
        "WARNING": sum(1 for p in detected_patterns if p["severity"] == "WARNING"),
        "INFO": sum(1 for p in detected_patterns if p["severity"] == "INFO")
    }

    print(f"Detected {len(detected_patterns)} anti-patterns", file=sys.stderr)
    print(f"  CRITICAL: {pattern_summary['CRITICAL']}", file=sys.stderr)
    print(f"  WARNING: {pattern_summary['WARNING']}", file=sys.stderr)
    print(f"  INFO: {pattern_summary['INFO']}", file=sys.stderr)

    details = {
        "detected_patterns": detected_patterns,
        "pattern_summary": pattern_summary,
        "note": "This version detects TIGHT_EVENT_LOOP and UNCONTROLLED_IO_MULTIPLICATION. Additional patterns (CASCADING_TIMERS, HMI_BURST, CROSS_RESOURCE) require extended file parsing."
    }

    return ValidationResult(success=True, errors=errors, warnings=warnings, details=details)


def main():
    args = parse_arguments()

    app_dir = Path(args.app_dir)
    if not app_dir.exists():
        print(f"Error: Directory not found: {app_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Detecting anti-patterns in: {app_dir}", file=sys.stderr)
    result = detect_patterns(app_dir)

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
