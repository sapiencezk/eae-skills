#!/usr/bin/env python3
"""
Validate EAE DataType files (.dt) against EAE rules and SE ADG naming conventions.

Validates:
- DOCTYPE references DataType.dtd (NOT LibraryElement.dtd)
- Standard is "1131-3" (IEC 61131-3, NOT 61499-2)
- NO GUID attribute present
- File extension is .dt (NOT .dtp)
- Located in DataType/ subfolder
- Hungarian notation naming (str*, e*, arr*, a*)
- Structure field naming conventions
- Enumeration value naming

Usage:
    python validate_datatype.py <file_or_directory>
    python validate_datatype.py IEC61499/DataType/strMotorData.dt
    python validate_datatype.py IEC61499/DataType/ --json

Exit codes:
    0  - All validations passed
    1  - Error running validation (file not found, parse error)
    10 - Validation warnings (non-blocking)
    11 - Validation errors found (blocking)
"""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class ValidationIssue:
    """A single validation issue."""
    severity: str  # ERROR, WARNING, INFO
    rule: str
    message: str
    file: str
    line: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of validating a DataType file."""
    file: str
    valid: bool
    datatype_name: Optional[str] = None
    datatype_kind: Optional[str] = None  # Structure, Enumeration, Array, Subrange
    issues: List[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'file': self.file,
            'valid': self.valid,
            'datatype_name': self.datatype_name,
            'datatype_kind': self.datatype_kind,
            'issues': [
                {
                    'severity': i.severity,
                    'rule': i.rule,
                    'message': i.message,
                    'line': i.line,
                    'suggestion': i.suggestion
                }
                for i in self.issues
            ]
        }


# Naming patterns based on SE ADG EIO0000004686.06
NAMING_PATTERNS = {
    'structure': (r'^str[A-Z][a-zA-Z0-9]*$', 'strPascalCase', 'str'),
    'enumeration': (r'^e[A-Z][a-zA-Z0-9]*$', 'ePascalCase', 'e'),
    'array': (r'^(arr|a)[A-Z][a-zA-Z0-9]*$', 'arrPascalCase or aPascalCase', 'arr'),
    'subrange': (r'^[A-Z][a-zA-Z0-9]*$', 'PascalCase', ''),  # No required prefix
}

FIELD_PATTERN = r'^[A-Z][a-zA-Z0-9]*$'  # PascalCase for interface fields


def validate_file_location(file_path: Path) -> List[ValidationIssue]:
    """Validate file is in correct location with correct extension."""
    issues = []

    # Check extension
    if file_path.suffix.lower() != '.dt':
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='FILE_EXTENSION',
            message=f'DataType file must have .dt extension, found: {file_path.suffix}',
            file=str(file_path),
            suggestion=f'Rename to {file_path.stem}.dt'
        ))

    # Check location (should be in DataType/ subfolder)
    parent_name = file_path.parent.name.lower()
    if parent_name != 'datatype':
        issues.append(ValidationIssue(
            severity='WARNING',
            rule='FILE_LOCATION',
            message=f'DataType should be in DataType/ subfolder, found in: {file_path.parent.name}/',
            file=str(file_path),
            suggestion='Move to IEC61499/DataType/ folder'
        ))

    return issues


def validate_doctype(content: str, file_path: str) -> List[ValidationIssue]:
    """Validate DOCTYPE declaration."""
    issues = []

    # Check for DOCTYPE
    doctype_match = re.search(r'<!DOCTYPE\s+(\w+)\s+SYSTEM\s+"([^"]+)"', content)

    if not doctype_match:
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='DOCTYPE_MISSING',
            message='DOCTYPE declaration not found',
            file=file_path,
            suggestion='Add: <!DOCTYPE DataType SYSTEM "../DataType.dtd">'
        ))
    else:
        root_element = doctype_match.group(1)
        dtd_path = doctype_match.group(2)

        if root_element != 'DataType':
            issues.append(ValidationIssue(
                severity='ERROR',
                rule='DOCTYPE_ROOT',
                message=f'DOCTYPE root element must be "DataType", found: {root_element}',
                file=file_path,
                suggestion='Use: <!DOCTYPE DataType SYSTEM "../DataType.dtd">'
            ))

        if 'DataType.dtd' not in dtd_path:
            issues.append(ValidationIssue(
                severity='ERROR',
                rule='DOCTYPE_DTD',
                message=f'DOCTYPE must reference DataType.dtd, found: {dtd_path}',
                file=file_path,
                suggestion='Use: <!DOCTYPE DataType SYSTEM "../DataType.dtd">'
            ))

    return issues


def validate_datatype_element(root: ET.Element, file_path: str) -> Tuple[Optional[str], Optional[str], List[ValidationIssue]]:
    """Validate DataType root element and return name, kind, and issues."""
    issues = []
    datatype_name = None
    datatype_kind = None

    # Check root element
    if root.tag != 'DataType':
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='ROOT_ELEMENT',
            message=f'Root element must be "DataType", found: {root.tag}',
            file=file_path
        ))
        return None, None, issues

    # Get name
    datatype_name = root.get('Name')
    if not datatype_name:
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='NAME_MISSING',
            message='DataType Name attribute is required',
            file=file_path
        ))

    # Check for GUID (should NOT exist)
    if root.get('GUID'):
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='NO_GUID',
            message='DataTypes must NOT have a GUID attribute',
            file=file_path,
            suggestion='Remove the GUID attribute from the DataType element'
        ))

    # Check for Namespace
    if not root.get('Namespace'):
        issues.append(ValidationIssue(
            severity='WARNING',
            rule='NAMESPACE_MISSING',
            message='Namespace attribute is recommended',
            file=file_path,
            suggestion='Add Namespace="YourLibrary" to the DataType element'
        ))

    # Check Identification Standard
    identification = root.find('Identification')
    if identification is not None:
        standard = identification.get('Standard')
        if standard != '1131-3':
            issues.append(ValidationIssue(
                severity='ERROR',
                rule='STANDARD',
                message=f'Standard must be "1131-3" (IEC 61131-3), found: {standard}',
                file=file_path,
                suggestion='Use: <Identification Standard="1131-3" />'
            ))
    else:
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='IDENTIFICATION_MISSING',
            message='Identification element is required',
            file=file_path,
            suggestion='Add: <Identification Standard="1131-3" />'
        ))

    # Determine DataType kind
    if root.find('StructuredType') is not None:
        datatype_kind = 'Structure'
    elif root.find('EnumeratedType') is not None:
        datatype_kind = 'Enumeration'
    elif root.find('ArrayType') is not None:
        datatype_kind = 'Array'
    elif root.find('SubrangeType') is not None:
        datatype_kind = 'Subrange'
    else:
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='TYPE_MISSING',
            message='DataType must contain StructuredType, EnumeratedType, ArrayType, or SubrangeType',
            file=file_path
        ))

    return datatype_name, datatype_kind, issues


def validate_naming(name: str, kind: str, file_path: str) -> List[ValidationIssue]:
    """Validate DataType name against SE ADG naming conventions."""
    issues = []

    if not name or not kind:
        return issues

    kind_lower = kind.lower()
    if kind_lower not in NAMING_PATTERNS:
        return issues

    pattern, convention, prefix = NAMING_PATTERNS[kind_lower]

    if not re.match(pattern, name):
        suggested_name = f'{prefix}{name}' if prefix and not name.startswith(prefix) else name
        # Ensure first letter after prefix is uppercase
        if prefix and len(suggested_name) > len(prefix):
            suggested_name = prefix + suggested_name[len(prefix)].upper() + suggested_name[len(prefix)+1:]

        issues.append(ValidationIssue(
            severity='WARNING',
            rule='NAMING_CONVENTION',
            message=f'{kind} name "{name}" should use {convention} convention',
            file=file_path,
            suggestion=f'Rename to "{suggested_name}"'
        ))

    return issues


def validate_structure_fields(root: ET.Element, file_path: str) -> List[ValidationIssue]:
    """Validate structure field naming."""
    issues = []

    structured_type = root.find('StructuredType')
    if structured_type is None:
        return issues

    for var in structured_type.findall('VarDeclaration'):
        field_name = var.get('Name')
        if field_name and not re.match(FIELD_PATTERN, field_name):
            # Only warn if it's not camelCase (which is allowed for internal fields)
            if not re.match(r'^[a-z][a-zA-Z0-9]*$', field_name):
                issues.append(ValidationIssue(
                    severity='INFO',
                    rule='FIELD_NAMING',
                    message=f'Field "{field_name}" should use PascalCase (interface) or camelCase (internal)',
                    file=file_path,
                    suggestion=f'Use PascalCase for interface fields, camelCase for internal fields'
                ))

        # Check for Comment
        if not var.get('Comment'):
            issues.append(ValidationIssue(
                severity='INFO',
                rule='FIELD_COMMENT',
                message=f'Field "{field_name}" is missing a Comment attribute',
                file=file_path,
                suggestion='Add Comment="Description of this field"'
            ))

    return issues


def validate_enumeration_values(root: ET.Element, file_path: str) -> List[ValidationIssue]:
    """Validate enumeration values."""
    issues = []

    enum_type = root.find('EnumeratedType')
    if enum_type is None:
        return issues

    values = enum_type.findall('EnumeratedValue')

    # Check for empty enum
    if not values:
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='ENUM_EMPTY',
            message='Enumeration has no values defined',
            file=file_path,
            suggestion='Add EnumeratedValue elements'
        ))
        return issues

    # Check for generic names
    generic_pattern = r'^(State|Value|Item|Option)\d+$'
    seen_names = set()

    for value in values:
        value_name = value.get('Name')
        if value_name:
            # Check for duplicates
            if value_name in seen_names:
                issues.append(ValidationIssue(
                    severity='ERROR',
                    rule='ENUM_DUPLICATE',
                    message=f'Duplicate enumeration value: {value_name}',
                    file=file_path
                ))
            seen_names.add(value_name)

            # Check for generic names
            if re.match(generic_pattern, value_name):
                issues.append(ValidationIssue(
                    severity='WARNING',
                    rule='ENUM_GENERIC_NAME',
                    message=f'Enumeration value "{value_name}" is generic',
                    file=file_path,
                    suggestion='Use meaningful, descriptive names like "Idle", "Running", "Faulted"'
                ))

    # Warn if too many values
    if len(values) > 20:
        issues.append(ValidationIssue(
            severity='INFO',
            rule='ENUM_SIZE',
            message=f'Enumeration has {len(values)} values (>20)',
            file=file_path,
            suggestion='Consider splitting into multiple enumerations or using a different approach'
        ))

    return issues


def validate_array(root: ET.Element, file_path: str) -> List[ValidationIssue]:
    """Validate array type."""
    issues = []

    array_type = root.find('ArrayType')
    if array_type is None:
        return issues

    # Check BaseType
    base_type = array_type.get('BaseType')
    if not base_type:
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='ARRAY_BASETYPE',
            message='ArrayType must have a BaseType attribute',
            file=file_path
        ))

    # Check Subrange
    subrange = array_type.find('Subrange')
    if subrange is None:
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='ARRAY_SUBRANGE',
            message='ArrayType must have a Subrange element',
            file=file_path
        ))
    else:
        try:
            lower = int(subrange.get('LowerLimit', '0'))
            upper = int(subrange.get('UpperLimit', '0'))

            if lower > upper:
                issues.append(ValidationIssue(
                    severity='ERROR',
                    rule='ARRAY_BOUNDS',
                    message=f'LowerLimit ({lower}) must be <= UpperLimit ({upper})',
                    file=file_path
                ))

            if lower == upper:
                issues.append(ValidationIssue(
                    severity='WARNING',
                    rule='ARRAY_SINGLE',
                    message=f'Array has only 1 element (LowerLimit={lower}, UpperLimit={upper})',
                    file=file_path
                ))

            size = upper - lower + 1
            if size > 1000:
                issues.append(ValidationIssue(
                    severity='WARNING',
                    rule='ARRAY_SIZE',
                    message=f'Array size is very large ({size} elements)',
                    file=file_path,
                    suggestion='Consider chunking or using a different data structure'
                ))
        except (ValueError, TypeError):
            issues.append(ValidationIssue(
                severity='ERROR',
                rule='ARRAY_LIMITS',
                message='Subrange LowerLimit and UpperLimit must be integers',
                file=file_path
            ))

    return issues


def validate_subrange(root: ET.Element, file_path: str) -> List[ValidationIssue]:
    """Validate subrange type."""
    issues = []

    subrange_type = root.find('SubrangeType')
    if subrange_type is None:
        return issues

    # Check BaseType
    base_type = subrange_type.get('BaseType')
    if not base_type:
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='SUBRANGE_BASETYPE',
            message='SubrangeType must have a BaseType attribute',
            file=file_path
        ))
    elif base_type not in ['INT', 'DINT', 'SINT', 'LINT', 'UINT', 'UDINT', 'USINT', 'ULINT', 'REAL', 'LREAL']:
        issues.append(ValidationIssue(
            severity='WARNING',
            rule='SUBRANGE_BASETYPE_NUMERIC',
            message=f'SubrangeType BaseType "{base_type}" may not support range constraints',
            file=file_path,
            suggestion='Use numeric types like INT, DINT, REAL'
        ))

    # Check Subrange
    subrange = subrange_type.find('Subrange')
    if subrange is not None:
        try:
            lower = float(subrange.get('LowerLimit', '0'))
            upper = float(subrange.get('UpperLimit', '0'))

            if lower >= upper:
                issues.append(ValidationIssue(
                    severity='ERROR',
                    rule='SUBRANGE_BOUNDS',
                    message=f'LowerLimit ({lower}) must be < UpperLimit ({upper})',
                    file=file_path
                ))

            # Check InitialValue
            initial = subrange_type.get('InitialValue')
            if initial:
                try:
                    initial_val = float(initial)
                    if initial_val < lower or initial_val > upper:
                        issues.append(ValidationIssue(
                            severity='ERROR',
                            rule='SUBRANGE_INITIAL',
                            message=f'InitialValue ({initial_val}) is outside range [{lower}, {upper}]',
                            file=file_path
                        ))
                except ValueError:
                    pass
        except (ValueError, TypeError):
            pass

    return issues


def validate_datatype_file(file_path: Path) -> ValidationResult:
    """Validate a single DataType file."""
    result = ValidationResult(file=str(file_path), valid=True)

    # Check file exists
    if not file_path.exists():
        result.valid = False
        result.issues.append(ValidationIssue(
            severity='ERROR',
            rule='FILE_NOT_FOUND',
            message=f'File not found: {file_path}',
            file=str(file_path)
        ))
        return result

    # Check file location and extension
    result.issues.extend(validate_file_location(file_path))

    # Read file content
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        result.valid = False
        result.issues.append(ValidationIssue(
            severity='ERROR',
            rule='FILE_READ_ERROR',
            message=f'Could not read file: {e}',
            file=str(file_path)
        ))
        return result

    # Validate DOCTYPE
    result.issues.extend(validate_doctype(content, str(file_path)))

    # Parse XML
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        result.valid = False
        result.issues.append(ValidationIssue(
            severity='ERROR',
            rule='XML_PARSE_ERROR',
            message=f'XML parse error: {e}',
            file=str(file_path)
        ))
        return result

    # Validate DataType element
    name, kind, element_issues = validate_datatype_element(root, str(file_path))
    result.datatype_name = name
    result.datatype_kind = kind
    result.issues.extend(element_issues)

    # Validate naming convention
    if name and kind:
        result.issues.extend(validate_naming(name, kind, str(file_path)))

    # Validate type-specific rules
    if kind == 'Structure':
        result.issues.extend(validate_structure_fields(root, str(file_path)))
    elif kind == 'Enumeration':
        result.issues.extend(validate_enumeration_values(root, str(file_path)))
    elif kind == 'Array':
        result.issues.extend(validate_array(root, str(file_path)))
    elif kind == 'Subrange':
        result.issues.extend(validate_subrange(root, str(file_path)))

    # Determine overall validity
    error_count = sum(1 for i in result.issues if i.severity == 'ERROR')
    result.valid = error_count == 0

    return result


def find_datatype_files(path: Path) -> List[Path]:
    """Find all .dt files in path (file or directory)."""
    if path.is_file():
        return [path] if path.suffix.lower() == '.dt' else []

    if path.is_dir():
        return list(path.rglob('*.dt'))

    return []


def main():
    parser = argparse.ArgumentParser(
        description='Validate EAE DataType files against EAE rules and SE ADG naming conventions'
    )
    parser.add_argument(
        'path',
        type=str,
        help='File or directory to validate'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Treat warnings as errors'
    )

    args = parser.parse_args()
    path = Path(args.path)

    # Find files to validate
    files = find_datatype_files(path)

    if not files:
        if args.json:
            print(json.dumps({'error': 'No .dt files found', 'path': str(path)}))
        else:
            print(f'No .dt files found in: {path}')
        sys.exit(1)

    # Validate all files
    results = [validate_datatype_file(f) for f in files]

    # Count issues
    total_errors = sum(
        sum(1 for i in r.issues if i.severity == 'ERROR')
        for r in results
    )
    total_warnings = sum(
        sum(1 for i in r.issues if i.severity == 'WARNING')
        for r in results
    )
    total_info = sum(
        sum(1 for i in r.issues if i.severity == 'INFO')
        for r in results
    )

    # Output results
    if args.json:
        output = {
            'files_validated': len(results),
            'total_errors': total_errors,
            'total_warnings': total_warnings,
            'total_info': total_info,
            'results': [r.to_dict() for r in results]
        }
        print(json.dumps(output, indent=2))
    else:
        print(f'Validating DataType files in: {path}')
        print(f'Found {len(files)} file(s)')
        print()

        for result in results:
            status = '✓' if result.valid else '✗'
            kind_str = f' ({result.datatype_kind})' if result.datatype_kind else ''
            name_str = f' "{result.datatype_name}"' if result.datatype_name else ''
            print(f'{status} {result.file}{name_str}{kind_str}')

            for issue in result.issues:
                prefix = {'ERROR': '  ✗', 'WARNING': '  ⚠', 'INFO': '  ℹ'}[issue.severity]
                print(f'{prefix} [{issue.rule}] {issue.message}')
                if issue.suggestion:
                    print(f'      Suggestion: {issue.suggestion}')

            if result.issues:
                print()

        print('-' * 60)
        print(f'Summary: {total_errors} errors, {total_warnings} warnings, {total_info} info')

        valid_count = sum(1 for r in results if r.valid)
        print(f'Valid: {valid_count}/{len(results)} files')

    # Determine exit code
    if total_errors > 0:
        sys.exit(11)  # Validation errors
    elif total_warnings > 0 and args.strict:
        sys.exit(11)  # Warnings treated as errors
    elif total_warnings > 0:
        sys.exit(10)  # Warnings only
    else:
        sys.exit(0)   # Success


if __name__ == '__main__':
    main()
