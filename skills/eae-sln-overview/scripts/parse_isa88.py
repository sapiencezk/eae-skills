#!/usr/bin/env python3
"""
EAE ISA88 Parser - Parse System.sys for ISA88 System/Subsystem hierarchy

Extracts ISA88 physical model hierarchy from EAE system configuration:
- System (top level from System.sys)
- Subsystems (from Device.FolderPath attribute and CATType instances)
- Equipment Modules (from FBNetwork in CAT .fbt files)

Exit Codes:
    0: Parsing successful
    1: System configuration not found or parsing error
   10: Partial success with warnings

Usage:
    python parse_isa88.py --project-dir /path/to/eae/project
    python parse_isa88.py --project-dir /path/to/project --json
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Set


@dataclass
class EquipmentModule:
    """An equipment module within a subsystem."""
    name: str
    type_name: str
    namespace: str
    fb_id: str = ''


@dataclass
class Subsystem:
    """A subsystem (CAT instance) in the ISA88 hierarchy."""
    name: str
    type_name: str
    namespace: str
    instance_id: str
    app_id: str
    resource_map: str
    equipment_modules: List[EquipmentModule] = field(default_factory=list)


@dataclass
class ISA88Hierarchy:
    """Complete ISA88 hierarchy."""
    system_name: str
    system_path: str
    subsystems: List[Subsystem]
    folder_path: List[str]  # From System.Device.FolderPath
    total_subsystems: int
    total_equipment_modules: int
    configured: bool
    warnings: List[str] = field(default_factory=list)


def find_system_dir(project_dir: Path) -> Optional[Path]:
    """Find the IEC61499/System directory."""
    system_dir = project_dir / 'IEC61499' / 'System'
    if system_dir.exists():
        return system_dir

    for subdir in project_dir.rglob('System'):
        if (subdir / 'System.sys').exists() or (subdir / 'System.cfg').exists():
            return subdir

    return None


def parse_system_sys(sys_path: Path) -> Dict[str, Any]:
    """Parse System.sys for subsystem definitions."""
    result = {
        'system_name': 'System',
        'folder_path': [],
        'subsystems': [],
        'warnings': []
    }

    try:
        tree = ET.parse(sys_path)
        root = tree.getroot()
    except ET.ParseError as e:
        result['warnings'].append(f"XML parse error in System.sys: {e}")
        return result

    # Get system name from root element
    system_name = root.get('Name', 'System')
    result['system_name'] = system_name

    # Look for Device.FolderPath attribute which lists subsystems
    for attr in root.findall('.//Attribute'):
        attr_name = attr.get('Name', '')
        if 'FolderPath' in attr_name or 'Device.FolderPath' in attr_name:
            value = attr.get('Value', '')
            if value:
                # FolderPath is comma-separated list of subsystem names
                result['folder_path'] = [s.strip() for s in value.split(',') if s.strip()]

    # Parse CATType elements for subsystem instances
    for cat_type in root.findall('.//CATType'):
        type_name = cat_type.get('Name', '')
        namespace = cat_type.get('Namespace', '')

        for inst in cat_type.findall('.//Inst'):
            inst_id = inst.get('ID', '')
            inst_name = inst.get('Name', '')
            app_id = inst.get('App', '')
            map_value = inst.get('Map', '')

            # Skip if this doesn't look like a top-level subsystem
            # Top-level subsystems typically have simple names without underscores at start
            # and match entries in folder_path
            is_subsystem = (
                type_name in result['folder_path'] or
                inst_name in result['folder_path'] or
                (not inst_name.startswith('_') and type_name == inst_name.split('_')[-1])
            )

            if type_name and inst_name:
                result['subsystems'].append({
                    'name': inst_name,
                    'type_name': type_name,
                    'namespace': namespace,
                    'instance_id': inst_id,
                    'app_id': app_id,
                    'resource_map': map_value,
                    'is_top_level': is_subsystem
                })

    return result


def parse_system_cfg(cfg_path: Path, sys_data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse System.cfg for additional CAT instance information."""
    result = sys_data.copy()

    try:
        tree = ET.parse(cfg_path)
        root = tree.getroot()
    except ET.ParseError as e:
        result['warnings'].append(f"XML parse error in System.cfg: {e}")
        return result

    # Parse CATType elements (similar structure to System.sys)
    existing_names = {s['name'] for s in result['subsystems']}

    for cat_type in root.findall('.//CATType'):
        type_name = cat_type.get('Name', '')
        namespace = cat_type.get('Namespace', '')

        for inst in cat_type.findall('.//Inst'):
            inst_name = inst.get('Name', '')

            # Only add if not already found
            if inst_name and inst_name not in existing_names:
                inst_id = inst.get('ID', '')
                app_id = inst.get('App', '')
                map_value = inst.get('Map', '')

                is_subsystem = (
                    type_name in result['folder_path'] or
                    inst_name in result['folder_path']
                )

                result['subsystems'].append({
                    'name': inst_name,
                    'type_name': type_name,
                    'namespace': namespace,
                    'instance_id': inst_id,
                    'app_id': app_id,
                    'resource_map': map_value,
                    'is_top_level': is_subsystem
                })
                existing_names.add(inst_name)

    return result


