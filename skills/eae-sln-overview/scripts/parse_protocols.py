#!/usr/bin/env python3
"""
EAE Protocol Parser - Extract protocol configurations

Detects and analyzes OPC-UA, Modbus, EtherNet/IP and other protocol configurations.

Exit Codes:
    0: Parsing successful
    1: System configuration not found or parsing error
   10: Partial success with warnings

Usage:
    python parse_protocols.py --project-dir /path/to/eae/project
    python parse_protocols.py --system-dir /path/to/IEC61499/System
    python parse_protocols.py --project-dir /path/to/project --json
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class OpcUaServer:
    """OPC-UA server configuration."""
    enabled: bool
    exposed_nodes: int
    over_exposed: bool  # True if root is exposed
    namespace_uri: str = ''


@dataclass
class OpcUaClient:
    """OPC-UA client connection."""
    name: str
    endpoint: str
    security_mode: str = ''


@dataclass
class ModbusMaster:
    """Modbus master configuration."""
    name: str
    protocol: str  # TCP or RTU
    address: str
    slave_count: int


@dataclass
class ModbusSlave:
    """Modbus slave device."""
    name: str
    unit_id: int
    master_name: str


@dataclass
class EtherNetIPScanner:
    """EtherNet/IP scanner configuration."""
    name: str
    connections: int


@dataclass
class ProtocolSummary:
    """Summary of all protocols."""
    opc_ua_server: Optional[OpcUaServer]
    opc_ua_clients: List[OpcUaClient]
    modbus_masters: List[ModbusMaster]
    modbus_slaves: List[ModbusSlave]
    ethernet_ip_scanners: List[EtherNetIPScanner]
    other_protocols: Dict[str, int]  # Protocol name -> count
    total_protocols: int
    # Library-based detection (more reliable)
    has_opcua: bool = False
    has_modbus: bool = False
    has_ethernet_ip: bool = False
    opcua_usage_count: int = 0
    modbus_usage_count: int = 0
    ethernet_ip_usage_count: int = 0
    warnings: List[str] = field(default_factory=list)


def find_system_dir(project_dir: Path) -> Optional[Path]:
    """Find the IEC61499/System directory."""
    system_dir = project_dir / 'IEC61499' / 'System'
    if system_dir.exists():
        return system_dir

    for subdir in project_dir.rglob('System'):
        if (subdir / 'System.cfg').exists() or (subdir / 'System.opcua.xml').exists():
            return subdir

    return None


def parse_opcua_server(system_dir: Path) -> Optional[OpcUaServer]:
    """Parse System.opcua.xml for server configuration."""
    opcua_path = system_dir / 'System.opcua.xml'
    if not opcua_path.exists():
        return None

    try:
        tree = ET.parse(opcua_path)
        root = tree.getroot()
    except ET.ParseError:
        return None

    # Count exposed nodes
    exposed_count = 0
    over_exposed = False

    # Check for Exposed="True" attributes
    for elem in root.iter():
        exposed = elem.get('Exposed', '').lower()
        if exposed == 'true':
            exposed_count += 1

            # Check if this is a root-level exposure (over-exposed)
            depth = 0
            parent = elem
            while parent is not None:
                depth += 1
                parent = parent.find('..')
            if depth <= 2:
                over_exposed = True

    # Get namespace URI if present
    namespace_uri = root.get('NamespaceUri', '')

    return OpcUaServer(
        enabled=exposed_count > 0,
        exposed_nodes=exposed_count,
        over_exposed=over_exposed,
        namespace_uri=namespace_uri
    )


def parse_opcua_clients(system_dir: Path) -> List[OpcUaClient]:
    """Parse System.opcuaclient.xml for client connections."""
    clients = []
    opcua_client_path = system_dir / 'System.opcuaclient.xml'

    if not opcua_client_path.exists():
        return clients

    try:
        tree = ET.parse(opcua_client_path)
        root = tree.getroot()
    except ET.ParseError:
        return clients

    # Look for client connection definitions
    for client_elem in root.findall('.//Client') + root.findall('.//Connection'):
        name = client_elem.get('Name', '') or client_elem.get('Id', '')
        endpoint = client_elem.get('Endpoint', '') or client_elem.get('ServerUri', '')
        security = client_elem.get('SecurityMode', '')

        if name or endpoint:
            clients.append(OpcUaClient(
                name=name,
                endpoint=endpoint,
                security_mode=security
            ))

    return clients


def parse_modbus_from_cfg(system_dir: Path) -> tuple:
    """Parse System.cfg for Modbus configurations."""
    masters = []
    slaves = []

    cfg_path = system_dir / 'System.cfg'
    if not cfg_path.exists():
        return masters, slaves

    try:
        tree = ET.parse(cfg_path)
        root = tree.getroot()
    except ET.ParseError:
        return masters, slaves

    # Look for Modbus-related FB instances
    modbus_master_types = ['AL1320', 'AL1322', 'MODBUS_MASTER', 'ModbusMaster', 'MB_MASTER']
    modbus_slave_types = ['MODBUS', 'ModbusSlave', 'MB_SLAVE']

    for fb_elem in root.iter():
        fb_type = fb_elem.get('Type', '')
        fb_name = fb_elem.get('Name', '')

        # Check if it's a Modbus master
        if any(mt in fb_type for mt in modbus_master_types):
            # Try to get address from parameters
            address = ''
            for param in fb_elem.findall('.//Param') + fb_elem.findall('.//Parameter'):
                param_name = param.get('Name', '').lower()
                if 'address' in param_name or 'ip' in param_name:
                    address = param.get('Value', '') or param.text or ''
                    break

            masters.append(ModbusMaster(
                name=fb_name,
                protocol='TCP' if 'TCP' in fb_type.upper() else 'RTU',
                address=address,
                slave_count=0
            ))

        # Check if it's a Modbus slave
        if any(st in fb_type for st in modbus_slave_types):
            unit_id = 0
            master_name = ''

            for param in fb_elem.findall('.//Param') + fb_elem.findall('.//Parameter'):
                param_name = param.get('Name', '').lower()
                if 'unit' in param_name or 'id' in param_name:
                    try:
                        unit_id = int(param.get('Value', '0') or param.text or '0')
                    except ValueError:
                        pass
                if 'master' in param_name:
                    master_name = param.get('Value', '') or param.text or ''

            slaves.append(ModbusSlave(
                name=fb_name,
                unit_id=unit_id,
                master_name=master_name
            ))

    return masters, slaves


def parse_modbus_from_sys(system_dir: Path, masters: List[ModbusMaster], slaves: List[ModbusSlave]) -> tuple:
    """Parse System.sys for additional Modbus configurations."""
    sys_path = system_dir / 'System.sys'
    if not sys_path.exists():
        return masters, slaves

    try:
        tree = ET.parse(sys_path)
        root = tree.getroot()
    except ET.ParseError:
        return masters, slaves

    # Look for CATType instances related to Modbus
    for cat_elem in root.findall('.//CATType'):
        cat_name = cat_elem.get('Name', '')
        namespace = cat_elem.get('Namespace', '')

        # Check for Modbus-related namespaces
        if 'Modbus' in namespace or 'MODBUS' in cat_name.upper():
            for inst_elem in cat_elem.findall('.//Inst'):
                inst_name = inst_elem.get('Name', '')

                # Determine if master or slave based on naming
                if 'Master' in inst_name or 'AL13' in cat_name:
                    # Check if already exists
                    if not any(m.name == inst_name for m in masters):
                        masters.append(ModbusMaster(
                            name=inst_name,
                            protocol='TCP',
                            address='',
                            slave_count=0
                        ))
                else:
                    if not any(s.name == inst_name for s in slaves):
                        slaves.append(ModbusSlave(
                            name=inst_name,
                            unit_id=0,
                            master_name=''
                        ))

    # Update slave counts for masters
    for master in masters:
        master.slave_count = sum(1 for s in slaves if s.master_name == master.name)

    return masters, slaves


def parse_ethernet_ip(system_dir: Path) -> List[EtherNetIPScanner]:
    """Parse for EtherNet/IP scanner configurations."""
    scanners = []

    # Check System.cfg and System.sys
    for config_file in ['System.cfg', 'System.sys']:
        config_path = system_dir / config_file
        if not config_path.exists():
            continue

        try:
            tree = ET.parse(config_path)
            root = tree.getroot()
        except ET.ParseError:
            continue

        # Look for EIP scanner instances
        eip_types = ['EIPSCANNER', 'EtherNetIPScanner', 'EIP_SCANNER', 'CIPScanner']

        for elem in root.iter():
            elem_type = elem.get('Type', '')
            elem_name = elem.get('Name', '')

            if any(et in elem_type for et in eip_types):
                # Count connections
                connections = 0
                for conn in elem.findall('.//Connection') + elem.findall('.//Target'):
                    connections += 1

                if not any(s.name == elem_name for s in scanners):
                    scanners.append(EtherNetIPScanner(
                        name=elem_name,
                        connections=max(1, connections)
                    ))

        # Also check CATType for EIP
        for cat_elem in root.findall('.//CATType'):
            cat_name = cat_elem.get('Name', '')
            namespace = cat_elem.get('Namespace', '')

            if 'EIP' in cat_name.upper() or 'EtherNet' in namespace:
                for inst_elem in cat_elem.findall('.//Inst'):
                    inst_name = inst_elem.get('Name', '')
                    if not any(s.name == inst_name for s in scanners):
                        scanners.append(EtherNetIPScanner(
                            name=inst_name,
                            connections=1
                        ))

    return scanners


def detect_other_protocols(system_dir: Path) -> Dict[str, int]:
    """Detect other protocols from configuration files."""
    protocols = {}

    # Check offline.xml for protocol hints
    offline_path = system_dir / 'System.offline.xml'
    if offline_path.exists():
        try:
            tree = ET.parse(offline_path)
            root = tree.getroot()

            for elem in root.iter():
                elem_type = elem.get('Type', '')

                # Check for known protocol types
                protocol_keywords = {
                    'DNP3': ['DNP3', 'dnp3'],
                    'PROFINET': ['PROFINET', 'Profinet'],
                    'CANopen': ['CANopen', 'CAN'],
                    'IO-Link': ['IOLink', 'IoLink', 'IO_LINK'],
                    'HART': ['HART', 'Hart'],
                    'BACnet': ['BACnet', 'BACNET'],
                }

                for protocol, keywords in protocol_keywords.items():
                    if any(kw in elem_type for kw in keywords):
                        protocols[protocol] = protocols.get(protocol, 0) + 1

        except ET.ParseError:
            pass

    # Check System.cfg for additional protocol hints
    cfg_path = system_dir / 'System.cfg'
    if cfg_path.exists():
        try:
            content = cfg_path.read_text(encoding='utf-8', errors='ignore')

            # Simple pattern matching for protocol keywords
            if 'DNP3' in content:
                protocols['DNP3'] = protocols.get('DNP3', 0) + 1
            if 'PROFINET' in content or 'Profinet' in content:
                protocols['PROFINET'] = protocols.get('PROFINET', 0) + 1
            if 'IOLink' in content or 'IO-Link' in content:
                protocols['IO-Link'] = protocols.get('IO-Link', 0) + 1

        except Exception:
            pass

    return protocols


def detect_protocols_from_libraries(project_dir: Path) -> Dict[str, Any]:
    """Detect protocols from library references and FB usage in .fbt files."""
    result = {
        'has_opcua': False,
        'has_modbus': False,
        'has_ethernet_ip': False,
        'has_profinet': False,
        'has_dnp3': False,
        'has_iolink': False,
        'opcua_usage_count': 0,
        'modbus_usage_count': 0,
        'ethernet_ip_usage_count': 0,
    }

    # Protocol library patterns
    protocol_patterns = {
        'opcua': ['Standard.IoOpcUa', 'OpcUa', 'OPCUA', 'Standard.OPCUAClient'],
        'modbus': ['Standard.IoModbus', 'SE.ModbusGateway', 'Modbus', 'Standard.IoModbusSlave'],
        'ethernet_ip': ['Standard.IoEtherNetIP', 'EtherNetIP', 'EIPSCANNER'],
        'profinet': ['Standard.IoProfinet', 'Profinet', 'PROFINET'],
        'dnp3': ['Standard.IoDnp3', 'DNP3', 'Standard.Scadapack'],
        'iolink': ['IoLink', 'IO-Link'],
    }

    # Check dfbproj files for library references
    for dfbproj_path in project_dir.rglob('*.dfbproj'):
        try:
            content = dfbproj_path.read_text(encoding='utf-8', errors='ignore')

            for proto, patterns in protocol_patterns.items():
                for pattern in patterns:
                    if pattern in content:
                        result[f'has_{proto}'] = True
                        break
        except Exception:
            pass

    # Check hardware config files (.hcf) for protocol configurations
    for hcf_path in project_dir.rglob('*.hcf'):
        try:
            tree = ET.parse(hcf_path)
            root = tree.getroot()

            for item in root.findall('.//ConfigurationBaseItem'):
                item_type = ''
                namespace = ''

                type_elem = item.find('.//Type')
                if type_elem is not None:
                    name_elem = type_elem.find('Name')
                    ns_elem = type_elem.find('Namespace')
                    if name_elem is not None:
                        item_type = name_elem.text or ''
                    if ns_elem is not None:
                        namespace = ns_elem.text or ''

                full_type = f"{namespace}.{item_type}" if namespace else item_type

                # Check for EtherNet/IP
                if 'EIPSCANNER' in item_type or 'IoEtherNetIP' in namespace:
                    result['has_ethernet_ip'] = True
                    result['ethernet_ip_usage_count'] += 1

                # Check for Modbus
                if 'Modbus' in item_type or 'Modbus' in namespace:
                    result['has_modbus'] = True
                    result['modbus_usage_count'] += 1

                # Check for OPC-UA
                if 'OPCUA' in item_type.upper() or 'OpcUa' in namespace:
                    result['has_opcua'] = True
                    result['opcua_usage_count'] += 1

                # Check for Profinet
                if 'PROFINET' in item_type.upper() or 'Profinet' in namespace:
                    result['has_profinet'] = True

                # Check for DNP3
                if 'DNP3' in item_type.upper():
                    result['has_dnp3'] = True

        except ET.ParseError:
            pass
        except Exception:
            pass

    # Count usage in .fbt files for more detail
    for fbt_path in project_dir.rglob('*.fbt'):
        try:
            content = fbt_path.read_text(encoding='utf-8', errors='ignore')

            # Count OPC-UA usage
            if 'Standard.IoOpcUa' in content or 'OpcUaClient' in content or 'Standard.OPCUAClient' in content:
                result['has_opcua'] = True
                result['opcua_usage_count'] += content.count('Standard.IoOpcUa') + content.count('Standard.OPCUAClient')

            # Count Modbus usage
            modbus_count = content.count('Standard.IoModbus') + content.count('SE.ModbusGateway')
            if modbus_count > 0:
                result['has_modbus'] = True
                result['modbus_usage_count'] += modbus_count

            # Count EtherNet/IP usage
            eip_count = content.count('Standard.IoEtherNetIP')
            if eip_count > 0:
                result['has_ethernet_ip'] = True
                result['ethernet_ip_usage_count'] += eip_count

            # Check for other protocols
            if 'Standard.IoProfinet' in content or 'Profinet' in content:
                result['has_profinet'] = True
            if 'Standard.IoDnp3' in content or 'DNP3' in content:
                result['has_dnp3'] = True
            if 'IoLink' in content:
                result['has_iolink'] = True

        except Exception:
            pass

    return result


def analyze_protocols(project_dir: Path, system_dir: Optional[Path] = None) -> ProtocolSummary:
    """Analyze all protocol configurations."""
    warnings = []

    # Detect protocols from libraries and hardware config (most reliable)
    lib_detection = detect_protocols_from_libraries(project_dir)

    # Find system directory
    if system_dir is None:
        system_dir = find_system_dir(project_dir)

    if system_dir is None:
        # Still return library-based detection even without System directory
        total = 0
        if lib_detection['has_opcua']:
            total += 1
        if lib_detection['has_modbus']:
            total += 1
        if lib_detection['has_ethernet_ip']:
            total += 1

        return ProtocolSummary(
            opc_ua_server=None,
            opc_ua_clients=[],
            modbus_masters=[],
            modbus_slaves=[],
            ethernet_ip_scanners=[],
            other_protocols={},
            total_protocols=total,
            has_opcua=lib_detection['has_opcua'],
            has_modbus=lib_detection['has_modbus'],
            has_ethernet_ip=lib_detection['has_ethernet_ip'],
            opcua_usage_count=lib_detection['opcua_usage_count'],
            modbus_usage_count=lib_detection['modbus_usage_count'],
            ethernet_ip_usage_count=lib_detection['ethernet_ip_usage_count'],
            warnings=['System directory not found']
        )

    # Parse OPC-UA
    opc_ua_server = parse_opcua_server(system_dir)
    opc_ua_clients = parse_opcua_clients(system_dir)

    # Parse Modbus
    modbus_masters, modbus_slaves = parse_modbus_from_cfg(system_dir)
    modbus_masters, modbus_slaves = parse_modbus_from_sys(system_dir, modbus_masters, modbus_slaves)

    # Parse EtherNet/IP
    eip_scanners = parse_ethernet_ip(system_dir)

    # Detect other protocols
    other_protocols = detect_other_protocols(system_dir)

    # Add library-detected protocols to other_protocols if not already covered
    if lib_detection['has_profinet'] and 'PROFINET' not in other_protocols:
        other_protocols['PROFINET'] = 1
    if lib_detection['has_dnp3'] and 'DNP3' not in other_protocols:
        other_protocols['DNP3'] = 1
    if lib_detection['has_iolink'] and 'IO-Link' not in other_protocols:
        other_protocols['IO-Link'] = 1

    # Calculate total - use library detection as the primary source
    total = 0
    if lib_detection['has_opcua'] or (opc_ua_server and opc_ua_server.enabled) or opc_ua_clients:
        total += 1
    if lib_detection['has_modbus'] or modbus_masters:
        total += 1
    if lib_detection['has_ethernet_ip'] or eip_scanners:
        total += 1
    total += len(other_protocols)

    # Add warnings for potential issues
    if opc_ua_server and opc_ua_server.over_exposed:
        warnings.append("OPC-UA server may be over-exposed (root-level exposure detected)")

    if len(modbus_slaves) > 0 and len(modbus_masters) == 0:
        warnings.append("Modbus slaves found but no masters configured")

    return ProtocolSummary(
        opc_ua_server=opc_ua_server,
        opc_ua_clients=opc_ua_clients,
        modbus_masters=modbus_masters,
        modbus_slaves=modbus_slaves,
        ethernet_ip_scanners=eip_scanners,
        other_protocols=other_protocols,
        total_protocols=total,
        has_opcua=lib_detection['has_opcua'],
        has_modbus=lib_detection['has_modbus'],
        has_ethernet_ip=lib_detection['has_ethernet_ip'],
        opcua_usage_count=lib_detection['opcua_usage_count'],
        modbus_usage_count=lib_detection['modbus_usage_count'],
        ethernet_ip_usage_count=lib_detection['ethernet_ip_usage_count'],
        warnings=warnings
    )


def main():
    parser = argparse.ArgumentParser(
        description='Parse EAE protocol configurations',
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

    # Analyze protocols
    result = analyze_protocols(project_dir, system_dir)

    # Convert to dict for JSON serialization
    def to_dict(obj):
        if obj is None:
            return None
        if hasattr(obj, '__dict__'):
            d = {}
            for k, v in obj.__dict__.items():
                if isinstance(v, list):
                    d[k] = [to_dict(i) for i in v]
                elif isinstance(v, dict):
                    d[k] = v
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
        lines.append("Protocol Summary")
        lines.append("=" * 40)
        lines.append(f"Total Protocol Configurations: {result.total_protocols}")
        lines.append("")

        lines.append("OPC-UA Server:")
        if result.opc_ua_server:
            lines.append(f"  Enabled: {result.opc_ua_server.enabled}")
            lines.append(f"  Exposed Nodes: {result.opc_ua_server.exposed_nodes}")
            lines.append(f"  Over-Exposed: {result.opc_ua_server.over_exposed}")
        else:
            lines.append("  Not configured")
        lines.append("")

        lines.append(f"OPC-UA Clients: {len(result.opc_ua_clients)}")
        for client in result.opc_ua_clients:
            lines.append(f"  - {client.name}: {client.endpoint}")
        lines.append("")

        lines.append(f"Modbus Masters: {len(result.modbus_masters)}")
        for master in result.modbus_masters:
            lines.append(f"  - {master.name} ({master.protocol}): {master.address}, {master.slave_count} slaves")
        lines.append("")

        lines.append(f"Modbus Slaves: {len(result.modbus_slaves)}")
        for slave in result.modbus_slaves:
            lines.append(f"  - {slave.name} (Unit {slave.unit_id})")
        lines.append("")

        lines.append(f"EtherNet/IP Scanners: {len(result.ethernet_ip_scanners)}")
        for scanner in result.ethernet_ip_scanners:
            lines.append(f"  - {scanner.name}: {scanner.connections} connections")
        lines.append("")

        if result.other_protocols:
            lines.append("Other Protocols:")
            for proto, count in result.other_protocols.items():
                lines.append(f"  - {proto}: {count}")
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
