#!/usr/bin/env python3
"""
Validate EAE IEC 61499 block files for common errors.

Usage:
    python validate_block.py MyBlock.fbt              # Validate a single file
    python validate_block.py IEC61499/MyBlock/        # Validate a CAT folder
    python validate_block.py --type basic MyBlock.fbt # Specify block type
    python validate_block.py --json MyBlock.fbt       # Output as JSON

Exit codes:
    0: Validation passed
    1: Error (could not run validation)
    10: Validation failed (errors found)
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional
from xml.etree import ElementTree as ET


@dataclass
class ValidationIssue:
    """A single validation issue."""
    severity: str  # "error" or "warning"
    file: str
    message: str
    line: Optional[int] = None


@dataclass
class Result:
    """Standard result structure for EAE skill scripts."""
    success: bool
    message: str
    block_type: str
    files_checked: List[str]
    issues: List[ValidationIssue] = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        d['issues'] = [asdict(i) for i in self.issues]
        return d


# Validation rules by block type
BLOCK_RULES = {
    'basic': {
        'extension': '.fbt',
        'root_element': 'FBType',
        'has_guid': True,
        'has_format': False,
        'has_basicfb': True,
        'has_fbnetwork': False,
        'doctype_system': '../LibraryElement.dtd',
        'standard': '61499-2',
        'companion_files': ['.doc.xml', '.meta.xml'],
    },
    'composite': {
        'extension': '.fbt',
        'root_element': 'FBType',
        'has_guid': True,
        'has_format': True,
        'has_basicfb': False,
        'has_fbnetwork': True,
        'doctype_system': '../LibraryElement.dtd',
        'standard': '61499-2',
        'companion_files': ['.doc.xml', '.meta.xml', '.composite.offline.xml'],
    },
    'cat': {
        'extension': '.fbt',
        'root_element': 'FBType',
        'has_guid': True,
        'has_format': True,
        'has_basicfb': False,
        'has_fbnetwork': True,
        'doctype_system': '../LibraryElement.dtd',
        'standard': '61499-2',
        'companion_files': ['.doc.xml', '.meta.xml', '_CAT.offline.xml', '_CAT.opcua.xml'],
        'cat_folder': True,
    },
    'adapter': {
        'extension': '.adp',
        'root_element': 'AdapterType',
        'has_guid': True,
        'has_format': False,
        'has_service': True,
        'doctype_system': '../LibraryElement.dtd',
        'standard': '61499-1',
        'companion_files': ['.doc.xml'],
    },
    'datatype': {
        'extension': '.dt',
        'root_element': 'DataType',
        'has_guid': False,
        'has_format': False,
        'doctype_system': '../DataType.dtd',
        'standard': '1131-3',
        'companion_files': ['.doc.xml'],
        'subfolder': 'DataType',
    },
}


def detect_block_type(file_path: Path) -> Optional[str]:
    """Auto-detect block type from file extension and content."""
    ext = file_path.suffix.lower()

    if ext == '.adp':
        return 'adapter'
    elif ext == '.dt':
        return 'datatype'
    elif ext == '.fbt':
        # Need to check content to distinguish basic/composite/cat
        try:
            content = file_path.read_text(encoding='utf-8')
            if '<BasicFB>' in content:
                return 'basic'
            elif '<FBNetwork>' in content:
                # Check if it's a CAT (has HMI.Alias attribute)
                if 'HMI.Alias' in content:
                    return 'cat'
                return 'composite'
        except:
            pass
        return 'composite'  # Default for .fbt
    elif ext == '.cfg':
        return 'cat'

    return None


def validate_xml_structure(file_path: Path, rules: dict, issues: List[ValidationIssue]):
    """Validate XML structure against rules."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        issues.append(ValidationIssue(
            severity="error",
            file=str(file_path),
            message=f"Could not read file: {e}"
        ))
        return

    # Check for xmlns on root element (common error)
    xmlns_pattern = rf'<{rules["root_element"]}\s+[^>]*xmlns\s*='
    if re.search(xmlns_pattern, content):
        issues.append(ValidationIssue(
            severity="error",
            file=str(file_path),
            message=f'Root element <{rules["root_element"]}> must NOT have xmlns attribute'
        ))

    # Check DOCTYPE
    doctype_pattern = rf'<!DOCTYPE\s+{rules["root_element"]}\s+SYSTEM\s+"([^"]+)"'
    doctype_match = re.search(doctype_pattern, content)
    if not doctype_match:
        issues.append(ValidationIssue(
            severity="error",
            file=str(file_path),
            message=f'Missing or invalid DOCTYPE declaration for {rules["root_element"]}'
        ))
    elif doctype_match.group(1) != rules['doctype_system']:
        issues.append(ValidationIssue(
            severity="error",
            file=str(file_path),
            message=f'Wrong DOCTYPE SYSTEM: expected "{rules["doctype_system"]}", got "{doctype_match.group(1)}"'
        ))

    # Parse XML for deeper validation
    try:
        # Remove DOCTYPE to parse (ET doesn't handle it well)
        xml_content = re.sub(r'<!DOCTYPE[^>]+>', '', content)
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        issues.append(ValidationIssue(
            severity="error",
            file=str(file_path),
            message=f"XML parse error: {e}"
        ))
        return

    # Check root element
    if root.tag != rules['root_element']:
        issues.append(ValidationIssue(
            severity="error",
            file=str(file_path),
            message=f'Wrong root element: expected <{rules["root_element"]}>, got <{root.tag}>'
        ))

    # Check GUID
    if rules.get('has_guid'):
        if 'GUID' not in root.attrib:
            issues.append(ValidationIssue(
                severity="error",
                file=str(file_path),
                message='Missing required GUID attribute'
            ))
    elif 'GUID' in root.attrib:
        issues.append(ValidationIssue(
            severity="warning",
            file=str(file_path),
            message='GUID attribute present but not expected for this block type'
        ))

    # Check Format attribute
    if rules.get('has_format'):
        if root.attrib.get('Format') != '2.0':
            issues.append(ValidationIssue(
                severity="error",
                file=str(file_path),
                message='Missing or wrong Format attribute (expected Format="2.0")'
            ))

    # Check Identification Standard
    ident = root.find('Identification')
    if ident is not None:
        std = ident.attrib.get('Standard', '')
        if std != rules['standard']:
            issues.append(ValidationIssue(
                severity="error",
                file=str(file_path),
                message=f'Wrong Standard: expected "{rules["standard"]}", got "{std}"'
            ))
    else:
        issues.append(ValidationIssue(
            severity="error",
            file=str(file_path),
            message='Missing <Identification> element'
        ))

    # Check for BasicFB or FBNetwork
    if rules.get('has_basicfb'):
        if root.find('BasicFB') is None:
            issues.append(ValidationIssue(
                severity="error",
                file=str(file_path),
                message='Missing <BasicFB> element for Basic FB'
            ))

    if rules.get('has_fbnetwork'):
        if root.find('FBNetwork') is None:
            issues.append(ValidationIssue(
                severity="error",
                file=str(file_path),
                message='Missing <FBNetwork> element for Composite/CAT FB'
            ))

    if rules.get('has_service'):
        if root.find('Service') is None:
            issues.append(ValidationIssue(
                severity="error",
                file=str(file_path),
                message='Missing <Service> element for Adapter'
            ))

    # Check for Events/VarDeclarations with IDs
    interface_list = root.find('InterfaceList')
    if interface_list is not None:
        for event in interface_list.findall('.//Event'):
            if 'ID' not in event.attrib:
                issues.append(ValidationIssue(
                    severity="warning",
                    file=str(file_path),
                    message=f'Event "{event.attrib.get("Name", "unnamed")}" missing ID attribute'
                ))

        for var in interface_list.findall('.//VarDeclaration'):
            if 'ID' not in var.attrib and rules['root_element'] != 'DataType':
                issues.append(ValidationIssue(
                    severity="warning",
                    file=str(file_path),
                    message=f'VarDeclaration "{var.attrib.get("Name", "unnamed")}" missing ID attribute'
                ))


