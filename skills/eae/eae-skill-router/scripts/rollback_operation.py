#!/usr/bin/env python3
"""
Rollback failed or unwanted fork/create operations.

Uses the tracking manifest to identify files and registration to remove,
enabling safe undo of fork operations.

Usage:
    python rollback_operation.py MyBlock SE.ScadapackWWW              # Rollback single block
    python rollback_operation.py --all-failed SE.ScadapackWWW         # Rollback all failed blocks
    python rollback_operation.py --dry-run MyBlock SE.ScadapackWWW    # Preview without changes
    python rollback_operation.py --force MyBlock SE.ScadapackWWW      # Skip confirmation

Exit codes:
    0: Rollback successful
    1: Error
    10: Block not found in tracking
    11: Rollback partially failed
"""

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict


@dataclass
class RollbackAction:
    """A single rollback action."""
    action_type: str  # "delete_folder", "delete_file", "remove_registration"
    target: str
    status: str  # "pending", "completed", "failed", "skipped"
    error: Optional[str] = None


@dataclass
class RollbackResult:
    """Result of rollback operation."""
    success: bool
    message: str
    block_name: str
    actions: List[RollbackAction] = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        d['actions'] = [asdict(a) for a in self.actions]
        return d


# Expected file locations by block type
BLOCK_LOCATIONS = {
    "cat": {
        "iec61499": "{lib}/IEC61499/{block}/",
        "hmi": "{lib}/HMI/{block}/",
    },
    "composite": {
        "iec61499": "{lib}/IEC61499/{block}/",
    },
    "basic": {
        "iec61499": "{lib}/IEC61499/{block}/",
    },
    "adapter": {
        "iec61499": "{lib}/IEC61499/{block}/",
    },
    "datatype": {
        "iec61499": "{lib}/IEC61499/DataType/",  # Files are in DataType folder
    },
}


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


def save_manifest(manifest: dict, manifest_path: Path):
    """Save the tracking manifest."""
    manifest['updated_at'] = datetime.now().isoformat()
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)


def get_block_folders(
    block_name: str,
    block_type: str,
    target_lib: str,
    project_path: Path
) -> List[Path]:
    """Get folder paths for a block."""
    folders = []
    locations = BLOCK_LOCATIONS.get(block_type, BLOCK_LOCATIONS["composite"])

    for loc_type, pattern in locations.items():
        folder_path = pattern.format(lib=target_lib, block=block_name)
        full_path = project_path / folder_path
        if full_path.exists():
            folders.append(full_path)

    return folders


def remove_dfbproj_registration(
    block_name: str,
    block_type: str,
    target_lib: str,
    project_path: Path,
    dry_run: bool = False
) -> List[RollbackAction]:
    """Remove block registration from dfbproj."""
    actions = []
    dfbproj_path = project_path / target_lib / "IEC61499" / f"{target_lib}.dfbproj"

    if not dfbproj_path.exists():
        actions.append(RollbackAction(
            action_type="remove_registration",
            target=str(dfbproj_path),
            status="skipped",
            error="dfbproj not found"
        ))
        return actions

    try:
        content = dfbproj_path.read_text(encoding='utf-8')

        # Patterns to remove (ItemGroup sections containing this block)
        patterns = [
            # CAT patterns
            rf'  <!-- {re.escape(block_name)} CAT Block -->\s*\n\s*<ItemGroup>.*?</ItemGroup>\s*\n\s*<ItemGroup>.*?</ItemGroup>',
            # Composite patterns
            rf'  <!-- {re.escape(block_name)} Composite FB -->\s*\n\s*<ItemGroup>.*?</ItemGroup>\s*\n\s*<ItemGroup>.*?</ItemGroup>',
            # Basic patterns
            rf'  <!-- {re.escape(block_name)} Basic FB -->\s*\n\s*<ItemGroup>.*?</ItemGroup>\s*\n\s*<ItemGroup>.*?</ItemGroup>',
            # Adapter patterns
            rf'  <!-- {re.escape(block_name)} Adapter -->\s*\n\s*<ItemGroup>.*?</ItemGroup>\s*\n\s*<ItemGroup>.*?</ItemGroup>',
            # DataType patterns
            rf'  <!-- {re.escape(block_name)} DataType -->\s*\n\s*<ItemGroup>.*?</ItemGroup>\s*\n\s*<ItemGroup>.*?</ItemGroup>',
            # Generic: any ItemGroup with this block's files
            rf'<ItemGroup>\s*<(?:Compile|None) Include="{re.escape(block_name)}\\[^"]*".*?</ItemGroup>',
            rf'<ItemGroup>\s*<(?:Compile|None) Include="DataType\\{re.escape(block_name)}[^"]*".*?</ItemGroup>',
        ]

        original_content = content
        for pattern in patterns:
            content = re.sub(pattern, '', content, flags=re.DOTALL)

        # Clean up multiple blank lines
        content = re.sub(r'\n{3,}', '\n\n', content)

        if content != original_content:
            if dry_run:
                actions.append(RollbackAction(
                    action_type="remove_registration",
                    target=f"dfbproj: {block_name}",
                    status="pending"
                ))
            else:
                dfbproj_path.write_text(content, encoding='utf-8')
                actions.append(RollbackAction(
                    action_type="remove_registration",
                    target=f"dfbproj: {block_name}",
                    status="completed"
                ))
        else:
            actions.append(RollbackAction(
                action_type="remove_registration",
                target=f"dfbproj: {block_name}",
                status="skipped",
                error="No registration found"
            ))

    except Exception as e:
        actions.append(RollbackAction(
            action_type="remove_registration",
            target=str(dfbproj_path),
            status="failed",
            error=str(e)
        ))

    return actions


