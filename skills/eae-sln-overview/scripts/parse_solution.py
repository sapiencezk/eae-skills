#!/usr/bin/env python3
"""
EAE Solution Parser - Parse .sln/.nxtsln and .dfbproj files

Extracts project structure, library references, and block counts from EAE solutions.

Exit Codes:
    0: Parsing successful
    1: Solution not found or parsing error
   10: Partial success with warnings

Usage:
    python parse_solution.py --project-dir /path/to/eae/project
    python parse_solution.py --solution /path/to/project.sln
    python parse_solution.py --project-dir /path/to/project --json
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class LibraryReference:
    """A library reference from .dfbproj."""
    name: str
    version: str
    is_se_library: bool
    is_project_reference: bool = False
    path: Optional[str] = None


@dataclass
class BlockCounts:
    """Count of blocks by type."""
    cat: int = 0
    basic: int = 0
    composite: int = 0
    adapter: int = 0
    datatype: int = 0
    subapp: int = 0
    function: int = 0
    total: int = 0


@dataclass
class ProjectInfo:
    """Information about a single IEC61499 project."""
    name: str
    path: str
    namespace: str
    nxt_version: str
    target_framework: str
    library_references: List[LibraryReference]
    blocks: BlockCounts
    warnings: List[str] = field(default_factory=list)


@dataclass
class SolutionInfo:
    """Complete solution information."""
    solution_name: str
    solution_path: str
    eae_version: str
    projects: List[ProjectInfo]
    total_projects: int
    total_blocks: int
    total_libraries: int
    warnings: List[str] = field(default_factory=list)


# SE library prefixes for classification
SE_LIBRARY_PREFIXES = [
    'SE.', 'Standard.', 'Runtime.', 'IEC61131.', 'HMI.',
    'System.', 'Schneider.', 'EcoStruxure.'
]


def is_se_library(name: str) -> bool:
    """Check if a library is an SE standard library."""
    return any(name.startswith(prefix) for prefix in SE_LIBRARY_PREFIXES)


def find_solution_file(project_dir: Path) -> Optional[Path]:
    """Find the solution file in the project directory."""
    # Try .nxtsln first (newer format)
    nxtsln_files = list(project_dir.glob('*.nxtsln'))
    if nxtsln_files:
        return nxtsln_files[0]

    # Fall back to .sln
    sln_files = list(project_dir.glob('*.sln'))
    if sln_files:
        return sln_files[0]

    return None


def parse_sln_file(sln_path: Path) -> List[Dict[str, str]]:
    """Parse a Visual Studio .sln file to extract project references."""
    projects = []

    try:
        content = sln_path.read_text(encoding='utf-8-sig')
    except Exception:
        content = sln_path.read_text(encoding='latin-1')

    # Pattern for project lines in .sln
    # Project("{GUID}") = "Name", "Path", "{GUID}"
    pattern = r'Project\("\{[^}]+\}"\)\s*=\s*"([^"]+)",\s*"([^"]+)",\s*"\{([^}]+)\}"'

    for match in re.finditer(pattern, content):
        name = match.group(1)
        path = match.group(2)
        guid = match.group(3)

        projects.append({
            'name': name,
            'path': path,
            'guid': guid
        })

    return projects


def parse_dfbproj(dfbproj_path: Path) -> ProjectInfo:
    """Parse a .dfbproj file to extract project information."""
    warnings = []
    library_refs = []
    blocks = BlockCounts()

    try:
        tree = ET.parse(dfbproj_path)
        root = tree.getroot()
    except ET.ParseError as e:
        return ProjectInfo(
            name=dfbproj_path.stem,
            path=str(dfbproj_path),
            namespace='',
            nxt_version='',
            target_framework='',
            library_references=[],
            blocks=BlockCounts(),
            warnings=[f"XML parse error: {e}"]
        )

    # Handle namespace in XML
    ns = {'msbuild': 'http://schemas.microsoft.com/developer/msbuild/2003'}

    # Try with namespace first, then without
    def find_element(xpath_with_ns, xpath_without_ns):
        elem = root.find(xpath_with_ns, ns)
        if elem is None:
            elem = root.find(xpath_without_ns)
        return elem

    def find_all_elements(xpath_with_ns, xpath_without_ns):
        elems = root.findall(xpath_with_ns, ns)
        if not elems:
            elems = root.findall(xpath_without_ns)
        return elems

    # Extract PropertyGroup values
    namespace = ''
    nxt_version = ''
    target_framework = ''

    for prop_group in find_all_elements('.//msbuild:PropertyGroup', './/PropertyGroup'):
        ns_elem = prop_group.find('msbuild:RootNamespace', ns)
        if ns_elem is None:
            ns_elem = prop_group.find('RootNamespace')
        if ns_elem is not None and ns_elem.text:
            namespace = ns_elem.text

        # Try NxtVersion (current) and NXTVersion (legacy)
        nxt_elem = prop_group.find('msbuild:NxtVersion', ns)
        if nxt_elem is None:
            nxt_elem = prop_group.find('NxtVersion')
        if nxt_elem is None:
            nxt_elem = prop_group.find('msbuild:NXTVersion', ns)
        if nxt_elem is None:
            nxt_elem = prop_group.find('NXTVersion')
        if nxt_elem is not None and nxt_elem.text:
            nxt_version = nxt_elem.text

        tf_elem = prop_group.find('msbuild:TargetFrameworkVersion', ns)
        if tf_elem is None:
            tf_elem = prop_group.find('TargetFrameworkVersion')
        if tf_elem is not None and tf_elem.text:
            target_framework = tf_elem.text

    # Extract library references
    for ref in find_all_elements('.//msbuild:Reference', './/Reference'):
        include = ref.get('Include', '')
        if not include:
            continue

        version_elem = ref.find('msbuild:Version', ns)
        if version_elem is None:
            version_elem = ref.find('Version')
        version = version_elem.text if version_elem is not None and version_elem.text else ''

        library_refs.append(LibraryReference(
            name=include,
            version=version,
            is_se_library=is_se_library(include),
            is_project_reference=False
        ))

    # Extract project references (internal projects)
    for ref in find_all_elements('.//msbuild:ProjectReference', './/ProjectReference'):
        include = ref.get('Include', '')
        if not include:
            continue

        name_elem = ref.find('msbuild:Name', ns)
        if name_elem is None:
            name_elem = ref.find('Name')
        name = name_elem.text if name_elem is not None and name_elem.text else Path(include).stem

        version_elem = ref.find('msbuild:Version', ns)
        if version_elem is None:
            version_elem = ref.find('Version')
        version = version_elem.text if version_elem is not None and version_elem.text else ''

        library_refs.append(LibraryReference(
            name=name,
            version=version,
            is_se_library=False,
            is_project_reference=True,
            path=include
        ))

    # Count blocks by IEC61499Type
    # IEC61499Type can be on Compile, None, or other ItemGroup elements
    block_type_counts = {}

    # Check all ItemGroup children for IEC61499Type
    for item_group in find_all_elements('.//msbuild:ItemGroup', './/ItemGroup'):
        for child in item_group:
            type_elem = child.find('msbuild:IEC61499Type', ns)
            if type_elem is None:
                type_elem = child.find('IEC61499Type')
            if type_elem is not None and type_elem.text:
                block_type = type_elem.text.upper()
                block_type_counts[block_type] = block_type_counts.get(block_type, 0) + 1

    blocks.cat = block_type_counts.get('CAT', 0)
    blocks.basic = block_type_counts.get('BASIC', 0) + block_type_counts.get('BASICFB', 0)
    blocks.composite = block_type_counts.get('COMPOSITE', 0) + block_type_counts.get('COMPOSITEFB', 0)
    blocks.adapter = block_type_counts.get('ADAPTER', 0)
    blocks.datatype = block_type_counts.get('DATATYPE', 0)
    blocks.subapp = block_type_counts.get('SUBAPP', 0)
    blocks.function = block_type_counts.get('FUNCTION', 0)
    blocks.total = sum(block_type_counts.values())

    return ProjectInfo(
        name=dfbproj_path.stem,
        path=str(dfbproj_path),
        namespace=namespace,
        nxt_version=nxt_version,
        target_framework=target_framework,
        library_references=library_refs,
        blocks=blocks,
        warnings=warnings
    )


def analyze_solution(project_dir: Path, solution_path: Optional[Path] = None) -> SolutionInfo:
    """Analyze a complete EAE solution."""
    warnings = []
    projects = []

    # Find solution file
    if solution_path is None:
        solution_path = find_solution_file(project_dir)

    if solution_path is None:
        # No solution file, try to find dfbproj files directly
        warnings.append("No solution file found, scanning for .dfbproj files")
        dfbproj_files = list(project_dir.rglob('*.dfbproj'))
    else:
        # Parse solution file to get project list
        sln_projects = parse_sln_file(solution_path)
        dfbproj_files = []

        for proj in sln_projects:
            proj_path = project_dir / proj['path']
            if proj_path.suffix == '.dfbproj' and proj_path.exists():
                dfbproj_files.append(proj_path)

        # Also scan for any dfbproj files not in solution
        all_dfbproj = set(project_dir.rglob('*.dfbproj'))
        found_dfbproj = set(dfbproj_files)
        missing = all_dfbproj - found_dfbproj
        if missing:
            warnings.append(f"Found {len(missing)} .dfbproj files not referenced in solution")
            dfbproj_files.extend(missing)

    # Parse each dfbproj
    for dfbproj_path in dfbproj_files:
        proj_info = parse_dfbproj(dfbproj_path)
        projects.append(proj_info)
        warnings.extend(proj_info.warnings)

    # Calculate totals
    total_blocks = sum(p.blocks.total for p in projects)

    # Collect unique libraries
    all_libs = set()
    for p in projects:
        for lib in p.library_references:
            if not lib.is_project_reference:
                all_libs.add(lib.name)

    # Get EAE version from the first project with a version
    eae_version = ''
    for p in projects:
        if p.nxt_version:
            eae_version = p.nxt_version
            break

    return SolutionInfo(
        solution_name=solution_path.stem if solution_path else project_dir.name,
        solution_path=str(solution_path) if solution_path else str(project_dir),
        eae_version=eae_version,
        projects=projects,
        total_projects=len(projects),
        total_blocks=total_blocks,
        total_libraries=len(all_libs),
        warnings=warnings
    )


def main():
    parser = argparse.ArgumentParser(
        description='Parse EAE solution and project files',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--project-dir', type=Path, help='Path to EAE project root directory')
    parser.add_argument('--solution', type=Path, help='Path to .sln or .nxtsln file')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--output', type=Path, help='Output file path')

    args = parser.parse_args()

    # Determine project directory
    if args.solution:
        solution_path = args.solution
        project_dir = solution_path.parent
    elif args.project_dir:
        project_dir = args.project_dir
        solution_path = None
    else:
        parser.error('Either --project-dir or --solution must be specified')

    if not project_dir.exists():
        print(f"Error: Project directory not found: {project_dir}", file=sys.stderr)
        sys.exit(1)

    # Analyze solution
    result = analyze_solution(project_dir, solution_path)

    # Convert to dict for JSON serialization
    def to_dict(obj):
        if hasattr(obj, '__dict__'):
            d = {}
            for k, v in obj.__dict__.items():
                if isinstance(v, list):
                    d[k] = [to_dict(i) for i in v]
                elif hasattr(v, '__dict__'):
                    d[k] = to_dict(v)
                else:
                    d[k] = v
            return d
        return obj

    result_dict = to_dict(result)

    # Output
    if args.json:
        output = json.dumps(result_dict, indent=2)
    else:
        # Human-readable output
        lines = []
        lines.append(f"Solution: {result.solution_name}")
        lines.append(f"Path: {result.solution_path}")
        lines.append(f"Projects: {result.total_projects}")
        lines.append(f"Total Blocks: {result.total_blocks}")
        lines.append(f"Libraries: {result.total_libraries}")
        lines.append("")

        for proj in result.projects:
            lines.append(f"  Project: {proj.name}")
            lines.append(f"    Namespace: {proj.namespace}")
            lines.append(f"    NXT Version: {proj.nxt_version}")
            lines.append(f"    Blocks: CAT={proj.blocks.cat}, Basic={proj.blocks.basic}, "
                        f"Composite={proj.blocks.composite}, Adapter={proj.blocks.adapter}, "
                        f"DataType={proj.blocks.datatype}")
            lines.append(f"    Libraries: {len(proj.library_references)}")
            for lib in proj.library_references:
                se_marker = "[SE]" if lib.is_se_library else "[Custom]"
                proj_marker = " (project ref)" if lib.is_project_reference else ""
                lines.append(f"      - {lib.name} v{lib.version} {se_marker}{proj_marker}")
            lines.append("")

        if result.warnings:
            lines.append("Warnings:")
            for w in result.warnings:
                lines.append(f"  - {w}")

        output = '\n'.join(lines)

    if args.output:
        args.output.write_text(output, encoding='utf-8')
    else:
        print(output)

    # Exit code
    if result.warnings:
        sys.exit(10)
    sys.exit(0)


if __name__ == '__main__':
    main()
