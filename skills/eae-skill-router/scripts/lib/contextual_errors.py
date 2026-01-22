"""
Contextual error reporting with fix guidance.

This module provides utilities for reporting errors with context and actionable
guidance, following the pattern established in eae-fork.
"""

from typing import Optional


def print_helpful_error(error_type: str, details: str, how_to_fix: str,
                       additional_context: Optional[str] = None) -> None:
    """
    Print error with context and fix guidance.

    This function prints errors in a structured format that tells the user:
    - WHAT failed (error type)
    - WHY it failed (details)
    - HOW to fix it (actionable guidance)
    - Additional context (optional)

    Args:
        error_type: Short description of what failed
        details: Detailed explanation of the error
        how_to_fix: Actionable steps to resolve the error
        additional_context: Optional additional context or background

    Example:
        >>> print_helpful_error(
        ...     "Unreachable ECC State",
        ...     "State 'IDLE' cannot be reached from START. No transition path exists.",
        ...     "Add a transition from an existing state to IDLE, or remove IDLE if unused",
        ...     "All ECC states must be reachable from START for the state machine to be valid"
        ... )

        [ERROR] Unreachable ECC State

        Details:
          State 'IDLE' cannot be reached from START. No transition path exists.

        How to fix:
          Add a transition from an existing state to IDLE, or remove IDLE if unused

        Context:
          All ECC states must be reachable from START for the state machine to be valid
    """
    print(f"\n[ERROR] {error_type}")
    print(f"\nDetails:")
    print(f"  {details}")
    print(f"\nHow to fix:")
    print(f"  {how_to_fix}")

    if additional_context:
        print(f"\nContext:")
        print(f"  {additional_context}")

    print()  # Blank line for readability


def format_error_with_context(error_type: str, details: str,
                              how_to_fix: str,
                              additional_context: Optional[str] = None) -> str:
    """
    Format error with context as a string (for programmatic use).

    Same as print_helpful_error but returns a formatted string instead of printing.

    Args:
        error_type: Short description of what failed
        details: Detailed explanation of the error
        how_to_fix: Actionable steps to resolve the error
        additional_context: Optional additional context

    Returns:
        Formatted error message string
    """
    parts = [
        f"[ERROR] {error_type}",
        "",
        "Details:",
        f"  {details}",
        "",
        "How to fix:",
        f"  {how_to_fix}"
    ]

    if additional_context:
        parts.extend([
            "",
            "Context:",
            f"  {additional_context}"
        ])

    return "\n".join(parts)


def print_warning(warning_type: str, details: str,
                 recommendation: Optional[str] = None) -> None:
    """
    Print warning with optional recommendation.

    Warnings are non-critical issues that should be reviewed but don't block operation.

    Args:
        warning_type: Short description of the warning
        details: Detailed explanation
        recommendation: Optional recommendation for addressing the warning

    Example:
        >>> print_warning(
        ...     "State Without Transitions",
        ...     "State 'CLEANUP' has no outgoing transitions (potential dead end)",
        ...     "Add a transition to another state or to a terminal state"
        ... )

        [WARN] State Without Transitions

        Details:
          State 'CLEANUP' has no outgoing transitions (potential dead end)

        Recommendation:
          Add a transition to another state or to a terminal state
    """
    print(f"\n[WARN] {warning_type}")
    print(f"\nDetails:")
    print(f"  {details}")

    if recommendation:
        print(f"\nRecommendation:")
        print(f"  {recommendation}")

    print()  # Blank line for readability


# ASCII-safe symbols (no emoji) for terminal compatibility
SYMBOLS = {
    'success': '[OK]',
    'error': '[ERROR]',
    'warning': '[WARN]',
    'info': '[INFO]',
    'check': '[PASS]',
    'cross': '[FAIL]',
}


def print_validation_summary(success: bool, error_count: int,
                            warning_count: int, message: str) -> None:
    """
    Print a validation summary.

    Args:
        success: Whether validation passed
        error_count: Number of errors found
        warning_count: Number of warnings found
        message: Summary message
    """
    symbol = SYMBOLS['success'] if success else SYMBOLS['error']
    print(f"\n{symbol} {message}")

    if error_count > 0:
        print(f"  {SYMBOLS['cross']} {error_count} error(s) found")

    if warning_count > 0:
        print(f"  {SYMBOLS['warning']} {warning_count} warning(s) found")

    print()  # Blank line for readability
