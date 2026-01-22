#!/usr/bin/env python3
"""
validate_hmi.py - CAT HMI File Structure Validator

Validates HMI C# files in a CAT block for basic structure and conventions.

This script performs basic validation of HMI files (NOT full C# parsing):
- .def.cs contains symbol definitions
- .event.cs contains event definitions
- File naming conventions are followed
- Basic class structure is present

Note: Full C# compilation is left to the EAE IDE. This script catches
common structural issues early.

Usage:
    python validate_hmi.py <hmi_directory_path> [options]

    Examples:
        # Validate HMI files (pass the HMI/{CATName} directory)
        python validate_hmi.py path/to/HMI/MyCATBlock

        # Validate with verbose output
        python validate_hmi.py path/to/HMI/MyCATBlock --verbose

        # Output JSON for automation
        python validate_hmi.py path/to/HMI/MyCATBlock --json

Exit Codes:
    0  - Validation passed (no errors)
    1  - General error (directory not found, parse error, etc.)
    10 - Validation failed (errors found)
    11 - Validation passed with warnings

Dependencies:
    - Python 3.7+
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional, List, Dict

# Add parent directory to path for shared library imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'eae-skill-router' / 'scripts'))

from lib.validation_result import ValidationResult, create_success, create_failure
from lib.contextual_errors import SYMBOLS, print_validation_summary


def validate_def_file(def_file: Path, cat_name: str) -> tuple[List[str], List[str]]:
    """
    Validate .def.cs file (symbol definitions).

    Args:
        def_file: Path to .def.cs file
        cat_name: Name of the CAT block

    Returns:
        Tuple of (errors, warnings)
    """
    errors = []
    warnings = []

    if not def_file.exists():
        errors.append(f"Symbol definition file not found: {def_file.name}")
        return errors, warnings

    try:
        content = def_file.read_text(encoding='utf-8')

        # Check for namespace declaration
        if 'namespace' not in content.lower():
            warnings.append(f"{def_file.name}: No namespace declaration found")

        # Check for class definition
        class_pattern = rf'class\s+{re.escape(cat_name)}'
        if not re.search(class_pattern, content):
            warnings.append(f"{def_file.name}: Expected class '{cat_name}' not found")

        # Check for inherits SE.App2CommonProcess.ApplicationTypes.SymbolDefinition
        if 'SymbolDefinition' not in content:
            warnings.append(f"{def_file.name}: Should inherit from SymbolDefinition")

        # Check file is not empty
        if len(content.strip()) < 100:
            warnings.append(f"{def_file.name}: File appears to be mostly empty (< 100 chars)")

    except Exception as e:
        errors.append(f"Error reading {def_file.name}: {e}")

    return errors, warnings


def validate_event_file(event_file: Path, cat_name: str) -> tuple[List[str], List[str]]:
    """
    Validate .event.cs file (event definitions).

    Args:
        event_file: Path to .event.cs file
        cat_name: Name of the CAT block

    Returns:
        Tuple of (errors, warnings)
    """
    errors = []
    warnings = []

    if not event_file.exists():
        errors.append(f"Event definition file not found: {event_file.name}")
        return errors, warnings

    try:
        content = event_file.read_text(encoding='utf-8')

        # Check for namespace declaration
        if 'namespace' not in content.lower():
            warnings.append(f"{event_file.name}: No namespace declaration found")

        # Check for partial class (events are often in partial classes)
        if 'partial class' not in content.lower():
            warnings.append(f"{event_file.name}: Expected 'partial class' declaration not found")

        # Check for event keyword (C# events)
        if 'event ' not in content:
            warnings.append(f"{event_file.name}: No C# events defined (no 'event ' keyword found)")

        # Check file is not empty
        if len(content.strip()) < 50:
            warnings.append(f"{event_file.name}: File appears to be mostly empty (< 50 chars)")

    except Exception as e:
        errors.append(f"Error reading {event_file.name}: {e}")

    return errors, warnings


def validate_cnv_files(hmi_dir: Path, cat_name: str) -> tuple[List[str], List[str]]:
    """
    Validate converter (.cnv.*) files.

    Args:
        hmi_dir: Path to HMI directory
        cat_name: Name of the CAT block

    Returns:
        Tuple of (errors, warnings)
    """
    errors = []
    warnings = []

    # Expected converter files
    expected_cnv_files = [
        f"{cat_name}_sDefault.cnv.cs",
        f"{cat_name}_sDefault.cnv.Designer.cs",
        f"{cat_name}_sDefault.cnv.resx",
        f"{cat_name}_sDefault.cnv.xml",
    ]

    for filename in expected_cnv_files:
        filepath = hmi_dir / filename
        if not filepath.exists():
            warnings.append(f"Converter file not found: {filename}")

    # Validate main .cnv.cs file if it exists
    main_cnv = hmi_dir / f"{cat_name}_sDefault.cnv.cs"
    if main_cnv.exists():
        try:
            content = main_cnv.read_text(encoding='utf-8')

            # Check for UserControl inheritance
            if 'UserControl' not in content:
                warnings.append(f"{main_cnv.name}: Should inherit from UserControl")

            # Check for partial class
            if 'partial class' not in content.lower():
                warnings.append(f"{main_cnv.name}: Expected 'partial class' declaration")

        except Exception as e:
            errors.append(f"Error reading {main_cnv.name}: {e}")

    return errors, warnings


def validate_hmi_files(hmi_dir: Path) -> ValidationResult:
    """
    Validate HMI files in a CAT block.

    Args:
        hmi_dir: Path to HMI/{CATName} directory

    Returns:
        ValidationResult with success status and any errors/warnings
    """
    errors = []
    warnings = []
    details = {}

    # ============================================================
    # Check 1: Verify directory exists and get CAT name
    # ============================================================
    if not hmi_dir.exists():
        return create_failure(
            "HMI directory not found",
            [f"Directory does not exist: {hmi_dir}"]
        )

    if not hmi_dir.is_dir():
        return create_failure(
            "Not a directory",
            [f"Path is not a directory: {hmi_dir}"]
        )

    cat_name = hmi_dir.name
    details['cat_name'] = cat_name
    details['hmi_directory'] = str(hmi_dir)

    # ============================================================
    # Check 2: Validate .def.cs file
    # ============================================================
    def_file = hmi_dir / f"{cat_name}.def.cs"
    def_errors, def_warnings = validate_def_file(def_file, cat_name)
    errors.extend(def_errors)
    warnings.extend(def_warnings)

    # ============================================================
    # Check 3: Validate .event.cs file
    # ============================================================
    event_file = hmi_dir / f"{cat_name}.event.cs"
    event_errors, event_warnings = validate_event_file(event_file, cat_name)
    errors.extend(event_errors)
    warnings.extend(event_warnings)

    # ============================================================
    # Check 4: Validate converter files
    # ============================================================
    cnv_errors, cnv_warnings = validate_cnv_files(hmi_dir, cat_name)
    errors.extend(cnv_errors)
    warnings.extend(cnv_warnings)

    # ============================================================
    # Check 5: Count files in directory
    # ============================================================
    hmi_files = list(hmi_dir.glob('*'))
    details['file_count'] = len(hmi_files)
    details['files'] = [f.name for f in hmi_files]

    # Check for resource files
    resx_files = list(hmi_dir.glob('*.resx'))
    details['resx_file_count'] = len(resx_files)

    cs_files = list(hmi_dir.glob('*.cs'))
    details['cs_file_count'] = len(cs_files)

    # ============================================================
    # Summary
    # ============================================================
    if errors:
        return create_failure(
            f"HMI validation failed with {len(errors)} error(s)",
            errors,
            warnings=warnings,
            details=details
        )
    elif warnings:
        return create_success(
            f"HMI validation passed with {len(warnings)} warning(s)",
            warnings=warnings,
            details=details
        )
    else:
        return create_success(
            f"HMI validation passed - {details['file_count']} files validated",
            details=details
        )


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
        description="Validate HMI file structure in EAE CAT blocks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate HMI files directory
  python validate_hmi.py path/to/HMI/MyCATBlock

  # Validate with verbose output
  python validate_hmi.py path/to/HMI/MyCATBlock --verbose

  # JSON output for automation
  python validate_hmi.py path/to/HMI/MyCATBlock --json

Note: This performs basic structure validation (class declarations, namespaces).
Full C# compilation is performed by the EAE IDE.
        """
    )
    parser.add_argument(
        "hmi_directory",
        type=Path,
        help="Path to HMI directory (HMI/{CATName})"
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

    # Validate
    result = validate_hmi_files(args.hmi_directory)

    # Output results
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print_validation_result(result, verbose=args.verbose)

    # Return appropriate exit code using the property from ValidationResult
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
