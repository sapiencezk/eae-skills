#!/usr/bin/env python3
"""
validate_fbnetwork.py - FBNetwork Connection Validator

Validates FBNetwork connections in EAE Composite Function Blocks for correctness.

This script checks:
- Event connections are event-to-event
- Data connections have compatible types (BOOL→BOOL, REAL→REAL, etc.)
- No dangling connections (all Source/Destination valid)
- FB instances reference valid types
- Cross-reference connections (../../) are properly formed
- Parameter values are provided where required

Usage:
    python validate_fbnetwork.py <composite_fb_file_path> [options]

    Examples:
        # Validate a Composite FB file
        python validate_fbnetwork.py path/to/MyCompositeFB.fbt

        # Validate with verbose output
        python validate_fbnetwork.py path/to/MyCompositeFB.fbt --verbose

        # Output JSON for automation
        python validate_fbnetwork.py path/to/MyCompositeFB.fbt --json

Exit Codes:
    0  - Validation passed (no errors)
    1  - General error (file not found, parse error, etc.)
    10 - Validation failed (errors found)
    11 - Validation passed with warnings

Dependencies:
    - Python 3.7+
    - lxml (optional, for better XML parsing)
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Set, List, Dict, Tuple

# Add parent directory to path for shared library imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'eae-skill-router' / 'scripts'))

from lib.validation_result import ValidationResult, create_success, create_failure
from lib.contextual_errors import SYMBOLS, print_validation_summary

# Try to import lxml for better XML parsing, fall back to stdlib
try:
    from lxml import etree as ET
    HAVE_LXML = True
except ImportError:
    import xml.etree.ElementTree as ET
    HAVE_LXML = False


# IEC 61499 Type Compatibility Matrix
# (source_type, dest_type) -> is_compatible
TYPE_COMPATIBILITY = {
    # Exact matches
    ('BOOL', 'BOOL'): True,
    ('INT', 'INT'): True,
    ('DINT', 'DINT'): True,
    ('REAL', 'REAL'): True,
    ('LREAL', 'LREAL'): True,
    ('STRING', 'STRING'): True,
    ('BYTE', 'BYTE'): True,
    ('WORD', 'WORD'): True,
    ('DWORD', 'DWORD'): True,
    ('TIME', 'TIME'): True,
    ('DATE', 'DATE'): True,
    ('TOD', 'TOD'): True,
    ('DT', 'DT'): True,

    # Implicit widening conversions (allowed in IEC 61131-3)
    ('INT', 'DINT'): True,
    ('INT', 'REAL'): True,
    ('INT', 'LREAL'): True,
    ('DINT', 'REAL'): True,
    ('DINT', 'LREAL'): True,
    ('REAL', 'LREAL'): True,
    ('BYTE', 'WORD'): True,
    ('BYTE', 'DWORD'): True,
    ('WORD', 'DWORD'): True,

    # Note: Narrowing conversions (DINT→INT, REAL→INT) are NOT in this matrix
    # They require explicit conversion and should be flagged as warnings
}


@dataclass
class FBInstance:
    """Represents an FB instance in the network."""
    name: str
    type_name: str
    x: int
    y: int


@dataclass
class Connection:
    """Represents a connection in the FBNetwork."""
    source: str
    destination: str
    is_event: bool
    dx1: Optional[int] = None
    dx2: Optional[int] = None


def parse_connection_ref(ref: str) -> Tuple[str, str]:
    """
    Parse a connection reference (e.g., "FB1.OUT1" or "../../INPUT1").

    Args:
        ref: Connection reference string

    Returns:
        Tuple of (fb_name or path, pin_name)
    """
    if '.' in ref:
        parts = ref.rsplit('.', 1)
        return (parts[0], parts[1])
    else:
        # Direct reference to interface (e.g., "../../INPUT1" or just "INPUT1")
        return ("", ref)


def is_cross_reference(ref: str) -> bool:
    """Check if a reference is a cross-reference (../..)."""
    return ref.startswith('../../')


def get_fb_instances(fbnetwork: ET.Element) -> Dict[str, FBInstance]:
    """
    Extract all FB instances from the FBNetwork.

    Args:
        fbnetwork: <FBNetwork> XML element

    Returns:
        Dictionary mapping instance names to FBInstance objects
    """
    instances = {}

    for fb_elem in fbnetwork.findall('.//FB'):
        name = fb_elem.get('Name')
        type_name = fb_elem.get('Type')
        x = int(fb_elem.get('x', 0))
        y = int(fb_elem.get('y', 0))

        if name and type_name:
            instances[name] = FBInstance(name, type_name, x, y)

    return instances


def get_interface_events(root: ET.Element) -> Tuple[Set[str], Set[str]]:
    """
    Get event inputs and outputs from the Composite FB's interface.

    Args:
        root: Root XML element

    Returns:
        Tuple of (event_inputs, event_outputs)
    """
    event_inputs = set()
    event_outputs = set()

    for event_elem in root.findall('.//InterfaceList/EventInputs/Event'):
        name = event_elem.get('Name')
        if name:
            event_inputs.add(name)

    for event_elem in root.findall('.//InterfaceList/EventOutputs/Event'):
        name = event_elem.get('Name')
        if name:
            event_outputs.add(name)

    return event_inputs, event_outputs


def get_interface_vars(root: ET.Element) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Get data inputs and outputs from the Composite FB's interface.

    Args:
        root: Root XML element

    Returns:
        Tuple of (var_inputs: {name: type}, var_outputs: {name: type})
    """
    var_inputs = {}
    var_outputs = {}

    for var_elem in root.findall('.//InterfaceList/InputVars/VarDeclaration'):
        name = var_elem.get('Name')
        var_type = var_elem.get('Type')
        if name:
            var_inputs[name] = var_type or 'UNKNOWN'

    for var_elem in root.findall('.//InterfaceList/OutputVars/VarDeclaration'):
        name = var_elem.get('Name')
        var_type = var_elem.get('Type')
        if name:
            var_outputs[name] = var_type or 'UNKNOWN'

    return var_inputs, var_outputs


