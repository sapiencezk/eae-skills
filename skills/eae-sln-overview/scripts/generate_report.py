#!/usr/bin/env python3
"""
EAE Report Generator - Generate formatted reports from analysis data

Generates markdown, JSON, or summary text reports from project analysis.

Exit Codes:
    0: Report generated successfully
    1: Error generating report

Usage:
    python generate_report.py --data analysis.json --format markdown
    python generate_report.py --data analysis.json --format json --output report.json
    python generate_report.py --data analysis.json --format summary
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


def generate_ascii_network_diagram(topology: Dict[str, Any]) -> str:
    """Generate ASCII art network diagram from topology data."""
    lines = []

    devices = topology.get('devices', [])
    if not devices:
        return "  No devices configured"

    # Simple horizontal layout
    lines.append("                    ┌─────────────────┐")
    lines.append("                    │   HMI / SCADA   │")
    lines.append("                    │    (OPC-UA)     │")
    lines.append("                    └────────┬────────┘")
    lines.append("                             │")

    # Calculate device width
    num_devices = len(devices)
    if num_devices == 0:
        return '\n'.join(lines)

    # Draw connection line
    if num_devices > 1:
        connector = "─" * 20
        lines.append(f"        ┌{'─' * 12}┼{'─' * 12}┐")

    # Draw devices
    device_boxes = []
    for device in devices[:4]:  # Max 4 devices
        name = device.get('name', 'Unknown')[:15]
        dtype = device.get('type', '')[:15]
        resources = len(device.get('resources', []))
        cats = device.get('total_cat_instances', 0)

        box = [
            f"┌{'─' * 17}┐",
            f"│ {name:^15} │",
            f"│ {dtype:^15} │",
            f"│ Res:{resources:2} CAT:{cats:3} │",
            f"└{'─' * 17}┘"
        ]
        device_boxes.append(box)

    # Print device boxes side by side
    if device_boxes:
        for row in range(5):
            row_str = "  ".join(box[row] for box in device_boxes)
            lines.append(f"  {row_str}")

    return '\n'.join(lines)


def generate_protocol_table(protocols: Dict[str, Any]) -> str:
    """Generate protocol summary table."""
    lines = []
    lines.append("| Protocol | Configured | Usage Count | Notes |")
    lines.append("|----------|------------|-------------|-------|")

    # Use library-based detection as primary, fall back to config-based
    has_opcua = protocols.get('has_opcua', False)
    has_modbus = protocols.get('has_modbus', False)
    has_ethernet_ip = protocols.get('has_ethernet_ip', False)
    opcua_count = protocols.get('opcua_usage_count', 0)
    modbus_count = protocols.get('modbus_usage_count', 0)
    eip_count = protocols.get('ethernet_ip_usage_count', 0)

    # OPC-UA Server
    opc_server = protocols.get('opc_ua_server')
    if has_opcua or opc_server:
        nodes = opc_server.get('exposed_nodes', 0) if opc_server else 0
        over = " (over-exposed)" if opc_server and opc_server.get('over_exposed') else ""
        lines.append(f"| OPC-UA Server | Yes | {opcua_count} refs | {nodes} nodes{over} |")
    else:
        lines.append("| OPC-UA Server | No | - | - |")

    # OPC-UA Clients
    clients = protocols.get('opc_ua_clients', [])
    if clients:
        lines.append(f"| OPC-UA Client | Yes | {len(clients)} | Cross-device comm |")

    # Modbus
    masters = protocols.get('modbus_masters', [])
    slaves = protocols.get('modbus_slaves', [])
    if has_modbus or masters:
        lines.append(f"| Modbus | Yes | {modbus_count} refs | {len(masters)} masters, {len(slaves)} slaves |")
    else:
        lines.append("| Modbus | No | - | - |")

    # EtherNet/IP
    eip = protocols.get('ethernet_ip_scanners', [])
    if has_ethernet_ip or eip:
        lines.append(f"| EtherNet/IP | Yes | {eip_count} refs | {len(eip)} scanners |")
    else:
        lines.append("| EtherNet/IP | No | - | - |")

    # Other protocols
    other = protocols.get('other_protocols', {})
    for proto, count in other.items():
        lines.append(f"| {proto} | Yes | {count} | - |")

    return '\n'.join(lines)


def generate_library_table(libraries: Dict[str, Any]) -> str:
    """Generate library summary tables."""
    lines = []

    # SE Libraries
    lines.append("### SE Standard Libraries")
    lines.append("")
    lines.append("| Library | Version | Category | Used |")
    lines.append("|---------|---------|----------|------|")

    se_libs = libraries.get('se_libraries', [])
    for lib in sorted(se_libs, key=lambda x: x.get('name', '')):
        if lib.get('is_se_library'):
            name = lib.get('name', '')
            version = lib.get('version', '-')
            category = lib.get('category', 'unknown')
            used = lib.get('blocks_used', 0)
            lines.append(f"| {name} | {version} | {category} | {used}x |")

    lines.append("")

    # Custom Libraries
    custom_libs = libraries.get('custom_libraries', [])
    if custom_libs:
        lines.append("### Custom Libraries")
        lines.append("")
        lines.append("| Library | Namespace | Blocks | Dependencies |")
        lines.append("|---------|-----------|--------|--------------|")

        for lib in custom_libs:
            name = lib.get('name', '')
            namespace = lib.get('namespace', '')
            blocks = lib.get('block_count', 0)
            deps = ', '.join(lib.get('depends_on', [])[:3])
            if len(lib.get('depends_on', [])) > 3:
                deps += '...'
            lines.append(f"| {name} | {namespace} | {blocks} | {deps} |")

    return '\n'.join(lines)


def generate_io_table(io_data: Dict[str, Any]) -> str:
    """Generate I/O summary table."""
    lines = []

    totals = io_data.get('totals', {})

    lines.append("| Category | Count |")
    lines.append("|----------|-------|")
    lines.append(f"| Event Inputs | {totals.get('event_inputs', 0):,} |")
    lines.append(f"| Event Outputs | {totals.get('event_outputs', 0):,} |")
    lines.append(f"| Data Inputs | {totals.get('data_inputs', 0):,} |")
    lines.append(f"| Data Outputs | {totals.get('data_outputs', 0):,} |")
    lines.append(f"| Internal Variables | {totals.get('internal_vars', 0):,} |")
    lines.append(f"| Adapters | {totals.get('adapters', 0):,} |")
    lines.append(f"| **Total I/O** | **{totals.get('total_io', 0):,}** |")

    return '\n'.join(lines)


def generate_isa88_tree(isa88: Dict[str, Any]) -> str:
    """Generate ISA88 hierarchy tree."""
    lines = []

    if not isa88.get('configured'):
        return "ISA88 hierarchy not configured"

    def format_asset(asset: Dict[str, Any], indent: int = 0) -> List[str]:
        result = []
        prefix = "  " * indent
        connector = "└── " if indent > 0 else ""

        name = asset.get('name', 'Unknown')
        atype = asset.get('asset_type', '')
        cat = asset.get('cat_link', '')

        type_label = f"[{atype}]" if atype else ""
        cat_label = f" -> {cat}" if cat else ""

        result.append(f"{prefix}{connector}{name} {type_label}{cat_label}")

        for child in asset.get('children', []):
            result.extend(format_asset(child, indent + 1))

        return result

    for root in isa88.get('root_assets', []):
        lines.extend(format_asset(root))

    return '\n'.join(lines) if lines else "No assets defined"


def generate_quality_table(quality: Dict[str, Any]) -> str:
    """Generate quality score breakdown table."""
    lines = []

    lines.append(f"**Overall: {quality.get('overall_score', 0)}/{quality.get('max_score', 100)} ({quality.get('percentage', 0):.1f}%) - Grade {quality.get('grade', 'F')}**")
    lines.append("")
    lines.append("| Dimension | Score | Max | Status |")
    lines.append("|-----------|-------|-----|--------|")

    for dim in quality.get('dimensions', []):
        name = dim.get('name', '')
        score = dim.get('score', 0)
        max_score = dim.get('max_score', 0)
        pct = dim.get('percentage', 0)

        if pct >= 70:
            status = "PASS"
        elif pct >= 50:
            status = "WARN"
        else:
            status = "FAIL"

        lines.append(f"| {name} | {score} | {max_score} | {status} |")

    return '\n'.join(lines)


def generate_markdown_report(data: Dict[str, Any]) -> str:
    """Generate full markdown report."""
    lines = []

    project_name = data.get('solution', {}).get('solution_name', 'Unknown Project')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    lines.append(f"# EAE Project Overview: {project_name}")
    lines.append("")
    lines.append(f"**Generated**: {timestamp}")
    lines.append("**Analyzed by**: eae-sln-overview v1.0.0")
    lines.append("")

    # Project Description (if available)
    description = data.get('description', {})
    if description.get('detailed_description'):
        lines.append("## About This Project")
        lines.append("")
        lines.append(description.get('detailed_description', ''))
        source = description.get('source', 'unknown')
        confidence = description.get('confidence', 0)
        lines.append("")
        lines.append(f"*Description source: {source} (confidence: {confidence:.0%})*")
        lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")

    solution = data.get('solution', {})
    topology = data.get('topology', {})
    io_data = data.get('io', {})
    quality = data.get('quality', {})
    eae_version = solution.get('eae_version', '')

    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    if eae_version:
        lines.append(f"| **EAE Version** | {eae_version} |")
    lines.append(f"| **Quality Score** | {quality.get('overall_score', 0)}/{quality.get('max_score', 100)} ({quality.get('grade', 'F')}) |")
    lines.append(f"| **Projects** | {solution.get('total_projects', 0)} |")
    lines.append(f"| **Devices** | {topology.get('total_devices', 0)} |")
    lines.append(f"| **Function Blocks** | {solution.get('total_blocks', 0)} |")
    lines.append(f"| **I/O Points** | {io_data.get('totals', {}).get('total_io', 0):,} |")
    lines.append("")

    # Network Architecture
    lines.append("## Network Architecture")
    lines.append("")
    lines.append("```")
    lines.append(generate_ascii_network_diagram(topology))
    lines.append("```")
    lines.append("")

    # Devices table
    if topology.get('devices'):
        lines.append("### Devices")
        lines.append("")
        lines.append("| Device | Type | Resources | CAT Instances |")
        lines.append("|--------|------|-----------|---------------|")
        for device in topology.get('devices', []):
            name = device.get('name', '')
            dtype = device.get('type', '')
            resources = len(device.get('resources', []))
            cats = device.get('total_cat_instances', 0)
            lines.append(f"| {name} | {dtype} | {resources} | {cats} |")
        lines.append("")

    # Protocol Inventory
    lines.append("## Protocol Inventory")
    lines.append("")
    lines.append(generate_protocol_table(data.get('protocols', {})))
    lines.append("")

    # Library Matrix
    lines.append("## Library Matrix")
    lines.append("")
    lines.append(generate_library_table(data.get('libraries', {})))
    lines.append("")

    # I/O Summary
    lines.append("## I/O Summary")
    lines.append("")
    lines.append(generate_io_table(io_data))
    lines.append("")

    # ISA88 Hierarchy
    lines.append("## ISA88 Hierarchy")
    lines.append("")
    isa88 = data.get('isa88', {})
    if isa88.get('configured'):
        lines.append(f"**Coverage**: {isa88.get('cat_coverage', 0):.1f}% of CATs linked to assets")
        lines.append("")
        lines.append("```")
        lines.append(generate_isa88_tree(isa88))
        lines.append("```")
    else:
        lines.append("*ISA88 hierarchy not configured*")
    lines.append("")

    # Quality Score
    lines.append("## Quality Score Breakdown")
    lines.append("")
    lines.append(generate_quality_table(quality))
    lines.append("")

    # Recommendations
    if quality.get('top_recommendations'):
        lines.append("### Recommendations")
        lines.append("")
        for i, rec in enumerate(quality.get('top_recommendations', []), 1):
            lines.append(f"{i}. {rec}")
        lines.append("")

    # Warnings
    all_warnings = []
    for section in ['solution', 'topology', 'protocols', 'libraries', 'io', 'isa88', 'quality']:
        section_data = data.get(section, {})
        all_warnings.extend(section_data.get('warnings', []))

    if all_warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in all_warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by eae-sln-overview skill*")

    return '\n'.join(lines)


def generate_summary_report(data: Dict[str, Any]) -> str:
    """Generate brief summary report."""
    lines = []

    project_name = data.get('solution', {}).get('solution_name', 'Unknown')
    quality = data.get('quality', {})
    solution = data.get('solution', {})
    topology = data.get('topology', {})
    description = data.get('description', {})

    eae_version = solution.get('eae_version', '')

    lines.append(f"Project: {project_name}")

    # Add short description if available
    short_desc = description.get('short_description', '')
    if short_desc:
        lines.append(f"Description: {short_desc}")
    if eae_version:
        lines.append(f"EAE Version: {eae_version}")
    lines.append(f"Quality: {quality.get('overall_score', 0)}/{quality.get('max_score', 100)} (Grade {quality.get('grade', 'F')})")
    lines.append(f"Projects: {solution.get('total_projects', 0)}")
    lines.append(f"Blocks: {solution.get('total_blocks', 0)}")

    # I/O summary
    io_data = data.get('io', {})
    io_totals = io_data.get('totals', {})
    lines.append(f"I/O Points: {io_totals.get('total_io', 0):,}")

    # Libraries with names
    libraries = data.get('libraries', {})
    se_libs = libraries.get('se_libraries', [])
    se_lib_names = [lib.get('name', '') for lib in se_libs if lib.get('is_se_library')]
    custom_libs = libraries.get('custom_libraries', [])
    custom_lib_names = [lib.get('name', '') for lib in custom_libs]

    lines.append(f"SE Libraries ({len(se_lib_names)}): {', '.join(sorted(se_lib_names)) if se_lib_names else 'None'}")
    if custom_lib_names:
        lines.append(f"Custom Libraries ({len(custom_lib_names)}): {', '.join(sorted(custom_lib_names))}")

    # Protocols - use library-based detection
    protocols = data.get('protocols') or {}
    proto_list = []

    # Use library-based detection as primary source
    if protocols.get('has_opcua'):
        count = protocols.get('opcua_usage_count', 0)
        proto_list.append(f"OPC-UA ({count} refs)")
    if protocols.get('has_modbus'):
        count = protocols.get('modbus_usage_count', 0)
        proto_list.append(f"Modbus ({count} refs)")
    if protocols.get('has_ethernet_ip'):
        count = protocols.get('ethernet_ip_usage_count', 0)
        proto_list.append(f"EtherNet/IP ({count} refs)")

    # Add other protocols
    other_protos = protocols.get('other_protocols', {})
    for proto in other_protos:
        proto_list.append(proto)

    lines.append(f"Protocols: {', '.join(proto_list) if proto_list else 'None'}")

    # ISA88 System/Subsystem hierarchy
    isa88 = data.get('isa88', {})
    if isa88.get('configured'):
        system_name = isa88.get('system_name', 'System')
        subsystems = isa88.get('subsystems', [])
        subsystem_names = [s.get('name', '') for s in subsystems]
        lines.append(f"System: {system_name}")
        lines.append(f"Subsystems ({len(subsystems)}): {', '.join(subsystem_names) if subsystem_names else 'None'}")

        # Equipment modules count
        total_equipment = sum(len(s.get('equipment_modules', [])) for s in subsystems)
        if total_equipment > 0:
            lines.append(f"Equipment Modules: {total_equipment}")
    else:
        lines.append(f"ISA88: Not configured")

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Generate EAE project reports',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--data', type=Path, required=True,
                        help='Path to analysis data JSON file')
    parser.add_argument('--format', choices=['markdown', 'json', 'summary'],
                        default='markdown', help='Output format')
    parser.add_argument('--output', type=Path, help='Output file path')

    args = parser.parse_args()

    if not args.data.exists():
        print(f"Error: Data file not found: {args.data}", file=sys.stderr)
        sys.exit(1)

    # Load data
    try:
        data = json.loads(args.data.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in data file: {e}", file=sys.stderr)
        sys.exit(1)

    # Generate report
    if args.format == 'markdown':
        output = generate_markdown_report(data)
    elif args.format == 'json':
        output = json.dumps(data, indent=2)
    else:  # summary
        output = generate_summary_report(data)

    # Write output
    if args.output:
        args.output.write_text(output, encoding='utf-8')
    else:
        print(output)

    sys.exit(0)


if __name__ == '__main__':
    main()
