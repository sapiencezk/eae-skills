"""
ValidationResult dataclass for structured validation output.

This module provides the standard result format used by all validation scripts
across the EAE skills ecosystem.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class ValidationResult:
    """
    Structured result for validation operations.

    This is the standard return type for all validation scripts in the EAE skills
    ecosystem. It provides a consistent interface for reporting success, errors,
    warnings, and additional details.

    Attributes:
        success: True if validation passed (no errors), False otherwise
        message: Human-readable summary message
        errors: List of error messages (critical issues that must be fixed)
        warnings: List of warning messages (issues that should be reviewed)
        details: Optional dictionary with additional context and debugging info

    Exit Code Mapping:
        - success=True, no warnings: Exit code 0
        - success=True, with warnings: Exit code 11
        - success=False: Exit code 10
        - Script failure: Exit code 1

    Example:
        >>> result = ValidationResult(
        ...     success=False,
        ...     message="ECC validation failed with 2 errors",
        ...     errors=["State 'IDLE' is unreachable from START",
        ...             "Transition references undefined algorithm 'DoWork'"],
        ...     warnings=["State 'TEMP' has no outgoing transitions"],
        ...     details={"total_states": 5, "reachable_states": 4}
        ... )
        >>> result.has_errors
        True
        >>> result.to_dict()
        {'success': False, 'message': '...', 'errors': [...], ...}
    """

    success: bool
    message: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Optional[Dict[str, Any]] = None

    @property
    def has_errors(self) -> bool:
        """Check if validation found errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if validation found warnings."""
        return len(self.warnings) > 0

    @property
    def exit_code(self) -> int:
        """
        Get the recommended exit code for this result.

        Returns:
            0: Validation passed, no warnings
            10: Validation failed (errors found)
            11: Validation passed with warnings
        """
        if not self.success:
            return 10  # Validation failed
        elif self.has_warnings:
            return 11  # Validation passed with warnings
        else:
            return 0  # Validation passed

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON output.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "success": self.success,
            "message": self.message,
            "errors": self.errors,
            "warnings": self.warnings,
            "details": self.details or {}
        }

    def __str__(self) -> str:
        """String representation for human-readable output."""
        status = "PASSED" if self.success else "FAILED"
        parts = [f"[{status}] {self.message}"]

        if self.errors:
            parts.append(f"\nErrors ({len(self.errors)}):")
            for i, error in enumerate(self.errors, 1):
                parts.append(f"  {i}. {error}")

        if self.warnings:
            parts.append(f"\nWarnings ({len(self.warnings)}):")
            for i, warning in enumerate(self.warnings, 1):
                parts.append(f"  {i}. {warning}")

        return "\n".join(parts)


def create_success(message: str, warnings: Optional[List[str]] = None,
                   details: Optional[Dict[str, Any]] = None) -> ValidationResult:
    """
    Create a successful ValidationResult.

    Args:
        message: Success message
        warnings: Optional list of warnings
        details: Optional additional details

    Returns:
        ValidationResult with success=True
    """
    return ValidationResult(
        success=True,
        message=message,
        errors=[],
        warnings=warnings or [],
        details=details
    )


def create_failure(message: str, errors: List[str],
                   warnings: Optional[List[str]] = None,
                   details: Optional[Dict[str, Any]] = None) -> ValidationResult:
    """
    Create a failed ValidationResult.

    Args:
        message: Failure message
        errors: List of error messages
        warnings: Optional list of warnings
        details: Optional additional details

    Returns:
        ValidationResult with success=False
    """
    return ValidationResult(
        success=False,
        message=message,
        errors=errors,
        warnings=warnings or [],
        details=details
    )
