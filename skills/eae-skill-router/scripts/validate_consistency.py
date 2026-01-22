#!/usr/bin/env python3
"""
Cross-validation script for EAE blocks.

Verifies consistency between:
- Files on disk (IEC61499 folder)
- dfbproj registration
- Block type declarations

Usage:
    python validate_consistency.py MyBlock SE.ScadapackWWW        # Validate single block
    python validate_consistency.py --all SE.ScadapackWWW          # Validate all blocks
    python validate_consistency.py --json MyBlock SE.ScadapackWWW # JSON output
    python validate_consistency.py --fix MyBlock SE.ScadapackWWW  # Auto-fix issues

Exit codes:
    0: Validation passed (all consistent)
    1: Error (could not run validation)
    10: Validation failed (inconsistencies found)
    11: Registration issues (missing or wrong entries)
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Set
from xml.etree import ElementTree as ET


@dataclass
class ConsistencyIssue:
    """A single consistency issue."""
    category: str  # "file_missing", "registration_missing", "type_mismatch", "orphan"
    severity: str  # "error" or "warning"
    block_name: str
    message: str
    fix_action: Optional[str] = None


@dataclass
class ConsistencyResult:
    """Result of consistency validation."""
    success: bool
    message: str
    blocks_checked: int
    issues: List[ConsistencyIssue] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)

    def to_dict(self):
        d = asdict(self)
        d['issues'] = [asdict(i) for i in self.issues]
        return d


# Expected files for each block type
EXPECTED_FILES = {
    "cat": {
        "required": ["{name}.fbt", "{name}_HMI.fbt", "{name}.cfg"],
        "optional": ["{name}_CAT.offline.xml", "{name}_CAT.opcua.xml", "{name}_CAT.aspmap.xml"],
        "folder": "{name}",
    },
    "composite": {
        "required": ["{name}.fbt"],
        "optional": ["{name}.doc.xml", "{name}.meta.xml", "{name}.composite.offline.xml"],
        "folder": "{name}",
    },
    "basic": {
        "required": ["{name}.fbt"],
        "optional": ["{name}.doc.xml", "{name}.meta.xml"],
        "folder": "{name}",
    },
    "adapter": {
        "required": ["{name}.adp"],
        "optional": ["{name}.doc.xml"],
        "folder": "{name}",
    },
    "datatype": {
        "required": ["{name}.dt"],
        "optional": ["{name}.doc.xml"],
        "folder": "DataType",
    },
}

# Registration patterns for each block type
REGISTRATION_PATTERNS = {
    "cat": r'<Compile Include="{name}\\{name}\.fbt"[^>]*>\s*<IEC61499Type>CAT</IEC61499Type>',
    "composite": r'<Compile Include="{name}\\{name}\.fbt"[^>]*>\s*<IEC61499Type>Composite</IEC61499Type>',
    "basic": r'<Compile Include="{name}\\{name}\.fbt"[^>]*>\s*<IEC61499Type>Basic</IEC61499Type>',
    "adapter": r'<Compile Include="{name}\\{name}\.adp"[^>]*>\s*<IEC61499Type>Adapter</IEC61499Type>',
    "datatype": r'<Compile Include="DataType\\{name}\.dt"[^>]*>\s*<IEC61499Type>DataType</IEC61499Type>',
}


def detect_block_type_from_files(iec_path: Path, block_name: str) -> Optional[str]:
    """Detect block type from existing files."""
    # Check for DataType (in DataType subfolder)
    if (iec_path / "DataType" / f"{block_name}.dt").exists():
        return "datatype"

    # Check for Adapter
    if (iec_path / block_name / f"{block_name}.adp").exists():
        return "adapter"

    # Check for CAT (has .cfg file)
    if (iec_path / block_name / f"{block_name}.cfg").exists():
        return "cat"

    # Check for Basic/Composite (has .fbt)
    fbt_path = iec_path / block_name / f"{block_name}.fbt"
    if fbt_path.exists():
        try:
            content = fbt_path.read_text(encoding='utf-8')
            if '<BasicFB>' in content:
                return "basic"
            elif '<FBNetwork>' in content:
                return "composite"
        except Exception:
            pass
        return "composite"  # Default for .fbt

    return None


def detect_block_type_from_registration(dfbproj_content: str, block_name: str) -> Optional[str]:
    """Detect block type from dfbproj registration."""
    for block_type, pattern in REGISTRATION_PATTERNS.items():
        regex = pattern.format(name=re.escape(block_name))
        if re.search(regex, dfbproj_content, re.DOTALL):
            return block_type
    return None


def get_registered_blocks(dfbproj_content: str) -> Dict[str, str]:
    """Extract all registered blocks and their types from dfbproj."""
    blocks = {}

    # Match Compile entries with IEC61499Type
    pattern = r'<Compile Include="([^"]+)"[^>]*>\s*<IEC61499Type>([^<]+)</IEC61499Type>'
    for match in re.finditer(pattern, dfbproj_content, re.DOTALL):
        path, iec_type = match.groups()

        # Extract block name from path
        if path.startswith("DataType\\"):
            name = Path(path).stem
        else:
            name = path.split("\\")[0]

        # Map IEC61499Type to our block type
        type_map = {
            "CAT": "cat",
            "Composite": "composite",
            "Basic": "basic",
            "Adapter": "adapter",
            "DataType": "datatype",
        }
        block_type = type_map.get(iec_type)
        if block_type and name not in blocks:
            blocks[name] = block_type

    return blocks


def get_blocks_on_disk(iec_path: Path) -> Dict[str, str]:
    """Get all blocks on disk and their detected types."""
    blocks = {}

    if not iec_path.exists():
        return blocks

    # Check DataType subfolder
    datatype_path = iec_path / "DataType"
    if datatype_path.exists():
        for dt_file in datatype_path.glob("*.dt"):
            blocks[dt_file.stem] = "datatype"

    # Check block folders
    for folder in iec_path.iterdir():
        if folder.is_dir() and folder.name != "DataType":
            block_type = detect_block_type_from_files(iec_path, folder.name)
            if block_type:
                blocks[folder.name] = block_type

    return blocks


def validate_block_files(iec_path: Path, block_name: str, block_type: str, issues: List[ConsistencyIssue]):
    """Validate that expected files exist for a block."""
    expected = EXPECTED_FILES.get(block_type)
    if not expected:
        return

    folder = expected["folder"].format(name=block_name)
    block_path = iec_path / folder

    # Check folder exists
    if not block_path.exists():
        issues.append(ConsistencyIssue(
            category="file_missing",
            severity="error",
            block_name=block_name,
            message=f"Block folder missing: {folder}",
            fix_action=f"Create folder: {block_path}"
        ))
        return

    # Check required files
    for file_template in expected["required"]:
        filename = file_template.format(name=block_name)
        file_path = block_path / filename if block_type != "datatype" else iec_path / folder / filename

        if not file_path.exists():
            issues.append(ConsistencyIssue(
                category="file_missing",
                severity="error",
                block_name=block_name,
                message=f"Required file missing: {filename}",
                fix_action=f"Create file or re-fork block"
            ))

    # Check optional files (warnings only)
    for file_template in expected.get("optional", []):
        filename = file_template.format(name=block_name)
        file_path = block_path / filename if block_type != "datatype" else iec_path / folder / filename

        if not file_path.exists():
            issues.append(ConsistencyIssue(
                category="file_missing",
                severity="warning",
                block_name=block_name,
                message=f"Optional file missing: {filename}"
            ))


def validate_registration(dfbproj_content: str, block_name: str, block_type: str, issues: List[ConsistencyIssue]):
    """Validate that block is properly registered in dfbproj."""
    pattern = REGISTRATION_PATTERNS.get(block_type)
    if not pattern:
        return

    regex = pattern.format(name=re.escape(block_name))
    if not re.search(regex, dfbproj_content, re.DOTALL):
        issues.append(ConsistencyIssue(
            category="registration_missing",
            severity="error",
            block_name=block_name,
            message=f"Block not registered in dfbproj as {block_type.upper()}",
            fix_action=f"Run: python register_dfbproj.py {block_name} <library> --type {block_type}"
        ))


def validate_single_block(
    iec_path: Path,
    dfbproj_content: str,
    block_name: str,
    expected_type: Optional[str] = None
) -> List[ConsistencyIssue]:
    """Validate a single block for consistency."""
    issues = []

    # Detect types from both sources
    file_type = detect_block_type_from_files(iec_path, block_name)
    reg_type = detect_block_type_from_registration(dfbproj_content, block_name)

    # Determine the effective type
    if expected_type:
        block_type = expected_type
    elif file_type and reg_type:
        block_type = file_type  # Trust files over registration
        if file_type != reg_type:
            issues.append(ConsistencyIssue(
                category="type_mismatch",
                severity="error",
                block_name=block_name,
                message=f"Type mismatch: files indicate {file_type.upper()}, registration says {reg_type.upper()}",
                fix_action=f"Re-register with correct type: python register_dfbproj.py {block_name} <library> --type {file_type}"
            ))
    elif file_type:
        block_type = file_type
    elif reg_type:
        block_type = reg_type
        issues.append(ConsistencyIssue(
            category="file_missing",
            severity="error",
            block_name=block_name,
            message=f"Block registered as {reg_type.upper()} but files not found",
            fix_action="Re-fork block or remove registration"
        ))
        return issues
    else:
        issues.append(ConsistencyIssue(
            category="orphan",
            severity="error",
            block_name=block_name,
            message="Block not found in files or registration"
        ))
        return issues

    # Validate files
    validate_block_files(iec_path, block_name, block_type, issues)

    # Validate registration
    validate_registration(dfbproj_content, block_name, block_type, issues)

    return issues


def validate_all_blocks(iec_path: Path, dfbproj_content: str) -> ConsistencyResult:
    """Validate all blocks in a library for consistency."""
    issues = []

    # Get blocks from both sources
    disk_blocks = get_blocks_on_disk(iec_path)
    reg_blocks = get_registered_blocks(dfbproj_content)

    all_blocks = set(disk_blocks.keys()) | set(reg_blocks.keys())

    for block_name in sorted(all_blocks):
        block_issues = validate_single_block(iec_path, dfbproj_content, block_name)
        issues.extend(block_issues)

    # Categorize issues
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    summary = {
        "total_blocks": len(all_blocks),
        "blocks_on_disk": len(disk_blocks),
        "blocks_registered": len(reg_blocks),
        "errors": len(errors),
        "warnings": len(warnings),
        "file_missing": len([i for i in issues if i.category == "file_missing"]),
        "registration_missing": len([i for i in issues if i.category == "registration_missing"]),
        "type_mismatch": len([i for i in issues if i.category == "type_mismatch"]),
        "orphan": len([i for i in issues if i.category == "orphan"]),
    }

    success = len(errors) == 0

    return ConsistencyResult(
        success=success,
        message=f"Validated {len(all_blocks)} blocks: {len(errors)} error(s), {len(warnings)} warning(s)",
        blocks_checked=len(all_blocks),
        issues=issues,
        summary=summary
    )


def find_project_paths(target_lib: str, project_path: Optional[Path] = None) -> tuple:
    """Find IEC61499 path and dfbproj file."""
    if project_path is None:
        project_path = Path.cwd()
        # Walk up to find project root
        for parent in [project_path] + list(project_path.parents):
            if (parent / target_lib).exists():
                project_path = parent
                break

    iec_path = project_path / target_lib / "IEC61499"
    dfbproj_path = iec_path / f"{target_lib}.dfbproj"

    return iec_path, dfbproj_path


def main():
    parser = argparse.ArgumentParser(
        description="Cross-validate EAE blocks (files vs registration)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python validate_consistency.py MyBlock SE.ScadapackWWW
    python validate_consistency.py --all SE.ScadapackWWW
    python validate_consistency.py --json --all SE.ScadapackWWW
        """
    )

    parser.add_argument("block_name", nargs="?", help="Block name (or use --all)")
    parser.add_argument("target_lib", help="Target library name")
    parser.add_argument("--all", "-a", action="store_true",
                        help="Validate all blocks in library")
    parser.add_argument("--type", "-t", choices=["cat", "composite", "basic", "adapter", "datatype"],
                        help="Expected block type (auto-detected if not specified)")
    parser.add_argument("--project-path", "-p",
                        help="Project path (auto-detected if not specified)")
    parser.add_argument("--json", "-j", action="store_true",
                        help="Output as JSON")
    parser.add_argument("--fix", "-f", action="store_true",
                        help="Show fix commands for issues")

    args = parser.parse_args()

    if not args.all and not args.block_name:
        parser.error("Either provide block_name or use --all")

    # Find paths
    project_path = Path(args.project_path) if args.project_path else None
    iec_path, dfbproj_path = find_project_paths(args.target_lib, project_path)

    if not iec_path.exists():
        print(f"ERROR: IEC61499 path not found: {iec_path}", file=sys.stderr)
        sys.exit(1)

    if not dfbproj_path.exists():
        print(f"ERROR: dfbproj not found: {dfbproj_path}", file=sys.stderr)
        sys.exit(1)

    # Read dfbproj content
    try:
        dfbproj_content = dfbproj_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"ERROR: Could not read dfbproj: {e}", file=sys.stderr)
        sys.exit(1)

    if not args.json:
        print(f"Library: {args.target_lib}")
        print(f"IEC61499: {iec_path}")
        print(f"dfbproj: {dfbproj_path}")
        print()

    # Run validation
    if args.all:
        result = validate_all_blocks(iec_path, dfbproj_content)
    else:
        issues = validate_single_block(iec_path, dfbproj_content, args.block_name, args.type)
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]

        result = ConsistencyResult(
            success=len(errors) == 0,
            message=f"Validated block '{args.block_name}': {len(errors)} error(s), {len(warnings)} warning(s)",
            blocks_checked=1,
            issues=issues,
            summary={
                "errors": len(errors),
                "warnings": len(warnings),
            }
        )

    # Output
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.issues:
            print("Issues found:")
            for issue in result.issues:
                prefix = "ERROR" if issue.severity == "error" else "WARN"
                print(f"  [{prefix}] {issue.block_name}: {issue.message}")
                if args.fix and issue.fix_action:
                    print(f"          Fix: {issue.fix_action}")
            print()

        if args.all and result.summary:
            print("Summary:")
            print(f"  Total blocks: {result.summary.get('total_blocks', 0)}")
            print(f"  On disk: {result.summary.get('blocks_on_disk', 0)}")
            print(f"  Registered: {result.summary.get('blocks_registered', 0)}")
            print()

        status = "[OK]" if result.success else "[FAIL]"
        print(f"{status} {result.message}")

    # Exit code
    if result.success:
        sys.exit(0)
    elif any(i.category == "registration_missing" for i in result.issues):
        sys.exit(11)  # Registration issue
    else:
        sys.exit(10)  # Validation failed


if __name__ == "__main__":
    main()