def parse_cat_fbt_for_equipment(fbt_path: Path) -> List[EquipmentModule]:
    """Parse a CAT .fbt file to extract equipment modules from FBNetwork."""
    equipment = []

    try:
        tree = ET.parse(fbt_path)
        root = tree.getroot()
    except ET.ParseError:
        return equipment

    # Look for FBNetwork element
    fb_network = root.find('.//FBNetwork')
    if fb_network is None:
        return equipment

    # Extract FB instances from FBNetwork
    for fb in fb_network.findall('FB'):
        fb_name = fb.get('Name', '')
        fb_type = fb.get('Type', '')
        fb_namespace = fb.get('Namespace', '')
        fb_id = fb.get('ID', '')

        if fb_name and fb_type:
            equipment.append(EquipmentModule(
                name=fb_name,
                type_name=fb_type,
                namespace=fb_namespace,
                fb_id=fb_id
            ))

    return equipment


def find_subsystem_equipment(project_dir: Path, subsystem_type: str, namespace: str) -> List[EquipmentModule]:
    """Find equipment modules for a subsystem by locating its .fbt file."""
    equipment = []

    # Look for the subsystem's .fbt file
    # Pattern: {namespace}/{subsystem_type}/{subsystem_type}.fbt or similar
    search_patterns = [
        f'**/{subsystem_type}/{subsystem_type}.fbt',
        f'**/{subsystem_type}.fbt',
        f'**/IEC61499/{subsystem_type}/{subsystem_type}.fbt',
    ]

    for pattern in search_patterns:
        fbt_files = list(project_dir.glob(pattern))
        for fbt_path in fbt_files:
            equipment = parse_cat_fbt_for_equipment(fbt_path)
            if equipment:
                return equipment

    return equipment


