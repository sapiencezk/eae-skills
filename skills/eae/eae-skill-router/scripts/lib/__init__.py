"""
Shared library for EAE skill scripts.

This package provides common utilities, patterns, and base classes used across
all EAE skills for validation, error handling, and state management.

Modules:
    validation_result: ValidationResult dataclass for structured validation output
    contextual_errors: Contextual error reporting with fix guidance
    transaction_manager: Transactional file operations with rollback
    resume_capability: Resume pattern for long-running operations
    preflight_checker: Base class for pre-operation validation

Usage:
    from lib.validation_result import ValidationResult
    from lib.contextual_errors import print_helpful_error
"""

__version__ = "1.0.0"

# Export commonly-used items
from .validation_result import ValidationResult
from .contextual_errors import print_helpful_error, format_error_with_context

__all__ = [
    'ValidationResult',
    'print_helpful_error',
    'format_error_with_context',
]