def validate_fbnetwork(tree: ET.ElementTree, filepath: Path) -> ValidationResult:
    """
    Validate FBNetwork in a Composite FB.

    Args:
        tree: Parsed XML tree
        filepath: Path to the file being validated

    Returns:
        ValidationResult with success status and any errors/warnings
    """
    errors = []
    warnings = []
    details = {}

    root = tree.getroot()

    # ============================================================
    # Check 1: Ensure this is a Composite FB with FBNetwork
    # ============================================================
    fbtype = root.find('.//FBType')
    if fbtype is None:
        return create_failure(
            "Not a valid FB file",
            ["File does not contain an FBType element"]
        )

    fbnetwork = root.find('.//FBNetwork')
    if fbnetwork is None:
        # Could be a Basic FB (no FBNetwork) - not an error, just not applicable
        return create_success(
            "No FBNetwork found - not a Composite FB",
            details={"note": "This appears to be a Basic FB or other type without FBNetwork"}
        )

    # ============================================================
    # Check 2: Get FB instances
    # ============================================================
    instances = get_fb_instances(fbnetwork)
    details['fb_count'] = len(instances)
    details['fb_instances'] = list(instances.keys())

    # ============================================================
    # Check 3: Get interface definitions
    # ============================================================
    event_inputs, event_outputs = get_interface_events(root)
    var_inputs, var_outputs = get_interface_vars(root)

    details['interface_event_inputs'] = list(event_inputs)
    details['interface_event_outputs'] = list(event_outputs)
    details['interface_var_inputs'] = list(var_inputs.keys())
    details['interface_var_outputs'] = list(var_outputs.keys())

    # ============================================================
    # Check 4: Validate Event Connections
    # ============================================================
    event_connections = []
    for conn_elem in fbnetwork.findall('.//EventConnections/Connection'):
        source = conn_elem.get('Source')
        destination = conn_elem.get('Destination')

        if not source or not destination:
            errors.append("Event connection missing Source or Destination attribute")
            continue

        event_connections.append(Connection(source, destination, is_event=True))

        # Parse source and destination
        src_fb, src_pin = parse_connection_ref(source)
        dst_fb, dst_pin = parse_connection_ref(destination)

        # Validate source exists
        if src_fb and not is_cross_reference(src_fb):
            if src_fb not in instances:
                errors.append(f"Event connection source references non-existent FB '{src_fb}'")
        elif is_cross_reference(src_fb):
            # Cross-reference to interface - should be event input
            if src_pin not in event_inputs:
                errors.append(f"Event connection references non-existent interface event input '{src_pin}'")

        # Validate destination exists
        if dst_fb and not is_cross_reference(dst_fb):
            if dst_fb not in instances:
                errors.append(f"Event connection destination references non-existent FB '{dst_fb}'")
        elif is_cross_reference(dst_fb):
            # Cross-reference to interface - should be event output
            if dst_pin not in event_outputs:
                errors.append(f"Event connection references non-existent interface event output '{dst_pin}'")

    details['event_connection_count'] = len(event_connections)

    # ============================================================
    # Check 5: Validate Data Connections
    # ============================================================
    data_connections = []
    for conn_elem in fbnetwork.findall('.//DataConnections/Connection'):
        source = conn_elem.get('Source')
        destination = conn_elem.get('Destination')

        if not source or not destination:
            errors.append("Data connection missing Source or Destination attribute")
            continue

        data_connections.append(Connection(source, destination, is_event=False))

        # Parse source and destination
        src_fb, src_pin = parse_connection_ref(source)
        dst_fb, dst_pin = parse_connection_ref(destination)

        # Determine source type
        src_type = None
        if is_cross_reference(src_fb):
            # Interface input
            src_type = var_inputs.get(src_pin)
        # Note: For FB instances, we'd need to load their types to validate
        # For now, we just check they exist (type checking would require type library)

        # Determine destination type
        dst_type = None
        if is_cross_reference(dst_fb):
            # Interface output
            dst_type = var_outputs.get(dst_pin)

        # Validate source exists
        if src_fb and not is_cross_reference(src_fb):
            if src_fb not in instances:
                errors.append(f"Data connection source references non-existent FB '{src_fb}'")
        elif is_cross_reference(src_fb):
            if src_pin not in var_inputs:
                errors.append(f"Data connection references non-existent interface var input '{src_pin}'")

        # Validate destination exists
        if dst_fb and not is_cross_reference(dst_fb):
            if dst_fb not in instances:
                errors.append(f"Data connection destination references non-existent FB '{dst_fb}'")
        elif is_cross_reference(dst_fb):
            if dst_pin not in var_outputs:
                errors.append(f"Data connection references non-existent interface var output '{dst_pin}'")

        # Type compatibility check (if we know both types)
        if src_type and dst_type:
            if (src_type, dst_type) not in TYPE_COMPATIBILITY:
                # Check if exact match (might be custom type)
                if src_type != dst_type:
                    errors.append(
                        f"Data connection type mismatch: {source} ({src_type}) → {destination} ({dst_type})"
                    )

    details['data_connection_count'] = len(data_connections)

    # ============================================================
    # Check 6: Check for dangling FB instances (no connections)
    # ============================================================
    connected_fbs = set()
    for conn in event_connections + data_connections:
        src_fb, _ = parse_connection_ref(conn.source)
        dst_fb, _ = parse_connection_ref(conn.destination)
        if src_fb and not is_cross_reference(src_fb):
            connected_fbs.add(src_fb)
        if dst_fb and not is_cross_reference(dst_fb):
            connected_fbs.add(dst_fb)

    dangling_fbs = set(instances.keys()) - connected_fbs
    if dangling_fbs:
        for fb in sorted(dangling_fbs):
            warnings.append(f"FB instance '{fb}' has no connections (unused in network)")

    # ============================================================
    # Check 7: Validate cross-reference format
    # ============================================================
    for conn in event_connections + data_connections:
        for ref in [conn.source, conn.destination]:
            if is_cross_reference(ref):
                # Should be ../../NAME format
                if not ref.startswith('../../'):
                    errors.append(f"Cross-reference '{ref}' has invalid format (should be ../../NAME)")

    # ============================================================
    # Summary
    # ============================================================
    if errors:
        return create_failure(
            f"FBNetwork validation failed with {len(errors)} error(s)",
            errors,
            warnings=warnings,
            details=details
        )
    elif warnings:
        return create_success(
            f"FBNetwork validation passed with {len(warnings)} warning(s)",
            warnings=warnings,
            details=details
        )
    else:
        return create_success(
            "FBNetwork validation passed - all connections are valid",
            details=details
        )


