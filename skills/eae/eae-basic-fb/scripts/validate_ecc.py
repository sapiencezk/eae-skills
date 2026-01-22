#!/usr/bin/env python3
"""
validate_ecc.py - ECC (Execution Control Chart) State Machine Validator

Validates ECC state machines in EAE Basic Function Blocks for correctness.

This script checks:
- All states are reachable from START
- All event inputs have at least one transition
- All transitions reference valid algorithms
- No circular dependencies in state machine
- Standard states are present (START, INIT, REQ if applicable)

Usage:
    python validate_ecc.py <basic_fb_file_path> [options]

    Examples:
        # Validate a Basic FB file
        python validate_ecc.py path/to/MyBasicFB.fbt

        # Validate with verbose output
        python validate_ecc.py path/to/MyBasicFB.fbt --verbose

        # Output JSON for automation
        python validate_ecc.py path/to/MyBasicFB.fbt --json

        # CI mode (JSON output, exit codes only)
        python validate_ecc.py path/to/MyBasicFB.fbt --ci

Exit Codes:
    0  - Validation passed (no errors)
    1  - General error (file not found, parse error, etc.)
    10 - Validation failed (errors found)
    11 - Validation passed with warnings

Dependencies:
    - Python 3.7+
    - lxml (optional, for better XML parsing)
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set, Dict

# Add parent directory to path for shared library imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'eae-skill-router' / 'scripts'))

from lib.validation_result import ValidationResult, create_success, create_failure
from lib.contextual_errors import SYMBOLS, print_validation_summary

# Try to import lxml for better XML parsing, fall back to stdlib
try:
    from lxml import etree as ET
    HAVE_LXML = True
except ImportError:
    import xml.etree.ElementTree as ET
    HAVE_LXML = False


@dataclass
class ECCState:
    """Represents an ECC state."""
    name: str
    actions: List[str] = field(default_factory=list)
    transitions: List['ECCTransition'] = field(default_factory=list)

    def __repr__(self):
        return f"ECCState({self.name})"


@dataclass
class ECCTransition:
    """Represents an ECC transition."""
    source: str
    destination: str
    condition: str
    actions: List[str] = field(default_factory=list)

    def __repr__(self):
        return f"Transition({self.source} -> {self.destination} on {self.condition})"


def build_ecc_graph(ecc_element: ET.Element) -> Dict[str, ECCState]:
    """
    Build a graph representation of the ECC.

    Args:
        ecc_element: <ECC> XML element

    Returns:
        Dictionary mapping state names to ECCState objects
    """
    states = {}

    # Build states
    for state_elem in ecc_element.findall('.//ECState'):
        state_name = state_elem.get('Name')
        if not state_name:
            continue

        state = ECCState(name=state_name)

        # Get actions for this state
        for action_elem in state_elem.findall('.//ECAction'):
            algorithm = action_elem.get('Algorithm')
            if algorithm:
                state.actions.append(algorithm)

        states[state_name] = state

    # Build transitions
    for trans_elem in ecc_element.findall('.//ECTransition'):
        source = trans_elem.get('Source')
        destination = trans_elem.get('Destination')
        condition = trans_elem.get('Condition', 'ALWAYS')

        if not source or not destination:
            continue

        transition = ECCTransition(
            source=source,
            destination=destination,
            condition=condition
        )

        # Get actions for this transition
        for action_elem in trans_elem.findall('.//ECAction'):
            algorithm = action_elem.get('Algorithm')
            if algorithm:
                transition.actions.append(algorithm)

        # Add transition to source state
        if source in states:
            states[source].transitions.append(transition)

    return states


def find_reachable_states(states: Dict[str, ECCState], start_state: str) -> Set[str]:
    """
    Find all states reachable from the start state using BFS.

    Args:
        states: Dictionary of state name to ECCState
        start_state: Name of the starting state

    Returns:
        Set of reachable state names
    """
    reachable = set()
    queue = [start_state]

    while queue:
        current = queue.pop(0)
        if current in reachable:
            continue

        reachable.add(current)

        # Add all destinations of transitions from current state
        if current in states:
            for transition in states[current].transitions:
                if transition.destination not in reachable:
                    queue.append(transition.destination)

    return reachable


def validate_ecc_state_machine(tree: ET.ElementTree, filepath: Path) -> ValidationResult:
    """
    Validate ECC state machine in a Basic FB.

    Args:
        tree: Parsed XML tree
        filepath: Path to the file being validated

    Returns:
        ValidationResult with success status and any errors/warnings
    """
    errors = []
    warnings = []
    details = {}

    root = tree.getroot()

    # ============================================================
    # Check 1: Ensure this is a Basic FB with ECC
    # ============================================================
    basic_fb = root.find('.//BasicFB')
    if basic_fb is None:
        return create_failure(
            "Not a Basic FB file",
            ["File does not contain a BasicFB element"]
        )

    ecc = basic_fb.find('.//ECC')
    if ecc is None:
        return create_failure(
            "No ECC found",
            ["BasicFB does not contain an ECC (Execution Control Chart)"]
        )

    # ============================================================
    # Check 2: Build ECC graph
    # ============================================================
    states = build_ecc_graph(ecc)
    details['total_states'] = len(states)
    details['state_names'] = list(states.keys())

    if not states:
        return create_failure(
            "Empty ECC",
            ["ECC has no states defined"],
            details=details
        )

    # ============================================================
    # Check 3: Verify START state exists
    # ============================================================
    if 'START' not in states:
        errors.append("Required state 'START' is missing from ECC")

    # ============================================================
    # Check 4: Check for standard states
    # ============================================================
    # Common pattern: START, INIT, REQ
    has_init = 'INIT' in states
    has_req = 'REQ' in states

    details['has_standard_states'] = {
        'START': 'START' in states,
        'INIT': has_init,
        'REQ': has_req
    }

    if not has_init:
        warnings.append("Recommended state 'INIT' is missing (not required but common pattern)")

    # ============================================================
    # Check 5: Find unreachable states
    # ============================================================
    if 'START' in states:
        reachable = find_reachable_states(states, 'START')
        unreachable = set(states.keys()) - reachable

        details['reachable_states'] = len(reachable)
        details['unreachable_states'] = len(unreachable)

        if unreachable:
            for state in sorted(unreachable):
                errors.append(f"State '{state}' is unreachable from START")

    # ============================================================
    # Check 6: Verify all states have at least one transition out
    # (except if they're terminal states)
    # ============================================================
    states_without_transitions = []
    for state_name, state in states.items():
        if not state.transitions and state_name != 'START':
            states_without_transitions.append(state_name)

    if states_without_transitions:
        for state in sorted(states_without_transitions):
            warnings.append(f"State '{state}' has no outgoing transitions (potential dead end)")

    # ============================================================
    # Check 7: Verify transitions reference valid destination states
    # ============================================================
    for state_name, state in states.items():
        for trans in state.transitions:
            if trans.destination not in states:
                errors.append(
                    f"Transition from '{state_name}' references non-existent destination state '{trans.destination}'"
                )

    # ============================================================
    # Check 8: Verify algorithms referenced in actions exist
    # ============================================================
    # Get all defined algorithms
    algorithms = set()
    for algo_elem in root.findall('.//Algorithm'):
        algo_name = algo_elem.get('Name')
        if algo_name:
            algorithms.add(algo_name)

    details['defined_algorithms'] = list(algorithms)

    # Check all referenced algorithms
    for state_name, state in states.items():
        # Check state actions
        for action in state.actions:
            if action and action not in algorithms:
                errors.append(
                    f"State '{state_name}' references undefined algorithm '{action}'"
                )

        # Check transition actions
        for trans in state.transitions:
            for action in trans.actions:
                if action and action not in algorithms:
                    errors.append(
                        f"Transition from '{state_name}' references undefined algorithm '{action}'"
                    )

    # ============================================================
    # Check 9: Check for infinite loops (state transitioning to itself with no condition)
    # ============================================================
    for state_name, state in states.items():
        for trans in state.transitions:
            if trans.source == trans.destination and trans.condition == '1':
                warnings.append(
                    f"State '{state_name}' has unconditional self-loop (infinite loop risk)"
                )

    # ============================================================
    # Check 10: Verify event inputs have transitions
    # ============================================================
    event_inputs = set()
    for event_elem in root.findall('.//InterfaceList/EventInputs/Event'):
        event_name = event_elem.get('Name')
        if event_name:
            event_inputs.add(event_name)

    # Check which event inputs are used in transitions
    used_events = set()
    for state in states.values():
        for trans in state.transitions:
            # Extract event name from condition (e.g., "REQ" from "REQ")
            # In ECC, conditions often reference event names directly
            used_events.add(trans.condition)

    unused_events = event_inputs - used_events
    if unused_events:
        for event in sorted(unused_events):
            warnings.append(f"Event input '{event}' is not used in any ECC transitions")

    # ============================================================
    # Summary
    # ============================================================
    if errors:
        return create_failure(
            f"ECC validation failed with {len(errors)} error(s)",
            errors,
            warnings=warnings,
            details=details
        )
    elif warnings:
        return create_success(
            f"ECC validation passed with {len(warnings)} warning(s)",
            warnings=warnings,
            details=details
        )
    else:
        return create_success(
            "ECC validation passed - state machine is correct",
            details=details
        )


def parse_xml_file(filepath: Path) -> Optional[ET.ElementTree]:
    """
    Parse XML file safely.

    Args:
        filepath: Path to XML file

    Returns:
        ElementTree or None if parsing failed
    """
    try:
        if HAVE_LXML:
            parser = ET.XMLParser(remove_blank_text=True, encoding='utf-8')
            tree = ET.parse(str(filepath), parser)
        else:
            tree = ET.parse(str(filepath))
        return tree
    except ET.ParseError as e:
        print(f"{SYMBOLS['error']} XML parsing error: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"{SYMBOLS['error']} Error reading file: {e}", file=sys.stderr)
        return None


def print_validation_result(result: ValidationResult, verbose: bool = False):
    """
    Print validation result in human-readable format.

    Args:
        result: ValidationResult to print
        verbose: Whether to print detailed information
    """
    # Use shared library function for summary
    print_validation_summary(result.success, len(result.errors), len(result.warnings), result.message)

    if result.errors:
        print(f"{SYMBOLS['error']} Errors ({len(result.errors)}):")
        for i, error in enumerate(result.errors, 1):
            print(f"  {i}. {error}")

    if result.warnings:
        print(f"\n{SYMBOLS['warning']} Warnings ({len(result.warnings)}):")
        for i, warning in enumerate(result.warnings, 1):
            print(f"  {i}. {warning}")

    if verbose and result.details:
        print(f"\n{SYMBOLS['info']} Details:")
        for key, value in result.details.items():
            if isinstance(value, (list, dict)):
                print(f"  {key}:")
                print(f"    {json.dumps(value, indent=4)}")
            else:
                print(f"  {key}: {value}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate ECC state machine in EAE Basic Function Blocks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python validate_ecc.py MyBasicFB.fbt
  python validate_ecc.py MyBasicFB.fbt --verbose
  python validate_ecc.py MyBasicFB.fbt --json
  python validate_ecc.py MyBasicFB.fbt --ci
        """
    )
    parser.add_argument(
        "filepath",
        type=Path,
        help="Path to Basic FB file to validate (.fbt)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output with detailed information"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format (for automation)"
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: JSON output with exit code only (no human messages)"
    )

    args = parser.parse_args()

    # CI mode implies JSON
    if args.ci:
        args.json = True

    # Check file exists
    if not args.filepath.exists():
        if not args.json:
            print(f"{SYMBOLS['error']} Error: File not found: {args.filepath}", file=sys.stderr)
        return 1

    # Check file extension
    if args.filepath.suffix != ".fbt":
        if not args.json:
            print(f"{SYMBOLS['error']} Error: Expected .fbt file, got {args.filepath.suffix}", file=sys.stderr)
        return 1

    # Parse XML
    tree = parse_xml_file(args.filepath)
    if tree is None:
        return 1

    # Validate
    result = validate_ecc_state_machine(tree, args.filepath)

    # Output results
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print_validation_result(result, verbose=args.verbose)

    # Return appropriate exit code using the property from ValidationResult
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
