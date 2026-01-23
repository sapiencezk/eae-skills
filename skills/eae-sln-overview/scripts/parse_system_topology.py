#!/usr/bin/env python3
"""
EAE System Topology Parser - Parse System.cfg for devices and resources

Extracts device topology, resource allocation, and CAT instances from EAE system configuration.

Exit Codes:
    0: Parsing successful
    1: System configuration not found or parsing error
   10: Partial success with warnings

Usage:
    python parse_system_topology.py --project-dir /path/to/eae/project
    python parse_system_topology.py --system-dir /path/to/IEC61499/System
    python parse_system_topology.py --project-dir /path/to/project --json
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Set


@dataclass
class CATInstance:
    """A CAT instance in the system."""
    id: str
    name: str
    type_name: str
    namespace: str
    device_id: Optional[str] = None
    resource_id: Optional[str] = None


@dataclass
class Resource:
    """A runtime resource on a device."""
    id: str
    name: str
    type: str
    cat_instances: List[CATInstance] = field(default_factory=list)


@dataclass
class Device:
    """A device in the system."""
    id: str
    name: str
    type: str
    namespace: str
    resources: List[Resource] = field(default_factory=list)
    total_cat_instances: int = 0


@dataclass
class Application:
    """An application in the system."""
    id: str
    name: str
    cat_instances: List[CATInstance] = field(default_factory=list)


@dataclass
class SystemTopology:
    """Complete system topology."""
    system_name: str
    system_path: str
    devices: List[Device]
    applications: List[Application]
    total_devices: int
    total_resources: int
    total_cat_instances: int
    device_types: Dict[str, int]  # Count by device type
    warnings: List[str] = field(default_factory=list)


def find_system_dir(project_dir: Path) -> Optional[Path]:
    """Find the IEC61499/System directory."""
    system_dir = project_dir / 'IEC61499' / 'System'
    if system_dir.exists():
        return system_dir

    # Try to find System directory elsewhere
    for subdir in project_dir.rglob('System'):
        if (subdir / 'System.cfg').exists() or (subdir / 'System.sys').exists():
            return subdir

    return None


def parse_system_cfg(cfg_path: Path) -> Dict[str, Any]:
    """Parse System.cfg file for device and resource information."""
    result = {
        'devices': {},
        'resources': {},
        'applications': {},
        'cat_instances': [],
        'warnings': []
    }

    try:
        tree = ET.parse(cfg_path)
        root = tree.getroot()
    except ET.ParseError as e:
        result['warnings'].append(f"XML parse error in System.cfg: {e}")
        return result

    # Parse Device elements
    for device_elem in root.findall('.//Device'):
        device_id = device_elem.get('ID', '')
        device_name = device_elem.get('Name', '')
        device_type = device_elem.get('Type', '')

        # Extract namespace from type if present
        namespace = ''
        if '::' in device_type:
            namespace, device_type = device_type.rsplit('::', 1)

        result['devices'][device_id] = {
            'id': device_id,
            'name': device_name,
            'type': device_type,
            'namespace': namespace,
            'resources': []
        }

        # Parse Resource elements within device
        for resource_elem in device_elem.findall('.//Resource'):
            res_id = resource_elem.get('ID', '')
            res_name = resource_elem.get('Name', '')
            res_type = resource_elem.get('Type', '')

            result['resources'][res_id] = {
                'id': res_id,
                'name': res_name,
                'type': res_type,
                'device_id': device_id,
                'cat_instances': []
            }
            result['devices'][device_id]['resources'].append(res_id)

    # Parse Application elements
    for app_elem in root.findall('.//Application'):
        app_id = app_elem.get('ID', '')
        app_name = app_elem.get('Name', '')

        result['applications'][app_id] = {
            'id': app_id,
            'name': app_name,
            'cat_instances': []
        }

    return result


def parse_system_sys(sys_path: Path, cfg_data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse System.sys file for CAT instance mappings."""
    result = cfg_data.copy()

    try:
        tree = ET.parse(sys_path)
        root = tree.getroot()
    except ET.ParseError as e:
        result['warnings'].append(f"XML parse error in System.sys: {e}")
        return result

    # Parse CATType elements for instances
    for cat_type_elem in root.findall('.//CATType'):
        cat_type_name = cat_type_elem.get('Name', '')
        cat_namespace = cat_type_elem.get('Namespace', '')

        for inst_elem in cat_type_elem.findall('.//Inst'):
            inst_id = inst_elem.get('ID', '')
            inst_name = inst_elem.get('Name', '')
            app_id = inst_elem.get('App', '')
            map_value = inst_elem.get('Map', '')

            # Parse Map to get device and resource IDs
            device_id = None
            resource_id = None
            if map_value:
                # Map format: "device_guid.resource_id;"
                parts = map_value.split('.')
                if len(parts) >= 1:
                    device_id = parts[0]
                if len(parts) >= 2:
                    resource_id = parts[1].rstrip(';')

            cat_instance = {
                'id': inst_id,
                'name': inst_name,
                'type_name': cat_type_name,
                'namespace': cat_namespace,
                'device_id': device_id,
                'resource_id': resource_id
            }

            result['cat_instances'].append(cat_instance)

            # Add to application if mapped
            if app_id and app_id in result['applications']:
                result['applications'][app_id]['cat_instances'].append(inst_id)

            # Add to resource if mapped
            if resource_id and resource_id in result['resources']:
                result['resources'][resource_id]['cat_instances'].append(inst_id)

    return result


