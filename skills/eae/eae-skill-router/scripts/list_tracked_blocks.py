#!/usr/bin/env python3
"""
List blocks tracked during the current session.

Usage:
    python list_tracked_blocks.py SE.ScadapackWWW              # List all tracked blocks
    python list_tracked_blocks.py SE.ScadapackWWW --status failed  # Filter by status
    python list_tracked_blocks.py SE.ScadapackWWW --type cat       # Filter by type
    python list_tracked_blocks.py SE.ScadapackWWW --json           # JSON output
    python list_tracked_blocks.py SE.ScadapackWWW --clear          # Clear tracking

Exit codes:
    0: Success
    1: Error or no manifest found
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List


def get_manifest_path(target_lib: str, project_path: Path) -> Path:
    """Get the path to the tracking manifest."""
    return project_path / target_lib / "IEC61499" / ".eae-tracking" / "manifest.json"


def find_project_path(target_lib: str, project_path: Optional[Path] = None) -> Path:
    """Find the project root path."""
    if project_path is None:
        project_path = Path.cwd()
        for parent in [project_path] + list(project_path.parents):
            if (parent / target_lib).exists():
                return parent
    return project_path


def load_manifest(manifest_path: Path) -> Optional[dict]:
    """Load the tracking manifest."""
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def filter_blocks(
    blocks: dict,
    status: Optional[str] = None,
    block_type: Optional[str] = None,
    operation: Optional[str] = None
) -> dict:
    """Filter blocks by criteria."""
    filtered = {}
    for name, block in blocks.items():
        if status and block.get('status') != status:
            continue
        if block_type and block.get('block_type') != block_type:
            continue
        if operation and block.get('operation') != operation:
            continue
        filtered[name] = block
    return filtered


def format_timestamp(ts: str) -> str:
    """Format ISO timestamp for display."""
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ts


def main():
    parser = argparse.ArgumentParser(
        description="List blocks tracked during the current session"
    )
    parser.add_argument("target_lib", help="Target library name")
    parser.add_argument("--status", "-s",
                       choices=["pending", "completed", "failed", "rolled_back"],
                       help="Filter by status")
    parser.add_argument("--type", "-t",
                       choices=["cat", "composite", "basic", "adapter", "datatype"],
                       help="Filter by block type")
    parser.add_argument("--operation", "-o",
                       choices=["create", "fork"],
                       help="Filter by operation")
    parser.add_argument("--project-path", "-p",
                       help="Project path")
    parser.add_argument("--json", "-j", action="store_true",
                       help="Output as JSON")
    parser.add_argument("--clear", "-c", action="store_true",
                       help="Clear the tracking manifest")
    parser.add_argument("--summary", action="store_true",
                       help="Show summary only")

    args = parser.parse_args()

    # Find project path
    project_path = Path(args.project_path) if args.project_path else None
    project_path = find_project_path(args.target_lib, project_path)

    manifest_path = get_manifest_path(args.target_lib, project_path)

    # Clear tracking
    if args.clear:
        if manifest_path.exists():
            manifest_path.unlink()
            print(f"[OK] Cleared tracking manifest for {args.target_lib}")
            sys.exit(0)
        else:
            print(f"[INFO] No tracking manifest found for {args.target_lib}")
            sys.exit(0)

    # Load manifest
    manifest = load_manifest(manifest_path)
    if not manifest:
        if args.json:
            print(json.dumps({"error": "No tracking manifest found", "blocks": []}))
        else:
            print(f"[INFO] No tracking manifest found for {args.target_lib}")
            print(f"       Path checked: {manifest_path}")
        sys.exit(1)

    blocks = manifest.get('blocks', {})

    # Apply filters
    filtered_blocks = filter_blocks(
        blocks,
        status=args.status,
        block_type=args.type,
        operation=args.operation
    )

    # Build result
    result = {
        "session_id": manifest.get('session_id'),
        "library": manifest.get('library'),
        "created_at": manifest.get('created_at'),
        "updated_at": manifest.get('updated_at'),
        "total_blocks": len(blocks),
        "filtered_blocks": len(filtered_blocks),
        "blocks": list(filtered_blocks.values()),
        "summary": {
            "by_status": {},
            "by_type": {},
            "by_operation": {}
        }
    }

    # Build summary
    for block in blocks.values():
        status = block.get('status', 'unknown')
        btype = block.get('block_type', 'unknown')
        op = block.get('operation', 'unknown')

        result['summary']['by_status'][status] = result['summary']['by_status'].get(status, 0) + 1
        result['summary']['by_type'][btype] = result['summary']['by_type'].get(btype, 0) + 1
        result['summary']['by_operation'][op] = result['summary']['by_operation'].get(op, 0) + 1

    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Library: {args.target_lib}")
        print(f"Session: {result['session_id']}")
        print(f"Updated: {format_timestamp(result['updated_at'])}")
        print()

        if args.summary:
            print("Summary:")
            print(f"  Total blocks: {result['total_blocks']}")
            print()
            print("  By status:")
            for status, count in result['summary']['by_status'].items():
                print(f"    {status}: {count}")
            print()
            print("  By type:")
            for btype, count in result['summary']['by_type'].items():
                print(f"    {btype}: {count}")
            print()
            print("  By operation:")
            for op, count in result['summary']['by_operation'].items():
                print(f"    {op}: {count}")
        else:
            if not filtered_blocks:
                print("No blocks match the filter criteria")
            else:
                # Table header
                print(f"{'Block':<25} {'Type':<12} {'Operation':<10} {'Status':<12} {'Time'}")
                print("-" * 80)

                for name, block in sorted(filtered_blocks.items()):
                    btype = block.get('block_type', '-')
                    op = block.get('operation', '-')
                    status = block.get('status', '-')
                    ts = format_timestamp(block.get('timestamp', '-'))
                    print(f"{name:<25} {btype:<12} {op:<10} {status:<12} {ts}")

                print()
                print(f"Total: {len(filtered_blocks)} block(s)")

    sys.exit(0)


if __name__ == "__main__":
    main()
