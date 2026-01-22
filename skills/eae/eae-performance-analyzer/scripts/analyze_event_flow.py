#!/usr/bin/env python3
"""
Event Flow Analyzer for EcoStruxure Automation Expert Applications

Traces event propagation through FBNetworks, calculates multiplication factors,
identifies explosive patterns, and detects event loops.

Exit Codes:
    0: No issues detected (multiplication <10x)
   10: Moderate risk (10-20x multiplication)
   11: High risk (>20x multiplication or explosive patterns)
    1: Error (parsing failure, invalid files)
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple


@dataclass
class ValidationResult:
    """Structured result for script outputs."""
    success: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def exit_code(self) -> int:
        """Calculate exit code based on results."""
        if not self.success:
            return 1  # Error

        # Check multiplication factors in details
        mult_factors = self.details.get("multiplication_factors", {})
        if not mult_factors:
            return 0  # No analysis (safe)

        max_multiplication = max(mult_factors.values()) if mult_factors else 0

        if max_multiplication >= 20:
            return 11  # Critical
        elif max_multiplication >= 10:
            return 10  # Warning
        else:
            return 0  # Safe

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(asdict(self), indent=2)


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Analyze event flow in EAE application"
    )
    parser.add_argument(
        "--app-dir",
        required=True,
        help="Path to EAE application directory"
    )
    parser.add_argument(
        "--resource",
        help="Specific resource name for incremental analysis (optional)"
    )
    parser.add_argument(
        "--output",
        help="Path for JSON report output (default: stdout)"
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Generate Graphviz DOT file for event flow diagram"
    )
    return parser.parse_args()


def find_fbt_files(app_dir: Path) -> List[Path]:
    """Find all .fbt files in application directory."""
    return list(app_dir.rglob("*.fbt"))


def safe_parse_xml(filepath: Path) -> Tuple[Optional[ET.Element], Optional[str]]:
    """Parse XML file with error handling."""
    try:
        tree = ET.parse(filepath)
        return tree.getroot(), None
    except ET.ParseError as e:
        return None, f"XML parsing error in {filepath.name}: {e}"
    except FileNotFoundError:
        return None, f"File not found: {filepath}"
    except Exception as e:
        return None, f"Unexpected error parsing {filepath.name}: {e}"


def parse_fb_type(filepath: Path) -> Dict[str, Any]:
    """Parse a single .fbt file into FB type definition."""
    root, error = safe_parse_xml(filepath)
    if error:
        return {"error": error}

    fb_type = {
        "name": root.get("Name", "Unknown"),
        "filepath": str(filepath),
        "event_inputs": [],
        "event_outputs": [],
        "fb_instances": [],
        "event_connections": []
    }

    # Parse interface
    interface = root.find("InterfaceList")
    if interface:
        # Event inputs
        for event in interface.findall(".//EventInputs/Event"):
            fb_type["event_inputs"].append(event.get("Name"))

        # Event outputs
        for event in interface.findall(".//EventOutputs/Event"):
            fb_type["event_outputs"].append(event.get("Name"))

    # Parse FBNetwork (Composite FBs and CATs)
    fbnetwork = root.find("FBNetwork")
    if fbnetwork:
        # FB instances
        for fb in fbnetwork.findall("FB"):
            fb_type["fb_instances"].append({
                "name": fb.get("Name"),
                "type": fb.get("Type")
            })

        # Event connections
        for conn in fbnetwork.findall(".//EventConnections/Connection"):
            source = conn.get("Source", "")
            destination = conn.get("Destination", "")
            fb_type["event_connections"].append({
                "source": source,
                "destination": destination
            })

    return fb_type


def build_event_graph(fb_types: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Build event propagation graph from FB types."""
    graph = {}

    for fb_type in fb_types:
        if "error" in fb_type:
            continue

        fb_name = fb_type["name"]

        # Initialize graph node
        if fb_name not in graph:
            graph[fb_name] = []

        # Add connections from event outputs to connected FBs
        for conn in fb_type.get("event_connections", []):
            source = conn["source"]
            dest = conn["destination"]

            # Parse source (FB_instance.event or just event)
            source_fb = source.split(".")[0] if "." in source else fb_name

            # Parse destination (FB_instance.event)
            if "." in dest:
                dest_fb = dest.split(".")[0]
                if dest_fb not in graph.get(source_fb, []):
                    if source_fb not in graph:
                        graph[source_fb] = []
                    graph[source_fb].append(dest_fb)

    return graph