def parse_hcf_files(system_dir: Path, cfg_data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse .hcf files to get additional device properties."""
    result = cfg_data.copy()

    for hcf_path in system_dir.rglob('*.hcf'):
        try:
            tree = ET.parse(hcf_path)
            root = tree.getroot()

            # Extract device ID from filename (usually GUID)
            device_guid = hcf_path.stem

            # Look for device information
            for device_elem in root.findall('.//Device'):
                device_name = device_elem.get('Name', '')
                device_type = device_elem.get('Type', '')

                if device_guid in result['devices']:
                    # Update existing device info
                    if device_name:
                        result['devices'][device_guid]['name'] = device_name
                    if device_type:
                        result['devices'][device_guid]['type'] = device_type

        except ET.ParseError:
            result['warnings'].append(f"Could not parse HCF file: {hcf_path.name}")

    return result


def analyze_topology(project_dir: Path, system_dir: Optional[Path] = None) -> SystemTopology:
    """Analyze complete system topology."""
    warnings = []

    # Find system directory
    if system_dir is None:
        system_dir = find_system_dir(project_dir)

    if system_dir is None:
        return SystemTopology(
            system_name='Unknown',
            system_path=str(project_dir),
            devices=[],
            applications=[],
            total_devices=0,
            total_resources=0,
            total_cat_instances=0,
            device_types={},
            warnings=['System directory not found']
        )

    # Parse System.cfg
    cfg_path = system_dir / 'System.cfg'
    if cfg_path.exists():
        data = parse_system_cfg(cfg_path)
    else:
        data = {
            'devices': {},
            'resources': {},
            'applications': {},
            'cat_instances': [],
            'warnings': ['System.cfg not found']
        }

    # Parse System.sys
    sys_path = system_dir / 'System.sys'
    if sys_path.exists():
        data = parse_system_sys(sys_path, data)
    else:
        data['warnings'].append('System.sys not found')

    # Parse HCF files
    data = parse_hcf_files(system_dir, data)

    warnings.extend(data.get('warnings', []))

    # Build device list
    devices = []
    device_types = {}
    total_resources = 0

    for device_id, device_data in data['devices'].items():
        resources = []
        device_cat_count = 0

        for res_id in device_data.get('resources', []):
            res_data = data['resources'].get(res_id, {})
            cat_instances = []

            for cat_data in data['cat_instances']:
                if cat_data.get('resource_id') == res_id or cat_data.get('device_id') == device_id:
                    cat_instances.append(CATInstance(
                        id=cat_data['id'],
                        name=cat_data['name'],
                        type_name=cat_data['type_name'],
                        namespace=cat_data['namespace'],
                        device_id=device_id,
                        resource_id=res_id
                    ))

            resources.append(Resource(
                id=res_data.get('id', res_id),
                name=res_data.get('name', ''),
                type=res_data.get('type', ''),
                cat_instances=cat_instances
            ))

            device_cat_count += len(cat_instances)

        total_resources += len(resources)

        device = Device(
            id=device_id,
            name=device_data['name'],
            type=device_data['type'],
            namespace=device_data['namespace'],
            resources=resources,
            total_cat_instances=device_cat_count
        )
        devices.append(device)

        # Count device types
        device_type = device_data['type']
        device_types[device_type] = device_types.get(device_type, 0) + 1

    # Build application list
    applications = []
    for app_id, app_data in data['applications'].items():
        cat_instances = []
        for cat_data in data['cat_instances']:
            if cat_data['id'] in app_data.get('cat_instances', []):
                cat_instances.append(CATInstance(
                    id=cat_data['id'],
                    name=cat_data['name'],
                    type_name=cat_data['type_name'],
                    namespace=cat_data['namespace']
                ))

        applications.append(Application(
            id=app_id,
            name=app_data['name'],
            cat_instances=cat_instances
        ))

    return SystemTopology(
        system_name=system_dir.parent.name if system_dir else 'Unknown',
        system_path=str(system_dir),
        devices=devices,
        applications=applications,
        total_devices=len(devices),
        total_resources=total_resources,
        total_cat_instances=len(data['cat_instances']),
        device_types=device_types,
        warnings=warnings
    )


def main():
    parser = argparse.ArgumentParser(
        description='Parse EAE system topology',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--project-dir', type=Path, help='Path to EAE project root directory')
    parser.add_argument('--system-dir', type=Path, help='Path to IEC61499/System directory')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--output', type=Path, help='Output file path')

    args = parser.parse_args()

    # Determine directories
    if args.system_dir:
        system_dir = args.system_dir
        project_dir = system_dir.parent.parent
    elif args.project_dir:
        project_dir = args.project_dir
        system_dir = None
    else:
        parser.error('Either --project-dir or --system-dir must be specified')

    if not project_dir.exists():
        print(f"Error: Project directory not found: {project_dir}", file=sys.stderr)
        sys.exit(1)

    # Analyze topology
    result = analyze_topology(project_dir, system_dir)

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

    # Output
    if args.json:
        output = json.dumps(result_dict, indent=2)
    else:
        # Human-readable output
        lines = []
        lines.append(f"System: {result.system_name}")
        lines.append(f"Path: {result.system_path}")
        lines.append(f"Devices: {result.total_devices}")
        lines.append(f"Resources: {result.total_resources}")
        lines.append(f"CAT Instances: {result.total_cat_instances}")
        lines.append("")

        lines.append("Device Types:")
        for dtype, count in result.device_types.items():
            lines.append(f"  {dtype}: {count}")
        lines.append("")

        lines.append("Devices:")
        for device in result.devices:
            lines.append(f"  {device.name} ({device.type})")
            lines.append(f"    ID: {device.id}")
            lines.append(f"    Namespace: {device.namespace}")
            lines.append(f"    Resources: {len(device.resources)}")
            lines.append(f"    CAT Instances: {device.total_cat_instances}")
            for res in device.resources:
                lines.append(f"      Resource: {res.name} ({res.type})")
                lines.append(f"        CATs: {len(res.cat_instances)}")
            lines.append("")

        if result.applications:
            lines.append("Applications:")
            for app in result.applications:
                lines.append(f"  {app.name}")
                lines.append(f"    ID: {app.id}")
                lines.append(f"    CAT Instances: {len(app.cat_instances)}")
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
    if result.warnings:
        sys.exit(10)
    sys.exit(0)


if __name__ == '__main__':
    main()
