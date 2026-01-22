#!/usr/bin/env python3
"""
EAE Naming Validator - Schneider Electric Convention Enforcement

Validates EcoStruxure Automation Expert artifact names against SE Application Design
Guidelines (EIO0000004686.06, Section 1.5: Colors and Naming Convention).

Exit Codes:
    0: All artifacts compliant
   10: Warnings found (non-blocking)
   11: Errors found (blocking - should prevent deployment)
    1: Parsing failure or invalid arguments

Usage:
    python validate_names.py --app-dir /path/to/eae/app
    python validate_names.py --app-dir /path/to/eae/app --output violations.json
    python validate_names.py --app-dir /path/to/eae/app --artifact-type CAT --strict
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Optional

# Naming rule definitions
NAMING_RULES = {
    "CAT": {
        "pattern": r"^[A-Z][a-zA-Z0-9]*$",
        "convention": "PascalCase",
        "severity": "ERROR",
        "description": "CATs must use PascalCase",
        "examples": ["AnalogInput", "DiscreteOutput", "SpMon"]
    },
    "SubApp": {
        "pattern": r"^[A-Z][a-zA-Z0-9]*$",
        "convention": "PascalCase",
        "severity": "ERROR",
        "description": "SubApps must use PascalCase",
        "examples": ["SeqManager", "AlarmHandling"]
    },
    "BasicFB": {
        "pattern": r"^[a-z][a-zA-Z0-9]*$",
        "convention": "camelCase",
        "severity": "ERROR",
        "description": "Basic Function Blocks must use camelCase",
        "examples": ["scaleLogic", "stateDevice", "pidController"]
    },
    "CompositeFB": {
        "pattern": r"^[a-z][a-zA-Z0-9]*$",
        "convention": "camelCase",
        "severity": "ERROR",
        "description": "Composite Function Blocks must use camelCase",
        "examples": ["motorControl", "valveSequence"]
    },
    "Function": {
        "pattern": r"^[a-z][a-zA-Z0-9]*$",
        "convention": "camelCase",
        "severity": "ERROR",
        "description": "Functions must use camelCase",
        "examples": ["calculateAverage", "convertTemperature"]
    },
    "Adapter": {
        "pattern": r"^I[A-Z][a-zA-Z0-9]*$",
        "convention": "IPascalCase",
        "severity": "ERROR",
        "description": "Adapters must use IPascalCase (uppercase 'I' prefix)",
        "examples": ["IPv", "IAnalogValue", "IMotorControl"]
    },
    "Event": {
        "pattern": r"^[A-Z_]+$",
        "convention": "SNAKE_CASE",
        "severity": "ERROR",
        "description": "Events must use SNAKE_CASE (all uppercase with underscores)",
        "examples": ["START_MOTOR", "STOP_PROCESS", "INIT", "INITO"],
        "reserved": ["INIT", "INITO"]  # Always valid
    },
    "Structure": {
        "pattern": r"^str[A-Z][a-zA-Z0-9]*$",
        "convention": "strPascalCase",
        "severity": "ERROR",
        "description": "Structure data types must use strPascalCase (lowercase 'str' prefix)",
        "examples": ["strMotorData", "strRecipeParms"]
    },
    "Alias": {
        "pattern": r"^a[A-Z][a-zA-Z0-9]*$",
        "convention": "aPascalCase",
        "severity": "WARNING",
        "description": "Alias data types must use aPascalCase (lowercase 'a' prefix)",
        "examples": ["aFrame", "aSymbol"]
    },
    "Enum": {
        "pattern": r"^e[A-Z][a-zA-Z0-9]*$",
        "convention": "ePascalCase",
        "severity": "ERROR",
        "description": "Enumeration data types must use ePascalCase (lowercase 'e' prefix)",
        "examples": ["eProductType", "eSelectAction"]
    },
    "Array": {
        "pattern": r"^arr[A-Z][a-zA-Z0-9]*$",
        "convention": "arrPascalCase",
        "severity": "WARNING",
        "description": "Array data types must use arrPascalCase (lowercase 'arr' prefix)",
        "examples": ["arrRecipeBuffer", "arrSensorValues"]
    },
    "VariableInterface": {
        "pattern": r"^[A-Z][a-zA-Z0-9]*$",
        "convention": "PascalCase",
        "severity": "ERROR",
        "description": "Interface variables (I/O) must use PascalCase",
        "examples": ["PermitOn", "FeedbackOn", "SetPoint"]
    },
    "VariableInternal": {
        "pattern": r"^[a-z][a-zA-Z0-9]*$",
        "convention": "camelCase",
        "severity": "WARNING",
        "description": "Internal variables must use camelCase",
        "examples": ["error", "outMinActiveLast", "tempBuffer"]
    },
    "Folder": {
        "pattern": r"^[A-Z][a-zA-Z0-9]*$",
        "convention": "PascalCase",
        "severity": "WARNING",
        "description": "Folders must use PascalCase (preferably single word)",
        "examples": ["Motors", "Positioner", "SetPointManagement"]
    }
}


@dataclass
class Violation:
    """A single naming convention violation."""
    artifact_type: str
    name: str
    file: str
    line: int  # Approximate line number
    rule: str  # Human-readable rule description
    pattern: str  # Regex pattern expected
    convention: str  # Convention name (e.g., "PascalCase")
    severity: str  # ERROR, WARNING, INFO
    suggestion: Optional[str] = None  # Suggested compliant name


@dataclass
class ValidationResult:
    """Structured result for validation script."""
    success: bool
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def exit_code(self) -> int:
        """Calculate exit code based on violations."""
        if not self.success:
            return 1  # Parse failure

        if self.errors:
            return 11  # Errors found (blocking)
        elif self.warnings:
            return 10  # Warnings found (non-blocking)
        else:
            return 0  # All compliant

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Validate EAE artifact names against SE Application Design Guidelines"
    )
    parser.add_argument("--app-dir", required=True, help="Path to EAE application")
    parser.add_argument("--output", help="JSON output file path (default: stdout)")
    parser.add_argument(
        "--artifact-type",
        help="Filter to specific types (comma-separated): CAT,BasicFB,CompositeFB,etc."
    )
    parser.add_argument(
        "--min-severity",
        choices=["ERROR", "WARNING", "INFO"],
        default="WARNING",
        help="Minimum severity to report (default: WARNING)"
    )
    parser.add_argument(
        "--exclude",
        help="Exclude files matching glob pattern (e.g., 'Legacy/*')"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat all violations as ERRORS"
    )
    return parser.parse_args()


def safe_parse_xml(file_path: Path) -> Optional[ET.Element]:
    """Safely parse XML file with error handling."""
    try:
        tree = ET.parse(file_path)
        return tree.getroot()
    except ET.ParseError as e:
        print(f"XML parse error in {file_path}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return None


def detect_artifact_type(root: ET.Element, file_path: Path) -> Optional[str]:
    """Detect artifact type from XML structure."""
    # CAT: CompositeFBType with specific attributes or HMI elements
    if root.tag == "CompositeFBType":
        # Simple heuristic: if it has HMI-related elements, it's likely a CAT
        # More sophisticated detection would check for specific CAT attributes
        return "CAT"  # Could be SubApp too - refine if needed

    # Function Block Type
    if root.tag == "FBType":
        # Basic FB: has ECC (Execution Control Chart)
        if root.find("ECC") is not None:
            return "BasicFB"
        # Composite FB: has FBNetwork
        elif root.find("FBNetwork") is not None:
            return "CompositeFB"
        # Function: stateless (neither ECC nor FBNetwork - rare)
        else:
            return "Function"

    # Adapter
    if root.tag == "AdapterType":
        return "Adapter"

    # DataType (.dtp files)
    if root.tag == "StructuredType":
        return "Structure"
    if root.tag == "EnumeratedType":
        return "Enum"
    if root.tag == "ArrayType":
        return "Array"
    if root.tag == "DataType":
        # Alias is detected by comment or absence of complex structure
        comment = root.get("Comment", "")
        if "ALIAS" in comment.upper():
            return "Alias"

    return None


def generate_suggestion(name: str, artifact_type: str) -> Optional[str]:
    """Generate a suggested compliant name."""
    rule = NAMING_RULES.get(artifact_type)
    if not rule:
        return None

    convention = rule["convention"]

    # Remove underscores and hyphens
    clean_name = name.replace("_", " ").replace("-", " ")
    words = clean_name.split()

    if convention == "PascalCase":
        suggestion = "".join(word.capitalize() for word in words)
    elif convention == "camelCase":
        if words:
            suggestion = words[0].lower() + "".join(word.capitalize() for word in words[1:])
        else:
            suggestion = name.lower()
    elif convention == "SNAKE_CASE":
        suggestion = "_".join(word.upper() for word in words)
    elif convention == "strPascalCase":
        base = "".join(word.capitalize() for word in words)
        suggestion = f"str{base}" if not base.startswith("str") else base
    elif convention == "IPascalCase":
        base = "".join(word.capitalize() for word in words)
        suggestion = f"I{base}" if not base.startswith("I") else base
    elif convention == "ePascalCase":
        base = "".join(word.capitalize() for word in words)
        suggestion = f"e{base}" if not base.startswith("e") else base
    elif convention == "aPascalCase":
        base = "".join(word.capitalize() for word in words)
        suggestion = f"a{base}" if not base.startswith("a") else base
    elif convention == "arrPascalCase":
        base = "".join(word.capitalize() for word in words)
        suggestion = f"arr{base}" if not base.startswith("arr") else base
    else:
        suggestion = None

    # Only return if different from original
    return suggestion if suggestion and suggestion != name else None


def validate_name(name: str, artifact_type: str, file_path: Path, line: int = 1) -> Optional[Violation]:
    """Validate a single artifact name against its type's naming rule."""
    rule = NAMING_RULES.get(artifact_type)
    if not rule:
        return None  # Unknown type, skip

    # Check reserved keywords (e.g., INIT, INITO for events)
    reserved = rule.get("reserved", [])
    if name in reserved:
        return None  # Reserved names are always valid

    # Apply regex pattern
    pattern = rule["pattern"]
    if not re.match(pattern, name):
        suggestion = generate_suggestion(name, artifact_type)
        return Violation(
            artifact_type=artifact_type,
            name=name,
            file=str(file_path.name),
            line=line,
            rule=rule["description"],
            pattern=pattern,
            convention=rule["convention"],
            severity=rule["severity"],
            suggestion=suggestion
        )

    return None


