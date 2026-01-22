#!/usr/bin/env python3
"""
List available EAE libraries and their blocks from Schneider Electric Libraries.

Usage:
    python list_libraries.py                    # List all libraries
    python list_libraries.py SE.App2CommonProcess  # List blocks in a library
    python list_libraries.py --search analog   # Search for blocks by name
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Library location
LIBRARIES_PATH = Path(r"C:\ProgramData\Schneider Electric\Libraries")


def get_all_libraries() -> Dict[str, Path]:
    """Get all installed libraries with their paths."""
    libraries = {}

    if not LIBRARIES_PATH.exists():
        return libraries

    for item in LIBRARIES_PATH.iterdir():
        if item.is_dir() and "-" in item.name:
            # Parse library name and version
            parts = item.name.rsplit("-", 1)
            if len(parts) == 2:
                lib_name, version = parts
                # Keep latest version if multiple exist
                if lib_name not in libraries:
                    libraries[lib_name] = item
                else:
                    # Compare versions, keep latest
                    existing_version = libraries[lib_name].name.rsplit("-", 1)[1]
                    if version_compare(version, existing_version) > 0:
                        libraries[lib_name] = item

    return libraries


def version_compare(v1: str, v2: str) -> int:
    """Compare version strings. Returns >0 if v1 > v2, <0 if v1 < v2, 0 if equal."""
    def parse_version(v: str) -> Tuple:
        parts = v.split(".")
        return tuple(int(x) if x.isdigit() else 0 for x in parts)

    p1, p2 = parse_version(v1), parse_version(v2)

    for a, b in zip(p1, p2):
        if a > b:
            return 1
        if a < b:
            return -1

    return len(p1) - len(p2)


def get_library_blocks(lib_path: Path) -> List[str]:
    """Get all blocks in a library."""
    blocks = []

    files_path = lib_path / "Files"
    if not files_path.exists():
        return blocks

    for item in files_path.iterdir():
        if item.is_dir():
            # Check if it contains an .fbt file
            fbt_file = item / f"{item.name}.fbt"
            if fbt_file.exists():
                blocks.append(item.name)

    return sorted(blocks)


def get_block_info(lib_path: Path, block_name: str) -> Optional[Dict]:
    """Get detailed info about a block."""
    block_path = lib_path / "Files" / block_name
    if not block_path.exists():
        return None

    info = {
        "name": block_name,
        "path": str(block_path),
        "files": []
    }

    for item in block_path.iterdir():
        if item.is_file():
            info["files"].append(item.name)

    # Detect block type
    fbt_file = block_path / f"{block_name}.fbt"
    if fbt_file.exists():
        try:
            content = fbt_file.read_text(encoding="utf-8")
            if "<CompositeFBType" in content or "<FBNetwork>" in content:
                if f"{block_name}.cfg" in info["files"]:
                    info["type"] = "CAT"
                else:
                    info["type"] = "Composite"
            elif "<BasicFBType" in content or "<ECC>" in content:
                info["type"] = "Basic"
            else:
                info["type"] = "Unknown"
        except Exception:
            info["type"] = "Unknown"

    return info


def search_blocks(query: str, libraries: Optional[List[str]] = None) -> List[Tuple[str, str, str]]:
    """Search for blocks matching query. Returns list of (library, block, type) tuples."""
    results = []

    all_libs = get_all_libraries()

    if libraries:
        all_libs = {k: v for k, v in all_libs.items() if k in libraries}

    query_lower = query.lower()

    for lib_name, lib_path in all_libs.items():
        blocks = get_library_blocks(lib_path)
        for block in blocks:
            if query_lower in block.lower():
                info = get_block_info(lib_path, block)
                block_type = info.get("type", "Unknown") if info else "Unknown"
                results.append((lib_name, block, block_type))

    return sorted(results)


def print_libraries():
    """Print all available libraries."""
    libraries = get_all_libraries()

    if not libraries:
        print("No libraries found.")
        print(f"Searched in: {LIBRARIES_PATH}")
        return

    print(f"\nInstalled EAE Libraries ({len(libraries)} found):\n")
    print(f"{'Library Name':<40} {'Version':<15} {'Blocks':<10}")
    print("-" * 70)

    for lib_name, lib_path in sorted(libraries.items()):
        version = lib_path.name.rsplit("-", 1)[1]
        blocks = get_library_blocks(lib_path)
        print(f"{lib_name:<40} {version:<15} {len(blocks):<10}")

    print(f"\nLocation: {LIBRARIES_PATH}")


def print_library_blocks(lib_name: str):
    """Print all blocks in a library."""
    libraries = get_all_libraries()

    if lib_name not in libraries:
        print(f"Library not found: {lib_name}")
        print("\nAvailable libraries:")
        for name in sorted(libraries.keys()):
            print(f"  {name}")
        return

    lib_path = libraries[lib_name]
    version = lib_path.name.rsplit("-", 1)[1]
    blocks = get_library_blocks(lib_path)

    if not blocks:
        print(f"No blocks found in {lib_name}")
        return

    print(f"\nBlocks in {lib_name} v{version} ({len(blocks)} total):\n")

    # Group by type
    cats = []
    composites = []
    basics = []
    others = []

    for block in blocks:
        info = get_block_info(lib_path, block)
        block_type = info.get("type", "Unknown") if info else "Unknown"

        if block_type == "CAT":
            cats.append(block)
        elif block_type == "Composite":
            composites.append(block)
        elif block_type == "Basic":
            basics.append(block)
        else:
            others.append(block)

    if cats:
        print(f"CAT Blocks ({len(cats)}):")
        for block in cats:
            print(f"  {block}")
        print()

    if composites:
        print(f"Composite Blocks ({len(composites)}):")
        for block in composites:
            print(f"  {block}")
        print()

    if basics:
        print(f"Basic Blocks ({len(basics)}):")
        for block in basics:
            print(f"  {block}")
        print()

    if others:
        print(f"Other Blocks ({len(others)}):")
        for block in others:
            print(f"  {block}")
        print()


def print_search_results(query: str, libraries: Optional[List[str]] = None):
    """Print search results."""
    results = search_blocks(query, libraries)

    if not results:
        print(f"No blocks found matching '{query}'")
        return

    print(f"\nSearch results for '{query}' ({len(results)} found):\n")
    print(f"{'Library':<30} {'Block':<30} {'Type':<10}")
    print("-" * 75)

    for lib_name, block_name, block_type in results:
        print(f"{lib_name:<30} {block_name:<30} {block_type:<10}")


def main():
    parser = argparse.ArgumentParser(
        description="List EAE libraries and blocks from Schneider Electric Libraries"
    )
    parser.add_argument("library", nargs="?", help="Library name to show blocks for")
    parser.add_argument("--search", "-s", help="Search for blocks by name")
    parser.add_argument("--libs", "-l", nargs="+", help="Limit search to specific libraries")

    args = parser.parse_args()

    if args.search:
        print_search_results(args.search, args.libs)
    elif args.library:
        print_library_blocks(args.library)
    else:
        print_libraries()


if __name__ == "__main__":
    main()
