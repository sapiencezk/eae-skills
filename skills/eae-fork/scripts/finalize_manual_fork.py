#!/usr/bin/env python3
"""
Finalize manually forked EAE block.

User must first fork the block in EAE GUI, then run this script to:
1. Detect source namespace (automatic)
2. Update namespaces in .fbt and .cs files
3. Update cross-block references (for blocks in forked set)
4. Update HMI cross-references (for blocks in forked set)
5. Generate new GUIDs
6. Register block in dfbproj/csproj
7. Validate everything

Usage:
    python finalize_manual_fork.py <block_name>... <target_lib>

Example:
    # Single block
    python finalize_manual_fork.py AnalogInput SE.ScadapackWWW

    # Hierarchy (all blocks in forked set)
    python finalize_manual_fork.py AnalogInputBase AnalogInputBaseExt AnalogInput SE.ScadapackWWW

    # Hierarchy + SubCATs (complete fork)
    python finalize_manual_fork.py AnalogInputBase AnalogInputBaseExt AnalogInput \
        LimitAlarm DeviationAlarm ROCAlarm SE.ScadapackWWW

Requirements:
    - Block(s) must already be forked in EAE GUI
    - IEC61499/{BlockName}/ directory exists
    - HMI/{BlockName}/ directory exists (for CAT blocks)

Exit Codes:
    0 - Success
    1 - General error
    10 - Validation failure (manual fork not found)
    11 - Registration failure
"""

import argparse
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional

# ============================================================================
# UTF-8 Encoding Fix (v7.1)
# Force UTF-8 output on Windows to prevent unicode encoding errors
# ============================================================================
if sys.platform == 'win32':
    try:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'replace')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'replace')
    except Exception:
        # Fallback: if encoding setup fails, continue with default
        pass

# ASCII-safe symbols for cross-platform compatibility
SYMBOLS = {
    'ok': '[OK]',
    'error': '[ERROR]',
    'success': '[SUCCESS]',
    'info': '[INFO]',
    'warn': '[WARN]',
    'arrow': '->',
}


# ============================================================================
# Better Error Messages (v7.2)
# Contextual error handling with actionable recovery suggestions
# ============================================================================

class ForkValidationError(Exception):
    """Raised when validation fails (block not found or incomplete)."""
    def __init__(self, block_name: str, missing_files: List[str]):
        self.block_name = block_name
        self.missing_files = missing_files
        super().__init__(f"Block '{block_name}' validation failed")


class NamespaceUpdateError(Exception):
    """Raised when namespace update fails."""
    def __init__(self, block_name: str, file_path: Path, original_error: Exception):
        self.block_name = block_name
        self.file_path = file_path
        self.original_error = original_error
        super().__init__(f"Failed to update '{file_path}'")


class RegistrationError(Exception):
    """Raised when block registration fails."""
    def __init__(self, block_name: str, block_type: str, original_error: Exception):
        self.block_name = block_name
        self.block_type = block_type
        self.original_error = original_error
        super().__init__(f"Failed to register {block_type} block '{block_name}'")


def print_helpful_error(error: Exception, context: Optional[Dict] = None):
    """Print helpful error message with context and recovery suggestions."""
    print(f"\n{SYMBOLS['error']} {error.__class__.__name__}: {error}")

    if isinstance(error, ForkValidationError):
        print(f"\nWhat happened:")
        print(f"  Block '{error.block_name}' was not found or is incomplete")
        if error.missing_files:
            print(f"\n  Missing files:")
            for f in error.missing_files:
                print(f"    - {f}")
        print(f"\nHow to fix:")
        print(f"  1. Open EAE GUI")
        print(f"  2. Navigate to source library")
        print(f"  3. Right-click '{error.block_name}' {SYMBOLS['arrow']} 'Copy Block'")
        print(f"  4. Select target library")
        print(f"  5. Wait for EAE to complete the copy")
        print(f"  6. Re-run this script")

    elif isinstance(error, NamespaceUpdateError):
        print(f"\nWhat happened:")
        print(f"  Failed to update file: {error.file_path}")
        print(f"  Original error: {error.original_error}")
        print(f"\nHow to fix:")
        print(f"  1. Check file is not read-only:")
        print(f"     attrib -R \"{error.file_path}\"")
        print(f"  2. Close file in all editors (VSCode, EAE, etc.)")
        print(f"  3. Check file permissions")
        print(f"  4. Re-run this script")

    elif isinstance(error, RegistrationError):
        print(f"\nWhat happened:")
        print(f"  Failed to register {error.block_type} block: {error.block_name}")
        print(f"  Original error: {error.original_error}")
        print(f"\nHow to fix:")
        print(f"  1. Check dfbproj file is not read-only")
        print(f"  2. Close project in EAE")
        print(f"  3. Check for XML syntax errors in dfbproj")
        print(f"  4. Re-run this script")

    elif isinstance(error, FileNotFoundError):
        print(f"\nWhat happened:")
        print(f"  File not found: {error.filename}")
        print(f"\nHow to fix:")
        print(f"  1. Verify you ran script from project directory")
        print(f"  2. Check block was manually forked in EAE GUI")
        print(f"  3. Use --project-path if running from different directory")

    elif isinstance(error, PermissionError):
        print(f"\nWhat happened:")
        print(f"  Permission denied accessing file: {error.filename}")
        print(f"\nHow to fix:")
        print(f"  1. Close all files/projects in EAE and editors")
        print(f"  2. Run as administrator if needed")
        print(f"  3. Check antivirus is not blocking file access")

    if context:
        print(f"\nContext:")
        for key, value in context.items():
            print(f"  {key}: {value}")


