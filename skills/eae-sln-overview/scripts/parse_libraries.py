#!/usr/bin/env python3
"""
EAE Library Analyzer - Analyze library references and dependencies

Categorizes SE standard libraries vs custom libraries and analyzes usage patterns.

Exit Codes:
    0: Analysis successful
    1: Project not found or parsing error
   10: Partial success with warnings

Usage:
    python parse_libraries.py --project-dir /path/to/eae/project
    python parse_libraries.py --project-dir /path/to/project --json
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Set


# SE Library definitions with categories
SE_LIBRARY_CATALOG = {
    # Runtime & Base
    'Runtime.Base': {'category': 'runtime', 'description': 'Core runtime function blocks'},
    'IEC61131.Standard': {'category': 'standard', 'description': 'IEC 61131-3 standard functions'},

    # SE Application Libraries
    'SE.App2Base': {'category': 'app-base', 'description': 'Base application blocks'},
    'SE.AppBase': {'category': 'app-base', 'description': 'Base application blocks (legacy)'},
    'SE.App2CommonProcess': {'category': 'process', 'description': 'Common process blocks (motors, valves, PID)'},
    'SE.AppCommonProcess': {'category': 'process', 'description': 'Common process blocks (legacy)'},
    'SE.App2WWW': {'category': 'web', 'description': 'Web service blocks'},
    'SE.AppSequence': {'category': 'sequence', 'description': 'Sequential control'},
    'SE.App2Sequence': {'category': 'sequence', 'description': 'Sequential control'},
    'SE.AppBatch': {'category': 'batch', 'description': 'ISA88 batch control'},

    # Hardware & I/O
    'SE.DPAC': {'category': 'hardware', 'description': 'Soft dPAC runtime'},
    'SE.HwCommon': {'category': 'hardware', 'description': 'Hardware common definitions'},
    'SE.FieldDevice': {'category': 'hardware', 'description': 'Field device communication'},
    'SE.IoTMx': {'category': 'io-module', 'description': 'Telemecanique TM I/O modules'},
    'SE.IoATV': {'category': 'io-module', 'description': 'Altivar motor drives'},
    'SE.ModbusGateway': {'category': 'protocol', 'description': 'Modbus gateway'},
    'SE.Standard': {'category': 'standard', 'description': 'SE standard blocks'},
    'SE.PowerTag': {'category': 'energy', 'description': 'PowerTag energy monitoring'},

    # Protocol Libraries
    'Standard.IoModbus': {'category': 'protocol', 'description': 'Modbus TCP/RTU master'},
    'Standard.IoModbusSlave': {'category': 'protocol', 'description': 'Modbus slave'},
    'Standard.IoEtherNetIP': {'category': 'protocol', 'description': 'EtherNet/IP (Allen-Bradley)'},
    'Standard.IoProfinet': {'category': 'protocol', 'description': 'PROFINET I/O'},
    'Standard.IoOpcUa': {'category': 'protocol', 'description': 'OPC-UA client'},
    'Standard.IoDnp3': {'category': 'protocol', 'description': 'DNP3 protocol'},

    # HMI & Visualization
    'Standard.HMIExtensions': {'category': 'hmi', 'description': 'HMI extension blocks'},
    'HMI.BaseSymbols': {'category': 'hmi', 'description': 'HMI base symbols'},
}

# SE library prefixes for classification
SE_LIBRARY_PREFIXES = [
    'SE.', 'Standard.', 'Runtime.', 'IEC61131.', 'HMI.',
    'System.', 'Schneider.', 'EcoStruxure.'
]


@dataclass
class LibraryInfo:
    """Detailed library information."""
    name: str
    version: str
    category: str
    description: str
    is_se_library: bool
    is_project_reference: bool
    blocks_used: int = 0
    path: Optional[str] = None


@dataclass
class CustomLibraryInfo:
    """Custom library information."""
    name: str
    namespace: str
    block_count: int
    depends_on: List[str]
    path: str


@dataclass
class LibraryAnalysis:
    """Complete library analysis."""
    se_libraries: List[LibraryInfo]
    custom_libraries: List[CustomLibraryInfo]
    project_references: List[LibraryInfo]
    total_se_libraries: int
    total_custom_libraries: int
    total_dependencies: int
    categories: Dict[str, int]  # Category -> count
    missing_libraries: List[str]
    unused_libraries: List[str]
    warnings: List[str] = field(default_factory=list)


def is_se_library(name: str) -> bool:
    """Check if a library is an SE standard library."""
    return any(name.startswith(prefix) for prefix in SE_LIBRARY_PREFIXES)


def get_library_info(name: str, version: str = '') -> LibraryInfo:
    """Get library information from catalog or create default."""
    catalog_entry = SE_LIBRARY_CATALOG.get(name, {})

    return LibraryInfo(
        name=name,
        version=version,
        category=catalog_entry.get('category', 'unknown'),
        description=catalog_entry.get('description', ''),
        is_se_library=is_se_library(name),
        is_project_reference=False
    )


def parse_dfbproj_libraries(dfbproj_path: Path) -> tuple:
    """Parse library references from a .dfbproj file."""
    se_libs = []
    project_refs = []
    warnings = []

    try:
        tree = ET.parse(dfbproj_path)
        root = tree.getroot()
    except ET.ParseError as e:
        return [], [], [f"XML parse error in {dfbproj_path.name}: {e}"]

    # Handle namespace
    ns = {'msbuild': 'http://schemas.microsoft.com/developer/msbuild/2003'}

    def find_all_elements(xpath_with_ns, xpath_without_ns):
        elems = root.findall(xpath_with_ns, ns)
        if not elems:
            elems = root.findall(xpath_without_ns)
        return elems

    # Extract library references
    for ref in find_all_elements('.//msbuild:Reference', './/Reference'):
        include = ref.get('Include', '')
        if not include:
            continue

        version_elem = ref.find('msbuild:Version', ns)
        if version_elem is None:
            version_elem = ref.find('Version')
        version = version_elem.text if version_elem is not None and version_elem.text else ''

        lib_info = get_library_info(include, version)
        se_libs.append(lib_info)

    # Extract project references
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

        project_refs.append(LibraryInfo(
            name=name,
            version=version,
            category='project',
            description='Project reference',
            is_se_library=False,
            is_project_reference=True,
            path=include
        ))

    return se_libs, project_refs, warnings


def analyze_custom_library(dfbproj_path: Path) -> Optional[CustomLibraryInfo]:
    """Analyze a custom library (project-level dfbproj)."""
    try:
        tree = ET.parse(dfbproj_path)
        root = tree.getroot()
    except ET.ParseError:
        return None

    ns = {'msbuild': 'http://schemas.microsoft.com/developer/msbuild/2003'}

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

    # Get namespace
    namespace = ''
    for prop_group in find_all_elements('.//msbuild:PropertyGroup', './/PropertyGroup'):
        ns_elem = prop_group.find('msbuild:RootNamespace', ns) or prop_group.find('RootNamespace')
        if ns_elem is not None and ns_elem.text:
            namespace = ns_elem.text
            break

    # Count blocks - check all ItemGroup children for IEC61499Type
    # (blocks can be in <None>, <Compile>, or other elements)
    block_count = 0
    for item_group in find_all_elements('.//msbuild:ItemGroup', './/ItemGroup'):
        for child in item_group:
            type_elem = child.find('msbuild:IEC61499Type', ns)
            if type_elem is None:
                type_elem = child.find('IEC61499Type')
            if type_elem is not None:
                block_count += 1

    # Get dependencies
    depends_on = []
    for ref in find_all_elements('.//msbuild:Reference', './/Reference'):
        include = ref.get('Include', '')
        if include and is_se_library(include):
            depends_on.append(include)

    return CustomLibraryInfo(
        name=dfbproj_path.stem,
        namespace=namespace,
        block_count=block_count,
        depends_on=depends_on,
        path=str(dfbproj_path)
    )


def count_library_usage(project_dir: Path, library_name: str) -> int:
    """Count how many times a library's blocks are used in the project."""
    count = 0

    # Search for namespace references in .fbt files
    for fbt_path in project_dir.rglob('*.fbt'):
        try:
            content = fbt_path.read_text(encoding='utf-8', errors='ignore')
            # Look for namespace::Type references
            if f'{library_name}::' in content or f'Namespace="{library_name}"' in content:
                count += content.count(f'{library_name}::')
                count += content.count(f'Namespace="{library_name}"')
        except Exception:
            pass

    return count