def remove_csproj_registration(
    block_name: str,
    target_lib: str,
    project_path: Path,
    dry_run: bool = False
) -> List[RollbackAction]:
    """Remove block registration from HMI csproj (for CAT blocks)."""
    actions = []
    csproj_path = project_path / target_lib / "HMI" / f"{target_lib}.HMI.csproj"

    if not csproj_path.exists():
        return actions  # Not a CAT block or no HMI project

    try:
        content = csproj_path.read_text(encoding='utf-8')

        # Pattern to remove ItemGroup entries referencing this block
        patterns = [
            rf'<(?:Compile|None|EmbeddedResource) Include="{re.escape(block_name)}\\[^"]*"[^>]*/>\s*',
            rf'<(?:Compile|None|EmbeddedResource) Include="{re.escape(block_name)}\\[^"]*"[^>]*>.*?</(?:Compile|None|EmbeddedResource)>\s*',
        ]

        original_content = content
        for pattern in patterns:
            content = re.sub(pattern, '', content, flags=re.DOTALL)

        # Clean up empty ItemGroups
        content = re.sub(r'<ItemGroup>\s*</ItemGroup>\s*', '', content)

        if content != original_content:
            if dry_run:
                actions.append(RollbackAction(
                    action_type="remove_registration",
                    target=f"csproj: {block_name}",
                    status="pending"
                ))
            else:
                csproj_path.write_text(content, encoding='utf-8')
                actions.append(RollbackAction(
                    action_type="remove_registration",
                    target=f"csproj: {block_name}",
                    status="completed"
                ))

    except Exception as e:
        actions.append(RollbackAction(
            action_type="remove_registration",
            target=str(csproj_path),
            status="failed",
            error=str(e)
        ))

    return actions


def rollback_block(
    block_name: str,
    block_type: str,
    target_lib: str,
    project_path: Path,
    dry_run: bool = False
) -> RollbackResult:
    """Rollback a single block."""
    actions = []

    # Get folders to delete
    folders = get_block_folders(block_name, block_type, target_lib, project_path)

    for folder in folders:
        if dry_run:
            actions.append(RollbackAction(
                action_type="delete_folder",
                target=str(folder),
                status="pending"
            ))
        else:
            try:
                shutil.rmtree(folder)
                actions.append(RollbackAction(
                    action_type="delete_folder",
                    target=str(folder),
                    status="completed"
                ))
            except Exception as e:
                actions.append(RollbackAction(
                    action_type="delete_folder",
                    target=str(folder),
                    status="failed",
                    error=str(e)
                ))

    # Handle DataType (single file, not folder)
    if block_type == "datatype":
        dt_file = project_path / target_lib / "IEC61499" / "DataType" / f"{block_name}.dt"
        doc_file = project_path / target_lib / "IEC61499" / "DataType" / f"{block_name}.doc.xml"

        for file_path in [dt_file, doc_file]:
            if file_path.exists():
                if dry_run:
                    actions.append(RollbackAction(
                        action_type="delete_file",
                        target=str(file_path),
                        status="pending"
                    ))
                else:
                    try:
                        file_path.unlink()
                        actions.append(RollbackAction(
                            action_type="delete_file",
                            target=str(file_path),
                            status="completed"
                        ))
                    except Exception as e:
                        actions.append(RollbackAction(
                            action_type="delete_file",
                            target=str(file_path),
                            status="failed",
                            error=str(e)
                        ))

    # Remove dfbproj registration
    actions.extend(remove_dfbproj_registration(
        block_name, block_type, target_lib, project_path, dry_run
    ))

    # Remove csproj registration (for CAT blocks)
    if block_type == "cat":
        actions.extend(remove_csproj_registration(
            block_name, target_lib, project_path, dry_run
        ))

    # Determine success
    failed = [a for a in actions if a.status == "failed"]
    success = len(failed) == 0

    return RollbackResult(
        success=success,
        message=f"Rollback {'completed' if success else 'partially failed'} for {block_name}",
        block_name=block_name,
        actions=actions
    )


