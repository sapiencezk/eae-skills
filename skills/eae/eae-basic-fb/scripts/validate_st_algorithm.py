#!/usr/bin/env python3
"""
validate_st_algorithm.py - Structured Text (ST) Algorithm Basic Validator

Performs basic validation of ST algorithms in EAE Basic Function Blocks.

This script performs simplified checks (NOT full ST parsing):
- Algorithm names match those referenced in ECC
- Variables referenced in algorithms are declared
- Basic syntax issues (empty algorithms, obvious syntax errors)

Note: Full ST syntax validation is left to the EAE compiler. This script catches
common mistakes early to save compilation cycles.

Usage:
    python validate_st_algorithm.py <basic_fb_file_path> [options]

    Examples:
        # Validate algorithms in a Basic FB file
        python validate_st_algorithm.py path/to/MyBasicFB.fbt

        # Validate with verbose output
        python validate_st_algorithm.py path/to/MyBasicFB.fbt --verbose

        # Output JSON for automation
        python validate_st_algorithm.py path/to/MyBasicFB.fbt --json

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
import re
import sys
from pathlib import Path
from typing import Optional, Set, List, Dict

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


def get_declared_variables(root: ET.Element) -> Dict[str, str]:
    """
    Extract all declared variables from InterfaceList and InternalVars.

    Args:
        root: Root XML element

    Returns:
        Dictionary mapping variable names to their types
    """
    variables = {}

    # EventInputs/EventOutputs
    for event_elem in root.findall('.//InterfaceList//Event'):
        var_name = event_elem.get('Name')
        if var_name:
            variables[var_name] = 'EVENT'

    # VarInputs/VarOutputs/InternalVars
    for var_elem in root.findall('.//VarDeclaration'):
        var_name = var_elem.get('Name')
        var_type = var_elem.get('Type')
        if var_name:
            variables[var_name] = var_type or 'UNKNOWN'

    return variables


def get_ecc_referenced_algorithms(root: ET.Element) -> Set[str]:
    """
    Get all algorithm names referenced in the ECC.

    Args:
        root: Root XML element

    Returns:
        Set of algorithm names used in ECC actions
    """
    referenced = set()

    for action_elem in root.findall('.//ECC//ECAction'):
        algorithm = action_elem.get('Algorithm')
        if algorithm:
            referenced.add(algorithm)

    return referenced


def extract_variable_references(st_code: str) -> Set[str]:
    """
    Extract variable references from ST code using simple pattern matching.

    This is NOT full ST parsing - just heuristic extraction of identifiers.

    Args:
        st_code: ST algorithm code

    Returns:
        Set of potential variable names found in code
    """
    # Pattern: word boundaries around identifiers
    # This will have false positives (ST keywords, function names) but that's okay
    # We're looking for undefined variables, not perfect parsing
    pattern = r'\b([A-Za-z_][A-Za-z0-9_]*)\b'
    matches = re.findall(pattern, st_code)

    # Filter out common ST keywords and operators
    st_keywords = {
        'IF', 'THEN', 'ELSE', 'ELSIF', 'END_IF',
        'CASE', 'OF', 'END_CASE',
        'FOR', 'TO', 'BY', 'DO', 'END_FOR',
        'WHILE', 'END_WHILE',
        'REPEAT', 'UNTIL', 'END_REPEAT',
        'AND', 'OR', 'NOT', 'XOR',
        'TRUE', 'FALSE',
        'MOD', 'DIV',
        'RETURN', 'EXIT',
        # Common type names
        'BOOL', 'INT', 'DINT', 'REAL', 'LREAL', 'STRING', 'BYTE', 'WORD', 'DWORD',
    }

    variables = set()
    for match in matches:
        upper_match = match.upper()
        if upper_match not in st_keywords:
            variables.add(match)

    return variables


def validate_st_algorithms(tree: ET.ElementTree, filepath: Path) -> ValidationResult:
    """
    Validate ST algorithms in a Basic FB (basic checks only).

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
    # Check 1: Ensure this is a Basic FB
    # ============================================================
    basic_fb = root.find('.//BasicFB')
    if basic_fb is None:
        return create_failure(
            "Not a Basic FB file",
            ["File does not contain a BasicFB element"]
        )

    # ============================================================
    # Check 2: Get declared variables
    # ============================================================
    declared_vars = get_declared_variables(root)
    details['declared_variables'] = list(declared_vars.keys())
    details['variable_count'] = len(declared_vars)

    # ============================================================
    # Check 3: Get ECC-referenced algorithms
    # ============================================================
    ecc_algorithms = get_ecc_referenced_algorithms(root)
    details['ecc_referenced_algorithms'] = list(ecc_algorithms)

    # ============================================================
    # Check 4: Validate each algorithm
    # ============================================================
    algorithms = {}
    for algo_elem in root.findall('.//Algorithm'):
        algo_name = algo_elem.get('Name')
        if not algo_name:
            warnings.append("Found algorithm without a Name attribute")
            continue

        algorithms[algo_name] = algo_elem

        # Check if algorithm has ST code
        st_elem = algo_elem.find('.//ST')
        if st_elem is None:
            warnings.append(f"Algorithm '{algo_name}' has no ST code")
            continue

        st_code = st_elem.find('.//Text')
        if st_code is None:
            warnings.append(f"Algorithm '{algo_name}' has no Text element in ST")
            continue

        code_text = st_code.text or ""

        # Check for empty algorithms
        if not code_text.strip():
            warnings.append(f"Algorithm '{algo_name}' is empty")
            continue

        # Extract variable references from ST code
        referenced_vars = extract_variable_references(code_text)

        # Check for undefined variables
        undefined_vars = set()
        for var in referenced_vars:
            if var not in declared_vars:
                undefined_vars.add(var)

        if undefined_vars:
            # Note: These might be false positives (function calls, etc.)
            # So we report as warnings, not errors
            for var in sorted(undefined_vars):
                warnings.append(
                    f"Algorithm '{algo_name}' references potential undefined variable '{var}' "
                    f"(may be a function or constant)"
                )

    details['defined_algorithms'] = list(algorithms.keys())
    details['algorithm_count'] = len(algorithms)

    # ============================================================
    # Check 5: Verify ECC references match defined algorithms
    # ============================================================
    undefined_algos = ecc_algorithms - set(algorithms.keys())
    if undefined_algos:
        for algo in sorted(undefined_algos):
            errors.append(f"ECC references undefined algorithm '{algo}'")

    # ============================================================
    # Check 6: Check for unused algorithms
    # ============================================================
    unused_algos = set(algorithms.keys()) - ecc_algorithms
    if unused_algos:
        for algo in sorted(unused_algos):
            warnings.append(f"Algorithm '{algo}' is defined but not used in ECC")

    # ============================================================
    # Summary
    # ============================================================
    if errors:
        return create_failure(
            f"ST algorithm validation failed with {len(errors)} error(s)",
            errors,
            warnings=warnings,
            details=details
        )
    elif warnings:
        return create_success(
            f"ST algorithm validation passed with {len(warnings)} warning(s)",
            warnings=warnings,
            details=details
        )
    else:
        return create_success(
            "ST algorithm validation passed - algorithms are consistent",
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
        description="Validate ST algorithms in EAE Basic Function Blocks (basic checks)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python validate_st_algorithm.py MyBasicFB.fbt
  python validate_st_algorithm.py MyBasicFB.fbt --verbose
  python validate_st_algorithm.py MyBasicFB.fbt --json

Note: This performs basic validation (undefined variables, algorithm consistency).
Full ST syntax validation is left to the EAE compiler.
        """
    )
    parser.add_argument(
        "filepath",
        type=Path,
        help="Path to Basic FB file to validate (.fbt)"
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
    result = validate_st_algorithms(tree, args.filepath)

    # Output results
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print_validation_result(result, verbose=args.verbose)

    # Return appropriate exit code using the property from ValidationResult
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