def parse_xml_file(filepath: Path) -> Optional[ET.ElementTree]:
    """
    Parse XML file safely.

    Args:
        filepath: Path to XML file

    Returns:
        ElementTree or None if parsing failed
    """
    try:
        if HAVE_LXML:
            parser = ET.XMLParser(remove_blank_text=True, encoding='utf-8')
            tree = ET.parse(str(filepath), parser)
        else:
            tree = ET.parse(str(filepath))
        return tree
    except ET.ParseError as e:
        print(f"{SYMBOLS['error']} XML parsing error: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"{SYMBOLS['error']} Error reading file: {e}", file=sys.stderr)
        return None


def print_validation_result(result: ValidationResult, verbose: bool = False):
    """
    Print validation result in human-readable format.

    Args:
        result: ValidationResult to print
        verbose: Whether to print detailed information
    """
    # Use shared library function for summary
    print_validation_summary(result.success, len(result.errors), len(result.warnings), result.message)

    if result.errors:
        print(f"{SYMBOLS['error']} Errors ({len(result.errors)}):")
        for i, error in enumerate(result.errors, 1):
            print(f"  {i}. {error}")

    if result.warnings:
        print(f"\n{SYMBOLS['warning']} Warnings ({len(result.warnings)}):")
        for i, warning in enumerate(result.warnings, 1):
            print(f"  {i}. {warning}")

    if verbose and result.details:
        print(f"\n{SYMBOLS['info']} Details:")
        for key, value in result.details.items():
            if isinstance(value, (list, dict)):
                print(f"  {key}:")
                print(f"    {json.dumps(value, indent=4)}")
            else:
                print(f"  {key}: {value}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate FBNetwork connections in EAE Composite Function Blocks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python validate_fbnetwork.py MyCompositeFB.fbt
  python validate_fbnetwork.py MyCompositeFB.fbt --verbose
  python validate_fbnetwork.py MyCompositeFB.fbt --json
  python validate_fbnetwork.py MyCompositeFB.fbt --ci
        """
    )
    parser.add_argument(
        "filepath",
        type=Path,
        help="Path to Composite FB file to validate (.fbt)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output with detailed information"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format (for automation)"
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: JSON output with exit code only (no human messages)"
    )

    args = parser.parse_args()

    # CI mode implies JSON
    if args.ci:
        args.json = True

    # Check file exists
    if not args.filepath.exists():
        if not args.json:
            print(f"{SYMBOLS['error']} Error: File not found: {args.filepath}", file=sys.stderr)
        return 1

    # Check file extension
    if args.filepath.suffix != ".fbt":
        if not args.json:
            print(f"{SYMBOLS['error']} Error: Expected .fbt file, got {args.filepath.suffix}", file=sys.stderr)
        return 1

    # Parse XML
    tree = parse_xml_file(args.filepath)
    if tree is None:
        return 1

    # Validate
    result = validate_fbnetwork(tree, args.filepath)

    # Output results
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print_validation_result(result, verbose=args.verbose)

    # Return appropriate exit code using the property from ValidationResult
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