def trace_event_cascade(
    graph: Dict[str, List[str]],
    source_fb: str,
    visited: Optional[Set[str]] = None
) -> List[Dict[str, Any]]:
    """
    Trace event cascade from source FB using BFS.
    Returns list of cascade paths with event counts.
    """
    if visited is None:
        visited = set()

    cascade_paths = []
    queue = [(source_fb, [source_fb], 1)]  # (current_fb, path, event_count)

    while queue:
        current_fb, path, events = queue.pop(0)

        # Get connected FBs
        targets = graph.get(current_fb, [])

        if not targets:
            # Leaf node - end of cascade
            cascade_paths.append({
                "source": source_fb,
                "path": path,
                "events_generated": events
            })
            continue

        for target_fb in targets:
            new_path = path + [target_fb]
            new_events = events + 1

            if target_fb not in visited:
                visited.add(target_fb)
                queue.append((target_fb, new_path, new_events))

    return cascade_paths


def calculate_multiplication_factor(cascade_paths: List[Dict[str, Any]]) -> float:
    """Calculate event multiplication factor from cascade paths."""
    if not cascade_paths:
        return 0.0

    total_events = sum(path["events_generated"] for path in cascade_paths)
    return float(total_events) / 1.0  # Divide by 1 source event


def detect_cycles(graph: Dict[str, List[str]], max_depth: int = 2) -> List[Dict[str, Any]]:
    """Detect event loops using DFS with depth limit."""
    cycles = []

    def dfs(current: str, target: str, path: List[str], depth: int) -> bool:
        if depth > max_depth:
            return False

        if current == target and depth > 0:
            return True  # Cycle found

        if current not in graph:
            return False

        for neighbor in graph[current]:
            if neighbor not in path or neighbor == target:
                if dfs(neighbor, target, path + [neighbor], depth + 1):
                    return True

        return False

    for source_fb in graph.keys():
        if dfs(source_fb, source_fb, [source_fb], 0):
            cycles.append({
                "fb": source_fb,
                "cycle_depth": f"≤{max_depth} hops",
                "severity": "CRITICAL"
            })

    return cycles


