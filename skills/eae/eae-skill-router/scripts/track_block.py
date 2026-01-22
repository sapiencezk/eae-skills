#!/usr/bin/env python3
"""
Track blocks created/forked during a session.

Maintains a manifest file for tracking state across operations, enabling:
- Session-level tracking of created/forked blocks
- Rollback capability for failed operations
- Audit trail for verification

Usage:
    python track_block.py add MyBlock SE.ScadapackWWW --type cat --source SE.App2CommonProcess
    python track_block.py add MyBlock SE.ScadapackWWW --type basic --operation create
    python track_block.py remove MyBlock SE.ScadapackWWW
    python track_block.py status MyBlock SE.ScadapackWWW

Exit codes:
    0: Operation successful
    1: Error
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict


@dataclass
class TrackedBlock:
    """A tracked block entry."""
    name: str
    library: str
    block_type: str
    operation: str  # "create" or "fork"
    timestamp: str
    status: str  # "pending", "completed", "failed", "rolled_back"
    source_library: Optional[str] = None
    files_created: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


@dataclass
class TrackingManifest:
    """Session tracking manifest."""
    session_id: str
    library: str
    created_at: str
    updated_at: str
    blocks: Dict[str, TrackedBlock] = field(default_factory=dict)

    def to_dict(self):
        d = asdict(self)
        d['blocks'] = {k: asdict(v) for k, v in self.blocks.items()}
        return d

    @classmethod
    def from_dict(cls, data: dict) -> 'TrackingManifest':
        blocks = {}
        for name, block_data in data.get('blocks', {}).items():
            blocks[name] = TrackedBlock(**block_data)
        return cls(
            session_id=data['session_id'],
            library=data['library'],
            created_at=data['created_at'],
            updated_at=data['updated_at'],
            blocks=blocks
        )


def get_manifest_path(target_lib: str, project_path: Path) -> Path:
    """Get the path to the tracking manifest."""
    manifest_dir = project_path / target_lib / "IEC61499" / ".eae-tracking"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    return manifest_dir / "manifest.json"


def generate_session_id() -> str:
    """Generate a session ID."""
    import uuid
    return str(uuid.uuid4())[:8]


def load_manifest(manifest_path: Path, target_lib: str) -> TrackingManifest:
    """Load or create the tracking manifest."""
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return TrackingManifest.from_dict(data)
        except Exception:
            pass

    # Create new manifest
    now = datetime.now().isoformat()
    return TrackingManifest(
        session_id=generate_session_id(),
        library=target_lib,
        created_at=now,
        updated_at=now,
        blocks={}
    )


def save_manifest(manifest: TrackingManifest, manifest_path: Path):
    """Save the tracking manifest."""
    manifest.updated_at = datetime.now().isoformat()
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest.to_dict(), f, indent=2)


def find_project_path(target_lib: str, project_path: Optional[Path] = None) -> Path:
    """Find the project root path."""
    if project_path is None:
        project_path = Path.cwd()
        for parent in [project_path] + list(project_path.parents):
            if (parent / target_lib).exists():
                return parent
    return project_path


def add_block(
    manifest: TrackingManifest,
    block_name: str,
    block_type: str,
    operation: str,
    source_library: Optional[str] = None,
    files: Optional[List[str]] = None,
    status: str = "completed"
) -> TrackedBlock:
    """Add a block to tracking."""
    block = TrackedBlock(
        name=block_name,
        library=manifest.library,
        block_type=block_type,
        operation=operation,
        timestamp=datetime.now().isoformat(),
        status=status,
        source_library=source_library,
        files_created=files or []
    )
    manifest.blocks[block_name] = block
    return block


def remove_block(manifest: TrackingManifest, block_name: str) -> bool:
    """Remove a block from tracking."""
    if block_name in manifest.blocks:
        del manifest.blocks[block_name]
        return True
    return False


def update_status(
    manifest: TrackingManifest,
    block_name: str,
    status: str,
    error_message: Optional[str] = None
) -> bool:
    """Update block status."""
    if block_name in manifest.blocks:
        manifest.blocks[block_name].status = status
        if error_message:
            manifest.blocks[block_name].error_message = error_message
        return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Track blocks created/forked during a session"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Add command
    add_parser = subparsers.add_parser("add", help="Add block to tracking")
    add_parser.add_argument("block_name", help="Block name")
    add_parser.add_argument("target_lib", help="Target library name")
    add_parser.add_argument("--type", "-t", required=True,
                           choices=["cat", "composite", "basic", "adapter", "datatype"],
                           help="Block type")
    add_parser.add_argument("--operation", "-o", default="create",
                           choices=["create", "fork"],
                           help="Operation type")
    add_parser.add_argument("--source", "-s",
                           help="Source library (for fork operations)")
    add_parser.add_argument("--files", "-f", nargs="*",
                           help="Files created")
    add_parser.add_argument("--status", default="completed",
                           choices=["pending", "completed", "failed"],
                           help="Initial status")
    add_parser.add_argument("--project-path", "-p",
                           help="Project path")
    add_parser.add_argument("--json", "-j", action="store_true",
                           help="Output as JSON")

    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove block from tracking")
    remove_parser.add_argument("block_name", help="Block name")
    remove_parser.add_argument("target_lib", help="Target library name")
    remove_parser.add_argument("--project-path", "-p",
                              help="Project path")
    remove_parser.add_argument("--json", "-j", action="store_true",
                              help="Output as JSON")

    # Status command
    status_parser = subparsers.add_parser("status", help="Check block status")
    status_parser.add_argument("block_name", help="Block name")
    status_parser.add_argument("target_lib", help="Target library name")
    status_parser.add_argument("--project-path", "-p",
                              help="Project path")
    status_parser.add_argument("--json", "-j", action="store_true",
                              help="Output as JSON")

    # Update command
    update_parser = subparsers.add_parser("update", help="Update block status")
    update_parser.add_argument("block_name", help="Block name")
    update_parser.add_argument("target_lib", help="Target library name")
    update_parser.add_argument("--status", "-s", required=True,
                              choices=["pending", "completed", "failed", "rolled_back"],
                              help="New status")
    update_parser.add_argument("--error", "-e",
                              help="Error message (for failed status)")
    update_parser.add_argument("--project-path", "-p",
                              help="Project path")
    update_parser.add_argument("--json", "-j", action="store_true",
                              help="Output as JSON")

    args = parser.parse_args()

    # Find project path
    project_path = Path(args.project_path) if hasattr(args, 'project_path') and args.project_path else None
    project_path = find_project_path(args.target_lib, project_path)

    # Load manifest
    manifest_path = get_manifest_path(args.target_lib, project_path)
    manifest = load_manifest(manifest_path, args.target_lib)

    result = {"success": False, "message": ""}

    if args.command == "add":
        block = add_block(
            manifest=manifest,
            block_name=args.block_name,
            block_type=args.type,
            operation=args.operation,
            source_library=args.source,
            files=args.files,
            status=args.status
        )
        save_manifest(manifest, manifest_path)
        result = {
            "success": True,
            "message": f"Added {args.block_name} to tracking",
            "block": asdict(block)
        }

    elif args.command == "remove":
        if remove_block(manifest, args.block_name):
            save_manifest(manifest, manifest_path)
            result = {
                "success": True,
                "message": f"Removed {args.block_name} from tracking"
            }
        else:
            result = {
                "success": False,
                "message": f"Block {args.block_name} not found in tracking"
            }

    elif args.command == "status":
        if args.block_name in manifest.blocks:
            block = manifest.blocks[args.block_name]
            result = {
                "success": True,
                "message": f"Block {args.block_name} status: {block.status}",
                "block": asdict(block)
            }
        else:
            result = {
                "success": False,
                "message": f"Block {args.block_name} not found in tracking"
            }

    elif args.command == "update":
        error_msg = args.error if hasattr(args, 'error') else None
        if update_status(manifest, args.block_name, args.status, error_msg):
            save_manifest(manifest, manifest_path)
            result = {
                "success": True,
                "message": f"Updated {args.block_name} status to {args.status}"
            }
        else:
            result = {
                "success": False,
                "message": f"Block {args.block_name} not found in tracking"
            }

    # Output
    if hasattr(args, 'json') and args.json:
        print(json.dumps(result, indent=2))
    else:
        status = "[OK]" if result["success"] else "[FAIL]"
        print(f"{status} {result['message']}")
        if "block" in result and not args.json:
            block = result["block"]
            print(f"  Type: {block['block_type']}")
            print(f"  Operation: {block['operation']}")
            print(f"  Status: {block['status']}")
            if block.get('source_library'):
                print(f"  Source: {block['source_library']}")

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