def validate_companion_files(main_file: Path, rules: dict, issues: List[ValidationIssue]) -> List[str]:
    """Check that required companion files exist."""
    files_checked = [str(main_file)]
    base_name = main_file.stem
    parent = main_file.parent

    for suffix in rules.get('companion_files', []):
        companion = parent / f"{base_name}{suffix}"
        if companion.exists():
            files_checked.append(str(companion))
        else:
            issues.append(ValidationIssue(
                severity="warning",
                file=str(companion),
                message=f'Expected companion file not found: {companion.name}'
            ))

    return files_checked


def main():
    parser = argparse.ArgumentParser(
        description="Validate EAE IEC 61499 block files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Block types:
    basic     - Basic FB with ECC and algorithms
    composite - Composite FB with FBNetwork
    cat       - CAT block with HMI
    adapter   - Adapter type
    datatype  - DataType (struct, enum, array, subrange)
        """
    )
    parser.add_argument("path", help="File or folder to validate")
    parser.add_argument("--type", "-t", choices=list(BLOCK_RULES.keys()),
                        help="Block type (auto-detected if not specified)")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")

    args = parser.parse_args()

    path = Path(args.path)

    if not path.exists():
        result = Result(
            success=False,
            message=f"Path does not exist: {path}",
            block_type="unknown",
            files_checked=[]
        )
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"Error: {result.message}", file=sys.stderr)
        return 1

    # Determine what to validate
    if path.is_dir():
        # Look for main file in folder
        fbt_files = list(path.glob("*.fbt"))
        cfg_files = list(path.glob("*.cfg"))

        if cfg_files:
            # CAT folder
            block_type = 'cat'
            main_file = next((f for f in fbt_files if not f.stem.endswith('_HMI')), fbt_files[0] if fbt_files else cfg_files[0])
        elif fbt_files:
            main_file = fbt_files[0]
            block_type = args.type or detect_block_type(main_file)
        else:
            result = Result(
                success=False,
                message=f"No .fbt or .cfg files found in {path}",
                block_type="unknown",
                files_checked=[]
            )
            if args.json:
                print(json.dumps(result.to_dict(), indent=2))
            else:
                print(f"Error: {result.message}", file=sys.stderr)
            return 1
    else:
        main_file = path
        block_type = args.type or detect_block_type(main_file)

    if not block_type:
        result = Result(
            success=False,
            message=f"Could not determine block type for {main_file}",
            block_type="unknown",
            files_checked=[]
        )
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"Error: {result.message}", file=sys.stderr)
        return 1

    rules = BLOCK_RULES[block_type]
    issues: List[ValidationIssue] = []

    # Validate main file
    validate_xml_structure(main_file, rules, issues)

    # Check companion files
    files_checked = validate_companion_files(main_file, rules, issues)

    # Check file extension
    if main_file.suffix != rules['extension']:
        issues.append(ValidationIssue(
            severity="error",
            file=str(main_file),
            message=f'Wrong file extension: expected {rules["extension"]}, got {main_file.suffix}'
        ))

    # Count errors vs warnings
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    success = len(errors) == 0

    result = Result(
        success=success,
        message=f"Validation {'passed' if success else 'failed'}: {len(errors)} error(s), {len(warnings)} warning(s)",
        block_type=block_type,
        files_checked=files_checked,
        issues=issues
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"Block type: {block_type}")
        print(f"Files checked: {len(files_checked)}")
        print()

        if issues:
            print("Issues found:")
            for issue in issues:
                prefix = "ERROR" if issue.severity == "error" else "WARN"
                print(f"  [{prefix}] {issue.file}: {issue.message}")
            print()

        print(result.message)

    return 0 if success else 10


if __name__ == "__main__":
    sys.exit(main())
