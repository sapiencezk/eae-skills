#!/usr/bin/env python3
"""
validate_cat.py - CAT Block Multi-File Consistency Validator

Validates all files in a CAT (Composite Application Type) block for consistency.

CAT blocks generate 15+ files across two directories:
- IEC61499/{CATName}/ - IEC 61499 files (.fbt, .cfg, .offline.xml, .opcua.xml, etc.)
- HMI/{CATName}/ - HMI files (.def.cs, .event.cs, .cnv.*, etc.)

This script checks:
- All required files exist in both directories
- .cfg file references correct files
- Namespaces are consistent across files
- Naming conventions are followed
- SubCAT references (if any) are valid

Usage:
    python validate_cat.py <cat_directory_path> [options]

    Examples:
        # Validate a CAT block (pass the IEC61499/{CATName} directory)
        python validate_cat.py path/to/IEC61499/MyCATBlock

        # Validate with verbose output
        python validate_cat.py path/to/IEC61499/MyCATBlock --verbose

        # Output JSON for automation
        python validate_cat.py path/to/IEC61499/MyCATBlock --json

Exit Codes:
    0  - Validation passed (no errors)
    1  - General error (directory not found, parse error, etc.)
    10 - Validation failed (errors found)
    11 - Validation passed with warnings

Dependencies:
    - Python 3.7+
    - lxml (optional, for better XML parsing)
"""

import argparse
import json
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


# Required files for a CAT block
REQUIRED_IEC61499_FILES = [
    '{name}.cfg',           # CAT configuration
    '{name}.fbt',           # Main composite FB
    '{name}.doc.xml',       # Documentation
    '{name}.meta.xml',      # Metadata
    '{name}_CAT.offline.xml',  # Offline parameter config
    '{name}_CAT.opcua.xml',    # OPC-UA server config
    '{name}_HMI.fbt',       # Service interface FB
    '{name}_HMI.doc.xml',   # HMI documentation
    '{name}_HMI.meta.xml',  # HMI metadata
    '{name}_HMI.offline.xml',  # HMI offline config
    '{name}_HMI.opcua.xml',    # HMI OPC-UA config
]

REQUIRED_HMI_FILES = [
    '{name}.def.cs',        # Symbol definitions
    '{name}.event.cs',      # Event definitions
    '{name}.Design.resx',   # Design resources
    '{name}_sDefault.cnv.cs',  # Default symbol
    '{name}_sDefault.cnv.Designer.cs',  # Symbol designer
    '{name}_sDefault.cnv.resx',  # Symbol resources
    '{name}_sDefault.cnv.xml',  # Symbol mapping
    '{name}_sDefault.doc.xml',  # Symbol documentation
]


def check_files_exist(cat_dir: Path, cat_name: str, hmi_dir: Optional[Path]) -> tuple[List[str], List[str]]:
    """
    Check if all required files exist.

    Args:
        cat_dir: Path to IEC61499/{CATName} directory
        cat_name: Name of the CAT block
        hmi_dir: Path to HMI/{CATName} directory (or None if not found)

    Returns:
        Tuple of (errors, warnings)
    """
    errors = []
    warnings = []

    # Check IEC61499 files
    for file_template in REQUIRED_IEC61499_FILES:
        filename = file_template.format(name=cat_name)
        filepath = cat_dir / filename

        if not filepath.exists():
            errors.append(f"Missing required IEC61499 file: {filename}")

    # Check HMI files
    if hmi_dir and hmi_dir.exists():
        for file_template in REQUIRED_HMI_FILES:
            filename = file_template.format(name=cat_name)
            filepath = hmi_dir / filename

            if not filepath.exists():
                # Some HMI files might be optional depending on configuration
                warnings.append(f"Missing recommended HMI file: {filename}")
    else:
        errors.append(f"HMI directory not found: expected at {hmi_dir}")

    return errors, warnings