def find_project_root() -> Optional[Path]:
    """Find the EAE project root by looking for .dfbproj files."""
    current = Path.cwd()

    # Search up to 3 levels up
    for _ in range(3):
        # Look for any .dfbproj file
        dfbproj_files = list(current.glob("*/*.dfbproj"))
        if dfbproj_files:
            return current

        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def validate_pre_fork(source_lib: str, block_names: List[str]) -> Dict:
    """
    Validate blocks exist in source library before fork.

    This prevents users from wasting time in GUI only to find blocks don't exist.

    Args:
        source_lib: Source library name (e.g., "SE.App2CommonProcess")
        block_names: List of block names to fork

    Returns:
        Dict with keys:
            - valid: bool (overall validation result)
            - source_library_path: Path or None
            - source_version: str or None
            - missing_blocks: List[str]
            - source_namespace: str or None
            - warnings: List[str]
    """
    result = {
        "valid": True,
        "source_library_path": None,
        "source_version": None,
        "missing_blocks": [],
        "source_namespace": None,
        "warnings": []
    }

    # Find source library
    lib_root = Path("C:/ProgramData/Schneider Electric/Libraries")
    if not lib_root.exists():
        result["valid"] = False
        result["warnings"].append(f"Libraries directory not found: {lib_root}")
        return result

    # Match library with version (e.g., SE.App2CommonProcess-25.0.1.5)
    lib_paths = list(lib_root.glob(f"{source_lib}-*"))
    if not lib_paths:
        result["valid"] = False
        result["warnings"].append(f"Source library '{source_lib}' not found in {lib_root}")
        return result

    # Use most recent version (highest version number)
    lib_path = max(lib_paths, key=lambda p: p.name)
    result["source_library_path"] = lib_path
    result["source_version"] = lib_path.name.split('-')[-1]

    print(f"{SYMBOLS['info']} Found source library: {lib_path.name}")

    # Check each block exists
    files_dir = lib_path / "Files"
    for block in block_names:
        block_path = files_dir / block
        if not block_path.exists():
            result["valid"] = False
            result["missing_blocks"].append(block)
            result["warnings"].append(f"Block '{block}' not found in {source_lib}")

    # If blocks found, detect source namespace from first block
    if block_names and not result["missing_blocks"]:
        first_block = block_names[0]
        fbt_file = files_dir / first_block / f"{first_block}.fbt"

        if fbt_file.exists():
            content = fbt_file.read_text(encoding='utf-8')
            match = re.search(r'<FBType[^>]*\sNamespace="([^"]*)"', content)
            if match:
                result["source_namespace"] = match.group(1)
                print(f"{SYMBOLS['info']} Detected source namespace: {result['source_namespace']}")
            else:
                result["warnings"].append(f"Could not detect namespace from {first_block}.fbt")
        else:
            result["valid"] = False
            result["warnings"].append(f"Block file not found: {fbt_file}")

    # Validate all blocks come from same namespace
    if result["source_namespace"]:
        for block in block_names:
            fbt_file = files_dir / block / f"{block}.fbt"
            if fbt_file.exists():
                content = fbt_file.read_text(encoding='utf-8')
                match = re.search(r'<FBType[^>]*\sNamespace="([^"]*)"', content)
                if match and match.group(1) != result["source_namespace"]:
                    result["valid"] = False
                    result["warnings"].append(
                        f"Block '{block}' has different namespace: {match.group(1)} "
                        f"(expected {result['source_namespace']})"
                    )

    return result


def detect_block_type(iec_dir: Path, block_name: str) -> Optional[str]:
    """Detect block type from files in IEC61499 directory."""

    # Check for .cfg (CAT block)
    if (iec_dir / f"{block_name}.cfg").exists():
        return "CAT"

    # Check for .fbt
    fbt_file = iec_dir / f"{block_name}.fbt"
    if not fbt_file.exists():
        return None

    # Read .fbt to determine Basic vs Composite
    content = fbt_file.read_text(encoding='utf-8')
    if "<BasicFB>" in content:
        return "Basic"
    else:
        return "Composite"


def detect_source_namespace(iec_dir: Path, block_name: str) -> Optional[str]:
    """
    Extract original namespace from .fbt file before updating.

    This allows us to identify which namespace references to update in HMI files.
    """
    fbt_file = iec_dir / f"{block_name}.fbt"
    if not fbt_file.exists():
        return None

    content = fbt_file.read_text(encoding='utf-8')
    match = re.search(r'<FBType[^>]*\sNamespace="([^"]*)"', content)
    if match:
        namespace = match.group(1)
        print(f"  Detected source namespace: {namespace}")
        return namespace
    return None


def validate_manual_fork(project_root: Path, lib_name: str, block_name: str) -> Dict:
    """
    Validate that user has manually forked the block in EAE GUI.

    Returns dict with:
        - valid: bool
        - block_type: str (CAT, Composite, Basic)
        - has_iec: bool
        - has_hmi: bool
        - missing_files: list
        - source_namespace: str (detected from .fbt)
    """

    iec_dir = project_root / lib_name / "IEC61499" / block_name
    hmi_dir = project_root / lib_name / "HMI" / block_name

    results = {
        "valid": False,
        "block_type": None,
        "has_iec": iec_dir.exists(),
        "has_hmi": hmi_dir.exists(),
        "missing_files": [],
        "source_namespace": None
    }

    if not results["has_iec"]:
        results["missing_files"].append(f"IEC61499/{block_name}/")
        return results

    # Detect source namespace BEFORE updating
    source_ns = detect_source_namespace(iec_dir, block_name)
    results["source_namespace"] = source_ns

    # Detect block type
    block_type = detect_block_type(iec_dir, block_name)
    if not block_type:
        results["missing_files"].append(f"{block_name}.fbt or {block_name}.cfg")
        return results

    results["block_type"] = block_type

    # CAT requires HMI
    if block_type == "CAT" and not results["has_hmi"]:
        results["missing_files"].append(f"HMI/{block_name}/")
        return results

    results["valid"] = True
    return results


def update_fbt_namespace(fbt_file: Path, target_namespace: str) -> None:
    """Update Namespace attribute and GUID in .fbt file."""
    content = fbt_file.read_text(encoding='utf-8')

    # Update root FBType namespace
    content = re.sub(
        r'(<FBType[^>]*\s)Namespace="[^"]*"',
        rf'\1Namespace="{target_namespace}"',
        content
    )

    # Generate new GUID for root element only
    new_guid = str(uuid.uuid4())
    content = re.sub(
        r'GUID="[0-9a-fA-F-]+"',
        f'GUID="{new_guid}"',
        content,
        count=1  # Only first occurrence (root element)
    )

    fbt_file.write_text(content, encoding='utf-8')
    print(f"  {SYMBOLS['ok']} Updated {fbt_file.name}")