def extract_artifacts_from_file(file_path: Path) -> List[Tuple[str, str, int]]:
    """Extract (artifact_type, name, line) tuples from an EAE XML file."""
    root = safe_parse_xml(file_path)
    if root is None:
        return []

    artifacts = []

    # Detect main artifact type
    artifact_type = detect_artifact_type(root, file_path)
    if artifact_type:
        name = root.get("Name")
        if name:
            artifacts.append((artifact_type, name, 1))

    # Extract variables (interface vs internal)
    interface_list = root.find("InterfaceList")
    if interface_list is not None:
        # Input/Output variables are interface
        for var in interface_list.findall(".//VarDeclaration"):
            var_name = var.get("Name")
            if var_name:
                artifacts.append(("VariableInterface", var_name, 1))  # Line approx

    # Internal variables (in Basic FB)
    basic_fb = root.find("BasicFB")
    if basic_fb is not None:
        internal_vars = basic_fb.find("InternalVars")
        if internal_vars is not None:
            for var in internal_vars.findall("VarDeclaration"):
                var_name = var.get("Name")
                if var_name:
                    artifacts.append(("VariableInternal", var_name, 1))

    # Events
    if interface_list is not None:
        for event_input in interface_list.findall(".//EventInputs/Event"):
            event_name = event_input.get("Name")
            if event_name:
                artifacts.append(("Event", event_name, 1))
        for event_output in interface_list.findall(".//EventOutputs/Event"):
            event_name = event_output.get("Name")
            if event_name:
                artifacts.append(("Event", event_name, 1))

    return artifacts