def analyze_event_flow(app_dir: Path, resource_filter: Optional[str] = None) -> ValidationResult:
    """Main analysis function."""
    errors = []
    warnings = []

    # Find and parse .fbt files
    fbt_files = find_fbt_files(app_dir)

    if not fbt_files:
        return ValidationResult(
            success=False,
            errors=["No .fbt files found in application directory"],
            details={}
        )

    print(f"Found {len(fbt_files)} .fbt files", file=sys.stderr)

    # Parse all FB types
    fb_types = []
    for fbt_file in fbt_files:
        fb_type = parse_fb_type(fbt_file)
        if "error" in fb_type:
            warnings.append(fb_type["error"])
        else:
            fb_types.append(fb_type)

    if not fb_types:
        return ValidationResult(
            success=False,
            errors=["Failed to parse any .fbt files"],
            warnings=warnings,
            details={}
        )

    print(f"Parsed {len(fb_types)} FB types successfully", file=sys.stderr)

    # Build event graph
    event_graph = build_event_graph(fb_types)

    if not event_graph:
        return ValidationResult(
            success=True,
            warnings=["No event connections found in application"],
            details={
                "multiplication_factors": {},
                "cascade_paths": [],
                "explosive_patterns": [],
                "cycles_detected": []
            }
        )

    print(f"Built event graph with {len(event_graph)} nodes", file=sys.stderr)

    # Calculate multiplication factors for each FB
    multiplication_factors = {}
    all_cascade_paths = []

    for source_fb in event_graph.keys():
        cascade_paths = trace_event_cascade(event_graph, source_fb)
        mult_factor = calculate_multiplication_factor(cascade_paths)

        if mult_factor > 0:
            multiplication_factors[source_fb] = round(mult_factor, 1)
            all_cascade_paths.extend(cascade_paths)

    # Identify explosive patterns (>20x multiplication)
    explosive_patterns = [
        {
            "source": fb,
            "multiplication": mult,
            "severity": "CRITICAL" if mult > 50 else "WARNING",
            "recommendation": "Use EventChainHead (SE.AppSequence) or adapter consolidation"
        }
        for fb, mult in multiplication_factors.items()
        if mult > 20
    ]

    # Detect tight event loops
    cycles = detect_cycles(event_graph, max_depth=2)

    # Prepare results
    details = {
        "multiplication_factors": multiplication_factors,
        "cascade_paths": all_cascade_paths[:50],  # Limit output size
        "explosive_patterns": explosive_patterns,
        "cycles_detected": cycles,
        "summary": {
            "total_fbs_analyzed": len(fb_types),
            "event_graph_nodes": len(event_graph),
            "max_multiplication": max(multiplication_factors.values()) if multiplication_factors else 0,
            "explosive_patterns_found": len(explosive_patterns),
            "cycles_found": len(cycles)
        }
    }

    # Determine success based on findings
    success = len(errors) == 0

    return ValidationResult(
        success=success,
        errors=errors,
        warnings=warnings,
        details=details
    )


def generate_graphviz(result: ValidationResult, output_path: Path):
    """Generate Graphviz DOT file for event flow visualization."""
    mult_factors = result.details.get("multiplication_factors", {})

    dot_content = ["digraph EventFlow {"]
    dot_content.append('  rankdir=LR;')
    dot_content.append('  node [shape=box];')

    # Add nodes with color coding
    for fb, mult in mult_factors.items():
        if mult < 10:
            color = "green"
        elif mult < 20:
            color = "yellow"
        elif mult < 50:
            color = "orange"
        else:
            color = "red"

        dot_content.append(f'  "{fb}" [color={color}, style=filled, label="{fb}\\n{mult}x"];')

    # Add edges from cascade paths
    cascade_paths = result.details.get("cascade_paths", [])
    edges_added = set()

    for path_info in cascade_paths[:100]:  # Limit edges
        path = path_info["path"]
        for i in range(len(path) - 1):
            edge = (path[i], path[i + 1])
            if edge not in edges_added:
                dot_content.append(f'  "{path[i]}" -> "{path[i + 1]}";')
                edges_added.add(edge)

    dot_content.append("}")

    with open(output_path, "w") as f:
        f.write("\n".join(dot_content))

    print(f"Graphviz DOT file generated: {output_path}", file=sys.stderr)


def main():
    """Main entry point."""
    args = parse_arguments()

    app_dir = Path(args.app_dir)
    if not app_dir.exists():
        print(f"Error: Application directory not found: {app_dir}", file=sys.stderr)
        sys.exit(1)

    # Run analysis
    print(f"Analyzing EAE application: {app_dir}", file=sys.stderr)
    result = analyze_event_flow(app_dir, args.resource)

    # Generate visualization if requested
    if args.visualize and result.success:
        viz_path = Path(args.output).with_suffix(".dot") if args.output else Path("event_flow.dot")
        generate_graphviz(result, viz_path)

    # Output results
    json_output = result.to_json()

    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            f.write(json_output)
        print(f"Results written to: {output_path}", file=sys.stderr)
    else:
        print(json_output)

    # Exit with appropriate code
    exit_code = result.exit_code
    print(f"Analysis complete. Exit code: {exit_code}", file=sys.stderr)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