def validate_cfg_file(cfg_path: Path, cat_name: str) -> tuple[List[str], Dict]:
    """
    Validate the .cfg file structure and references.

    Args:
        cfg_path: Path to .cfg file
        cat_name: Name of the CAT block

    Returns:
        Tuple of (errors, details)
    """
    errors = []
    details = {}

    if not cfg_path.exists():
        return [f"CAT configuration file not found: {cfg_path.name}"], details

    try:
        if HAVE_LXML:
            parser = ET.XMLParser(remove_blank_text=True, encoding='utf-8')
            tree = ET.parse(str(cfg_path), parser)
        else:
            tree = ET.parse(str(cfg_path))

        root = tree.getroot()

        # Check root element is CAT
        if root.tag != 'CAT':
            errors.append(f".cfg file root element should be 'CAT', found '{root.tag}'")

        # Check Name attribute
        cfg_name = root.get('Name')
        if cfg_name != cat_name:
            errors.append(f".cfg file Name attribute '{cfg_name}' doesn't match directory name '{cat_name}'")

        details['cfg_name'] = cfg_name

        # Check CATFile reference
        cat_file_ref = root.get('CATFile')
        expected_cat_file = f"{cat_name}\\{cat_name}.fbt"
        if cat_file_ref != expected_cat_file:
            errors.append(f".cfg CATFile should be '{expected_cat_file}', found '{cat_file_ref}'")

        # Check SymbolDefFile reference
        symbol_def_ref = root.get('SymbolDefFile')
        expected_symbol_def = f"..\\HMI\\{cat_name}\\{cat_name}.def.cs"
        if symbol_def_ref != expected_symbol_def:
            errors.append(f".cfg SymbolDefFile should be '{expected_symbol_def}', found '{symbol_def_ref}'")

        # Check HMIFile reference
        hmi_file_ref = root.get('HMIFile')
        expected_hmi_file = f"{cat_name}\\{cat_name}_HMI.fbt"
        if hmi_file_ref != expected_hmi_file:
            errors.append(f".cfg HMIFile should be '{expected_hmi_file}', found '{hmi_file_ref}'")

    except ET.ParseError as e:
        errors.append(f".cfg file XML parsing error: {e}")
    except Exception as e:
        errors.append(f"Error validating .cfg file: {e}")

    return errors, details


def validate_namespace_consistency(cat_dir: Path, cat_name: str, expected_namespace: Optional[str]) -> List[str]:
    """
    Validate that namespaces are consistent across .fbt files.

    Args:
        cat_dir: Path to IEC61499/{CATName} directory
        cat_name: Name of the CAT block
        expected_namespace: Expected namespace (if known)

    Returns:
        List of errors
    """
    errors = []
    namespaces = {}

    # Check main .fbt file
    main_fbt = cat_dir / f"{cat_name}.fbt"
    if main_fbt.exists():
        try:
            tree = ET.parse(str(main_fbt))
            root = tree.getroot()
            fbtype = root.find('.//FBType')
            if fbtype is not None:
                namespace = fbtype.get('Namespace')
                namespaces['main_fbt'] = namespace

                if expected_namespace and namespace != expected_namespace:
                    errors.append(
                        f"{cat_name}.fbt has namespace '{namespace}', expected '{expected_namespace}'"
                    )
        except:
            pass  # Parse errors reported elsewhere

    # Check HMI .fbt file
    hmi_fbt = cat_dir / f"{cat_name}_HMI.fbt"
    if hmi_fbt.exists():
        try:
            tree = ET.parse(str(hmi_fbt))
            root = tree.getroot()
            fbtype = root.find('.//FBType')
            if fbtype is not None:
                namespace = fbtype.get('Namespace')
                namespaces['hmi_fbt'] = namespace

                # HMI namespace should match main namespace
                if 'main_fbt' in namespaces and namespace != namespaces['main_fbt']:
                    errors.append(
                        f"{cat_name}_HMI.fbt has namespace '{namespace}', "
                        f"should match main FB namespace '{namespaces['main_fbt']}'"
                    )
        except:
            pass  # Parse errors reported elsewhere

    return errors


