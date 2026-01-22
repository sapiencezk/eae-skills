#!/usr/bin/env python3
"""
Pre-flight validation for eae-fork operations.

Checks prerequisites before fork operations to catch errors early:
- Source library exists
- Source block exists with required files
- Target library exists
- Target block doesn't already exist (or warn)
- Block type detection

Usage:
    python preflight_check.py AnalogInput SE.App2CommonProcess SE.ScadapackWWW
    python preflight_check.py --json AnalogInput SE.App2CommonProcess SE.ScadapackWWW
    python preflight_check.py --allow-overwrite AnalogInput SE.App2CommonProcess SE.ScadapackWWW

Exit codes:
    0: Pre-flight passed, ready to fork
    1: Error (missing arguments, etc.)
    10: Pre-flight failed (prerequisites not met)
    11: Warning (target exists, use --allow-overwrite)
"""

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict
from xml.etree import ElementTree as ET


@dataclass
class PreflightIssue:
    """A single pre-flight issue."""
    category: str  # "source", "target", "config"
    severity: str  # "error" or "warning"
    message: str
    fix_hint: Optional[str] = None


@dataclass
class PreflightResult:
    """Result of pre-flight validation."""
    ready_to_fork: bool
    block_name: str
    source_library: str
    target_library: str
    detected_type: Optional[str] = None
    source_files: List[str] = field(default_factory=list)
    issues: List[PreflightIssue] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self):
        d = asdict(self)
        d['issues'] = [asdict(i) for i in self.issues]
        return d


# Standard library locations
LIBRARY_PATHS = [
    Path(r"C:\ProgramData\Schneider Electric\Libraries"),
    Path(r"C:\Users\Public\Documents\Schneider Electric\Libraries"),
]


def find_source_library(library_name: str) -> Optional[Path]:
    """Find the source library in standard locations."""
    for base_path in LIBRARY_PATHS:
        if not base_path.exists():
            continue

        # Look for library with version suffix
        for lib_dir in base_path.iterdir():
            if lib_dir.is_dir() and lib_dir.name.startswith(f"{library_name}-"):
                return lib_dir

        # Also check exact name
        exact_path = base_path / library_name
        if exact_path.exists():
            return exact_path

    return None


def find_source_block(library_path: Path, block_name: str) -> Optional[Path]:
    """Find the source block in the library."""
    # Check in Files/ subfolder (uncompiled source)
    files_path = library_path / "Files" / block_name
    if files_path.exists():
        return files_path

    # Check in IEC61499/ subfolder
    iec_path = library_path / "IEC61499" / block_name
    if iec_path.exists():
        return iec_path

    # Check for DataType
    dt_path = library_path / "Files" / "DataType" / f"{block_name}.dt"
    if dt_path.exists():
        return dt_path.parent

    return None


def detect_block_type(block_path: Path, block_name: str) -> Optional[str]:
    """Detect block type from source files."""
    # Check for DataType
    if (block_path / f"{block_name}.dt").exists():
        return "datatype"

    # Check for Adapter
    if (block_path / f"{block_name}.adp").exists():
        return "adapter"

    # Check for CAT (has .cfg)
    if (block_path / f"{block_name}.cfg").exists():
        return "cat"

    # Check for Basic/Composite (has .fbt)
    fbt_path = block_path / f"{block_name}.fbt"
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


def get_source_files(block_path: Path, block_name: str, block_type: str) -> List[str]:
    """Get list of files in source block."""
    files = []
    if block_path.exists():
        for f in block_path.iterdir():
            if f.is_file():
                files.append(f.name)
    return sorted(files)


def find_target_library(target_lib: str, project_path: Optional[Path] = None) -> Optional[Path]:
    """Find target library in the project."""
    if project_path is None:
        project_path = Path.cwd()
        for parent in [project_path] + list(project_path.parents):
            if (parent / target_lib).exists():
                project_path = parent
                break

    target_path = project_path / target_lib
    if target_path.exists():
        return target_path
    return None


def check_target_exists(target_lib_path: Path, block_name: str) -> bool:
    """Check if block already exists in target."""
    iec_path = target_lib_path / "IEC61499"

    # Check block folder
    if (iec_path / block_name).exists():
        return True

    # Check DataType
    if (iec_path / "DataType" / f"{block_name}.dt").exists():
        return True

    return False