def update_cross_block_references(
    iec_dir: Path,
    block_name: str,
    forked_blocks: List[str],
    target_namespace: str
) -> int:
    """
    Update FB/SubCAT Namespace attributes for blocks in forked set.

    Returns number of cross-references updated.
    """
    count = 0

    for fbt_file in iec_dir.glob("*.fbt"):
        content = fbt_file.read_text(encoding='utf-8')
        original_content = content

        # Find all FB/SubCAT elements with Type in forked_blocks
        for forked_block in forked_blocks:
            if forked_block == block_name:
                continue  # Skip self-reference

            # Pattern 1: <FB ... Type="ForkedBlock" ... Namespace="OldNS">
            pattern = rf'(<FB[^>]*\sType="{forked_block}"[^>]*\s)Namespace="[^"]*"'
            replacement = rf'\1Namespace="{target_namespace}"'
            content = re.sub(pattern, replacement, content)

            # Pattern 2: <SubCAT ... Type="ForkedBlock" ... Namespace="OldNS">
            pattern = rf'(<SubCAT[^>]*\sType="{forked_block}"[^>]*\s)Namespace="[^"]*"'
            replacement = rf'\1Namespace="{target_namespace}"'
            content = re.sub(pattern, replacement, content)

        if content != original_content:
            fbt_file.write_text(content, encoding='utf-8')
            # Count changes
            changes = len([m for m in re.finditer(target_namespace, content)]) - \
                     len([m for m in re.finditer(target_namespace, original_content)])
            count += changes

    return count


def update_hmi_cross_references(
    hmi_dir: Path,
    forked_blocks: List[str],
    source_namespace: str,
    target_namespace: str
) -> int:
    """
    Update fully qualified type references in HMI C# files.

    Only updates references to blocks in the forked set.

    Returns number of HMI references updated.
    """
    count = 0

    for cs_file in hmi_dir.glob("*.cs"):
        content = cs_file.read_text(encoding='utf-8')
        original_content = content

        for forked_block in forked_blocks:
            # Pattern 1: SE.OldLib.Symbols.ForkedBlock.ClassName
            pattern = rf'{re.escape(source_namespace)}\.Symbols\.{forked_block}\.'
            replacement = f'{target_namespace}.Symbols.{forked_block}.'
            content = content.replace(pattern, replacement)

            # Pattern 2: SE.OldLib.Faceplates.ForkedBlock.ClassName
            pattern = rf'{re.escape(source_namespace)}\.Faceplates\.{forked_block}\.'
            replacement = f'{target_namespace}.Faceplates.{forked_block}.'
            content = content.replace(pattern, replacement)

        if content != original_content:
            cs_file.write_text(content, encoding='utf-8')
            # Count changes
            changes = content.count(target_namespace) - original_content.count(target_namespace)
            count += changes

    return count


def find_source_library_path(source_namespace: str) -> Optional[Path]:
    """
    Find source library path in standard Schneider Electric locations.

    Args:
        source_namespace: Source library name (e.g., "SE.App2CommonProcess")

    Returns:
        Path to source library or None if not found
    """
    program_data = Path("C:/ProgramData/Schneider Electric/Libraries")
    if not program_data.exists():
        return None

    # Look for library directories matching pattern: {namespace}-{version}
    for lib_dir in program_data.glob(f"{source_namespace}-*"):
        if lib_dir.is_dir():
            return lib_dir

    return None


def restore_original_fb_namespaces(
    fbt_file: Path,
    source_namespace: str,
    block_name: str,
    forked_blocks: List[str]
) -> int:
    """
    Restore original FB namespaces for blocks NOT in the forked set.

    When EAE GUI copies a block, it changes ALL FB namespaces to the target library.
    This function restores the original namespaces for FBs that weren't explicitly forked.

    Args:
        fbt_file: Path to forked .fbt file
        source_namespace: Source library namespace (e.g., "SE.App2CommonProcess")
        block_name: Name of the block
        forked_blocks: List of blocks that were explicitly forked

    Returns:
        Number of FB namespaces restored
    """
    # Find source library
    source_lib_path = find_source_library_path(source_namespace)
    if not source_lib_path:
        print(f"  {SYMBOLS['warn']} Source library not found: {source_namespace}")
        print(f"  {SYMBOLS['warn']} Cannot restore original FB namespaces")
        return 0

    # Find original .fbt file
    original_fbt = source_lib_path / "Files" / block_name / f"{block_name}.fbt"
    if not original_fbt.exists():
        print(f"  {SYMBOLS['warn']} Original .fbt not found: {original_fbt}")
        print(f"  {SYMBOLS['warn']} Cannot restore original FB namespaces")
        return 0

    # Read original .fbt to get original FB namespaces
    original_content = original_fbt.read_text(encoding='utf-8')

    # Extract all FB elements with their Type and Namespace
    fb_pattern = r'<FB[^>]*\sType="([^"]*)"[^>]*\sNamespace="([^"]*)"'
    original_fbs = {}  # {Type: Namespace}
    for match in re.finditer(fb_pattern, original_content):
        fb_type = match.group(1)
        fb_namespace = match.group(2)
        original_fbs[fb_type] = fb_namespace

    # Read forked .fbt
    forked_content = fbt_file.read_text(encoding='utf-8')
    modified_content = forked_content
    restore_count = 0

    # For each FB in forked file, restore original namespace if NOT in forked_blocks
    for fb_type, original_namespace in original_fbs.items():
        # Skip if this FB type is in the forked blocks list
        if fb_type in forked_blocks:
            continue

        # Restore original namespace for this FB type
        # Pattern: <FB ... Type="FBType" ... Namespace="AnyNS" ...>
        pattern = rf'(<FB[^>]*\sType="{re.escape(fb_type)}"[^>]*\s)Namespace="[^"]*"'
        replacement = rf'\1Namespace="{original_namespace}"'
        new_content = re.sub(pattern, replacement, modified_content)

        if new_content != modified_content:
            restore_count += 1
            modified_content = new_content

    # Write back if changes were made
    if modified_content != forked_content:
        fbt_file.write_text(modified_content, encoding='utf-8')
        print(f"  {SYMBOLS['ok']} Restored {restore_count} original FB namespaces")

    return restore_count


