#!/usr/bin/env python3
"""
Validate EAE Adapter files (.adp) against EAE rules and SE ADG naming conventions.

Validates:
- Root element is AdapterType (NOT FBType)
- Standard is "61499-1" (IEC 61499-1, NOT 61499-2)
- File extension is .adp (NOT .fbt)
- IPascalCase naming with uppercase 'I' prefix
- GUID is present (required for Adapters)
- Service element presence
- ServiceSequence parameter consistency

Usage:
    python validate_adapter.py <file_or_directory>
    python validate_adapter.py IEC61499/IMotorControl.adp
    python validate_adapter.py IEC61499/ --json

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
from typing import Dict, List, Optional, Set, Tuple


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
    """Result of validating an Adapter file."""
    file: str
    valid: bool
    adapter_name: Optional[str] = None
    socket_events: int = 0
    plug_events: int = 0
    socket_vars: int = 0
    plug_vars: int = 0
    issues: List[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'file': self.file,
            'valid': self.valid,
            'adapter_name': self.adapter_name,
            'socket_events': self.socket_events,
            'plug_events': self.plug_events,
            'socket_vars': self.socket_vars,
            'plug_vars': self.plug_vars,
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


# Naming pattern for Adapters: IPascalCase (uppercase I prefix)
ADAPTER_NAME_PATTERN = r'^I[A-Z][a-zA-Z0-9]*$'

# Event naming pattern: UPPER_SNAKE_CASE or PascalCase
EVENT_PATTERN = r'^([A-Z][A-Z0-9_]*|[A-Z][a-zA-Z0-9]*)$'

# Variable naming pattern: PascalCase for interface
VAR_PATTERN = r'^[A-Z][a-zA-Z0-9]*$'

# GUID pattern
GUID_PATTERN = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'


def validate_file_extension(file_path: Path) -> List[ValidationIssue]:
    """Validate file has correct extension."""
    issues = []

    if file_path.suffix.lower() != '.adp':
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='FILE_EXTENSION',
            message=f'Adapter file must have .adp extension, found: {file_path.suffix}',
            file=str(file_path),
            suggestion=f'Rename to {file_path.stem}.adp'
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
            suggestion='Add: <!DOCTYPE AdapterType SYSTEM "LibraryElement.dtd">'
        ))
    else:
        root_element = doctype_match.group(1)

        if root_element != 'AdapterType':
            issues.append(ValidationIssue(
                severity='ERROR',
                rule='DOCTYPE_ROOT',
                message=f'DOCTYPE root element must be "AdapterType", found: {root_element}',
                file=file_path,
                suggestion='Use: <!DOCTYPE AdapterType SYSTEM "LibraryElement.dtd">'
            ))

    return issues


def validate_adapter_element(root: ET.Element, file_path: str) -> Tuple[Optional[str], List[ValidationIssue]]:
    """Validate AdapterType root element and return name and issues."""
    issues = []
    adapter_name = None

    # Check root element
    if root.tag != 'AdapterType':
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='ROOT_ELEMENT',
            message=f'Root element must be "AdapterType", found: {root.tag}',
            file=file_path,
            suggestion='Adapters use <AdapterType>, not <FBType>'
        ))
        return None, issues

    # Get name
    adapter_name = root.get('Name')
    if not adapter_name:
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='NAME_MISSING',
            message='AdapterType Name attribute is required',
            file=file_path
        ))

    # Check for GUID (required for Adapters)
    guid = root.get('GUID')
    if not guid:
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='GUID_MISSING',
            message='GUID attribute is required for Adapters',
            file=file_path,
            suggestion='Generate a GUID using: python ../eae-skill-router/scripts/generate_ids.py --guid 1'
        ))
    elif not re.match(GUID_PATTERN, guid):
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='GUID_FORMAT',
            message=f'GUID format is invalid: {guid}',
            file=file_path,
            suggestion='Use format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
        ))

    # Check for Namespace
    if not root.get('Namespace'):
        issues.append(ValidationIssue(
            severity='WARNING',
            rule='NAMESPACE_MISSING',
            message='Namespace attribute is recommended',
            file=file_path,
            suggestion='Add Namespace="YourLibrary" to the AdapterType element'
        ))

    # Check Identification Standard
    identification = root.find('Identification')
    if identification is not None:
        standard = identification.get('Standard')
        if standard != '61499-1':
            issues.append(ValidationIssue(
                severity='ERROR',
                rule='STANDARD',
                message=f'Standard must be "61499-1" (IEC 61499-1 for Adapters), found: {standard}',
                file=file_path,
                suggestion='Use: <Identification Standard="61499-1" /> (Adapters use 61499-1, not 61499-2)'
            ))
    else:
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='IDENTIFICATION_MISSING',
            message='Identification element is required',
            file=file_path,
            suggestion='Add: <Identification Standard="61499-1" />'
        ))

    return adapter_name, issues


def validate_naming(name: str, file_path: str) -> List[ValidationIssue]:
    """Validate Adapter name against SE ADG naming conventions."""
    issues = []

    if not name:
        return issues

    if not re.match(ADAPTER_NAME_PATTERN, name):
        # Generate suggested name
        suggested = name
        if not name.startswith('I'):
            suggested = 'I' + name
        if len(suggested) > 1 and suggested[1].islower():
            suggested = suggested[0] + suggested[1].upper() + suggested[2:]

        issues.append(ValidationIssue(
            severity='WARNING',
            rule='NAMING_CONVENTION',
            message=f'Adapter name "{name}" should use IPascalCase (uppercase I prefix)',
            file=file_path,
            suggestion=f'Rename to "{suggested}"'
        ))

    # Check for lowercase 'i' prefix
    if name.startswith('i') and len(name) > 1 and name[1].isupper():
        issues.append(ValidationIssue(
            severity='WARNING',
            rule='NAMING_LOWERCASE_I',
            message=f'Adapter name "{name}" uses lowercase "i" prefix',
            file=file_path,
            suggestion=f'Use uppercase "I": "I{name[1:]}"'
        ))

    return issues


def validate_service_interface(root: ET.Element, file_path: str) -> Tuple[int, int, int, int, List[ValidationIssue]]:
    """Validate Service Interface (socket/plug) structure."""
    issues = []
    socket_events = 0
    plug_events = 0
    socket_vars = 0
    plug_vars = 0

    # Find InterfaceList (contains socket interface)
    interface_list = root.find('InterfaceList')
    if interface_list is None:
        issues.append(ValidationIssue(
            severity='ERROR',
            rule='INTERFACE_MISSING',
            message='InterfaceList element is required',
            file=file_path
        ))
        return 0, 0, 0, 0, issues

    # Check Socket Interface (defined in InterfaceList)
    # Socket: EventInputs become outputs, EventOutputs become inputs when used as plug
    event_inputs = interface_list.find('EventInputs')
    event_outputs = interface_list.find('EventOutputs')
    input_vars = interface_list.find('InputVars')
    output_vars = interface_list.find('OutputVars')

    if event_inputs is not None:
        socket_events += len(event_inputs.findall('Event'))
    if event_outputs is not None:
        plug_events += len(event_outputs.findall('Event'))
    if input_vars is not None:
        socket_vars += len(input_vars.findall('VarDeclaration'))
    if output_vars is not None:
        plug_vars += len(output_vars.findall('VarDeclaration'))

    # Check for Service element
    service = root.find('Service')
    if service is None:
        issues.append(ValidationIssue(
            severity='WARNING',
            rule='SERVICE_MISSING',
            message='Service element is recommended for defining adapter behavior',
            file=file_path,
            suggestion='Add a Service element with ServiceSequence to define adapter protocol'
        ))
    else:
        # Validate Service has ServiceSequence
        service_sequences = service.findall('.//ServiceSequence')
        if not service_sequences:
            issues.append(ValidationIssue(
                severity='INFO',
                rule='SERVICE_SEQUENCE_MISSING',
                message='Service element has no ServiceSequence definitions',
                file=file_path,
                suggestion='Add ServiceSequence elements to define the adapter protocol'
            ))
        else:
            # Validate ServiceSequence parameters reference valid events
            all_events = set()
            if event_inputs is not None:
                all_events.update(e.get('Name', '') for e in event_inputs.findall('Event'))
            if event_outputs is not None:
                all_events.update(e.get('Name', '') for e in event_outputs.findall('Event'))

            for seq in service_sequences:
                for transaction in seq.findall('.//ServiceTransaction'):
                    # Check InputPrimitive
                    input_prim = transaction.find('InputPrimitive')
                    if input_prim is not None:
                        event = input_prim.get('Event')
                        if event and event not in all_events:
                            issues.append(ValidationIssue(
                                severity='WARNING',
                                rule='SERVICE_EVENT_UNKNOWN',
                                message=f'ServiceTransaction references unknown event: {event}',
                                file=file_path
                            ))

                    # Check OutputPrimitive
                    output_prim = transaction.find('OutputPrimitive')
                    if output_prim is not None:
                        event = output_prim.get('Event')
                        if event and event not in all_events:
                            issues.append(ValidationIssue(
                                severity='WARNING',
                                rule='SERVICE_EVENT_UNKNOWN',
                                message=f'ServiceTransaction references unknown event: {event}',
                                file=file_path
                            ))

    # Validate event and variable naming
    for event_container in [event_inputs, event_outputs]:
        if event_container is not None:
            for event in event_container.findall('Event'):
                event_name = event.get('Name', '')
                if event_name and not re.match(EVENT_PATTERN, event_name):
                    issues.append(ValidationIssue(
                        severity='INFO',
                        rule='EVENT_NAMING',
                        message=f'Event "{event_name}" should use UPPER_SNAKE_CASE or PascalCase',
                        file=file_path
                    ))

    for var_container in [input_vars, output_vars]:
        if var_container is not None:
            for var in var_container.findall('VarDeclaration'):
                var_name = var.get('Name', '')
                if var_name and not re.match(VAR_PATTERN, var_name):
                    issues.append(ValidationIssue(
                        severity='INFO',
                        rule='VAR_NAMING',
                        message=f'Variable "{var_name}" should use PascalCase',
                        file=file_path
                    ))

    # Check for WITH associations
    for event_container in [event_inputs, event_outputs]:
        if event_container is not None:
            for event in event_container.findall('Event'):
                withs = event.findall('With')
                if not withs:
                    event_name = event.get('Name', '')
                    issues.append(ValidationIssue(
                        severity='INFO',
                        rule='EVENT_NO_WITH',
                        message=f'Event "{event_name}" has no WITH associations',
                        file=file_path,
                        suggestion='Consider adding WITH elements to associate data with events'
                    ))

    return socket_events, plug_events, socket_vars, plug_vars, issues


def validate_adapter_file(file_path: Path) -> ValidationResult:
    """Validate a single Adapter file."""
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

    # Check file extension
    result.issues.extend(validate_file_extension(file_path))

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

    # Validate AdapterType element
    name, element_issues = validate_adapter_element(root, str(file_path))
    result.adapter_name = name
    result.issues.extend(element_issues)

    # Validate naming convention
    if name:
        result.issues.extend(validate_naming(name, str(file_path)))

    # Validate service interface
    socket_e, plug_e, socket_v, plug_v, interface_issues = validate_service_interface(root, str(file_path))
    result.socket_events = socket_e
    result.plug_events = plug_e
    result.socket_vars = socket_v
    result.plug_vars = plug_v
    result.issues.extend(interface_issues)

    # Determine overall validity
    error_count = sum(1 for i in result.issues if i.severity == 'ERROR')
    result.valid = error_count == 0

    return result


def find_adapter_files(path: Path) -> List[Path]:
    """Find all .adp files in path (file or directory)."""
    if path.is_file():
        return [path] if path.suffix.lower() == '.adp' else []

    if path.is_dir():
        return list(path.rglob('*.adp'))

    return []


def main():
    parser = argparse.ArgumentParser(
        description='Validate EAE Adapter files against EAE rules and SE ADG naming conventions'
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
    files = find_adapter_files(path)

    if not files:
        if args.json:
            print(json.dumps({'error': 'No .adp files found', 'path': str(path)}))
        else:
            print(f'No .adp files found in: {path}')
        sys.exit(1)

    # Validate all files
    results = [validate_adapter_file(f) for f in files]

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
        print(f'Validating Adapter files in: {path}')
        print(f'Found {len(files)} file(s)')
        print()

        for result in results:
            status = '✓' if result.valid else '✗'
            name_str = f' "{result.adapter_name}"' if result.adapter_name else ''
            interface_str = f' [Socket: {result.socket_events}E/{result.socket_vars}V, Plug: {result.plug_events}E/{result.plug_vars}V]'
            print(f'{status} {result.file}{name_str}{interface_str}')

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
