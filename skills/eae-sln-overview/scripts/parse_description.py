#!/usr/bin/env python3
"""
EAE Project Description Parser - Generate project descriptions

Hybrid approach:
1. Search for and parse existing documentation (.doc.xml, README, VersionInfo)
2. If no meaningful docs found, infer description from project metadata

Exit Codes:
    0: Description generated successfully
    1: Project directory not found
   10: Partial success (inferred, no docs found)

Usage:
    python parse_description.py --project-dir /path/to/eae/project
    python parse_description.py --project-dir /path/to/project --json
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple


@dataclass
class DocumentationSource:
    """A source of documentation found in the project."""
    source_type: str  # 'readme', 'doc_xml', 'version_info', 'comment'
    file_path: str
    content: str
    relevance_score: float  # 0.0 to 1.0


@dataclass
class ProjectMetadata:
    """Metadata extracted from project structure for description inference."""
    project_name: str
    subsystems: List[str]
    equipment_types: List[str]
    protocols: List[str]
    library_categories: List[str]
    fb_count: int
    device_count: int
    industry_hints: List[str]


@dataclass
class ProjectDescription:
    """Generated project description."""
    short_description: str  # 1-2 sentences
    detailed_description: str  # Full paragraph
    source: str  # 'documentation', 'inferred', 'hybrid'
    confidence: float  # 0.0 to 1.0
    documentation_found: List[DocumentationSource]
    metadata_used: Optional[ProjectMetadata]
    warnings: List[str] = field(default_factory=list)


# Industry keywords for classification
INDUSTRY_KEYWORDS = {
    'food_beverage': [
        'jet', 'spray', 'mix', 'blend', 'batch', 'tank', 'vessel', 'pump',
        'valve', 'clean', 'cip', 'sip', 'pasteur', 'steril', 'fill', 'bottle',
        'can', 'pack', 'label', 'conveyor', 'hopper', 'feeder', 'dose', 'weigh'
    ],
    'water_wastewater': [
        'water', 'pump', 'filter', 'treat', 'chlor', 'uv', 'membrane', 'sludge',
        'aerat', 'clarif', 'sediment', 'reservoir', 'well', 'intake', 'discharge'
    ],
    'pharmaceutical': [
        'reactor', 'vessel', 'batch', 'clean', 'steril', 'cip', 'sip', 'dose',
        'fill', 'lyophil', 'granul', 'coat', 'tablet', 'capsule', 'vial', 'gmp'
    ],
    'manufacturing': [
        'conveyor', 'robot', 'arm', 'pick', 'place', 'assemble', 'weld', 'cut',
        'drill', 'mill', 'lathe', 'cnc', 'press', 'stamp', 'mold', 'inject'
    ],
    'material_handling': [
        'conveyor', 'sorter', 'pick', 'pack', 'warehouse', 'storage', 'retriev',
        'agv', 'crane', 'hoist', 'lift', 'palletiz', 'depalletiz', 'scanner'
    ],
    'energy': [
        'turbine', 'generator', 'transform', 'switch', 'breaker', 'grid', 'solar',
        'wind', 'battery', 'inverter', 'charger', 'meter', 'power', 'energy'
    ],
    'mining': [
        'crush', 'grind', 'mill', 'screen', 'conveyor', 'hopper', 'feeder',
        'flotation', 'thicken', 'filter', 'pump', 'cyclone', 'magnetic'
    ],
    'hvac': [
        'hvac', 'ahu', 'chiller', 'boiler', 'fan', 'damper', 'vav', 'thermostat',
        'humidif', 'dehumidif', 'heat', 'cool', 'ventilat', 'air', 'duct'
    ]
}

# Equipment type to description mapping
EQUIPMENT_DESCRIPTIONS = {
    'motor': 'motor control',
    'valve': 'valve actuation',
    'pump': 'pump operation',
    'tank': 'tank/vessel management',
    'conveyor': 'conveyor systems',
    'mixer': 'mixing operations',
    'heater': 'heating control',
    'cooler': 'cooling control',
    'sensor': 'sensor integration',
    'pid': 'PID control loops',
    'batch': 'batch processing',
    'recipe': 'recipe management',
    'alarm': 'alarm handling',
    'trend': 'trend logging',
    'hmi': 'HMI visualization'
}


def find_readme_files(project_dir: Path) -> List[Tuple[Path, str]]:
    """Find README files in the project."""
    readme_patterns = ['README.md', 'README.txt', 'README', 'readme.md', 'Readme.md']
    found = []

    for pattern in readme_patterns:
        for readme_path in project_dir.rglob(pattern):
            try:
                content = readme_path.read_text(encoding='utf-8', errors='ignore')
                if content.strip():
                    found.append((readme_path, content))
            except Exception:
                pass

    return found


def find_doc_xml_files(project_dir: Path) -> List[Tuple[Path, str]]:
    """Find .doc.xml documentation files."""
    found = []

    for doc_path in project_dir.rglob('*.doc.xml'):
        try:
            tree = ET.parse(doc_path)
            root = tree.getroot()

            # Extract text content from documentation
            texts = []
            for elem in root.iter():
                if elem.text and elem.text.strip():
                    texts.append(elem.text.strip())
                if elem.tail and elem.tail.strip():
                    texts.append(elem.tail.strip())

            content = ' '.join(texts)
            if content.strip():
                found.append((doc_path, content))
        except Exception:
            pass

    return found


def find_version_info(project_dir: Path) -> List[Tuple[Path, str]]:
    """Find version info or project description in .dfbproj files."""
    found = []

    for dfbproj_path in project_dir.rglob('*.dfbproj'):
        try:
            tree = ET.parse(dfbproj_path)
            root = tree.getroot()

            # Look for Description, Comment, or VersionInfo elements
            ns = {'msbuild': 'http://schemas.microsoft.com/developer/msbuild/2003'}

            for tag in ['Description', 'Comment', 'VersionInfo', 'ProjectDescription']:
                for elem in root.findall(f'.//{tag}', ns):
                    if elem.text and elem.text.strip():
                        found.append((dfbproj_path, elem.text.strip()))

                # Also try without namespace
                for elem in root.findall(f'.//{tag}'):
                    if elem.text and elem.text.strip():
                        found.append((dfbproj_path, elem.text.strip()))
        except Exception:
            pass

    return found


def extract_fbt_comments(project_dir: Path, limit: int = 20) -> List[Tuple[Path, str]]:
    """Extract meaningful comments from .fbt files."""
    found = []
    count = 0

    for fbt_path in project_dir.rglob('*.fbt'):
        if count >= limit:
            break

        try:
            tree = ET.parse(fbt_path)
            root = tree.getroot()

            # Look for Comment attribute on root or CompositeFB
            comment = root.get('Comment', '')
            if not comment:
                for child in root:
                    comment = child.get('Comment', '')
                    if comment:
                        break

            # Also check Documentation elements
            for doc_elem in root.findall('.//Documentation'):
                if doc_elem.text and doc_elem.text.strip():
                    comment = doc_elem.text.strip()
                    break

            if comment and len(comment) > 20:  # Meaningful comment
                found.append((fbt_path, comment))
                count += 1
        except Exception:
            pass

    return found


def calculate_relevance_score(content: str) -> float:
    """Calculate how relevant/meaningful a piece of documentation is."""
    if not content:
        return 0.0

    score = 0.0
    content_lower = content.lower()

    # Length bonus (longer = more informative, up to a point)
    words = len(content.split())
    if words > 10:
        score += 0.2
    if words > 50:
        score += 0.2
    if words > 200:
        score += 0.1

    # Contains descriptive keywords
    descriptive_words = ['system', 'control', 'manage', 'process', 'automat',
                         'monitor', 'operation', 'function', 'purpose', 'design']
    for word in descriptive_words:
        if word in content_lower:
            score += 0.05

    # Penalty for boilerplate
    boilerplate = ['copyright', 'license', 'all rights reserved', 'confidential',
                   'do not distribute', 'auto-generated', 'template']
    for word in boilerplate:
        if word in content_lower:
            score -= 0.1

    # Bonus for complete sentences
    if re.search(r'[A-Z][^.!?]*[.!?]', content):
        score += 0.1

    return max(0.0, min(1.0, score))


def collect_documentation(project_dir: Path) -> List[DocumentationSource]:
    """Collect all documentation sources from the project."""
    sources = []

    # README files (highest priority)
    for path, content in find_readme_files(project_dir):
        sources.append(DocumentationSource(
            source_type='readme',
            file_path=str(path.relative_to(project_dir)),
            content=content[:2000],  # Limit content size
            relevance_score=calculate_relevance_score(content)
        ))

    # Version info from dfbproj
    for path, content in find_version_info(project_dir):
        sources.append(DocumentationSource(
            source_type='version_info',
            file_path=str(path.relative_to(project_dir)),
            content=content[:500],
            relevance_score=calculate_relevance_score(content)
        ))

    # .doc.xml files
    for path, content in find_doc_xml_files(project_dir):
        sources.append(DocumentationSource(
            source_type='doc_xml',
            file_path=str(path.relative_to(project_dir)),
            content=content[:1000],
            relevance_score=calculate_relevance_score(content)
        ))

    # FBT comments (lower priority)
    for path, content in extract_fbt_comments(project_dir):
        sources.append(DocumentationSource(
            source_type='comment',
            file_path=str(path.relative_to(project_dir)),
            content=content[:500],
            relevance_score=calculate_relevance_score(content) * 0.7  # Reduce score for comments
        ))

    # Sort by relevance
    sources.sort(key=lambda x: x.relevance_score, reverse=True)

    return sources


def collect_metadata(project_dir: Path) -> ProjectMetadata:
    """Collect project metadata for description inference."""
    project_name = project_dir.name
    subsystems = []
    equipment_types = set()
    protocols = set()
    library_categories = set()
    fb_count = 0
    device_count = 0
    industry_hints = []

    # Count FBs and extract types
    for fbt_path in project_dir.rglob('*.fbt'):
        fb_count += 1
        fb_name = fbt_path.stem.lower()

        # Extract equipment types from FB names
        for equip_type in EQUIPMENT_DESCRIPTIONS.keys():
            if equip_type in fb_name:
                equipment_types.add(equip_type)

    # Find subsystems from System.sys
    sys_path = project_dir / 'IEC61499' / 'System' / 'System.sys'
    if sys_path.exists():
        try:
            tree = ET.parse(sys_path)
            root = tree.getroot()

            # Get folder path (subsystems)
            for attr in root.findall('.//Attribute'):
                if 'FolderPath' in attr.get('Name', ''):
                    value = attr.get('Value', '')
                    if value:
                        subsystems = [s.strip() for s in value.split(',') if s.strip()]
        except Exception:
            pass

    # Count devices from System.cfg
    cfg_path = project_dir / 'IEC61499' / 'System' / 'System.cfg'
    if cfg_path.exists():
        try:
            tree = ET.parse(cfg_path)
            root = tree.getroot()
            device_count = len(root.findall('.//Device'))
        except Exception:
            pass

    # Detect protocols from library references
    for dfbproj_path in project_dir.rglob('*.dfbproj'):
        try:
            content = dfbproj_path.read_text(encoding='utf-8', errors='ignore')
            content_lower = content.lower()

            if 'opcua' in content_lower or 'opc.ua' in content_lower:
                protocols.add('OPC-UA')
            if 'modbus' in content_lower:
                protocols.add('Modbus')
            if 'ethernetip' in content_lower or 'ethernet/ip' in content_lower:
                protocols.add('EtherNet/IP')
            if 'profinet' in content_lower:
                protocols.add('PROFINET')
            if 'iolink' in content_lower or 'io-link' in content_lower:
                protocols.add('IO-Link')

            # Detect library categories
            if 'se.app' in content_lower:
                library_categories.add('SE Process Libraries')
            if 'runtime.base' in content_lower:
                library_categories.add('Runtime Base')
            if 'se.io' in content_lower:
                library_categories.add('SE I/O Libraries')
        except Exception:
            pass

    # Detect industry from project name and subsystem names
    all_names = [project_name.lower()] + [s.lower() for s in subsystems]
    all_names_str = ' '.join(all_names)

    industry_scores = {}
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in all_names_str)
        if score > 0:
            industry_scores[industry] = score

    # Get top industries
    sorted_industries = sorted(industry_scores.items(), key=lambda x: x[1], reverse=True)
    industry_hints = [ind for ind, score in sorted_industries[:2] if score >= 2]

    return ProjectMetadata(
        project_name=project_name,
        subsystems=subsystems,
        equipment_types=list(equipment_types),
        protocols=list(protocols),
        library_categories=list(library_categories),
        fb_count=fb_count,
        device_count=device_count,
        industry_hints=industry_hints
    )


def infer_description_from_metadata(metadata: ProjectMetadata) -> Tuple[str, str]:
    """Infer project description from metadata."""
    parts = []
    details = []

    # Project name analysis
    name = metadata.project_name
    name_readable = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)  # CamelCase to spaces
    name_readable = re.sub(r'[_-]', ' ', name_readable)  # Underscores/dashes to spaces

    # Industry classification
    if metadata.industry_hints:
        industry_map = {
            'food_beverage': 'food and beverage processing',
            'water_wastewater': 'water/wastewater treatment',
            'pharmaceutical': 'pharmaceutical manufacturing',
            'manufacturing': 'discrete manufacturing',
            'material_handling': 'material handling and logistics',
            'energy': 'energy management',
            'mining': 'mining and minerals processing',
            'hvac': 'HVAC and building automation'
        }
        industry = industry_map.get(metadata.industry_hints[0], metadata.industry_hints[0])
        parts.append(f"an IEC 61499 automation project for {industry}")
    else:
        parts.append("an IEC 61499 industrial automation project")

    # Subsystems
    if metadata.subsystems:
        if len(metadata.subsystems) <= 3:
            subsys_str = ', '.join(metadata.subsystems)
            details.append(f"The system includes {len(metadata.subsystems)} subsystems: {subsys_str}")
        else:
            details.append(f"The system includes {len(metadata.subsystems)} subsystems including {metadata.subsystems[0]} and {metadata.subsystems[1]}")

    # Equipment types
    if metadata.equipment_types:
        equip_descriptions = [EQUIPMENT_DESCRIPTIONS.get(e, e) for e in metadata.equipment_types[:4]]
        details.append(f"It implements {', '.join(equip_descriptions)}")

    # Scale
    if metadata.fb_count > 0:
        scale = "small" if metadata.fb_count < 50 else "medium" if metadata.fb_count < 200 else "large"
        details.append(f"The project is a {scale}-scale implementation with {metadata.fb_count} function blocks")

    if metadata.device_count > 0:
        details.append(f"deployed across {metadata.device_count} devices")

    # Protocols
    if metadata.protocols:
        details.append(f"Communication uses {', '.join(sorted(metadata.protocols))}")

    # Libraries
    if metadata.library_categories:
        details.append(f"Built with {', '.join(sorted(metadata.library_categories))}")

    # Build short description
    short_desc = f"{name_readable} is {parts[0]}."

    # Build detailed description
    detailed_parts = [short_desc]
    detailed_parts.extend([d + '.' if not d.endswith('.') else d for d in details])
    detailed_desc = ' '.join(detailed_parts)

    return short_desc, detailed_desc


def generate_description_from_docs(sources: List[DocumentationSource]) -> Tuple[str, str]:
    """Generate description from documentation sources."""
    # Get the best source
    best_source = sources[0]
    content = best_source.content

    # Try to extract first meaningful paragraph
    paragraphs = re.split(r'\n\s*\n', content)

    # Filter out headers and short lines
    meaningful_paragraphs = []
    for p in paragraphs:
        p = p.strip()
        # Skip if too short, looks like a header, or is a list item
        if (len(p) > 50 and
            not p.startswith('#') and
            not p.startswith('-') and
            not p.startswith('*') and
            not re.match(r'^[A-Z][^.!?]*$', p)):  # Not a title
            meaningful_paragraphs.append(p)

    if meaningful_paragraphs:
        # Use first meaningful paragraph
        detailed = meaningful_paragraphs[0]
        # Create short version (first sentence or truncate)
        sentences = re.split(r'(?<=[.!?])\s+', detailed)
        short = sentences[0] if sentences else detailed[:200]

        return short, detailed

    # Fallback: use the content as-is
    short = content[:200].strip()
    if len(content) > 200:
        short = short.rsplit(' ', 1)[0] + '...'

    return short, content[:500]


def generate_project_description(project_dir: Path) -> ProjectDescription:
    """Generate a project description using hybrid approach."""
    warnings = []

    # Step 1: Collect documentation
    doc_sources = collect_documentation(project_dir)

    # Step 2: Collect metadata (always, for potential hybrid use)
    metadata = collect_metadata(project_dir)

    # Step 3: Determine source and generate description
    high_quality_docs = [d for d in doc_sources if d.relevance_score > 0.4]

    if high_quality_docs:
        # Use documentation
        short_desc, detailed_desc = generate_description_from_docs(high_quality_docs)
        source = 'documentation'
        confidence = min(0.9, high_quality_docs[0].relevance_score + 0.3)
    else:
        # Infer from metadata
        short_desc, detailed_desc = infer_description_from_metadata(metadata)
        source = 'inferred'
        confidence = 0.6 if metadata.subsystems else 0.4

        if not doc_sources:
            warnings.append("No documentation found in project")
        else:
            warnings.append("Documentation found but not meaningful enough; description inferred from structure")

    # Enhance inferred description with any available doc snippets
    if source == 'inferred' and doc_sources:
        # Add a note about available docs
        source = 'hybrid'
        confidence += 0.1

    return ProjectDescription(
        short_description=short_desc,
        detailed_description=detailed_desc,
        source=source,
        confidence=min(1.0, confidence),
        documentation_found=doc_sources[:5],  # Top 5 sources
        metadata_used=metadata if source != 'documentation' else None,
        warnings=warnings
    )


def main():
    parser = argparse.ArgumentParser(
        description='Generate project description for EAE projects',
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

    # Generate description
    result = generate_project_description(args.project_dir)

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
        lines.append("Project Description")
        lines.append("=" * 50)
        lines.append(f"Source: {result.source} (confidence: {result.confidence:.0%})")
        lines.append("")
        lines.append("Short Description:")
        lines.append(f"  {result.short_description}")
        lines.append("")
        lines.append("Detailed Description:")
        lines.append(f"  {result.detailed_description}")
        lines.append("")

        if result.documentation_found:
            lines.append(f"Documentation Sources Found: {len(result.documentation_found)}")
            for doc in result.documentation_found[:3]:
                lines.append(f"  - {doc.source_type}: {doc.file_path} (relevance: {doc.relevance_score:.0%})")

        if result.metadata_used:
            lines.append("")
            lines.append("Metadata Used:")
            lines.append(f"  - Subsystems: {', '.join(result.metadata_used.subsystems) or 'None'}")
            lines.append(f"  - Equipment Types: {', '.join(result.metadata_used.equipment_types) or 'None'}")
            lines.append(f"  - Protocols: {', '.join(result.metadata_used.protocols) or 'None'}")
            lines.append(f"  - Industry Hints: {', '.join(result.metadata_used.industry_hints) or 'None'}")

        if result.warnings:
            lines.append("")
            lines.append("Warnings:")
            for w in result.warnings:
                lines.append(f"  - {w}")

        output = '\n'.join(lines)

    if args.output:
        args.output.write_text(output, encoding='utf-8')
    else:
        print(output)

    # Exit code
    if result.source == 'documentation':
        sys.exit(0)
    elif result.source in ['inferred', 'hybrid']:
        sys.exit(10)  # Partial success
    sys.exit(0)


if __name__ == '__main__':
    main()