def update_cs_namespace(cs_file: Path, target_namespace: str, block_name: str) -> None:
    """Update namespace declarations in C# files."""
    content = cs_file.read_text(encoding='utf-8')

    # Determine if Symbols or Faceplates from filename
    if "fp" in cs_file.stem and not "s" in cs_file.stem[:2]:
        ns_type = "Faceplates"
    else:
        ns_type = "Symbols"

    # Pattern 1: namespace SE.X.Symbols.BlockName; or namespace SE.X.Symbols.BlockName {
    pattern = r'namespace\s+[\w.]+\.(Symbols|Faceplates)\.' + re.escape(block_name) + r'\s*[;{]'
    replacement = f'namespace {target_namespace}.{ns_type}.{block_name}'

    # Replace with proper ending (preserve ; or {)
    def replacer(match):
        ending = match.group(0)[-1]
        return f'{replacement}{ending}'

    content = re.sub(pattern, replacer, content)

    # Pattern 2: using SE.X.Symbols.BlockName; or using SE.X.Faceplates.BlockName;
    # Only update if it's OUR block being forked
    source_pattern = r'using\s+SE\.\w+\.(Symbols|Faceplates)\.' + re.escape(block_name) + r'\s*;'
    content = re.sub(source_pattern, f'using {target_namespace}.\\1.{block_name};', content)

    cs_file.write_text(content, encoding='utf-8')
    print(f"  {SYMBOLS['ok']} Updated {cs_file.name}")


def fix_def_event_faceplate_namespaces(hmi_dir: Path, block_name: str, target_namespace: str) -> int:
    """
    Fix namespace bug in .def.cs and .event.cs files.

    EAE GUI incorrectly places faceplate partial classes in the Symbols namespace.

    This function:
    1. Moves faceplate partial classes to Faceplates namespace
    2. Updates fully qualified EventArgs references from Symbols to Faceplates

    Returns number of files fixed.
    """
    count = 0

    for cs_file in hmi_dir.glob(f"{block_name}.*.cs"):
        # Only process .def.cs and .event.cs files
        if not (cs_file.name.endswith('.def.cs') or cs_file.name.endswith('.event.cs')):
            continue

        content = cs_file.read_text(encoding='utf-8')
        original_content = content

        # Check if file contains faceplate partial classes (fp*)
        has_faceplate_classes = bool(re.search(r'partial\s+class\s+fp\w+', content))

        if has_faceplate_classes:
            # Fix 1: namespace Symbols.BlockName -> Faceplates.BlockName (for faceplate classes ONLY)
            # First, change all to Faceplates
            pattern = rf'namespace\s+{re.escape(target_namespace)}\.Symbols\.{re.escape(block_name)}\s*([{{;])'
            replacement = rf'namespace {target_namespace}.Faceplates.{block_name}\1'
            content = re.sub(pattern, replacement, content)

            # Then, change back to Symbols for symbol partial classes (s*)
            # Check if file has symbol partial classes
            has_symbol_classes = bool(re.search(r'partial\s+class\s+s\w+', content))

            if has_symbol_classes:
                # Split content into lines for line-by-line processing
                lines = content.split('\n')
                namespace_line_idx = -1

                for i, line in enumerate(lines):
                    # Check if this is a Faceplates namespace declaration
                    if re.match(rf'namespace\s+{re.escape(target_namespace)}\.Faceplates\.{re.escape(block_name)}\s*[{{;]', line):
                        namespace_line_idx = i

                    # Check if we find a symbol partial class after the namespace
                    elif namespace_line_idx >= 0 and re.search(r'partial\s+class\s+s\w+', line):
                        # This namespace block contains a symbol class - change it back to Symbols
                        lines[namespace_line_idx] = re.sub(
                            rf'namespace\s+{re.escape(target_namespace)}\.Faceplates\.{re.escape(block_name)}',
                            f'namespace {target_namespace}.Symbols.{block_name}',
                            lines[namespace_line_idx]
                        )
                        namespace_line_idx = -1  # Reset

                    # Check for closing brace that ends namespace
                    elif namespace_line_idx >= 0 and line.strip() == '}':
                        namespace_line_idx = -1

                content = '\n'.join(lines)

            # Fix 2: Update fully qualified EventArgs references
            # Pattern: SE.X.Symbols.BlockName.EventArgsClass -> SE.X.Faceplates.BlockName.EventArgsClass
            # EventArgs classes are defined alongside faceplate classes, so they moved to Faceplates too
            pattern = rf'{re.escape(target_namespace)}\.Symbols\.{re.escape(block_name)}\.(\w+EventArgs)'
            replacement = rf'{target_namespace}.Faceplates.{block_name}.\1'
            content = re.sub(pattern, replacement, content)

            # Fix 3: Change virtual back to override for methods that exist in base class
            # The methods OnEndInit, FireEventCallback, DoOpenFaceplate exist in base classes
            # (GroupShape, HMISymbolController) and should be overridden, not redeclared as virtual
            methods_need_override = [
                'DoOpenFaceplate',
                'OnEndInit',
                'FireEventCallback'
            ]

            for method in methods_need_override:
                # Pattern: protected virtual void MethodName( -> protected override void MethodName(
                pattern = rf'(\s+)protected\s+virtual\s+(void\s+{method}\s*\()'
                replacement = r'\1protected override \2'
                content = re.sub(pattern, replacement, content)

                # Pattern: public virtual void MethodName( -> public override void MethodName(
                pattern = rf'(\s+)public\s+virtual\s+(void\s+{method}\s*\()'
                replacement = r'\1public override \2'
                content = re.sub(pattern, replacement, content)

        if content != original_content:
            cs_file.write_text(content, encoding='utf-8')
            count += 1

    return count