def run_preflight(
    block_name: str,
    source_library: str,
    target_library: str,
    allow_overwrite: bool = False,
    project_path: Optional[Path] = None
) -> PreflightResult:
    """Run pre-flight validation."""
    issues = []
    result = PreflightResult(
        ready_to_fork=False,
        block_name=block_name,
        source_library=source_library,
        target_library=target_library
    )

    # Check source library
    source_lib_path = find_source_library(source_library)
    if not source_lib_path:
        issues.append(PreflightIssue(
            category="source",
            severity="error",
            message=f"Source library '{source_library}' not found",
            fix_hint=f"Check if {source_library} is installed in C:\\ProgramData\\Schneider Electric\\Libraries"
        ))
    else:
        result.metadata['source_library_path'] = str(source_lib_path)

        # Check source block
        source_block_path = find_source_block(source_lib_path, block_name)
        if not source_block_path:
            issues.append(PreflightIssue(
                category="source",
                severity="error",
                message=f"Block '{block_name}' not found in '{source_library}'",
                fix_hint=f"Check spelling or verify block exists in library"
            ))
        else:
            result.metadata['source_block_path'] = str(source_block_path)

            # Detect type
            block_type = detect_block_type(source_block_path, block_name)
            if block_type:
                result.detected_type = block_type
                result.source_files = get_source_files(source_block_path, block_name, block_type)
            else:
                issues.append(PreflightIssue(
                    category="source",
                    severity="warning",
                    message=f"Could not detect block type for '{block_name}'",
                    fix_hint="Specify type manually during fork"
                ))

            # Check for required files
            if block_type == "cat":
                required = [f"{block_name}.fbt", f"{block_name}.cfg"]
                for req in required:
                    if req not in result.source_files:
                        issues.append(PreflightIssue(
                            category="source",
                            severity="error",
                            message=f"Required file missing in source: {req}"
                        ))

    # Check target library
    target_lib_path = find_target_library(target_library, project_path)
    if not target_lib_path:
        issues.append(PreflightIssue(
            category="target",
            severity="error",
            message=f"Target library '{target_library}' not found in project",
            fix_hint="Ensure you're in the correct project directory"
        ))
    else:
        result.metadata['target_library_path'] = str(target_lib_path)

        # Check if target already exists
        if check_target_exists(target_lib_path, block_name):
            if allow_overwrite:
                issues.append(PreflightIssue(
                    category="target",
                    severity="warning",
                    message=f"Block '{block_name}' already exists in target (will be overwritten)"
                ))
            else:
                issues.append(PreflightIssue(
                    category="target",
                    severity="error",
                    message=f"Block '{block_name}' already exists in target library",
                    fix_hint="Use --allow-overwrite to replace, or choose a different name"
                ))

        # Check dfbproj exists
        dfbproj_path = target_lib_path / "IEC61499" / f"{target_library}.dfbproj"
        if not dfbproj_path.exists():
            issues.append(PreflightIssue(
                category="target",
                severity="error",
                message=f"Target dfbproj not found: {dfbproj_path.name}",
                fix_hint="Verify library structure is correct"
            ))

    # Determine if ready
    result.issues = issues
    errors = [i for i in issues if i.severity == "error"]
    result.ready_to_fork = len(errors) == 0

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Pre-flight validation for fork operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python preflight_check.py AnalogInput SE.App2CommonProcess SE.ScadapackWWW
    python preflight_check.py --allow-overwrite AnalogInput SE.App2CommonProcess SE.ScadapackWWW
        """
    )

    parser.add_argument("block_name", help="Block to fork")
    parser.add_argument("source_library", help="Source library name")
    parser.add_argument("target_library", help="Target library name")
    parser.add_argument("--allow-overwrite", "-f", action="store_true",
                       help="Allow overwriting existing target block")
    parser.add_argument("--project-path", "-p",
                       help="Project path")
    parser.add_argument("--json", "-j", action="store_true",
                       help="Output as JSON")

    args = parser.parse_args()

    project_path = Path(args.project_path) if args.project_path else None

    result = run_preflight(
        block_name=args.block_name,
        source_library=args.source_library,
        target_library=args.target_library,
        allow_overwrite=args.allow_overwrite,
        project_path=project_path
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"Pre-flight Check: {args.block_name}")
        print(f"  Source: {args.source_library}")
        print(f"  Target: {args.target_library}")
        print()

        if result.detected_type:
            print(f"Detected type: {result.detected_type.upper()}")
            print(f"Source files: {len(result.source_files)}")
            for f in result.source_files[:10]:  # Limit display
                print(f"  - {f}")
            if len(result.source_files) > 10:
                print(f"  ... and {len(result.source_files) - 10} more")
            print()

        if result.issues:
            print("Issues:")
            for issue in result.issues:
                prefix = "ERROR" if issue.severity == "error" else "WARN"
                print(f"  [{prefix}] {issue.message}")
                if issue.fix_hint:
                    print(f"          Hint: {issue.fix_hint}")
            print()

        if result.ready_to_fork:
            print("[OK] Pre-flight passed - ready to fork")
            sys.exit(0)
        else:
            errors = [i for i in result.issues if i.severity == "error"]
            if any(i.category == "target" and "already exists" in i.message for i in errors):
                print("[BLOCKED] Target already exists (use --allow-overwrite)")
                sys.exit(11)
            else:
                print("[FAIL] Pre-flight failed - cannot proceed")
                sys.exit(10)


if __name__ == "__main__":
    main()