def analyze_libraries(project_dir: Path) -> LibraryAnalysis:
    """Analyze all library references in the project."""
    warnings = []
    all_se_libs = {}  # name -> LibraryInfo
    all_project_refs = []
    custom_libs = []
    custom_lib_names = set()  # Track analyzed custom libraries to avoid duplicates
    categories = {}

    # Find all dfbproj files
    dfbproj_files = list(project_dir.rglob('*.dfbproj'))

    if not dfbproj_files:
        warnings.append("No .dfbproj files found")

    # Process each dfbproj
    main_dfbproj = None
    for dfbproj_path in dfbproj_files:
        # Identify main project vs sub-projects
        is_main = dfbproj_path.parent.name == 'IEC61499'

        se_libs, project_refs, parse_warnings = parse_dfbproj_libraries(dfbproj_path)
        warnings.extend(parse_warnings)

        # Merge SE libraries (avoid duplicates, keep latest version)
        for lib in se_libs:
            if lib.name not in all_se_libs:
                all_se_libs[lib.name] = lib
            else:
                # Keep the one with a version
                if lib.version and not all_se_libs[lib.name].version:
                    all_se_libs[lib.name] = lib

        # Collect project references
        all_project_refs.extend(project_refs)

        # Analyze as custom library if not main and has blocks
        if not is_main:
            custom_lib = analyze_custom_library(dfbproj_path)
            if custom_lib and custom_lib.block_count > 0:
                if custom_lib.name not in custom_lib_names:
                    custom_libs.append(custom_lib)
                    custom_lib_names.add(custom_lib.name)

        if is_main:
            main_dfbproj = dfbproj_path

    # Analyze Project References as custom libraries
    # These are external library projects referenced by the main project
    for proj_ref in all_project_refs:
        if proj_ref.name in custom_lib_names:
            continue  # Already analyzed

        # Resolve the path relative to main dfbproj
        if main_dfbproj and proj_ref.path:
            ref_path = Path(proj_ref.path)
            # Path is relative to the dfbproj file location
            resolved_path = (main_dfbproj.parent / ref_path).resolve()

            if resolved_path.exists():
                custom_lib = analyze_custom_library(resolved_path)
                if custom_lib:
                    # Use the reference name (from <Name> element) if available
                    custom_lib.name = proj_ref.name
                    custom_libs.append(custom_lib)
                    custom_lib_names.add(proj_ref.name)
            else:
                # Try to find it in parent directories (common for sibling projects)
                # e.g., ..\JetMetal.IoLink\IEC61499\JetMetal.IoLink.dfbproj
                alt_path = (project_dir.parent / ref_path.parts[-3] / ref_path.parts[-2] / ref_path.parts[-1]).resolve() if len(ref_path.parts) >= 3 else None
                if alt_path and alt_path.exists():
                    custom_lib = analyze_custom_library(alt_path)
                    if custom_lib:
                        custom_lib.name = proj_ref.name
                        custom_libs.append(custom_lib)
                        custom_lib_names.add(proj_ref.name)
                else:
                    # Create a basic entry from the reference info
                    custom_libs.append(CustomLibraryInfo(
                        name=proj_ref.name,
                        namespace=proj_ref.name,
                        block_count=0,  # Unknown
                        depends_on=[],
                        path=proj_ref.path
                    ))
                    custom_lib_names.add(proj_ref.name)

    # Count library usage
    for lib_name, lib_info in all_se_libs.items():
        lib_info.blocks_used = count_library_usage(project_dir, lib_name)

    # Categorize libraries
    for lib_info in all_se_libs.values():
        cat = lib_info.category
        categories[cat] = categories.get(cat, 0) + 1

    # Identify unused libraries
    unused = [lib.name for lib in all_se_libs.values()
              if lib.blocks_used == 0 and lib.is_se_library]

    # Check for missing libraries (referenced but not in catalog)
    missing = [lib.name for lib in all_se_libs.values()
               if lib.is_se_library and lib.category == 'unknown']

    return LibraryAnalysis(
        se_libraries=list(all_se_libs.values()),
        custom_libraries=custom_libs,
        project_references=all_project_refs,
        total_se_libraries=sum(1 for lib in all_se_libs.values() if lib.is_se_library),
        total_custom_libraries=len(custom_libs),
        total_dependencies=len(all_se_libs) + len(all_project_refs),
        categories=categories,
        missing_libraries=missing,
        unused_libraries=unused,
        warnings=warnings
    )