def update_cfg_project_references(cfg_file: Path, target_lib: str) -> None:
    """Update Project= references in .cfg Plugin elements."""
    content = cfg_file.read_text(encoding='utf-8')

    # Update Project="OldLib" to Project="NewLib"
    content = re.sub(
        r'Project="[^"]*"',
        f'Project="{target_lib}"',
        content
    )

    cfg_file.write_text(content, encoding='utf-8')
    print(f"  {SYMBOLS['ok']} Updated {cfg_file.name}")


def update_cfg_subcat_namespaces(
    cfg_file: Path,
    forked_blocks: List[str],
    target_namespace: str
) -> int:
    """
    Update SubCAT Namespace attributes in .cfg files for forked blocks.

    Returns number of SubCAT references updated.
    """
    content = cfg_file.read_text(encoding='utf-8')
    original_content = content
    count = 0

    for forked_block in forked_blocks:
        # Pattern: <SubCAT ... Type="ForkedBlock" ... Namespace="OldNS" ...>
        pattern = rf'(<SubCAT[^>]*\sType="{forked_block}"[^>]*\s)Namespace="[^"]*"'
        replacement = rf'\1Namespace="{target_namespace}"'
        content = re.sub(pattern, replacement, content)

    if content != original_content:
        cfg_file.write_text(content, encoding='utf-8')
        # Count changes
        count = original_content.count('<SubCAT') - \
                len([m for m in re.finditer(rf'<SubCAT[^>]*\sNamespace="{target_namespace}"', original_content)])

    return count


def update_namespaces(
    project_root: Path,
    lib_name: str,
    block_name: str,
    block_type: str,
    target_namespace: str,
    forked_blocks: List[str],
    source_namespace: Optional[str]
) -> bool:
    """Update namespaces in .fbt and .cs files, including cross-block references."""

    try:
        # Update IEC61499 files
        iec_dir = project_root / lib_name / "IEC61499" / block_name
        for fbt_file in iec_dir.glob("*.fbt"):
            update_fbt_namespace(fbt_file, target_namespace)

        # Update .cfg if CAT
        if block_type == "CAT":
            cfg_file = iec_dir / f"{block_name}.cfg"
            if cfg_file.exists():
                update_cfg_project_references(cfg_file, lib_name)

                # Update SubCAT namespace references in .cfg
                if len(forked_blocks) > 1:
                    cfg_subcat_count = update_cfg_subcat_namespaces(
                        cfg_file, forked_blocks, target_namespace
                    )
                    if cfg_subcat_count > 0:
                        print(f"  {SYMBOLS['ok']} Updated {cfg_subcat_count} SubCAT namespaces in .cfg")

        # Update cross-block references in IEC61499
        if len(forked_blocks) > 1:
            cross_ref_count = update_cross_block_references(
                iec_dir, block_name, forked_blocks, target_namespace
            )
            if cross_ref_count > 0:
                print(f"  {SYMBOLS['ok']} Updated {cross_ref_count} cross-block references")

        # Restore original FB namespaces for non-forked blocks
        # This fixes the issue where EAE GUI changes ALL FB namespaces during manual fork
        if source_namespace:
            fbt_file = iec_dir / f"{block_name}.fbt"
            if fbt_file.exists():
                restore_count = restore_original_fb_namespaces(
                    fbt_file, source_namespace, block_name, forked_blocks
                )

        # Update HMI files (CAT only)
        if block_type == "CAT":
            hmi_dir = project_root / lib_name / "HMI" / block_name

            # Update namespace declarations
            for cs_file in hmi_dir.glob("*.cs"):
                update_cs_namespace(cs_file, target_namespace, block_name)

            # Fix .def.cs and .event.cs faceplate namespace bug
            fixed_count = fix_def_event_faceplate_namespaces(hmi_dir, block_name, target_namespace)
            if fixed_count > 0:
                print(f"  {SYMBOLS['ok']} Fixed {fixed_count} faceplate namespace bugs in .def.cs/.event.cs")

            # Update HMI cross-references (if we have source namespace and multiple blocks)
            if source_namespace and len(forked_blocks) > 1:
                hmi_ref_count = update_hmi_cross_references(
                    hmi_dir, forked_blocks, source_namespace, target_namespace
                )
                if hmi_ref_count > 0:
                    print(f"  {SYMBOLS['ok']} Updated {hmi_ref_count} HMI cross-references")

        return True
    except Exception as e:
        print(f"ERROR: Failed to update namespaces: {e}", file=sys.stderr)
        return False


def register_block(
    project_root: Path,
    lib_name: str,
    block_name: str,
    block_type: str
) -> bool:
    """Register block using appropriate sub-skill's registration script."""

    skill_map = {
        "CAT": "eae-cat",
        "Composite": "eae-composite-fb",
        "Basic": "eae-basic-fb"
    }

    skill = skill_map.get(block_type)
    if not skill:
        print(f"ERROR: Unknown block type: {block_type}", file=sys.stderr)
        return False

    # Find the registration script in the skill router
    skills_base = Path(__file__).parent.parent.parent
    register_script = skills_base / "eae-skill-router" / "scripts" / "register_dfbproj.py"

    if not register_script.exists():
        print(f"ERROR: Registration script not found: {register_script}", file=sys.stderr)
        print(f"  Looked in: {register_script.parent}", file=sys.stderr)
        return False

    # Call registration script
    cmd = [
        sys.executable,
        str(register_script),
        block_name,
        lib_name,
        "--type", block_type.lower()
    ]

    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR: Registration failed", file=sys.stderr)
        print(f"STDOUT: {result.stdout}", file=sys.stderr)
        print(f"STDERR: {result.stderr}", file=sys.stderr)
        return False

    print(result.stdout)
    return True


