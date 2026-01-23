#!/usr/bin/env python3
"""
EAE Quality Calculator - Project quality rating engine

Calculates an overall quality score based on 8 dimensions:
- Naming Compliance (20 points)
- Library Organization (15 points)
- Documentation (15 points)
- ISA88 Hierarchy (15 points)
- Protocol Configuration (10 points)
- Code Organization (10 points)
- Block Complexity (10 points)
- Reusability (5 points)

Exit Codes:
    0: Quality score >= 70 (passing)
    1: Error calculating quality
   10: Quality score 50-69 (needs improvement)
   11: Quality score < 50 (failing)

Usage:
    python calculate_quality.py --project-dir /path/to/eae/project
    python calculate_quality.py --project-dir /path/to/project --json
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class DimensionScore:
    """Score for a single quality dimension."""
    name: str
    score: int
    max_score: int
    percentage: float
    details: List[str]
    recommendations: List[str]


@dataclass
class QualityResult:
    """Complete quality assessment."""
    overall_score: int
    max_score: int
    percentage: float
    grade: str
    dimensions: List[DimensionScore]
    top_recommendations: List[str]
    warnings: List[str] = field(default_factory=list)


# Grade thresholds
GRADE_THRESHOLDS = [
    (90, 'A'),
    (80, 'B'),
    (70, 'C'),
    (60, 'D'),
    (0, 'F')
]


def get_grade(percentage: float) -> str:
    """Get letter grade from percentage."""
    for threshold, grade in GRADE_THRESHOLDS:
        if percentage >= threshold:
            return grade
    return 'F'


# Naming convention patterns (simplified from eae-naming-validator)
NAMING_PATTERNS = {
    'CAT': r'^[A-Z][a-zA-Z0-9]*$',
    'BasicFB': r'^[a-z][a-zA-Z0-9]*$',
    'CompositeFB': r'^[a-z][a-zA-Z0-9]*$',
    'Adapter': r'^I[A-Z][a-zA-Z0-9]*$',
    'DataType': r'^(str|e|arr|a)[A-Z][a-zA-Z0-9]*$',
    'Event': r'^[A-Z][A-Z0-9_]*$',
    'Variable': r'^[A-Z][a-zA-Z0-9]*$',
}


def check_naming_compliance(project_dir: Path) -> Tuple[int, List[str], List[str]]:
    """Check naming convention compliance. Returns (score, details, recommendations)."""
    total_items = 0
    compliant_items = 0
    violations = []

    # Check .fbt files
    for fbt_path in project_dir.rglob('*.fbt'):
        try:
            tree = ET.parse(fbt_path)
            root = tree.getroot()

            block_name = root.get('Name', '')
            root_tag = root.tag

            # Determine expected pattern
            if root_tag == 'SubAppType':
                pattern = NAMING_PATTERNS['CAT']
                block_type = 'CAT'
            elif root_tag == 'AdapterType':
                pattern = NAMING_PATTERNS['Adapter']
                block_type = 'Adapter'
            elif root.find('.//BasicFB') is not None:
                pattern = NAMING_PATTERNS['BasicFB']
                block_type = 'BasicFB'
            else:
                pattern = NAMING_PATTERNS['CompositeFB']
                block_type = 'CompositeFB'

            total_items += 1
            if re.match(pattern, block_name):
                compliant_items += 1
            else:
                violations.append(f"{block_type} '{block_name}' does not match pattern")

        except ET.ParseError:
            pass

    # Check .dt files
    for dt_path in project_dir.rglob('*.dt'):
        try:
            tree = ET.parse(dt_path)
            root = tree.getroot()

            type_name = root.get('Name', '')
            total_items += 1

            if re.match(NAMING_PATTERNS['DataType'], type_name):
                compliant_items += 1
            else:
                violations.append(f"DataType '{type_name}' does not match pattern")

        except ET.ParseError:
            pass

    # Calculate score (20 points max)
    if total_items == 0:
        return 20, ["No blocks to check"], []

    compliance_rate = compliant_items / total_items
    score = int(compliance_rate * 20)

    details = [
        f"Checked {total_items} items",
        f"Compliant: {compliant_items} ({compliance_rate*100:.1f}%)",
        f"Violations: {len(violations)}"
    ]

    recommendations = []
    if violations:
        recommendations.append(f"Fix {len(violations)} naming violations")
        if len(violations) <= 5:
            recommendations.extend(violations[:5])

    return score, details, recommendations


def check_library_organization(project_dir: Path) -> Tuple[int, List[str], List[str]]:
    """Check library organization. Returns (score, details, recommendations)."""
    score = 15  # Start with max
    details = []
    recommendations = []

    se_libs = 0
    custom_libs = 0
    project_refs = 0
    unused_libs = []

    # Parse dfbproj files
    for dfbproj in project_dir.rglob('*.dfbproj'):
        try:
            tree = ET.parse(dfbproj)
            root = tree.getroot()

            ns = {'msbuild': 'http://schemas.microsoft.com/developer/msbuild/2003'}

            for ref in root.findall('.//Reference', ns) + root.findall('.//Reference'):
                include = ref.get('Include', '')
                if include.startswith('SE.') or include.startswith('Standard.') or include.startswith('Runtime.'):
                    se_libs += 1
                else:
                    custom_libs += 1

            for ref in root.findall('.//ProjectReference', ns) + root.findall('.//ProjectReference'):
                project_refs += 1

        except ET.ParseError:
            pass

    details.append(f"SE Libraries: {se_libs}")
    details.append(f"Custom Libraries: {custom_libs}")
    details.append(f"Project References: {project_refs}")

    # Deductions
    if custom_libs > se_libs and se_libs > 0:
        score -= 3
        recommendations.append("Consider using more SE standard libraries")

    if project_refs > 5:
        score -= 2
        recommendations.append("High number of project references may indicate over-fragmentation")

    return max(0, score), details, recommendations


def check_documentation(project_dir: Path) -> Tuple[int, List[str], List[str]]:
    """Check documentation coverage. Returns (score, details, recommendations)."""
    total_blocks = 0
    documented_blocks = 0

    # Check for .doc.xml files
    doc_files = set(p.stem.replace('.doc', '') for p in project_dir.rglob('*.doc.xml'))

    # Check .fbt files
    for fbt_path in project_dir.rglob('*.fbt'):
        total_blocks += 1
        block_name = fbt_path.stem

        # Check if documentation exists
        if block_name in doc_files:
            documented_blocks += 1
        else:
            # Check for inline documentation
            try:
                tree = ET.parse(fbt_path)
                root = tree.getroot()

                # Look for Comment attributes on variables
                has_comments = False
                for var in root.findall('.//VarDeclaration'):
                    if var.get('Comment'):
                        has_comments = True
                        break

                if has_comments:
                    documented_blocks += 0.5  # Partial credit

            except ET.ParseError:
                pass

    # Calculate score (15 points max)
    if total_blocks == 0:
        return 15, ["No blocks to check"], []

    doc_rate = documented_blocks / total_blocks
    score = int(doc_rate * 15)

    details = [
        f"Total blocks: {total_blocks}",
        f"Documented: {documented_blocks:.0f} ({doc_rate*100:.1f}%)"
    ]

    recommendations = []
    if doc_rate < 0.7:
        recommendations.append(f"Add documentation to {int(total_blocks * 0.7 - documented_blocks)} more blocks")

    return score, details, recommendations


def check_isa88_hierarchy(project_dir: Path) -> Tuple[int, List[str], List[str]]:
    """Check ISA88 hierarchy configuration. Returns (score, details, recommendations)."""
    score = 0
    details = []
    recommendations = []

    # Find System directory for ISA88 hierarchy
    system_dir = project_dir / 'IEC61499' / 'System'
    if not system_dir.exists():
        for subdir in project_dir.rglob('System'):
            if (subdir / 'System.sys').exists():
                system_dir = subdir
                break

    if not system_dir.exists():
        details.append("System directory not found")
        recommendations.append("Configure system topology")
        return 0, details, recommendations

    # Check System.sys for subsystem hierarchy
    sys_path = system_dir / 'System.sys'
    if not sys_path.exists():
        details.append("System.sys not found")
        recommendations.append("Configure system with subsystems")
        return 0, details, recommendations

    try:
        tree = ET.parse(sys_path)
        root = tree.getroot()

        # Look for Device.FolderPath attribute (subsystem list)
        folder_path = []
        for attr in root.findall('.//Attribute'):
            attr_name = attr.get('Name', '')
            if 'FolderPath' in attr_name:
                value = attr.get('Value', '')
                if value:
                    folder_path = [s.strip() for s in value.split(',') if s.strip()]

        # Count CATType instances (subsystems and equipment)
        cat_types = root.findall('.//CATType')
        total_cat_instances = sum(len(ct.findall('.//Inst')) for ct in cat_types)

        details.append(f"Subsystems: {len(folder_path)}")
        details.append(f"CAT instances: {total_cat_instances}")

        if folder_path:
            details.append(f"Folder path: {', '.join(folder_path)}")

        # Score based on hierarchy configuration
        if len(folder_path) >= 4:
            score = 15  # Full marks for 4+ subsystems
        elif len(folder_path) >= 3:
            score = 12
        elif len(folder_path) >= 2:
            score = 10
        elif len(folder_path) >= 1:
            score = 7
        elif total_cat_instances > 0:
            score = 5  # Some CAT instances but no folder structure
        else:
            score = 0

        if len(folder_path) == 0 and total_cat_instances > 0:
            recommendations.append("Define subsystem hierarchy using Device.FolderPath")

    except ET.ParseError as e:
        details.append(f"Error parsing System.sys: {e}")
        return 0, details, recommendations

    return score, details, recommendations


def check_protocol_configuration(project_dir: Path) -> Tuple[int, List[str], List[str]]:
    """Check protocol configuration quality. Returns (score, details, recommendations)."""
    score = 10  # Start with max
    details = []
    recommendations = []

    system_dir = project_dir / 'IEC61499' / 'System'
    if not system_dir.exists():
        details.append("System directory not found")
        return 5, details, ["Configure system topology"]

    # Check OPC-UA configuration
    opcua_path = system_dir / 'System.opcua.xml'
    if opcua_path.exists():
        try:
            tree = ET.parse(opcua_path)
            root = tree.getroot()

            exposed_count = sum(1 for elem in root.iter() if elem.get('Exposed', '').lower() == 'true')
            details.append(f"OPC-UA exposed nodes: {exposed_count}")

            # Check for over-exposure
            if exposed_count > 1000:
                score -= 3
                recommendations.append("Review OPC-UA exposure - consider reducing exposed nodes")

        except ET.ParseError:
            pass
    else:
        details.append("OPC-UA not configured")

    # Check for protocol configuration files
    protocol_files = list(system_dir.rglob('*.offline.xml')) + list(system_dir.rglob('*.cfg'))
    if protocol_files:
        details.append(f"Protocol config files: {len(protocol_files)}")
    else:
        score -= 2
        details.append("No protocol configuration files found")

    return max(0, score), details, recommendations


def check_code_organization(project_dir: Path) -> Tuple[int, List[str], List[str]]:
    """Check code organization. Returns (score, details, recommendations)."""
    score = 10  # Start with max
    details = []
    recommendations = []

    # Check for Folders.xml
    folders_files = list(project_dir.rglob('Folders.xml'))
    if folders_files:
        details.append(f"Folder organization files: {len(folders_files)}")
    else:
        score -= 3
        details.append("No Folders.xml found")
        recommendations.append("Organize blocks into folders using Folders.xml")

    # Check directory structure
    iec_dir = project_dir / 'IEC61499'
    if iec_dir.exists():
        subdirs = [d for d in iec_dir.iterdir() if d.is_dir()]
        if len(subdirs) >= 3:
            details.append(f"IEC61499 subdirectories: {len(subdirs)}")
        else:
            score -= 2
            recommendations.append("Organize IEC61499 blocks into subdirectories")
    else:
        score -= 5
        details.append("IEC61499 directory not found")

    # Check for consistent naming in folders
    fbt_folders = set()
    for fbt in project_dir.rglob('*.fbt'):
        fbt_folders.add(fbt.parent.name)

    if len(fbt_folders) > 1:
        details.append(f"FBT organized across {len(fbt_folders)} folders")
    else:
        score -= 2
        recommendations.append("Distribute blocks across multiple organized folders")

    return max(0, score), details, recommendations


def check_block_complexity(project_dir: Path) -> Tuple[int, List[str], List[str]]:
    """Check block complexity. Returns (score, details, recommendations)."""
    score = 10  # Start with max
    details = []
    recommendations = []

    complex_blocks = []
    total_blocks = 0

    for fbt_path in project_dir.rglob('*.fbt'):
        try:
            tree = ET.parse(fbt_path)
            root = tree.getroot()

            total_blocks += 1
            block_name = root.get('Name', fbt_path.stem)

            # Count variables
            var_count = len(root.findall('.//VarDeclaration'))

            # Count events
            event_in = len(root.findall('.//EventInputs/Event'))
            event_out = len(root.findall('.//EventOutputs/Event'))

            # Check thresholds
            if var_count > 100:
                complex_blocks.append(f"{block_name}: {var_count} vars")

            if event_in > 0 and event_out / event_in > 10:
                complex_blocks.append(f"{block_name}: high event fanout")

        except ET.ParseError:
            pass

    details.append(f"Total blocks analyzed: {total_blocks}")
    details.append(f"Complex blocks: {len(complex_blocks)}")

    # Deduct points for complex blocks
    if len(complex_blocks) > 15:
        score -= 8
    elif len(complex_blocks) > 5:
        score -= 4
    elif len(complex_blocks) > 0:
        score -= 2

    if complex_blocks:
        recommendations.append(f"Refactor {len(complex_blocks)} complex blocks")

    return max(0, score), details, recommendations


def check_reusability(project_dir: Path) -> Tuple[int, List[str], List[str]]:
    """Check reusability patterns. Returns (score, details, recommendations)."""
    score = 0
    details = []
    recommendations = []

    # Count adapters
    adapters = list(project_dir.rglob('*.adp'))
    adapter_count = len(adapters)

    # Count composite FBs (reuse pattern)
    composite_count = 0
    for fbt in project_dir.rglob('*.fbt'):
        try:
            tree = ET.parse(fbt)
            root = tree.getroot()
            if root.find('.//FBNetwork') is not None:
                composite_count += 1
        except ET.ParseError:
            pass

    details.append(f"Adapters: {adapter_count}")
    details.append(f"Composite FBs: {composite_count}")

    # Score based on reusability patterns
    if adapter_count >= 10:
        score += 3
    elif adapter_count >= 5:
        score += 2
    elif adapter_count >= 1:
        score += 1

    if composite_count >= 20:
        score += 2
    elif composite_count >= 5:
        score += 1

    if adapter_count == 0:
        recommendations.append("Consider using adapters for reusable interfaces")

    return min(5, score), details, recommendations


def calculate_quality(project_dir: Path) -> QualityResult:
    """Calculate overall project quality."""
    dimensions = []
    warnings = []

    # Check each dimension
    checks = [
        ("Naming Compliance", 20, check_naming_compliance),
        ("Library Organization", 15, check_library_organization),
        ("Documentation", 15, check_documentation),
        ("ISA88 Hierarchy", 15, check_isa88_hierarchy),
        ("Protocol Configuration", 10, check_protocol_configuration),
        ("Code Organization", 10, check_code_organization),
        ("Block Complexity", 10, check_block_complexity),
        ("Reusability", 5, check_reusability),
    ]

    for name, max_score, check_func in checks:
        try:
            score, details, recommendations = check_func(project_dir)
            dimensions.append(DimensionScore(
                name=name,
                score=score,
                max_score=max_score,
                percentage=(score / max_score * 100) if max_score > 0 else 0,
                details=details,
                recommendations=recommendations
            ))
        except Exception as e:
            warnings.append(f"Error checking {name}: {e}")
            dimensions.append(DimensionScore(
                name=name,
                score=0,
                max_score=max_score,
                percentage=0,
                details=[f"Error: {e}"],
                recommendations=[]
            ))

    # Calculate totals
    overall_score = sum(d.score for d in dimensions)
    max_score = sum(d.max_score for d in dimensions)
    percentage = (overall_score / max_score * 100) if max_score > 0 else 0
    grade = get_grade(percentage)

    # Collect top recommendations
    all_recommendations = []
    for d in dimensions:
        for rec in d.recommendations:
            all_recommendations.append((d.name, rec, d.max_score - d.score))

    # Sort by impact (points lost)
    all_recommendations.sort(key=lambda x: x[2], reverse=True)
    top_recommendations = [f"[{r[0]}] {r[1]}" for r in all_recommendations[:5]]

    return QualityResult(
        overall_score=overall_score,
        max_score=max_score,
        percentage=percentage,
        grade=grade,
        dimensions=dimensions,
        top_recommendations=top_recommendations,
        warnings=warnings
    )


def main():
    parser = argparse.ArgumentParser(
        description='Calculate EAE project quality score',
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

    # Calculate quality
    result = calculate_quality(args.project_dir)

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
        lines.append("Project Quality Assessment")
        lines.append("=" * 50)
        lines.append(f"Overall Score: {result.overall_score}/{result.max_score} ({result.percentage:.1f}%)")
        lines.append(f"Grade: {result.grade}")
        lines.append("")

        lines.append("Dimension Scores:")
        lines.append("-" * 50)
        for dim in result.dimensions:
            status = "PASS" if dim.percentage >= 70 else "WARN" if dim.percentage >= 50 else "FAIL"
            lines.append(f"  {dim.name}: {dim.score}/{dim.max_score} ({dim.percentage:.0f}%) [{status}]")
            for detail in dim.details:
                lines.append(f"    - {detail}")
        lines.append("")

        if result.top_recommendations:
            lines.append("Top Recommendations:")
            lines.append("-" * 50)
            for i, rec in enumerate(result.top_recommendations, 1):
                lines.append(f"  {i}. {rec}")
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

    # Exit code based on quality
    if result.percentage >= 70:
        sys.exit(0)
    elif result.percentage >= 50:
        sys.exit(10)
    else:
        sys.exit(11)


if __name__ == '__main__':
    main()
