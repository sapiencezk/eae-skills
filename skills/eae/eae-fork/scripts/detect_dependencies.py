#!/usr/bin/env python3
"""
Detect EAE block dependencies by parsing .cfg files.

Recursively finds all SubCAT blocks referenced by a CAT block to help users
fork complete hierarchies without missing required dependencies.

Usage:
    python detect_dependencies.py <source_lib> <block_name> [--json] [--max-depth N]

Example:
    python detect_dependencies.py SE.App2CommonProcess AnalogInput
    python detect_dependencies.py SE.App2CommonProcess MotorVs --max-depth 2

Exit Codes:
    0 - Success
    1 - Error (block not found, parsing failed, etc.)
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Optional
from xml.etree import ElementTree as ET


# ASCII-safe symbols for cross-platform compatibility
SYMBOLS = {
    'ok': '[OK]',
    'error': '[ERROR]',
    'success': '[SUCCESS]',
    'info': '[INFO]',
    'warn': '[WARN]',
    'arrow': '->',
}


def find_library_path(lib_name: str) -> Optional[Path]:
    """Find library path in standard locations."""
    lib_root = Path("C:/ProgramData/Schneider Electric/Libraries")

    if not lib_root.exists():
        return None

    # Match library with version (e.g., SE.App2CommonProcess-25.0.1.5)
    lib_paths = list(lib_root.glob(f"{lib_name}-*"))
    if not lib_paths:
        return None

    # Use most recent version (highest version number)
    return max(lib_paths, key=lambda p: p.name)


def detect_block_hierarchy(
    lib_path: Path,
    block_name: str
) -> List[str]:
    """
    Detect if block is part of a Base -> BaseExt -> Full hierarchy.

    Returns list of blocks in hierarchy order (Base first, Full last).
    """
    files_dir = lib_path / "Files"
    hierarchy = []

    # Common patterns for EAE hierarchies
    if block_name.endswith("Base"):
        # This is the base - check for BaseExt and Full
        base_name = block_name[:-4]  # Remove "Base"

        hierarchy.append(block_name)

        if (files_dir / f"{base_name}BaseExt").exists():
            hierarchy.append(f"{base_name}BaseExt")

        if (files_dir / base_name).exists():
            hierarchy.append(base_name)

    elif block_name.endswith("BaseExt"):
        # This is BaseExt - check for Base and Full
        base_name = block_name[:-7]  # Remove "BaseExt"

        if (files_dir / f"{base_name}Base").exists():
            hierarchy.append(f"{base_name}Base")

        hierarchy.append(block_name)

        if (files_dir / base_name).exists():
            hierarchy.append(base_name)

    else:
        # This might be the Full block - check for Base and BaseExt
        if (files_dir / f"{block_name}Base").exists():
            hierarchy.append(f"{block_name}Base")

        if (files_dir / f"{block_name}BaseExt").exists():
            hierarchy.append(f"{block_name}BaseExt")

        hierarchy.append(block_name)

    # If only one block found (no hierarchy), return just that block
    if len(hierarchy) == 1:
        return [block_name]

    return hierarchy


def parse_subcats_from_cfg(cfg_file: Path) -> Set[str]:
    """
    Parse .cfg file to extract SubCAT Type references.

    Returns set of SubCAT block names.
    """
    subcats = set()

    try:
        tree = ET.parse(cfg_file)
        root = tree.getroot()

        # Handle XML namespace if present
        namespace = ''
        if root.tag.startswith('{'):
            namespace = root.tag[root.tag.find('{'):root.tag.find('}')+1]

        # Find all <SubCAT Type="..."> elements (with or without namespace)
        if namespace:
            for subcat in root.findall(f'.//{namespace}SubCAT[@Type]'):
                subcat_type = subcat.get('Type')
                if subcat_type:
                    subcats.add(subcat_type)
        else:
            for subcat in root.findall('.//SubCAT[@Type]'):
                subcat_type = subcat.get('Type')
                if subcat_type:
                    subcats.add(subcat_type)

    except ET.ParseError as e:
        print(f"{SYMBOLS['warn']} Failed to parse {cfg_file.name}: {e}", file=sys.stderr)

    return subcats


def detect_dependencies(
    lib_path: Path,
    block_name: str,
    visited: Optional[Set[str]] = None,
    depth: int = 0,
    max_depth: int = 3
) -> Dict:
    """
    Recursively detect all dependencies of a block.

    Args:
        lib_path: Path to source library
        block_name: Block to analyze
        visited: Set of already-visited blocks (prevents infinite recursion)
        depth: Current recursion depth
        max_depth: Maximum recursion depth

    Returns:
        Dict with structure:
        {
            'block': str,
            'has_cfg': bool,
            'subcats': List[str],
            'dependencies': List[Dict],  # Recursive
            'depth': int
        }
    """
    if visited is None:
        visited = set()

    # Prevent infinite recursion
    if block_name in visited or depth >= max_depth:
        return None

    visited.add(block_name)

    files_dir = lib_path / "Files" / block_name
    cfg_file = files_dir / f"{block_name}.cfg"

    result = {
        'block': block_name,
        'has_cfg': cfg_file.exists(),
        'subcats': [],
        'dependencies': [],
        'depth': depth
    }

    if not cfg_file.exists():
        # Not a CAT block or block doesn't exist
        return result

    # Parse SubCATs from .cfg file
    subcats = parse_subcats_from_cfg(cfg_file)
    result['subcats'] = sorted(list(subcats))

    # Recursively detect dependencies of each SubCAT
    for subcat in subcats:
        dep = detect_dependencies(lib_path, subcat, visited, depth + 1, max_depth)
        if dep:
            result['dependencies'].append(dep)

    return result


def flatten_dependency_tree(tree: Dict) -> List[str]:
    """
    Flatten dependency tree to a list of unique blocks in dependency order.

    Returns blocks in the order they should be forked (dependencies first).
    """
    blocks = []

    def traverse(node):
        if not node:
            return

        # First add dependencies (depth-first)
        for dep in node.get('dependencies', []):
            traverse(dep)

        # Then add this block
        if node['block'] not in blocks:
            blocks.append(node['block'])

    traverse(tree)
    return blocks


def format_dependency_tree(tree: Dict, indent: int = 0) -> str:
    """Format dependency tree as a readable string."""
    if not tree:
        return ""

    lines = []
    prefix = "  " * indent

    block_name = tree['block']
    subcats = tree.get('subcats', [])

    if subcats:
        lines.append(f"{prefix}{SYMBOLS['arrow']} {block_name} (uses {len(subcats)} SubCATs)")
        for subcat in subcats:
            lines.append(f"{prefix}    - {subcat}")
    else:
        lines.append(f"{prefix}{SYMBOLS['arrow']} {block_name}")

    # Recursively format dependencies
    for dep in tree.get('dependencies', []):
        dep_lines = format_dependency_tree(dep, indent + 1)
        if dep_lines:
            lines.append(dep_lines)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Detect EAE block dependencies by parsing .cfg files",
        epilog="""