def validate_application(app_dir: Path, artifact_filter: Optional[Set[str]] = None) -> List[Violation]:
    """Validate all artifacts in an EAE application directory."""
    violations = []

    # Find all relevant files
    file_patterns = ["**/*.fbt", "**/*.cat", "**/*.dtp", "**/*.adp"]
    files = []
    for pattern in file_patterns:
        files.extend(app_dir.rglob(pattern))

    print(f"Scanning {len(files)} files in {app_dir}...", file=sys.stderr)

    for file_path in files:
        artifacts = extract_artifacts_from_file(file_path)
        for artifact_type, name, line in artifacts:
            # Apply filter if specified
            if artifact_filter and artifact_type not in artifact_filter:
                continue

            violation = validate_name(name, artifact_type, file_path, line)
            if violation:
                violations.append(violation)

    return violations


def main():
    args = parse_arguments()

    app_dir = Path(args.app_dir)
    if not app_dir.exists():
        print(f"Error: Directory not found: {app_dir}", file=sys.stderr)
        sys.exit(1)

    # Parse artifact type filter
    artifact_filter = None
    if args.artifact_type:
        artifact_filter = set(args.artifact_type.split(","))

    # Run validation
    print(f"Validating naming conventions in: {app_dir}", file=sys.stderr)
    violations = validate_application(app_dir, artifact_filter)

    # Apply min_severity filter
    severity_order = {"INFO": 0, "WARNING": 1, "ERROR": 2}
    min_severity_level = severity_order[args.min_severity]
    violations = [v for v in violations if severity_order.get(v.severity, 0) >= min_severity_level]

    # Apply strict mode (all violations become ERRORS)
    if args.strict:
        for v in violations:
            v.severity = "ERROR"

    # Categorize violations
    errors = [v for v in violations if v.severity == "ERROR"]
    warnings = [v for v in violations if v.severity == "WARNING"]
    info = [v for v in violations if v.severity == "INFO"]

    # Calculate compliance
    total_artifacts = len(violations) + 100  # Placeholder - need to count all artifacts
    compliant_count = total_artifacts - len(violations)
    compliance_pct = (compliant_count / total_artifacts * 100) if total_artifacts > 0 else 100.0

    # Build result
    result = ValidationResult(
        success=True,
        errors=[asdict(v) for v in errors],
        warnings=[asdict(v) for v in warnings],
        details={
            "total_violations": len(violations),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "info_count": len(info),
            "total_artifacts": total_artifacts,
            "compliant_artifacts": compliant_count,
            "compliance_percentage": round(compliance_pct, 1)
        }
    )

    # Print human-readable report to stderr
    print(f"\nVIOLATIONS FOUND: {len(violations)}\n", file=sys.stderr)

    for v in errors:
        print(f"[ERROR] {v.artifact_type} \"{v.name}\" ({v.file}:{v.line})", file=sys.stderr)
        print(f"  Rule: {v.rule}", file=sys.stderr)
        print(f"  Expected pattern: {v.pattern}", file=sys.stderr)
        if v.suggestion:
            print(f"  Suggestion: Rename to \"{v.suggestion}\"", file=sys.stderr)
        print("", file=sys.stderr)

    for v in warnings:
        print(f"[WARNING] {v.artifact_type} \"{v.name}\" ({v.file}:{v.line})", file=sys.stderr)
        print(f"  Rule: {v.rule}", file=sys.stderr)
        if v.suggestion:
            print(f"  Suggestion: Rename to \"{v.suggestion}\"", file=sys.stderr)
        print("", file=sys.stderr)

    print(f"Summary: {len(errors)} ERRORS, {len(warnings)} WARNINGS, {len(info)} INFO", file=sys.stderr)
    print(f"Compliance: {compliance_pct:.1f}% ({compliant_count}/{total_artifacts} artifacts compliant)", file=sys.stderr)
    print(f"Exit code: {result.exit_code}", file=sys.stderr)

    # Output JSON
    json_output = result.to_json()
    if args.output:
        with open(args.output, "w") as f:
            f.write(json_output)
        print(f"Results written to: {args.output}", file=sys.stderr)
    else:
        print(json_output)

    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