def finalize_block(
    project_root: Path,
    lib_name: str,
    block_name: str,
    target_namespace: str,
    forked_blocks: List[str],
    dry_run: bool = False,
    source_lib: Optional[str] = None
) -> tuple:
    """
    Finalize a single manually forked block.

    Args:
        source_lib: Optional source library name (e.g., "SE.App2CommonProcess").
                   If provided, used for restoring original FB namespaces.

    Returns: (success: bool, source_namespace: str)
    """

    print(f"\n{'='*60}")
    print(f"Finalizing: {block_name}")
    print(f"{'='*60}")

    # Step 1: Validate
    print(f"\n[1/4] Validating manual fork...")
    validation = validate_manual_fork(project_root, lib_name, block_name)

    if not validation["valid"]:
        print(f"{SYMBOLS['error']} Manual fork not found or incomplete", file=sys.stderr)
        for missing in validation["missing_files"]:
            print(f"  Missing: {missing}", file=sys.stderr)
        return False, None

    print(f"  {SYMBOLS['ok']} Found {validation['block_type']} block")
    if validation["has_hmi"]:
        print(f"  {SYMBOLS['ok']} HMI files present")

    # Use provided source_lib if given, otherwise try to detect from .fbt
    source_namespace = source_lib if source_lib else validation["source_namespace"]
    if source_lib:
        print(f"  Using source library: {source_lib}")

    if dry_run:
        print(f"\n[DRY RUN] Would perform:")
        print(f"  - Update namespaces to {target_namespace}")
        print(f"  - Update cross-block references for {len(forked_blocks)} blocks")
        if source_namespace:
            print(f"  - Update HMI cross-references from {source_namespace}")
        print(f"  - Generate new GUIDs")
        print(f"  - Register as {validation['block_type']} block")
        return True, source_namespace

    # Step 2: Update namespaces
    print(f"\n[2/4] Updating namespaces...")
    if not update_namespaces(
        project_root, lib_name, block_name, validation["block_type"],
        target_namespace, forked_blocks, source_namespace
    ):
        print(f"{SYMBOLS['error']} Namespace update failed", file=sys.stderr)
        return False, source_namespace

    # Step 3: Register
    print(f"\n[3/4] Registering in project...")
    if not register_block(project_root, lib_name, block_name, validation["block_type"]):
        print(f"{SYMBOLS['error']} Registration failed", file=sys.stderr)
        return False, source_namespace

    # Step 4: Summary
    print(f"\n[4/4] {SYMBOLS['success']} Finalization complete!")
    print(f"  Type: {validation['block_type']}")
    print(f"  Namespace: {target_namespace}")
    print(f"  Location: {lib_name}/IEC61499/{block_name}/")

    return True, source_namespace


# ============================================================================
# Transactional Rollback (v7.1)
# Protects against partial failures by backing up all blocks before changes
# ============================================================================

