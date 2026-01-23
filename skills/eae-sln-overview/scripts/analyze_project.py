#!/usr/bin/env python3
"""
EAE Project Analyzer - Main orchestration script

Coordinates all analysis modules to generate comprehensive EAE project reports.

Exit Codes:
    0: Analysis complete, quality score >= 70
    1: Error (project not found, critical failure)
   10: Analysis complete with warnings, or quality 50-69
   11: Analysis complete, quality score < 50

Usage:
    python analyze_project.py --project-dir /path/to/eae/project
    python analyze_project.py --project-dir /path/to/project --format json
    python analyze_project.py --project-dir /path/to/project --format summary
    python analyze_project.py --project-dir /path/to/project --output report.md
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Import analysis modules
from parse_solution import analyze_solution
from parse_system_topology import analyze_topology
from parse_protocols import analyze_protocols
from parse_libraries import analyze_libraries
from count_io import analyze_io
from parse_isa88 import analyze_isa88
from parse_description import generate_project_description
from calculate_quality import calculate_quality
from generate_report import generate_markdown_report, generate_summary_report


def to_dict(obj) -> Any:
    """Convert dataclass objects to dictionaries recursively."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if hasattr(obj, '__dict__'):
        result = {}
        for key, value in obj.__dict__.items():
            result[key] = to_dict(value)
        return result
    return obj


def analyze_project(project_dir: Path) -> Dict[str, Any]:
    """Run all analysis modules on the project."""
    results = {
        'project_dir': str(project_dir),
        'analyzed_at': datetime.now().isoformat(),
        'version': '1.0.0'
    }

    print(f"Analyzing project: {project_dir}", file=sys.stderr)

    # 1. Parse solution structure
    print("  [1/8] Parsing solution...", file=sys.stderr)
    try:
        solution_result = analyze_solution(project_dir)
        results['solution'] = to_dict(solution_result)
    except Exception as e:
        results['solution'] = {'error': str(e), 'warnings': [str(e)]}

    # 2. Parse system topology
    print("  [2/8] Parsing topology...", file=sys.stderr)
    try:
        topology_result = analyze_topology(project_dir)
        results['topology'] = to_dict(topology_result)
    except Exception as e:
        results['topology'] = {'error': str(e), 'warnings': [str(e)]}

    # 3. Parse protocols
    print("  [3/8] Parsing protocols...", file=sys.stderr)
    try:
        protocols_result = analyze_protocols(project_dir)
        results['protocols'] = to_dict(protocols_result)
    except Exception as e:
        results['protocols'] = {'error': str(e), 'warnings': [str(e)]}

    # 4. Analyze libraries
    print("  [4/8] Analyzing libraries...", file=sys.stderr)
    try:
        libraries_result = analyze_libraries(project_dir)
        results['libraries'] = to_dict(libraries_result)
    except Exception as e:
        results['libraries'] = {'error': str(e), 'warnings': [str(e)]}

    # 5. Count I/O
    print("  [5/8] Counting I/O...", file=sys.stderr)
    try:
        io_result = analyze_io(project_dir)
        results['io'] = to_dict(io_result)
    except Exception as e:
        results['io'] = {'error': str(e), 'warnings': [str(e)]}

    # 6. Parse ISA88 hierarchy
    print("  [6/8] Parsing ISA88...", file=sys.stderr)
    try:
        isa88_result = analyze_isa88(project_dir)
        results['isa88'] = to_dict(isa88_result)
    except Exception as e:
        results['isa88'] = {'error': str(e), 'warnings': [str(e)]}

    # 7. Generate project description
    print("  [7/8] Generating description...", file=sys.stderr)
    try:
        description_result = generate_project_description(project_dir)
        results['description'] = to_dict(description_result)
    except Exception as e:
        results['description'] = {'error': str(e), 'warnings': [str(e)]}

    # 8. Calculate quality score
    print("  [8/8] Calculating quality...", file=sys.stderr)
    try:
        quality_result = calculate_quality(project_dir)
        results['quality'] = to_dict(quality_result)
    except Exception as e:
        results['quality'] = {'error': str(e), 'warnings': [str(e)]}

    print("  Analysis complete.", file=sys.stderr)

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Analyze EAE project and generate comprehensive report',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python analyze_project.py --project-dir C:\\Projects\\MyEAEProject
    python analyze_project.py --project-dir ./project --format json --output analysis.json
    python analyze_project.py --project-dir ./project --format summary
        """
    )
    parser.add_argument('--project-dir', type=Path, required=True,
                        help='Path to EAE project root directory')
    parser.add_argument('--format', choices=['markdown', 'json', 'summary'],
                        default='markdown', help='Output format (default: markdown)')
    parser.add_argument('--output', type=Path, help='Output file path (default: stdout)')
    parser.add_argument('--json', action='store_true',
                        help='Shortcut for --format json')

    args = parser.parse_args()

    # Handle --json shortcut
    if args.json:
        args.format = 'json'

    # Validate project directory
    if not args.project_dir.exists():
        print(f"Error: Project directory not found: {args.project_dir}", file=sys.stderr)
        sys.exit(1)

    if not args.project_dir.is_dir():
        print(f"Error: Path is not a directory: {args.project_dir}", file=sys.stderr)
        sys.exit(1)

    # Run analysis
    try:
        results = analyze_project(args.project_dir)
    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        sys.exit(1)

    # Generate output
    if args.format == 'json':
        output = json.dumps(results, indent=2, default=str)
    elif args.format == 'summary':
        output = generate_summary_report(results)
    else:  # markdown
        output = generate_markdown_report(results)

    # Write output
    if args.output:
        try:
            args.output.write_text(output, encoding='utf-8')
            print(f"Report written to: {args.output}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(output)

    # Determine exit code based on quality
    quality = results.get('quality', {})
    percentage = quality.get('percentage', 0)

    # Collect all warnings
    all_warnings = []
    for section in results.values():
        if isinstance(section, dict):
            all_warnings.extend(section.get('warnings', []))

    if percentage >= 70 and not all_warnings:
        sys.exit(0)
    elif percentage >= 50:
        sys.exit(10)
    else:
        sys.exit(11)


if __name__ == '__main__':
    main()