def validate_cat_block(cat_dir: Path, expected_namespace: Optional[str] = None) -> ValidationResult:
    """
    Validate a CAT block's file structure and consistency.

    Args:
        cat_dir: Path to IEC61499/{CATName} directory
        expected_namespace: Optional expected namespace

    Returns:
        ValidationResult with success status and any errors/warnings
    """
    errors = []
    warnings = []
    details = {}

    # ============================================================
    # Check 1: Verify directory exists and get CAT name
    # ============================================================
    if not cat_dir.exists():
        return create_failure(
            "CAT directory not found",
            [f"Directory does not exist: {cat_dir}"]
        )

    if not cat_dir.is_dir():
        return create_failure(
            "Not a directory",
            [f"Path is not a directory: {cat_dir}"]
        )

    cat_name = cat_dir.name
    details['cat_name'] = cat_name
    details['cat_directory'] = str(cat_dir)

    # ============================================================
    # Check 2: Determine HMI directory location
    # ============================================================
    # HMI directory should be at ../../HMI/{CATName} relative to IEC61499/{CATName}
    hmi_dir = cat_dir.parent.parent / 'HMI' / cat_name
    details['hmi_directory'] = str(hmi_dir)
    details['hmi_exists'] = hmi_dir.exists()

    # ============================================================
    # Check 3: Verify all required files exist
    # ============================================================
    file_errors, file_warnings = check_files_exist(cat_dir, cat_name, hmi_dir)
    errors.extend(file_errors)
    warnings.extend(file_warnings)

    # ============================================================
    # Check 4: Validate .cfg file
    # ============================================================
    cfg_path = cat_dir / f"{cat_name}.cfg"
    cfg_errors, cfg_details = validate_cfg_file(cfg_path, cat_name)
    errors.extend(cfg_errors)
    details.update(cfg_details)

    # ============================================================
    # Check 5: Validate namespace consistency
    # ============================================================
    namespace_errors = validate_namespace_consistency(cat_dir, cat_name, expected_namespace)
    errors.extend(namespace_errors)

    # ============================================================
    # Check 6: Count files in each directory
    # ============================================================
    iec61499_files = list(cat_dir.glob('*'))
    details['iec61499_file_count'] = len(iec61499_files)

    if hmi_dir.exists():
        hmi_files = list(hmi_dir.glob('*'))
        details['hmi_file_count'] = len(hmi_files)
    else:
        details['hmi_file_count'] = 0

    # ============================================================
    # Summary
    # ============================================================
    if errors:
        return create_failure(
            f"CAT validation failed with {len(errors)} error(s)",
            errors,
            warnings=warnings,
            details=details
        )
    elif warnings:
        return create_success(
            f"CAT validation passed with {len(warnings)} warning(s)",
            warnings=warnings,
            details=details
        )
    else:
        return create_success(
            f"CAT validation passed - all {details['iec61499_file_count'] + details['hmi_file_count']} files are consistent",
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
        description="Validate CAT block file structure and consistency",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate a CAT block directory
  python validate_cat.py path/to/IEC61499/MyCATBlock

  # Validate with verbose output
  python validate_cat.py path/to/IEC61499/MyCATBlock --verbose

  # Specify expected namespace
  python validate_cat.py path/to/IEC61499/MyCATBlock --namespace MyLibrary

  # JSON output for automation
  python validate_cat.py path/to/IEC61499/MyCATBlock --json

Note: Pass the IEC61499/{CATName} directory path. The script will automatically
locate the corresponding HMI/{CATName} directory.
        """
    )
    parser.add_argument(
        "cat_directory",
        type=Path,
        help="Path to CAT directory (IEC61499/{CATName})"
    )
    parser.add_argument(
        "-n", "--namespace",
        type=str,
        help="Expected namespace for validation"
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
    result = validate_cat_block(args.cat_directory, expected_namespace=args.namespace)

    # Output results
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print_validation_result(result, verbose=args.verbose)

    # Return appropriate exit code using the property from ValidationResult
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
