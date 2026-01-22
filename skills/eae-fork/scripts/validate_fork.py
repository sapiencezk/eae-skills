#!/usr/bin/env python3
"""
Validate EAE block fork prerequisites.

This script checks that source blocks exist BEFORE user performs manual fork in GUI.
Prevents wasted time by catching issues early.

Usage:
    python validate_fork.py <source_lib> <block_name>... [--json]

Example:
    python validate_fork.py SE.App2CommonProcess MotorVsBase MotorVsBaseExt MotorVs
    python validate_fork.py SE.App2CommonProcess AnalogInput --json

Exit Codes:
    0 - Validation passed, ready to fork
    1 - General error
    10 - Validation failed (blocks not found or other issues)
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

# ASCII-safe symbols for cross-platform compatibility
SYMBOLS = {
    'ok': '[OK]',
    'error': '[ERROR]',
    'success': '[SUCCESS]',
    'info': '[INFO]',
    'warn': '[WARN]',
}


def validate_fork(source_lib: str, block_names: List[str]) -> Dict:
    """
    Validate blocks exist in source library before fork.

    Args:
        source_lib: Source library name (e.g., "SE.App2CommonProcess")
        block_names: List of block names to fork

    Returns:
        Dict with keys:
            - valid: bool (overall validation result)
            - source_library_path: Path or None
            - source_version: str or None
            - missing_blocks: List[str]
            - source_namespace: str or None
            - warnings: List[str]
    """
    result = {
        "valid": True,
        "source_library_path": None,
        "source_version": None,
        "missing_blocks": [],
        "source_namespace": None,
        "warnings": []
    }

    # Find source library
    lib_root = Path("C:/ProgramData/Schneider Electric/Libraries")
    if not lib_root.exists():
        result["valid"] = False
        result["warnings"].append(f"Libraries directory not found: {lib_root}")
        return result

    # Match library with version (e.g., SE.App2CommonProcess-25.0.1.5)
    lib_paths = list(lib_root.glob(f"{source_lib}-*"))
    if not lib_paths:
        result["valid"] = False
        result["warnings"].append(f"Source library '{source_lib}' not found in {lib_root}")
        return result

    # Use most recent version (highest version number)
    lib_path = max(lib_paths, key=lambda p: p.name)
    result["source_library_path"] = str(lib_path)
    result["source_version"] = lib_path.name.split('-')[-1]

    # Check each block exists
    files_dir = lib_path / "Files"
    for block in block_names:
        block_path = files_dir / block
        if not block_path.exists():
            result["valid"] = False
            result["missing_blocks"].append(block)
            result["warnings"].append(f"Block '{block}' not found in {source_lib}")

    # If blocks found, detect source namespace from first block
    if block_names and not result["missing_blocks"]:
        first_block = block_names[0]
        fbt_file = files_dir / first_block / f"{first_block}.fbt"

        if fbt_file.exists():
            content = fbt_file.read_text(encoding='utf-8')
            match = re.search(r'<FBType[^>]*\sNamespace="([^"]*)"', content)
            if match:
                result["source_namespace"] = match.group(1)
            else:
                result["warnings"].append(f"Could not detect namespace from {first_block}.fbt")
        else:
            result["valid"] = False
            result["warnings"].append(f"Block file not found: {fbt_file}")

    # Validate all blocks come from same namespace
    if result["source_namespace"]:
        for block in block_names:
            fbt_file = files_dir / block / f"{block}.fbt"
            if fbt_file.exists():
                content = fbt_file.read_text(encoding='utf-8')
                match = re.search(r'<FBType[^>]*\sNamespace="([^"]*)"', content)
                if match and match.group(1) != result["source_namespace"]:
                    result["valid"] = False
                    result["warnings"].append(
                        f"Block '{block}' has different namespace: {match.group(1)} "
                        f"(expected {result['source_namespace']})"
                    )

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Validate EAE block fork prerequisites",
        epilog="""
Examples:
  # Validate single block
  python validate_fork.py SE.App2CommonProcess MotorVs

  # Validate hierarchy
  python validate_fork.py SE.App2CommonProcess MotorVsBase MotorVsBaseExt MotorVs

  # JSON output (for automation)
  python validate_fork.py SE.App2CommonProcess AnalogInput --json
        """
    )
    parser.add_argument("source_lib", help="Source library (e.g., SE.App2CommonProcess)")
    parser.add_argument("blocks", nargs='+', help="Block name(s) to validate")
    parser.add_argument("--json", action="store_true", help="Output JSON format")

    args = parser.parse_args()

    # Run validation
    result = validate_fork(args.source_lib, args.blocks)

    # Output
    if args.json:
        # JSON output for automation
        print(json.dumps(result, indent=2))
    else:
        # Human-readable output
        print(f"\n{SYMBOLS['info']} Validating fork prerequisites...")
        print(f"  Source: {args.source_lib}")
        print(f"  Blocks: {', '.join(args.blocks)}\n")

        if result["source_library_path"]:
            print(f"{SYMBOLS['ok']} Found source library: {Path(result['source_library_path']).name}")
        if result["source_namespace"]:
            print(f"{SYMBOLS['ok']} Detected namespace: {result['source_namespace']}")

        if result["missing_blocks"]:
            print(f"\n{SYMBOLS['error']} Missing blocks:")
            for block in result["missing_blocks"]:
                print(f"  - {block}")

        if result["warnings"] and not result["missing_blocks"]:
            print(f"\n{SYMBOLS['warn']} Warnings:")
            for warning in result["warnings"]:
                print(f"  - {warning}")

        if result["valid"]:
            print(f"\n{SYMBOLS['success']} Validation passed - ready to fork!")
            print(f"  {len(args.blocks)} block(s) found in {args.source_lib}")
            sys.exit(0)
        else:
            print(f"\n{SYMBOLS['error']} Validation failed")
            print(f"\nPlease fix these issues before forking:")
            for warning in result["warnings"]:
                print(f"  - {warning}")
            sys.exit(10)


if __name__ == "__main__":
    main()