def main():
    parser = argparse.ArgumentParser(
        description="Rollback failed or unwanted fork/create operations"
    )

    parser.add_argument("block_name", nargs="?", help="Block name to rollback")
    parser.add_argument("target_lib", help="Target library name")
    parser.add_argument("--all-failed", "-a", action="store_true",
                       help="Rollback all blocks with failed status")
    parser.add_argument("--type", "-t",
                       choices=["cat", "composite", "basic", "adapter", "datatype"],
                       help="Block type (auto-detected from manifest if not specified)")
    parser.add_argument("--dry-run", "-n", action="store_true",
                       help="Show what would be done without making changes")
    parser.add_argument("--force", "-f", action="store_true",
                       help="Skip confirmation prompt")
    parser.add_argument("--project-path", "-p",
                       help="Project path")
    parser.add_argument("--json", "-j", action="store_true",
                       help="Output as JSON")

    args = parser.parse_args()

    if not args.all_failed and not args.block_name:
        parser.error("Either provide block_name or use --all-failed")

    # Find project path
    project_path = Path(args.project_path) if args.project_path else None
    project_path = find_project_path(args.target_lib, project_path)

    # Load manifest
    manifest_path = get_manifest_path(args.target_lib, project_path)
    manifest = load_manifest(manifest_path)

    blocks_to_rollback = []

    if args.all_failed:
        if not manifest:
            print(f"ERROR: No tracking manifest found for {args.target_lib}")
            sys.exit(1)

        for name, block in manifest.get('blocks', {}).items():
            if block.get('status') == 'failed':
                blocks_to_rollback.append({
                    'name': name,
                    'type': block.get('block_type', 'composite')
                })

        if not blocks_to_rollback:
            print(f"No failed blocks found in tracking for {args.target_lib}")
            sys.exit(0)
    else:
        # Single block
        block_type = args.type
        if not block_type and manifest:
            block_data = manifest.get('blocks', {}).get(args.block_name)
            if block_data:
                block_type = block_data.get('block_type', 'composite')

        if not block_type:
            # Try to detect from files
            block_type = 'composite'  # Default

        blocks_to_rollback.append({
            'name': args.block_name,
            'type': block_type
        })

    # Confirmation
    if not args.force and not args.dry_run:
        print(f"This will rollback the following blocks from {args.target_lib}:")
        for b in blocks_to_rollback:
            print(f"  - {b['name']} ({b['type']})")
        print()
        print("This will:")
        print("  - Delete IEC61499 files/folders")
        print("  - Delete HMI files/folders (for CAT blocks)")
        print("  - Remove dfbproj registration")
        print("  - Remove csproj registration (for CAT blocks)")
        print()
        response = input("Continue? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled")
            sys.exit(0)

    # Execute rollbacks
    results = []
    for block in blocks_to_rollback:
        result = rollback_block(
            block_name=block['name'],
            block_type=block['type'],
            target_lib=args.target_lib,
            project_path=project_path,
            dry_run=args.dry_run
        )
        results.append(result)

        # Update manifest
        if not args.dry_run and manifest:
            if block['name'] in manifest.get('blocks', {}):
                manifest['blocks'][block['name']]['status'] = 'rolled_back'
            save_manifest(manifest, manifest_path)

    # Output
    if args.json:
        output = {
            "success": all(r.success for r in results),
            "results": [r.to_dict() for r in results]
        }
        print(json.dumps(output, indent=2))
    else:
        for result in results:
            status = "[OK]" if result.success else "[PARTIAL]"
            prefix = "[DRY RUN] " if args.dry_run else ""
            print(f"{prefix}{status} {result.message}")

            for action in result.actions:
                if action.status == "completed":
                    print(f"  + {action.action_type}: {action.target}")
                elif action.status == "pending":
                    print(f"  ~ {action.action_type}: {action.target}")
                elif action.status == "failed":
                    print(f"  ! {action.action_type}: {action.target} - {action.error}")
                elif action.status == "skipped":
                    print(f"  - {action.action_type}: {action.target} (skipped: {action.error})")

    # Exit code
    all_success = all(r.success for r in results)
    if all_success:
        sys.exit(0)
    elif any(r.success for r in results):
        sys.exit(11)  # Partial success
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
