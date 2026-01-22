#!/usr/bin/env python3
"""
validate_layout.py - FBNetwork Layout Validator

Validates FBNetwork layout and positioning guidelines in EAE Composite Function Blocks.

This script checks (warnings only - layout is non-critical):
- FBs positioned within recommended bounds (x: 0-5000, y: 0-3000)
- No overlapping FBs (same x,y coordinates)
- Layout follows left-to-right flow guidelines
- Connection routing is reasonable

Note: Layout validation produces warnings, not errors. Layout issues don't prevent
compilation but affect visual clarity in the EAE IDE.

Usage:
    python validate_layout.py <composite_fb_file_path> [options]

    Examples:
        # Validate layout
        python validate_layout.py path/to/MyCompositeFB.fbt

        # Verbose output with positioning details
        python validate_layout.py path/to/MyCompositeFB.fbt --verbose

        # JSON output for automation
        python validate_layout.py path/to/MyCompositeFB.fbt --json

Exit Codes:
    0  - Validation passed (no warnings)
    1  - General error (file not found, parse error, etc.)
    11 - Validation passed with warnings

Dependencies:
    - Python 3.7+
    - lxml (optional, for better XML parsing)
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Tuple

# Add parent directory to path for shared library imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'eae-skill-router' / 'scripts'))

from lib.validation_result import ValidationResult, create_success
from lib.contextual_errors import SYMBOLS, print_validation_summary

# Try to import lxml for better XML parsing, fall back to stdlib
try:
    from lxml import etree as ET
    HAVE_LXML = True
except ImportError:
    import xml.etree.ElementTree as ET
    HAVE_LXML = False


# Layout guidelines (from EAE best practices)
LAYOUT_BOUNDS = {
    'x_min': 0,
    'x_max': 5000,
    'y_min': 0,
    'y_max': 3000,
}

# Minimum spacing to avoid visual overlap
MIN_FB_SPACING = 100  # pixels


@dataclass
class FBPosition:
    """FB instance position."""
    name: str
    type_name: str
    x: int
    y: int


def get_fb_positions(fbnetwork: ET.Element) -> List[FBPosition]:
    """
    Extract FB positions from FBNetwork.

    Args:
        fbnetwork: <FBNetwork> XML element

    Returns:
        List of FBPosition objects
    """
    positions = []

    for fb_elem in fbnetwork.findall('.//FB'):
        name = fb_elem.get('Name')
        type_name = fb_elem.get('Type')
        x = int(fb_elem.get('x', 0))
        y = int(fb_elem.get('y', 0))

        if name and type_name:
            positions.append(FBPosition(name, type_name, x, y))

    return positions


def check_bounds(positions: List[FBPosition]) -> List[str]:
    """
    Check if FBs are within recommended bounds.

    Args:
        positions: List of FB positions

    Returns:
        List of warning messages
    """
    warnings = []

    for pos in positions:
        if pos.x < LAYOUT_BOUNDS['x_min'] or pos.x > LAYOUT_BOUNDS['x_max']:
            warnings.append(
                f"FB '{pos.name}' x-position ({pos.x}) is outside recommended bounds "
                f"({LAYOUT_BOUNDS['x_min']}-{LAYOUT_BOUNDS['x_max']})"
            )

        if pos.y < LAYOUT_BOUNDS['y_min'] or pos.y > LAYOUT_BOUNDS['y_max']:
            warnings.append(
                f"FB '{pos.name}' y-position ({pos.y}) is outside recommended bounds "
                f"({LAYOUT_BOUNDS['y_min']}-{LAYOUT_BOUNDS['y_max']})"
            )

    return warnings


def check_overlaps(positions: List[FBPosition]) -> List[str]:
    """
    Check for overlapping FBs (too close together).

    Args:
        positions: List of FB positions

    Returns:
        List of warning messages
    """
    warnings = []

    for i, pos1 in enumerate(positions):
        for pos2 in positions[i+1:]:
            # Check if positions are too close
            dx = abs(pos1.x - pos2.x)
            dy = abs(pos1.y - pos2.y)

            if dx < MIN_FB_SPACING and dy < MIN_FB_SPACING:
                warnings.append(
                    f"FBs '{pos1.name}' and '{pos2.name}' are too close together "
                    f"(spacing: x={dx}, y={dy}, minimum recommended: {MIN_FB_SPACING})"
                )

    return warnings


def check_flow_direction(positions: List[FBPosition], root: ET.Element) -> List[str]:
    """
    Check if layout follows left-to-right flow guidelines.

    Guidelines:
    - Input connections typically on the left
    - Output connections typically on the right
    - Signal flow generally left to right

    Args:
        positions: List of FB positions
        root: Root XML element

    Returns:
        List of warning messages
    """
    warnings = []

    # Create position map
    pos_map = {pos.name: pos for pos in positions}

    # Check data connections for backwards flow
    fbnetwork = root.find('.//FBNetwork')
    if fbnetwork is None:
        return warnings

    backwards_count = 0
    for conn_elem in fbnetwork.findall('.//DataConnections/Connection'):
        source = conn_elem.get('Source', '')
        destination = conn_elem.get('Destination', '')

        # Parse FB names
        src_fb = source.split('.')[0] if '.' in source else None
        dst_fb = destination.split('.')[0] if '.' in destination else None

        # Skip cross-references
        if not src_fb or not dst_fb or src_fb.startswith('../../') or dst_fb.startswith('../../'):
            continue

        # Check if both FBs exist in position map
        if src_fb in pos_map and dst_fb in pos_map:
            src_pos = pos_map[src_fb]
            dst_pos = pos_map[dst_fb]

            # Check if destination is significantly to the left of source
            if dst_pos.x < src_pos.x - MIN_FB_SPACING:
                backwards_count += 1

    if backwards_count > 0:
        warnings.append(
            f"Found {backwards_count} data connection(s) flowing right-to-left "
            f"(consider rearranging FBs for left-to-right flow)"
        )

    return warnings


def validate_layout(tree: ET.ElementTree, filepath: Path) -> ValidationResult:
    """
    Validate FBNetwork layout in a Composite FB.

    Args:
        tree: Parsed XML tree
        filepath: Path to the file being validated

    Returns:
        ValidationResult with success status and warnings
    """
    warnings = []
    details = {}

    root = tree.getroot()

    # ============================================================
    # Check 1: Ensure FBNetwork exists
    # ============================================================
    fbnetwork = root.find('.//FBNetwork')
    if fbnetwork is None:
        return create_success(
            "No FBNetwork found - not applicable",
            details={"note": "This appears to be a Basic FB or other type without FBNetwork"}
        )

    # ============================================================
    # Check 2: Get FB positions
    # ============================================================
    positions = get_fb_positions(fbnetwork)
    details['fb_count'] = len(positions)

    if not positions:
        return create_success(
            "No FBs in network - nothing to validate",
            details=details
        )

    # Calculate bounds
    x_coords = [p.x for p in positions]
    y_coords = [p.y for p in positions]
    details['layout_bounds'] = {
        'x_min': min(x_coords),
        'x_max': max(x_coords),
        'y_min': min(y_coords),
        'y_max': max(y_coords),
    }

    # ============================================================
    # Check 3: Validate bounds
    # ============================================================
    bounds_warnings = check_bounds(positions)
    warnings.extend(bounds_warnings)

    # ============================================================
    # Check 4: Check for overlaps
    # ============================================================
    overlap_warnings = check_overlaps(positions)
    warnings.extend(overlap_warnings)

    # ============================================================
    # Check 5: Check flow direction
    # ============================================================
    flow_warnings = check_flow_direction(positions, root)
    warnings.extend(flow_warnings)

    # ============================================================
    # Summary
    # ============================================================
    # Note: Layout validation produces warnings only, never errors
    if warnings:
        return create_success(
            f"Layout validation completed with {len(warnings)} guideline violation(s)",
            warnings=warnings,
            details=details
        )
    else:
        return create_success(
            "Layout validation passed - all guidelines followed",
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
    print_validation_summary(result.success, 0, len(result.warnings), result.message)

    if result.warnings:
        print(f"{SYMBOLS['warning']} Layout Guidelines ({len(result.warnings)}):")
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
        description="Validate FBNetwork layout in EAE Composite Function Blocks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python validate_layout.py MyCompositeFB.fbt
  python validate_layout.py MyCompositeFB.fbt --verbose
  python validate_layout.py MyCompositeFB.fbt --json

Note: Layout validation produces warnings only (non-critical).
Layout issues don't prevent compilation but affect visual clarity.
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
    result = validate_layout(tree, args.filepath)

    # Output results
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print_validation_result(result, verbose=args.verbose)

    # Return appropriate exit code
    # Layout validation never returns error code 10 (only 0 or 11)
    if result.has_warnings:
        return 11  # Validation passed with warnings
    else:
        return 0   # Validation passed


if __name__ == "__main__":
    sys.exit(main())
