#!/usr/bin/env python3
"""
EAE I/O Counter - Count events and data I/Os from .fbt files

Analyzes function block interfaces to count event inputs/outputs and data inputs/outputs.

Exit Codes:
    0: Counting successful
    1: Project not found or parsing error
   10: Partial success with warnings

Usage:
    python count_io.py --project-dir /path/to/eae/project
    python count_io.py --project-dir /path/to/project --json
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class BlockIOCounts:
    """I/O counts for a single block."""
    name: str
    namespace: str
    block_type: str  # CAT, Basic, Composite, Adapter
    event_inputs: int = 0
    event_outputs: int = 0
    data_inputs: int = 0
    data_outputs: int = 0
    internal_vars: int = 0
    adapters: int = 0  # Socket/Plug adapters
    total_io: int = 0


@dataclass
class IOTotals:
    """Aggregated I/O totals."""
    event_inputs: int = 0
    event_outputs: int = 0
    data_inputs: int = 0
    data_outputs: int = 0
    internal_vars: int = 0
    adapters: int = 0
    total_io: int = 0


@dataclass
class IOAnalysis:
    """Complete I/O analysis."""
    totals: IOTotals
    by_block_type: Dict[str, IOTotals]
    by_namespace: Dict[str, IOTotals]
    blocks: List[BlockIOCounts]
    block_count: int
    largest_blocks: List[BlockIOCounts]  # Top 5 by I/O count
    complexity_warnings: List[str]
    warnings: List[str] = field(default_factory=list)


# Complexity thresholds
MAX_VARS_WARNING = 100
MAX_VARS_ERROR = 200
MAX_EVENT_FANOUT_WARNING = 10
MAX_EVENT_FANOUT_ERROR = 20


def parse_fbt_io(fbt_path: Path) -> Optional[BlockIOCounts]:
    """Parse a .fbt file and count I/Os."""
    try:
        tree = ET.parse(fbt_path)
        root = tree.getroot()
    except ET.ParseError:
        return None

    # Get block name and type
    block_name = root.get('Name', fbt_path.stem)
    namespace = root.get('Namespace', '')

    # Determine block type from root element
    root_tag = root.tag
    if root_tag == 'FBType':
        # Check for BasicFB or CompositeFB child
        if root.find('.//BasicFB') is not None:
            block_type = 'Basic'
        elif root.find('.//FBNetwork') is not None:
            block_type = 'Composite'
        else:
            block_type = 'Basic'
    elif root_tag == 'SubAppType':
        block_type = 'CAT'
    elif root_tag == 'AdapterType':
        block_type = 'Adapter'
    elif root_tag == 'DataType':
        block_type = 'DataType'
    else:
        block_type = 'Unknown'

    # Count interface elements
    event_inputs = 0
    event_outputs = 0
    data_inputs = 0
    data_outputs = 0
    internal_vars = 0
    adapters = 0

    # Find InterfaceList
    interface_list = root.find('.//InterfaceList')
    if interface_list is not None:
        # Event inputs
        event_inputs_elem = interface_list.find('EventInputs')
        if event_inputs_elem is not None:
            event_inputs = len(event_inputs_elem.findall('Event'))

        # Event outputs
        event_outputs_elem = interface_list.find('EventOutputs')
        if event_outputs_elem is not None:
            event_outputs = len(event_outputs_elem.findall('Event'))

        # Data inputs (InputVars)
        input_vars_elem = interface_list.find('InputVars')
        if input_vars_elem is not None:
            data_inputs = len(input_vars_elem.findall('VarDeclaration'))

        # Data outputs (OutputVars)
        output_vars_elem = interface_list.find('OutputVars')
        if output_vars_elem is not None:
            data_outputs = len(output_vars_elem.findall('VarDeclaration'))

        # Sockets and Plugs (adapters)
        sockets = interface_list.find('Sockets')
        if sockets is not None:
            adapters += len(sockets.findall('AdapterDeclaration'))

        plugs = interface_list.find('Plugs')
        if plugs is not None:
            adapters += len(plugs.findall('AdapterDeclaration'))

    # Internal variables (from BasicFB or InternalVars)
    internal_vars_elem = root.find('.//InternalVars')
    if internal_vars_elem is not None:
        internal_vars = len(internal_vars_elem.findall('VarDeclaration'))

    # Also check for vars in BasicFB
    basic_fb = root.find('.//BasicFB')
    if basic_fb is not None:
        basic_vars = basic_fb.find('InternalVars')
        if basic_vars is not None:
            internal_vars += len(basic_vars.findall('VarDeclaration'))

    total_io = event_inputs + event_outputs + data_inputs + data_outputs + internal_vars + adapters

    return BlockIOCounts(
        name=block_name,
        namespace=namespace,
        block_type=block_type,
        event_inputs=event_inputs,
        event_outputs=event_outputs,
        data_inputs=data_inputs,
        data_outputs=data_outputs,
        internal_vars=internal_vars,
        adapters=adapters,
        total_io=total_io
    )


def aggregate_totals(blocks: List[BlockIOCounts]) -> IOTotals:
    """Aggregate I/O totals from a list of blocks."""
    totals = IOTotals()
    for block in blocks:
        totals.event_inputs += block.event_inputs
        totals.event_outputs += block.event_outputs
        totals.data_inputs += block.data_inputs
        totals.data_outputs += block.data_outputs
        totals.internal_vars += block.internal_vars
        totals.adapters += block.adapters
        totals.total_io += block.total_io
    return totals


def check_complexity(blocks: List[BlockIOCounts]) -> List[str]:
    """Check for complexity issues in blocks."""
    warnings = []

    for block in blocks:
        total_vars = block.data_inputs + block.data_outputs + block.internal_vars

        # Check variable count
        if total_vars >= MAX_VARS_ERROR:
            warnings.append(f"ERROR: {block.name} has {total_vars} variables (max: {MAX_VARS_ERROR})")
        elif total_vars >= MAX_VARS_WARNING:
            warnings.append(f"WARNING: {block.name} has {total_vars} variables (recommended max: {MAX_VARS_WARNING})")

        # Check event fanout
        if block.event_inputs > 0:
            fanout = block.event_outputs / block.event_inputs
            if fanout >= MAX_EVENT_FANOUT_ERROR:
                warnings.append(f"ERROR: {block.name} has event fanout of {fanout:.1f} (max: {MAX_EVENT_FANOUT_ERROR})")
            elif fanout >= MAX_EVENT_FANOUT_WARNING:
                warnings.append(f"WARNING: {block.name} has event fanout of {fanout:.1f} (recommended max: {MAX_EVENT_FANOUT_WARNING})")

    return warnings


def analyze_io(project_dir: Path) -> IOAnalysis:
    """Analyze all I/O in the project."""
    warnings = []
    blocks = []

    # Find all .fbt files
    fbt_files = list(project_dir.rglob('*.fbt'))

    if not fbt_files:
        warnings.append("No .fbt files found")

    # Parse each file
    for fbt_path in fbt_files:
        block_io = parse_fbt_io(fbt_path)
        if block_io:
            blocks.append(block_io)
        else:
            warnings.append(f"Could not parse: {fbt_path.name}")

    # Calculate totals
    totals = aggregate_totals(blocks)

    # Group by block type
    by_block_type = {}
    for block in blocks:
        if block.block_type not in by_block_type:
            by_block_type[block.block_type] = []
        by_block_type[block.block_type].append(block)

    by_block_type_totals = {
        bt: aggregate_totals(block_list)
        for bt, block_list in by_block_type.items()
    }

    # Group by namespace
    by_namespace = {}
    for block in blocks:
        ns = block.namespace or 'Main'
        if ns not in by_namespace:
            by_namespace[ns] = []
        by_namespace[ns].append(block)

    by_namespace_totals = {
        ns: aggregate_totals(block_list)
        for ns, block_list in by_namespace.items()
    }

    # Find largest blocks
    sorted_blocks = sorted(blocks, key=lambda x: x.total_io, reverse=True)
    largest_blocks = sorted_blocks[:5]

    # Check complexity
    complexity_warnings = check_complexity(blocks)

    return IOAnalysis(
        totals=totals,
        by_block_type=by_block_type_totals,
        by_namespace=by_namespace_totals,
        blocks=blocks,
        block_count=len(blocks),
        largest_blocks=largest_blocks,
        complexity_warnings=complexity_warnings,
        warnings=warnings
    )


def main():
    parser = argparse.ArgumentParser(
        description='Count I/Os from EAE .fbt files',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--project-dir', type=Path, required=True,
                        help='Path to EAE project root directory')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--output', type=Path, help='Output file path')
    parser.add_argument('--details', action='store_true', help='Include per-block details')

    args = parser.parse_args()

    if not args.project_dir.exists():
        print(f"Error: Project directory not found: {args.project_dir}", file=sys.stderr)
        sys.exit(1)

    # Analyze I/O
    result = analyze_io(args.project_dir)

    # Convert to dict for JSON serialization
    def to_dict(obj):
        if hasattr(obj, '__dict__'):
            d = {}
            for k, v in obj.__dict__.items():
                if isinstance(v, list):
                    d[k] = [to_dict(i) for i in v]
                elif isinstance(v, dict):
                    d[k] = {kk: to_dict(vv) for kk, vv in v.items()}
                elif hasattr(v, '__dict__'):
                    d[k] = to_dict(v)
                else:
                    d[k] = v
            return d
        return obj

    result_dict = to_dict(result)

    # For JSON, optionally exclude per-block details
    if args.json and not args.details:
        result_dict.pop('blocks', None)

    # Output
    if args.json:
        output = json.dumps(result_dict, indent=2)
    else:
        # Human-readable output
        lines = []
        lines.append("I/O Analysis")
        lines.append("=" * 50)
        lines.append(f"Total Blocks Analyzed: {result.block_count}")
        lines.append("")

        lines.append("Overall Totals:")
        lines.append(f"  Event Inputs:    {result.totals.event_inputs:,}")
        lines.append(f"  Event Outputs:   {result.totals.event_outputs:,}")
        lines.append(f"  Data Inputs:     {result.totals.data_inputs:,}")
        lines.append(f"  Data Outputs:    {result.totals.data_outputs:,}")
        lines.append(f"  Internal Vars:   {result.totals.internal_vars:,}")
        lines.append(f"  Adapters:        {result.totals.adapters:,}")
        lines.append(f"  Total I/O:       {result.totals.total_io:,}")
        lines.append("")

        lines.append("By Block Type:")
        for bt, totals in sorted(result.by_block_type.items()):
            lines.append(f"  {bt}:")
            lines.append(f"    EI={totals.event_inputs}, EO={totals.event_outputs}, "
                        f"DI={totals.data_inputs}, DO={totals.data_outputs}, "
                        f"Int={totals.internal_vars}, Adp={totals.adapters}")
        lines.append("")

        lines.append("By Namespace:")
        for ns, totals in sorted(result.by_namespace.items()):
            lines.append(f"  {ns}:")
            lines.append(f"    EI={totals.event_inputs}, EO={totals.event_outputs}, "
                        f"DI={totals.data_inputs}, DO={totals.data_outputs}")
        lines.append("")

        lines.append("Largest Blocks (by I/O count):")
        for block in result.largest_blocks:
            lines.append(f"  {block.name} ({block.block_type}): {block.total_io} I/O")
            lines.append(f"    EI={block.event_inputs}, EO={block.event_outputs}, "
                        f"DI={block.data_inputs}, DO={block.data_outputs}, "
                        f"Int={block.internal_vars}")
        lines.append("")

        if result.complexity_warnings:
            lines.append("Complexity Warnings:")
            for w in result.complexity_warnings:
                lines.append(f"  {w}")
            lines.append("")

        if result.warnings:
            lines.append("Parse Warnings:")
            for w in result.warnings:
                lines.append(f"  - {w}")

        output = '\n'.join(lines)

    if args.output:
        args.output.write_text(output, encoding='utf-8')
    else:
        print(output)

    # Exit code
    if result.complexity_warnings or result.warnings:
        sys.exit(10)
    sys.exit(0)


if __name__ == '__main__':
    main()