def identify_top_level_subsystems(sys_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Identify which CAT instances are top-level subsystems."""
    subsystems = sys_data.get('subsystems', [])
    folder_path = sys_data.get('folder_path', [])

    # If folder_path is defined, use it to identify subsystems
    if folder_path:
        top_level = []
        for sub in subsystems:
            type_name = sub['type_name']
            # Check if this type matches a folder path entry
            if type_name in folder_path:
                # Find the instance for this type
                if sub not in top_level:
                    top_level.append(sub)
        return top_level

    # Fallback: identify subsystems by naming patterns
    # Top-level subsystems typically:
    # - Have instance names like "U25_JetSpray", "U27_JetMix"
    # - Or match their type name directly
    top_level = []
    type_counts = {}

    for sub in subsystems:
        type_name = sub['type_name']
        type_counts[type_name] = type_counts.get(type_name, 0) + 1

    # Types with only 1 instance are likely top-level subsystems
    for sub in subsystems:
        type_name = sub['type_name']
        namespace = sub['namespace']

        # Heuristics for identifying top-level subsystems:
        # 1. Only one instance of this type exists
        # 2. Namespace is 'Main' (not a library type)
        # 3. Type name starts with uppercase (CAT naming convention)
        if (type_counts[type_name] == 1 and
            namespace in ['Main', ''] and
            type_name and type_name[0].isupper()):
            top_level.append(sub)

    return top_level


def analyze_isa88(project_dir: Path) -> ISA88Hierarchy:
    """Analyze ISA88 hierarchy from System configuration."""
    warnings = []

    # Find system directory
    system_dir = find_system_dir(project_dir)

    if system_dir is None:
        return ISA88Hierarchy(
            system_name='Unknown',
            system_path=str(project_dir),
            subsystems=[],
            folder_path=[],
            total_subsystems=0,
            total_equipment_modules=0,
            configured=False,
            warnings=['System directory not found']
        )

    # Parse System.sys
    sys_path = system_dir / 'System.sys'
    if sys_path.exists():
        sys_data = parse_system_sys(sys_path)
    else:
        sys_data = {
            'system_name': 'System',
            'folder_path': [],
            'subsystems': [],
            'warnings': ['System.sys not found']
        }

    # Parse System.cfg for additional data
    cfg_path = system_dir / 'System.cfg'
    if cfg_path.exists():
        sys_data = parse_system_cfg(cfg_path, sys_data)

    warnings.extend(sys_data.get('warnings', []))

    # Identify top-level subsystems
    top_level_subs = identify_top_level_subsystems(sys_data)

    if not top_level_subs and sys_data.get('folder_path'):
        # Use folder_path directly if no instances found
        warnings.append("No CAT instances found matching folder path - using folder path as subsystem list")

    # Build subsystem objects with equipment modules
    subsystems = []
    total_equipment = 0

    for sub_data in top_level_subs:
        # Find equipment modules for this subsystem
        equipment = find_subsystem_equipment(
            project_dir,
            sub_data['type_name'],
            sub_data['namespace']
        )

        subsystem = Subsystem(
            name=sub_data['name'],
            type_name=sub_data['type_name'],
            namespace=sub_data['namespace'],
            instance_id=sub_data['instance_id'],
            app_id=sub_data['app_id'],
            resource_map=sub_data['resource_map'],
            equipment_modules=equipment
        )
        subsystems.append(subsystem)
        total_equipment += len(equipment)

    # If no subsystems found but folder_path exists, create placeholder subsystems
    if not subsystems and sys_data.get('folder_path'):
        for folder_name in sys_data['folder_path']:
            equipment = find_subsystem_equipment(project_dir, folder_name, 'Main')
            subsystem = Subsystem(
                name=folder_name,
                type_name=folder_name,
                namespace='Main',
                instance_id='',
                app_id='',
                resource_map='',
                equipment_modules=equipment
            )
            subsystems.append(subsystem)
            total_equipment += len(equipment)

    configured = len(subsystems) > 0 or len(sys_data.get('folder_path', [])) > 0

    return ISA88Hierarchy(
        system_name=sys_data['system_name'],
        system_path=str(system_dir),
        subsystems=subsystems,
        folder_path=sys_data.get('folder_path', []),
        total_subsystems=len(subsystems),
        total_equipment_modules=total_equipment,
        configured=configured,
        warnings=warnings
    )


def format_hierarchy_tree(hierarchy: ISA88Hierarchy) -> List[str]:
    """Format ISA88 hierarchy as a tree."""
    lines = []

    lines.append(f"System: {hierarchy.system_name}")

    for subsystem in hierarchy.subsystems:
        lines.append(f"  +-- Subsystem: {subsystem.name} ({subsystem.type_name})")

        for equip in subsystem.equipment_modules[:10]:  # Limit to first 10
            lines.append(f"      +-- {equip.name} ({equip.type_name})")

        if len(subsystem.equipment_modules) > 10:
            lines.append(f"      +-- ... and {len(subsystem.equipment_modules) - 10} more")

    return lines


def main():
    parser = argparse.ArgumentParser(
        description='Parse ISA88 hierarchy from EAE System configuration',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--project-dir', type=Path, required=True,
                        help='Path to EAE project root directory')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--output', type=Path, help='Output file path')

    args = parser.parse_args()

    if not args.project_dir.exists():
        print(f"Error: Project directory not found: {args.project_dir}", file=sys.stderr)
        sys.exit(1)

    # Analyze ISA88
    result = analyze_isa88(args.project_dir)

    # Convert to dict for JSON serialization
    def to_dict(obj):
        if hasattr(obj, '__dict__'):
            d = {}
            for k, v in obj.__dict__.items():
                if isinstance(v, list):
                    d[k] = [to_dict(i) for i in v]
                elif hasattr(v, '__dict__'):
                    d[k] = to_dict(v)
                else:
                    d[k] = v
            return d
        return obj

    result_dict = to_dict(result)

    # Output
    if args.json:
        output = json.dumps(result_dict, indent=2)
    else:
        # Human-readable output
        lines = []
        lines.append("ISA88 System/Subsystem Hierarchy")
        lines.append("=" * 50)
        lines.append(f"Configured: {result.configured}")
        lines.append(f"System Name: {result.system_name}")
        lines.append(f"System Path: {result.system_path}")
        lines.append(f"Total Subsystems: {result.total_subsystems}")
        lines.append(f"Total Equipment Modules: {result.total_equipment_modules}")
        lines.append("")

        if result.folder_path:
            lines.append(f"Folder Path: {', '.join(result.folder_path)}")
            lines.append("")

        if result.subsystems:
            lines.append("Hierarchy:")
            lines.extend(format_hierarchy_tree(result))
            lines.append("")

        if result.warnings:
            lines.append("Warnings:")
            for w in result.warnings:
                lines.append(f"  - {w}")

        output = '\n'.join(lines)

    if args.output:
        args.output.write_text(output, encoding='utf-8')
    else:
        print(output)

    # Exit code
    if not result.configured:
        sys.exit(10)
    if result.warnings:
        sys.exit(10)
    sys.exit(0)


if __name__ == '__main__':
    main()