Examples:
  # Detect dependencies for AnalogInput
  python detect_dependencies.py SE.App2CommonProcess AnalogInput

  # Detect with limited depth
  python detect_dependencies.py SE.App2CommonProcess MotorVs --max-depth 2

  # JSON output for automation
  python detect_dependencies.py SE.App2CommonProcess AnalogInput --json
        """
    )
    parser.add_argument("source_lib", help="Source library (e.g., SE.App2CommonProcess)")
    parser.add_argument("block_name", help="Block name to analyze")
    parser.add_argument("--max-depth", type=int, default=3, help="Maximum recursion depth (default: 3)")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--include-hierarchy", action="store_true",
                       help="Include Base/BaseExt hierarchy in results")

    args = parser.parse_args()

    # Find source library
    lib_path = find_library_path(args.source_lib)
    if not lib_path:
        print(f"{SYMBOLS['error']} Source library not found: {args.source_lib}", file=sys.stderr)
        sys.exit(1)

    print(f"{SYMBOLS['info']} Analyzing dependencies...")
    print(f"  Library: {lib_path.name}")
    print(f"  Block: {args.block_name}")
    print(f"  Max depth: {args.max_depth}\n")

    # Detect hierarchy if requested
    hierarchy = []
    if args.include_hierarchy:
        hierarchy = detect_block_hierarchy(lib_path, args.block_name)
        if len(hierarchy) > 1:
            print(f"{SYMBOLS['info']} Detected hierarchy: {' -> '.join(hierarchy)}\n")

    # Detect dependencies
    dep_tree = detect_dependencies(lib_path, args.block_name, max_depth=args.max_depth)

    if not dep_tree or not dep_tree['has_cfg']:
        print(f"{SYMBOLS['warn']} Not a CAT block or .cfg file not found")
        print(f"{SYMBOLS['info']} Only CAT blocks have SubCAT dependencies")
        sys.exit(0)

    # Flatten to get complete list
    all_deps = flatten_dependency_tree(dep_tree)

    if args.json:
        import json
        output = {
            'block': args.block_name,
            'hierarchy': hierarchy if args.include_hierarchy else [args.block_name],
            'dependencies': all_deps,
            'dependency_tree': dep_tree,
            'total_blocks': len(set(hierarchy + all_deps)) if args.include_hierarchy else len(all_deps)
        }
        print(json.dumps(output, indent=2))
    else:
        # Human-readable output
        print(f"{SYMBOLS['success']} Dependency Analysis Complete\n")

        if hierarchy and len(hierarchy) > 1:
            print(f"Hierarchy ({len(hierarchy)} blocks):")
            for i, block in enumerate(hierarchy, 1):
                print(f"  {i}. {block}")
            print()

        print(f"Dependencies ({len(all_deps)} blocks):")
        if all_deps:
            for i, block in enumerate(all_deps, 1):
                print(f"  {i}. {block}")
        else:
            print(f"  (none)")

        print(f"\nDependency Tree:")
        print(format_dependency_tree(dep_tree))

        # Summary
        all_blocks = set(hierarchy + all_deps) if args.include_hierarchy else set(all_deps)
        print(f"\n{SYMBOLS['info']} Total blocks to fork: {len(all_blocks)}")

        if args.include_hierarchy and len(hierarchy) > 1:
            print(f"  Hierarchy: {len(hierarchy)}")
            print(f"  SubCATs: {len(all_deps)}")

        print(f"\nRecommended fork command:")
        blocks_to_fork = hierarchy + [b for b in all_deps if b not in hierarchy] if args.include_hierarchy else all_deps
        print(f"  python finalize_manual_fork.py {' '.join(blocks_to_fork)} <target_lib>")


if __name__ == "__main__":
    main()