def main():
    parser = argparse.ArgumentParser(
        description='Analyze EAE library references',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--project-dir', type=Path, required=True,
                        help='Path to EAE project root directory')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--output', type=Path, help='Output file path')

    args = parser.parse_args()

    if not args.project_dir.exists():
        print(f"Error: Project directory not found: {args.project_dir}", file=sys.stderr)
        sys.exit(1)

    # Analyze libraries
    result = analyze_libraries(args.project_dir)

    # Convert to dict for JSON serialization
    def to_dict(obj):
        if hasattr(obj, '__dict__'):
            d = {}
            for k, v in obj.__dict__.items():
                if isinstance(v, list):
                    d[k] = [to_dict(i) for i in v]
                elif isinstance(v, dict):
                    d[k] = v
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
        lines.append("Library Analysis")
        lines.append("=" * 50)
        lines.append(f"Total SE Libraries: {result.total_se_libraries}")
        lines.append(f"Total Custom Libraries: {result.total_custom_libraries}")
        lines.append(f"Total Dependencies: {result.total_dependencies}")
        lines.append("")

        lines.append("Categories:")
        for cat, count in sorted(result.categories.items()):
            lines.append(f"  {cat}: {count}")
        lines.append("")

        lines.append("SE Standard Libraries:")
        for lib in sorted(result.se_libraries, key=lambda x: x.name):
            if lib.is_se_library:
                usage = f" (used {lib.blocks_used}x)" if lib.blocks_used > 0 else " (unused)"
                lines.append(f"  [{lib.category}] {lib.name} v{lib.version}{usage}")
                if lib.description:
                    lines.append(f"      {lib.description}")
        lines.append("")

        if result.custom_libraries:
            lines.append("Custom Libraries:")
            for lib in result.custom_libraries:
                lines.append(f"  {lib.name} ({lib.namespace})")
                lines.append(f"    Blocks: {lib.block_count}")
                lines.append(f"    Depends on: {', '.join(lib.depends_on) if lib.depends_on else 'None'}")
            lines.append("")

        if result.project_references:
            lines.append("Project References:")
            for lib in result.project_references:
                lines.append(f"  {lib.name} -> {lib.path}")
            lines.append("")

        if result.unused_libraries:
            lines.append("Potentially Unused Libraries:")
            for name in result.unused_libraries:
                lines.append(f"  - {name}")
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