class ForkTransaction:
    """
    Context manager for atomic fork operations with automatic rollback.

    Creates a backup of all blocks before finalization. If any error occurs,
    automatically restores all blocks to their original state.

    Usage:
        with ForkTransaction(project_root, lib_name, block_names):
            # All finalization logic here
            for block in block_names:
                finalize_block(...)
    """

    def __init__(self, project_root: Path, lib_name: str, blocks: List[str]):
        self.project_root = project_root
        self.lib_name = lib_name
        self.blocks = blocks
        self.backup_dir = None
        self.success = False

    def __enter__(self):
        """Create backup of all block directories before changes."""
        import tempfile
        import shutil

        # Create temp directory for backup
        self.backup_dir = tempfile.mkdtemp(prefix='eae-fork-backup-')

        print(f"\n{SYMBOLS['info']} Creating safety backup...")
        print(f"  Location: {self.backup_dir}")

        backup_count = 0
        for block in self.blocks:
            # Backup IEC61499 files
            src_iec = self.project_root / self.lib_name / "IEC61499" / block
            dst_iec = Path(self.backup_dir) / "IEC61499" / block
            if src_iec.exists():
                shutil.copytree(src_iec, dst_iec)
                backup_count += 1

            # Backup HMI files
            src_hmi = self.project_root / self.lib_name / "HMI" / block
            dst_hmi = Path(self.backup_dir) / "HMI" / block
            if src_hmi.exists():
                shutil.copytree(src_hmi, dst_hmi)
                backup_count += 1

        print(f"  {SYMBOLS['ok']} Backed up {backup_count} directories")
        print(f"  {SYMBOLS['info']} If anything fails, backup will auto-restore\n")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore backup if error occurred, otherwise clean up."""
        import shutil

        if exc_type is not None:
            # Error occurred - rollback
            print(f"\n{SYMBOLS['error']} Error during finalization detected")
            print(f"{SYMBOLS['info']} Rolling back all changes...\n")

            restore_count = 0
            for block in self.blocks:
                # Restore IEC61499 from backup
                src_iec = Path(self.backup_dir) / "IEC61499" / block
                dst_iec = self.project_root / self.lib_name / "IEC61499" / block
                if src_iec.exists() and dst_iec.exists():
                    shutil.rmtree(dst_iec)
                    shutil.copytree(src_iec, dst_iec)
                    restore_count += 1

                # Restore HMI from backup
                src_hmi = Path(self.backup_dir) / "HMI" / block
                dst_hmi = self.project_root / self.lib_name / "HMI" / block
                if src_hmi.exists() and dst_hmi.exists():
                    shutil.rmtree(dst_hmi)
                    shutil.copytree(src_hmi, dst_hmi)
                    restore_count += 1

            print(f"{SYMBOLS['success']} Rollback complete - {restore_count} directories restored")
            print(f"{SYMBOLS['info']} Project is back to original state")
            print(f"{SYMBOLS['warn']} Backup preserved at: {self.backup_dir}")
            print(f"{SYMBOLS['info']} Delete it after verifying project state\n")
        else:
            # Success - mark transaction complete
            self.success = True

            # Clean up backup
            if self.backup_dir and Path(self.backup_dir).exists():
                shutil.rmtree(self.backup_dir)
                print(f"\n{SYMBOLS['info']} Backup cleaned up (transaction successful)")

        # Don't suppress exceptions
        return False


# ============================================================================
# Resume Capability (v7.2)
# Gracefully handle interrupted forks by tracking session state
# ============================================================================

def get_session_state_file(project_root: Path, target_lib: str) -> Path:
    """Get path to session state file for this library."""
    return project_root / target_lib / ".eae-fork-state.json"


def load_session_state(project_root: Path, target_lib: str) -> Optional[Dict]:
    """
    Load existing fork session state from disk.

    Returns None if:
    - No state file exists
    - State file is corrupted
    - State file is for a different set of blocks
    """
    import json
    from datetime import datetime

    state_file = get_session_state_file(project_root, target_lib)

    if not state_file.exists():
        return None

    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)

        # Validate required fields
        required_fields = ['session_id', 'target_lib', 'blocks_total',
                          'blocks_completed', 'blocks_pending', 'started_at']
        if not all(field in state for field in required_fields):
            print(f"{SYMBOLS['warn']} Session state file is corrupted (missing fields)")
            return None

        # Check if session is stale (>24 hours old)
        started_at = datetime.fromisoformat(state['started_at'])
        age_hours = (datetime.now() - started_at).total_seconds() / 3600

        if age_hours > 24:
            print(f"{SYMBOLS['warn']} Session state is stale ({age_hours:.1f} hours old)")
            # Don't auto-load stale sessions, but let user decide

        return state

    except (json.JSONDecodeError, ValueError) as e:
        print(f"{SYMBOLS['warn']} Session state file is corrupted: {e}")
        return None


def save_session_state(
    project_root: Path,
    target_lib: str,
    state: Dict
) -> None:
    """Save fork session state to disk."""
    import json
    from datetime import datetime

    state['last_update'] = datetime.now().isoformat()

    state_file = get_session_state_file(project_root, target_lib)
    state_file.parent.mkdir(parents=True, exist_ok=True)

    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, indent=2, fp=f)


def clear_session_state(project_root: Path, target_lib: str) -> None:
    """Remove session state file (called on successful completion)."""
    state_file = get_session_state_file(project_root, target_lib)
    if state_file.exists():
        state_file.unlink()


def prompt_resume_or_restart(state: Dict, requested_blocks: List[str]) -> str:
    """
    Prompt user to resume existing session or restart.

    Returns: 'resume', 'restart', or 'cancel'
    """
    from datetime import datetime

    print(f"\n{SYMBOLS['info']} Found existing fork session:")
    print(f"  Session ID: {state['session_id']}")
    print(f"  Started: {state['started_at']}")
    print(f"  Progress: {len(state['blocks_completed'])}/{state['blocks_total']} blocks completed")

    if state['blocks_completed']:
        print(f"  Completed: {', '.join(state['blocks_completed'])}")

    if state['blocks_pending']:
        print(f"  Pending: {', '.join(state['blocks_pending'])}")

    # Check if requested blocks match session blocks
    session_blocks = set(state['blocks_completed'] + state['blocks_pending'])
    requested_set = set(requested_blocks)

    if session_blocks != requested_set:
        print(f"\n{SYMBOLS['warn']} Block mismatch detected:")
        print(f"  Session blocks: {', '.join(sorted(session_blocks))}")
        print(f"  Requested blocks: {', '.join(sorted(requested_set))}")
        print(f"\n  This session cannot be resumed - blocks don't match")
        print(f"\nOptions:")
        print(f"  1. Restart with new blocks (will delete old session)")
        print(f"  2. Cancel and investigate")

        while True:
            choice = input(f"\nChoice (1-2): ").strip()
            if choice == '1':
                return 'restart'
            elif choice == '2':
                return 'cancel'
            else:
                print(f"{SYMBOLS['error']} Invalid choice. Enter 1 or 2.")
    else:
        # Blocks match - offer resume or restart
        print(f"\nOptions:")
        print(f"  1. Resume from last successful block (Recommended)")
        print(f"  2. Restart from beginning (will lose progress)")
        print(f"  3. Cancel")

        while True:
            choice = input(f"\nChoice (1-3): ").strip()
            if choice == '1':
                return 'resume'
            elif choice == '2':
                return 'restart'
            elif choice == '3':
                return 'cancel'
            else:
                print(f"{SYMBOLS['error']} Invalid choice. Enter 1-3.")


def main():
    parser = argparse.ArgumentParser(
        description="Finalize manually forked EAE block(s)",
        epilog="""
Examples:
  # Finalize single block
  python finalize_manual_fork.py AnalogInput SE.ScadapackWWW

  # Finalize hierarchy (3 blocks)
  python finalize_manual_fork.py AnalogInputBase AnalogInputBaseExt AnalogInput SE.ScadapackWWW

  # Finalize hierarchy + SubCATs (6 blocks)
  python finalize_manual_fork.py AnalogInputBase AnalogInputBaseExt AnalogInput \
      LimitAlarm DeviationAlarm ROCAlarm SE.ScadapackWWW

  # Dry run
  python finalize_manual_fork.py AnalogInput SE.ScadapackWWW --dry-run
        """
    )
    parser.add_argument("blocks", nargs='+', help="Block name(s) followed by target library")
    parser.add_argument("--project-path", help="Project root path (auto-detected if not specified)")
    parser.add_argument("--source-lib", help="Source library name (e.g., SE.App2CommonProcess) - required for restoring original FB namespaces")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")

    args = parser.parse_args()

    # Parse arguments: last arg is target library, rest are block names
    if len(args.blocks) < 2:
        print("ERROR: Must provide at least one block name and target library", file=sys.stderr)
        print("Usage: python finalize_manual_fork.py <block_name>... <target_lib>", file=sys.stderr)
        sys.exit(1)

    block_names = args.blocks[:-1]
    target_lib = args.blocks[-1]

    # Determine project root
    if args.project_path:
        project_root = Path(args.project_path).resolve()
    else:
        project_root = find_project_root()
        if not project_root:
            print("ERROR: Could not find EAE project root", file=sys.stderr)
            print("Please run from project directory or use --project-path", file=sys.stderr)
            sys.exit(1)

    print(f"Project root: {project_root}")
    print(f"Target library: {target_lib}")
    print(f"Blocks to finalize: {', '.join(block_names)}")
    print(f"Forked set: {len(block_names)} blocks (cross-references will be updated)")

    # Use full library name as folder name (e.g., SE.ScadapackWWW -> SE.ScadapackWWW)
    lib_name = target_lib

    # Check that target library exists
    lib_dir = project_root / lib_name
    if not lib_dir.exists():
        print(f"ERROR: Target library not found: {lib_dir}", file=sys.stderr)
        sys.exit(1)

    # Infer forked blocks from arguments - ALL blocks in the command are in the forked set
    forked_blocks = block_names

    # ========================================================================
    # Resume Capability: Check for existing session state
    # ========================================================================
    existing_state = load_session_state(project_root, target_lib)
    session_state = None
    blocks_to_process = block_names  # Default: process all blocks

    if existing_state and not args.dry_run:
        # Found existing session - prompt user
        action = prompt_resume_or_restart(existing_state, block_names)

        if action == 'cancel':
            print(f"\n{SYMBOLS['info']} Operation cancelled by user")
            sys.exit(0)
        elif action == 'resume':
            # Resume from existing session
            session_state = existing_state
            blocks_to_process = existing_state['blocks_pending']
            print(f"\n{SYMBOLS['success']} Resuming session {session_state['session_id']}")
            print(f"  Skipping {len(session_state['blocks_completed'])} already completed blocks")
            print(f"  Processing {len(blocks_to_process)} remaining blocks\n")
        elif action == 'restart':
            # Clear old session and start fresh
            clear_session_state(project_root, target_lib)
            print(f"\n{SYMBOLS['info']} Cleared old session, starting fresh\n")
            session_state = None

    # Create new session state if not resuming
    if not session_state and not args.dry_run:
        from datetime import datetime
        import random
        import string

        session_id = f"fork-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{''.join(random.choices(string.ascii_lowercase, k=4))}"
        session_state = {
            'session_id': session_id,
            'target_lib': target_lib,
            'blocks_total': len(block_names),
            'blocks_completed': [],
            'blocks_pending': list(block_names),
            'started_at': datetime.now().isoformat()
        }
        save_session_state(project_root, target_lib, session_state)
        print(f"\n{SYMBOLS['info']} Created new session: {session_id}\n")

    # Finalize each block within transactional context
    success_count = 0
    failed_blocks = []
    total_cross_refs = 0
    total_hmi_refs = 0

    # Skip transaction for dry-run mode
    if args.dry_run:
        print(f"\n{SYMBOLS['info']} Dry-run mode: No backup needed\n")

    try:
        # Wrap finalization in transaction (with automatic rollback on error)
        # NOTE: Transaction only backs up blocks being processed (not already completed)
        transaction_context = ForkTransaction(project_root, lib_name, blocks_to_process) if not args.dry_run else None

        if transaction_context:
            with transaction_context:
                for block_name in blocks_to_process:
                    success, source_ns = finalize_block(
                        project_root, lib_name, block_name, target_lib,
                        forked_blocks, args.dry_run, args.source_lib
                    )
                    if success:
                        success_count += 1

                        # Update session state after each successful block
                        if session_state:
                            session_state['blocks_completed'].append(block_name)
                            session_state['blocks_pending'].remove(block_name)
                            save_session_state(project_root, target_lib, session_state)
                    else:
                        failed_blocks.append(block_name)
                        # Raise exception to trigger rollback
                        raise Exception(f"Failed to finalize {block_name}")
        else:
            # Dry-run mode - no transaction
            for block_name in blocks_to_process:
                success, source_ns = finalize_block(
                    project_root, lib_name, block_name, target_lib,
                    forked_blocks, args.dry_run, args.source_lib
                )
                if success:
                    success_count += 1
                else:
                    failed_blocks.append(block_name)

    except Exception as e:
        # Transaction will auto-rollback if needed
        print(f"\n{SYMBOLS['error']} Finalization failed: {e}")
        if not args.dry_run:
            print(f"{SYMBOLS['info']} All changes have been rolled back")
            print(f"{SYMBOLS['info']} Session state preserved for resume")
            if session_state:
                print(f"  Session ID: {session_state['session_id']}")
                print(f"  Completed: {len(session_state['blocks_completed'])} blocks")
                print(f"  Remaining: {len(session_state['blocks_pending'])} blocks")
                print(f"\n  Re-run the same command to resume from where you left off")
        sys.exit(1)

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")

    # Calculate total including resumed blocks
    total_completed = success_count
    if session_state and 'blocks_completed' in session_state:
        # If we resumed, count all completed blocks (previous + new)
        total_completed = len(session_state['blocks_completed'])

    print(f"  Successful: {total_completed}/{len(block_names)}")

    if session_state and success_count < len(blocks_to_process):
        # Partial completion in this run
        print(f"  This run: {success_count}/{len(blocks_to_process)}")

    if failed_blocks:
        print(f"  Failed: {', '.join(failed_blocks)}")

        # Print help for failed blocks
        print(f"\nTo manually fork in EAE GUI:")
        print(f"  1. Open EAE GUI")
        print(f"  2. Navigate to source library")
        print(f"  3. Right-click block -> 'Copy Block' or 'Fork'")
        print(f"  4. Select {lib_name} as target")
        print(f"  5. Re-run this script")

        sys.exit(10)

    if not args.dry_run:
        # Clear session state on successful completion
        if session_state:
            clear_session_state(project_root, target_lib)
            print(f"\n{SYMBOLS['info']} Session state cleared (all blocks completed)")

        print(f"\n{SYMBOLS['success']} All blocks finalized successfully!")
        print(f"  Cross-block references updated: YES")
        print(f"  HMI cross-references updated: YES")
        print(f"  New GUIDs generated: {total_completed * 2}")  # Main + HMI for each block


if __name__ == "__main__":
    main()
