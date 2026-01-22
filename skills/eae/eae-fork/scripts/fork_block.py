#!/usr/bin/env python3
"""
Fork an EAE function block from a source library to a target library.

This script:
1. Locates the source block in Schneider Electric Libraries
2. Copies all block files to the target library
3. Updates namespaces in .fbt and .cfg files
4. Generates new GUIDs for forked blocks

Usage:
    python fork_block.py <block_name> <source_lib> <target_lib> [options]

Example:
    python fork_block.py AnalogInput SE.App2CommonProcess SE.ScadapackWWW
    python fork_block.py AnalogInput SE.App2CommonProcess SE.ScadapackWWW --hierarchy
    python fork_block.py AnalogInput SE.App2CommonProcess SE.ScadapackWWW --dry-run
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# Library location
LIBRARIES_PATH = Path(r"C:\ProgramData\Schneider Electric\Libraries")

# Decompilation cache directory
DECOMPILE_CACHE = Path(tempfile.gettempdir()) / "eae-fork-decompile"

# IEC61499 files to copy for each block
IEC61499_FILES = [
    "{block}.fbt",
    "{block}.cfg",
    "{block}.doc.xml",
    "{block}_HMI.fbt",
    "{block}_CAT.offline.xml",
    "{block}_CAT.opcua.xml",
    "{block}_CAT.aspmap.xml",
    "{block}_CAT.engInstAttrMapping.xml",
    "{block}_HMI.offline.xml",
    "{block}_HMI.opcua.xml",
]

# HMI files patterns (per symbol/faceplate)
# These are complete implementations, NOT stubs
HMI_BASE_FILES = [
    "{block}.def.cs",
    "{block}.event.cs",
    "{block}.Design.resx",
]

# Symbol/faceplate patterns - discovered dynamically from source
HMI_SYMBOL_PATTERNS = [
    "{block}_{symbol}.cnv.cs",
    "{block}_{symbol}.cnv.Designer.cs",
    "{block}_{symbol}.cnv.resx",
]

# Only symbols (not faceplates) have .cnv.xml files
HMI_SYMBOL_XML_PATTERN = "{block}_{symbol}.cnv.xml"

# Known symbol/faceplate prefixes
FACEPLATE_PREFIXES = ["fp"]  # Faceplates start with fp
SYMBOL_PREFIXES = ["s"]  # Symbols start with s


@dataclass
class ForkResult:
    """Result of fork operation."""
    success: bool
    message: str
    files_copied: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def find_library_version(library_name: str) -> Optional[Path]:
    """Find the latest version of a library in the Libraries folder."""
    if not LIBRARIES_PATH.exists():
        return None

    # Look for directories matching library name pattern
    pattern = f"{library_name}-*"
    matches = list(LIBRARIES_PATH.glob(pattern))

    if not matches:
        return None

    # Sort by version (assuming semantic versioning)
    def version_key(p: Path) -> Tuple:
        version_str = p.name.replace(f"{library_name}-", "")
        parts = version_str.split(".")
        return tuple(int(x) if x.isdigit() else 0 for x in parts)

    matches.sort(key=version_key, reverse=True)
    return matches[0]


def find_source_block(library_path: Path, block_name: str) -> Optional[Path]:
    """Find a block in a library's Files directory."""
    files_path = library_path / "Files" / block_name
    if files_path.exists():
        return files_path
    return None


def find_source_hmi(library_path: Path, block_name: str, library_name: str) -> Optional[Path]:
    """
    Find HMI source files for a block.

    Checks:
    1. Files/{Block}/ directory (if source files available)
    2. HMI/{Block}/ directory structure

    Note: Schneider Electric libraries typically compile HMI into DLLs.
    Source files are only available if:
    - The block was previously forked via EAE GUI
    - Source was manually placed in Files directory
    """
    # Check if source HMI files exist in Files directory
    files_hmi_path = library_path / "Files" / block_name
    def_cs = files_hmi_path / f"{block_name}.def.cs"
    if def_cs.exists():
        return files_hmi_path

    # Check HMI subdirectory (some libraries structure it this way)
    hmi_path = library_path / "HMI" / block_name
    def_cs = hmi_path / f"{block_name}.def.cs"
    if def_cs.exists():
        return hmi_path

    # No source files available - would need decompilation
    return None


def check_ilspycmd_available() -> bool:
    """Check if ilspycmd (ILSpy CLI) is available."""
    try:
        result = subprocess.run(
            ["ilspycmd", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def decompile_hmi_dll(library_path: Path, library_name: str) -> Optional[Path]:
    """
    Decompile the HMI DLL for a library using ILSpy CLI.

    Returns the path to the decompiled output directory, or None if failed.
    Caches the decompilation result to avoid repeated decompilation.
    """
    # Find the HMI DLL
    hmi_dll = library_path / "HMI" / f"{library_name}.HMI.dll"
    if not hmi_dll.exists():
        return None

    # Check cache
    cache_dir = DECOMPILE_CACHE / library_name
    cache_marker = cache_dir / ".decompiled"

    if cache_marker.exists():
        # Already decompiled
        return cache_dir

    # Check if ilspycmd is available
    if not check_ilspycmd_available():
        print("Warning: ilspycmd not available. Install with: dotnet tool install -g ilspycmd")
        return None

    # Create cache directory
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Decompile
    print(f"Decompiling {hmi_dll.name}... (this may take a moment)")
    try:
        result = subprocess.run(
            ["ilspycmd", "-p", "-o", str(cache_dir), str(hmi_dll)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout for large DLLs
        )
        if result.returncode == 0:
            # Create marker file
            cache_marker.touch()
            print(f"Decompilation complete: {cache_dir}")
            return cache_dir
        else:
            print(f"Decompilation failed: {result.stderr}")
            return None
    except subprocess.TimeoutExpired:
        print("Decompilation timed out")
        return None
    except Exception as e:
        print(f"Decompilation error: {e}")
        return None


def extract_decompiled_hmi(decompile_dir: Path, block_name: str, source_ns: str,
                           target_path: Path, target_ns: str,
                           forked_blocks: Set[str] = None,
                           dry_run: bool = False) -> Tuple[List[str], List[str]]:
    """
    Extract and transform decompiled HMI files using the standalone decompile_hmi.py script.

    This delegates to the complete implementation in decompile_hmi.py which creates:
    - .cnv.cs files (main implementation)
    - .cnv.Designer.cs files (InitializeComponent)
    - .cnv.resx files (resources)
    - .cnv.xml files (symbol mappings - symbols only)
    - .def.cs and .event.cs files
    - .Design.resx file

    Args:
        decompile_dir: Path to the decompiled HMI output
        block_name: Name of the block being extracted
        source_ns: Source library namespace
        target_path: Target path for extracted files
        target_ns: Target library namespace
        forked_blocks: Set of all blocks being forked (for cross-block refs)
        dry_run: If True, don't write files

    Returns (files_created, warnings)
    """
    files_created = []
    warnings = []

    if forked_blocks is None:
        forked_blocks = {block_name}
    elif block_name not in forked_blocks:
        forked_blocks = forked_blocks | {block_name}

    if dry_run:
        warnings.append(f"Would extract HMI files for {block_name} using decompile_hmi.py")
        return files_created, warnings

    # Call the standalone decompile_hmi.py script
    script_dir = Path(__file__).parent
    decompile_script = script_dir / "decompile_hmi.py"

    if not decompile_script.exists():
        warnings.append(f"decompile_hmi.py not found at {decompile_script}")
        warnings.append("HMI files will not be created - install decompile_hmi.py script")
        return files_created, warnings

    # Build command
    cmd = [
        sys.executable,
        str(decompile_script),
        source_ns,  # source_lib
        block_name,
        target_ns,  # target_namespace
        str(target_path.parent),  # output_dir (HMI/ parent directory)
        "--decompiled-dir", str(decompile_dir),
        "--forked-blocks", *list(forked_blocks)
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            # Parse output to get created files
            for line in result.stdout.split('\n'):
                if 'Created:' in line:
                    file_path = line.split('Created:')[1].strip()
                    file_name = Path(file_path).name
                    files_created.append(file_name)

            # Check if we actually got files
            if target_path.exists():
                actual_files = list(target_path.glob('*'))
                if actual_files:
                    files_created = [f.name for f in actual_files]

            warnings.append(f"Extracting HMI from decompiled DLL for {block_name}")
            warnings.append(f"Preserved library references: SupportClasses, SE.App2Base")
            warnings.append(f"Extracted {len(files_created)} files from decompiled HMI DLL")
        else:
            warnings.append(f"HMI extraction failed: {result.stderr}")
            warnings.append("Some HMI files may be missing")

    except subprocess.TimeoutExpired:
        warnings.append(f"HMI extraction timed out for {block_name}")
    except Exception as e:
        warnings.append(f"HMI extraction error: {e}")

    return files_created, warnings


def generate_hmi_stubs(target_path: Path, block_name: str, target_ns: str,
                       symbols: List[str] = None, dry_run: bool = False) -> Tuple[List[str], List[str]]:
    """
    Generate minimal HMI stub files when source is not available.

    This creates placeholder files that allow the block to compile.
    The HMI can be customized later in the EAE designer.

    Returns (files_created, warnings)
    """
    files_created = []
    warnings = []

    if dry_run:
        return files_created, warnings

    if symbols is None:
        symbols = ["fpDefault", "sDefault"]

    target_path.mkdir(parents=True, exist_ok=True)

    # Generate .def.cs (faceplate accessor definitions)
    def_content = f'''using System;
using System.ComponentModel;
using NxtControl.GuiFramework;

namespace {target_ns}.Faceplates.{block_name}
{{
    // Faceplate accessor stubs - customize in EAE designer
}}

namespace {target_ns}.Symbols.{block_name}
{{
    // Symbol accessor stubs - customize in EAE designer
}}
'''
    def_file = target_path / f"{block_name}.def.cs"
    with open(def_file, "w", encoding="utf-8") as f:
        f.write(def_content)
    files_created.append(f"{block_name}.def.cs")

    # Generate .event.cs (event handlers)
    event_content = f'''using System;
using NxtControl.GuiFramework;

namespace {target_ns}.Faceplates.{block_name}
{{
    // Faceplate event stubs
}}

namespace {target_ns}.Symbols.{block_name}
{{
    // Symbol event stubs
}}
'''
    event_file = target_path / f"{block_name}.event.cs"
    with open(event_file, "w", encoding="utf-8") as f:
        f.write(event_content)
    files_created.append(f"{block_name}.event.cs")

    # Generate symbol/faceplate stubs for each symbol
    for symbol in symbols:
        is_faceplate = symbol.startswith("fp")
        category = "Faceplates" if is_faceplate else "Symbols"
        base_class = "HMIFaceplate" if is_faceplate else "HMISymbol"

        # Main .cnv.cs file
        cnv_content = f'''using System;
using System.ComponentModel;
using NxtControl.GuiFramework;

namespace {target_ns}.{category}.{block_name}
{{
    /// <summary>
    /// {symbol} stub - customize in EAE designer
    /// </summary>
    public partial class {symbol} : {base_class}
    {{
        public {symbol}()
        {{
            InitializeComponent();
        }}
    }}
}}
'''
        cnv_file = target_path / f"{block_name}_{symbol}.cnv.cs"
        with open(cnv_file, "w", encoding="utf-8") as f:
            f.write(cnv_content)
        files_created.append(f"{block_name}_{symbol}.cnv.cs")

        # Designer.cs file
        designer_content = f'''using System;
using System.ComponentModel;
using NxtControl.GuiFramework;

namespace {target_ns}.{category}.{block_name}
{{
    partial class {symbol}
    {{
        private void InitializeComponent()
        {{
            // Designer-generated initialization
        }}
    }}
}}
'''
        designer_file = target_path / f"{block_name}_{symbol}.cnv.Designer.cs"
        with open(designer_file, "w", encoding="utf-8") as f:
            f.write(designer_content)
        files_created.append(f"{block_name}_{symbol}.cnv.Designer.cs")

    warnings.append(f"Generated stub HMI files for {block_name}. Customize in EAE designer.")

    return files_created, warnings


def discover_hmi_symbols(source_path: Path, block_name: str) -> List[str]:
    """
    Discover available symbols/faceplates from source HMI files.

    Returns list of symbol names like ['fpDefault', 'fpParameter', 'sDefault', 'sVertical']
    """
    symbols = []

    if not source_path.exists():
        return symbols

    # Look for .cnv.cs files to discover symbols
    pattern = f"{block_name}_*.cnv.cs"
    for file in source_path.glob(pattern):
        # Extract symbol name: {block}_{symbol}.cnv.cs -> symbol
        filename = file.stem.replace(".cnv", "")  # Remove .cnv
        parts = filename.split("_", 1)
        if len(parts) == 2:
            symbol = parts[1]
            if symbol not in symbols:
                symbols.append(symbol)

    return symbols


def copy_hmi_files(source_path: Path, target_path: Path, block_name: str,
                   dry_run: bool = False) -> Tuple[List[str], List[str]]:
    """
    Copy HMI files from source to target.

    Returns (files_copied, errors)
    """
    files_copied = []
    errors = []

    if not source_path.exists():
        errors.append(f"Source HMI path not found: {source_path}")
        return files_copied, errors

    if not dry_run:
        target_path.mkdir(parents=True, exist_ok=True)

    # Copy base files
    for pattern in HMI_BASE_FILES:
        filename = pattern.format(block=block_name)
        source_file = source_path / filename
        target_file = target_path / filename

        if source_file.exists():
            if not dry_run:
                shutil.copy2(source_file, target_file)
            files_copied.append(filename)

    # Discover and copy symbol/faceplate files
    symbols = discover_hmi_symbols(source_path, block_name)

    for symbol in symbols:
        # Copy standard files for each symbol
        for pattern in HMI_SYMBOL_PATTERNS:
            filename = pattern.format(block=block_name, symbol=symbol)
            source_file = source_path / filename
            target_file = target_path / filename

            if source_file.exists():
                if not dry_run:
                    shutil.copy2(source_file, target_file)
                files_copied.append(filename)

        # Only symbols (not faceplates) have .cnv.xml files
        is_faceplate = any(symbol.startswith(p) for p in FACEPLATE_PREFIXES)
        if not is_faceplate:
            xml_filename = HMI_SYMBOL_XML_PATTERN.format(block=block_name, symbol=symbol)
            source_xml = source_path / xml_filename
            target_xml = target_path / xml_filename

            if source_xml.exists():
                if not dry_run:
                    shutil.copy2(source_xml, target_xml)
                files_copied.append(xml_filename)

    return files_copied, errors


def update_hmi_namespace(file_path: Path, source_ns: str, target_ns: str,
                         forked_blocks: Set[str] = None,
                         dry_run: bool = False) -> Tuple[bool, List[str]]:
    """
    Update C# namespace in HMI file with proper handling of different reference types.

    Namespace Reference Categories:
    1. Block-specific (Symbols/Faceplates.{Block}) - UPDATE if block is forked
    2. Cross-block references - UPDATE only if referenced block is in forked set
    3. SupportClasses - ALWAYS KEEP (library-wide utilities)
    4. Base library (SE.App2Base.*) - ALWAYS KEEP
    5. Framework (System.*, NxtControl.*) - ALWAYS KEEP

    Args:
        file_path: Path to the C# file
        source_ns: Source library namespace (e.g., SE.App2CommonProcess)
        target_ns: Target library namespace (e.g., SE.ScadapackWWW)
        forked_blocks: Set of block names that are being forked (for cross-block refs)
        dry_run: If True, don't write changes
    """
    changes = []

    if forked_blocks is None:
        forked_blocks = set()

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # IMPORTANT: Skip SupportClasses - these should NEVER be updated
        # SupportClasses contains library-wide utility classes shared across all blocks
        # Pattern to detect and preserve: {SourceNS}.SupportClasses
        # We handle this by explicitly NOT matching SupportClasses in our patterns

        # Pattern 1: namespace declarations (only for forked blocks)
        # namespace SE.App2CommonProcess.Symbols.AnalogInputBase
        pattern1 = re.compile(
            rf'namespace\s+{re.escape(source_ns)}\.(Symbols|Faceplates)\.(\w+)',
            re.MULTILINE
        )

        def replace_ns(match):
            category = match.group(1)  # Symbols or Faceplates
            block = match.group(2)
            # Only update if this block is in the forked set
            if block in forked_blocks or not forked_blocks:
                return f'namespace {target_ns}.{category}.{block}'
            return match.group(0)  # Keep original

        content, count1 = pattern1.subn(replace_ns, content)
        if count1 > 0:
            changes.append(f"Updated {count1} namespace declaration(s)")

        # Pattern 2: Using directives for Symbols/Faceplates (only for forked blocks)
        # using SE.App2CommonProcess.Symbols.AnalogInputBase;
        # using SE.App2CommonProcess.Faceplates.AnalogInputBase;
        pattern2 = re.compile(
            rf'using\s+{re.escape(source_ns)}\.(Symbols|Faceplates)\.(\w+)\s*;',
            re.MULTILINE
        )

        def replace_using(match):
            category = match.group(1)  # Symbols or Faceplates
            block = match.group(2)
            # Only update if this block is in the forked set
            if block in forked_blocks or not forked_blocks:
                return f'using {target_ns}.{category}.{block};'
            return match.group(0)  # Keep original

        content, count2 = pattern2.subn(replace_using, content)
        if count2 > 0:
            changes.append(f"Updated {count2} using directive(s)")

        # Pattern 3: Fully qualified type references (only for forked blocks)
        # SE.App2CommonProcess.Symbols.AnalogInputBase.sDefault
        # new SE.App2CommonProcess.Symbols.AnalogInputBase.sDefault()
        pattern3 = re.compile(
            rf'{re.escape(source_ns)}\.(Symbols|Faceplates)\.(\w+)\.(\w+)',
            re.MULTILINE
        )

        def replace_type(match):
            category = match.group(1)
            block = match.group(2)
            cls = match.group(3)
            # Only update if this block is in the forked set
            if block in forked_blocks or not forked_blocks:
                return f'{target_ns}.{category}.{block}.{cls}'
            return match.group(0)  # Keep original

        content, count3 = pattern3.subn(replace_type, content)
        if count3 > 0:
            changes.append(f"Updated {count3} type reference(s)")

        # Pattern 4: Simple Symbols/Faceplates namespace reference (without class)
        # SE.App2CommonProcess.Symbols.AnalogInputBase (without trailing .ClassName)
        # This handles cases like typeof(SE.App2CommonProcess.Symbols.AnalogInputBase)
        pattern4 = re.compile(
            rf'(?<!\.)({re.escape(source_ns)})\.(Symbols|Faceplates)\.(\w+)(?!\.)',
            re.MULTILINE
        )

        def replace_simple(match):
            ns = match.group(1)
            category = match.group(2)
            block = match.group(3)
            # Only update if this block is in the forked set
            if block in forked_blocks or not forked_blocks:
                return f'{target_ns}.{category}.{block}'
            return match.group(0)  # Keep original

        content, count4 = pattern4.subn(replace_simple, content)
        if count4 > 0:
            changes.append(f"Updated {count4} simple namespace reference(s)")

        # NOTE: We explicitly do NOT update:
        # - {source_ns}.SupportClasses - shared utility classes
        # - SE.App2Base.* - base library references
        # - System.*, NxtControl.* - framework references

        if content != original_content:
            if not dry_run:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
            # Track which references were preserved
            if f'{source_ns}.SupportClasses' in original_content:
                changes.append(f"Preserved {source_ns}.SupportClasses reference(s)")
            if 'SE.App2Base.' in original_content:
                changes.append("Preserved SE.App2Base.* reference(s)")

        return True, changes

    except Exception as e:
        return False, [f"Error updating {file_path}: {str(e)}"]


def generate_guid() -> str:
    """Generate a new GUID for a forked block."""
    return str(uuid.uuid4())


def update_fbt_namespace(fbt_path: Path, source_ns: str, target_ns: str,
                         forked_blocks: Set[str], dry_run: bool = False) -> Tuple[bool, List[str]]:
    """
    Update namespace in .fbt file.

    - Updates root FBType namespace
    - Updates references to forked sub-blocks
    - Keeps original namespaces for non-forked blocks
    - Generates new GUID
    """
    changes = []

    try:
        # Read file content
        with open(fbt_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Parse XML
        tree = ET.parse(fbt_path)
        root = tree.getroot()

        # Update root namespace
        old_ns = root.get("Namespace", "")
        if old_ns == source_ns:
            root.set("Namespace", target_ns)
            changes.append(f"Updated root namespace: {source_ns} -> {target_ns}")

        # Generate new GUID
        old_guid = root.get("GUID", "")
        new_guid = generate_guid()
        root.set("GUID", new_guid)
        changes.append(f"Generated new GUID: {new_guid} (was: {old_guid})")

        # Update sub-block references for forked blocks only
        for fb in root.iter("FB"):
            fb_type = fb.get("Type", "")
            fb_ns = fb.get("Namespace", "")

            if fb_type in forked_blocks and fb_ns == source_ns:
                fb.set("Namespace", target_ns)
                fb_name = fb.get("Name", fb_type)
                changes.append(f"Updated sub-block '{fb_name}' ({fb_type}): {source_ns} -> {target_ns}")

        # Update SubCAT references in .cfg-like sections (if embedded)
        for subcat in root.iter("SubCAT"):
            subcat_type = subcat.get("Type", "")
            subcat_ns = subcat.get("Namespace", "")

            if subcat_type in forked_blocks and subcat_ns == source_ns:
                subcat.set("Namespace", target_ns)
                subcat_name = subcat.get("Name", subcat_type)
                changes.append(f"Updated SubCAT '{subcat_name}' ({subcat_type}): {source_ns} -> {target_ns}")

        if not dry_run:
            # Write back with proper XML declaration
            tree.write(fbt_path, encoding="utf-8", xml_declaration=True)

            # Re-read and fix DOCTYPE (ElementTree doesn't preserve DOCTYPE)
            with open(fbt_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Add DOCTYPE if it was in original
            if "<!DOCTYPE" in original_content and "<!DOCTYPE" not in content:
                # Extract DOCTYPE from original
                doctype_match = re.search(r'<!DOCTYPE[^>]+>', original_content)
                if doctype_match:
                    doctype = doctype_match.group(0)
                    content = content.replace(
                        '<?xml version="1.0" encoding="utf-8"?>',
                        f'<?xml version="1.0" encoding="utf-8"?>\n{doctype}'
                    )
                    with open(fbt_path, "w", encoding="utf-8") as f:
                        f.write(content)

        return True, changes

    except Exception as e:
        return False, [f"Error updating {fbt_path}: {str(e)}"]


def update_cfg_namespace(cfg_path: Path, source_ns: str, target_ns: str,
                         forked_blocks: Set[str], dry_run: bool = False) -> Tuple[bool, List[str]]:
    """
    Update namespace references in .cfg file.

    Updates:
    - SubCAT namespace references for forked blocks
    - Plugin Project attributes from source to target library
    """
    changes = []

    try:
        # Read original content to preserve formatting
        with open(cfg_path, "r", encoding="utf-8") as f:
            original_content = f.read()

        tree = ET.parse(cfg_path)
        root = tree.getroot()

        # Handle XML namespace
        ns = {"": "http://www.nxtcontrol.com/IEC61499.xsd"}

        # Update SubCAT namespace references for forked blocks
        # Try both with and without namespace
        for subcat in list(root.iter("SubCAT")) + list(root.iter("{http://www.nxtcontrol.com/IEC61499.xsd}SubCAT")):
            subcat_type = subcat.get("Type", "")
            subcat_ns = subcat.get("Namespace", "")

            if subcat_type in forked_blocks and subcat_ns == source_ns:
                subcat.set("Namespace", target_ns)
                subcat_name = subcat.get("Name", subcat_type)
                changes.append(f"Updated SubCAT '{subcat_name}' ({subcat_type}): {source_ns} -> {target_ns}")

        # Update Plugin Project attributes
        for plugin in list(root.iter("Plugin")) + list(root.iter("{http://www.nxtcontrol.com/IEC61499.xsd}Plugin")):
            project = plugin.get("Project", "")
            if project == source_ns:
                plugin.set("Project", target_ns)
                plugin_name = plugin.get("Name", "")
                # Extract just the plugin type from the Name attribute
                plugin_type = plugin_name.split(";")[0].replace("Plugin=", "") if ";" in plugin_name else plugin_name
                changes.append(f"Updated Plugin Project '{plugin_type}': {source_ns} -> {target_ns}")

        if not dry_run and changes:
            # Write with ElementTree
            tree.write(cfg_path, encoding="utf-8", xml_declaration=True)

            # Fix namespace prefix issues - ElementTree adds ns0: prefixes
            with open(cfg_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Remove ns0: prefixes and restore default namespace
            content = re.sub(r'<ns0:', '<', content)
            content = re.sub(r'</ns0:', '</', content)
            content = re.sub(r'xmlns:ns0=', 'xmlns=', content)

            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write(content)

        return True, changes

    except Exception as e:
        return False, [f"Error updating {cfg_path}: {str(e)}"]


def get_block_dependencies(fbt_path: Path, source_ns: str) -> Set[str]:
    """Get list of sub-blocks from the same source namespace (potential fork candidates)."""
    deps = set()

    try:
        tree = ET.parse(fbt_path)
        root = tree.getroot()

        for fb in root.iter("FB"):
            fb_type = fb.get("Type", "")
            fb_ns = fb.get("Namespace", "")

            if fb_ns == source_ns:
                deps.add(fb_type)

    except Exception:
        pass

    return deps


def detect_hierarchy(block_name: str, source_path: Path, source_ns: str) -> List[str]:
    """
    Detect block hierarchy (Base -> BaseExt -> Full).

    Returns list of blocks to fork in order (base first).
    """
    hierarchy = []

    # Common patterns
    patterns = [
        f"{block_name}Base",
        f"{block_name}BaseExt",
        block_name
    ]

    for pattern in patterns:
        pattern_path = source_path.parent / pattern
        if pattern_path.exists():
            hierarchy.append(pattern)

    return hierarchy


def fork_block(block_name: str, source_lib: str, target_lib: str,
               project_path: Path, forked_blocks: Set[str],
               dry_run: bool = False) -> ForkResult:
    """Fork a single block from source to target library."""

    result = ForkResult(success=False, message="")

    # Find source library
    source_lib_path = find_library_version(source_lib)
    if not source_lib_path:
        result.message = f"Source library not found: {source_lib}"
        result.errors.append(f"Searched in: {LIBRARIES_PATH}")
        return result

    # Find source block
    source_block_path = find_source_block(source_lib_path, block_name)
    if not source_block_path:
        result.message = f"Block not found: {block_name}"
        result.errors.append(f"Searched in: {source_lib_path / 'Files'}")
        return result

    # Prepare target paths
    target_iec_path = project_path / target_lib / "IEC61499" / block_name
    target_hmi_path = project_path / target_lib / "HMI" / block_name

    # Create target directories
    if not dry_run:
        target_iec_path.mkdir(parents=True, exist_ok=True)

    result.message = f"Forking {block_name} from {source_lib} to {target_lib}"

    # =========================================================
    # Step 1: Copy IEC61499 files
    # =========================================================
    for file_pattern in IEC61499_FILES:
        filename = file_pattern.format(block=block_name)
        source_file = source_block_path / filename
        target_file = target_iec_path / filename

        if source_file.exists():
            if not dry_run:
                shutil.copy2(source_file, target_file)
            result.files_copied.append(f"IEC61499/{block_name}/{filename}")

    # =========================================================
    # Step 2: Update .fbt namespace and GUID
    # =========================================================
    fbt_file = target_iec_path / f"{block_name}.fbt"
    if fbt_file.exists() or (dry_run and (source_block_path / f"{block_name}.fbt").exists()):
        actual_path = fbt_file if fbt_file.exists() else source_block_path / f"{block_name}.fbt"
        success, changes = update_fbt_namespace(
            actual_path,
            source_lib, target_lib, forked_blocks, dry_run
        )
        if success:
            result.files_modified.append(f"{block_name}.fbt")
            for change in changes:
                result.warnings.append(change)  # Using warnings for info messages
        else:
            result.errors.extend(changes)

    # Update _HMI.fbt namespace (same as main .fbt)
    hmi_fbt_file = target_iec_path / f"{block_name}_HMI.fbt"
    if hmi_fbt_file.exists() or (dry_run and (source_block_path / f"{block_name}_HMI.fbt").exists()):
        actual_path = hmi_fbt_file if hmi_fbt_file.exists() else source_block_path / f"{block_name}_HMI.fbt"
        success, changes = update_fbt_namespace(
            actual_path,
            source_lib, target_lib, forked_blocks, dry_run
        )
        if success:
            result.files_modified.append(f"{block_name}_HMI.fbt")
            for change in changes:
                result.warnings.append(change)
        else:
            result.errors.extend(changes)

    # =========================================================
    # Step 3: Update .cfg namespace
    # =========================================================
    cfg_file = target_iec_path / f"{block_name}.cfg"
    if cfg_file.exists() or (dry_run and (source_block_path / f"{block_name}.cfg").exists()):
        actual_path = cfg_file if cfg_file.exists() else source_block_path / f"{block_name}.cfg"
        success, changes = update_cfg_namespace(
            actual_path,
            source_lib, target_lib, forked_blocks, dry_run
        )
        if success and changes:
            result.files_modified.append(f"{block_name}.cfg")
            for change in changes:
                result.warnings.append(change)
        elif not success:
            result.errors.extend(changes)

    # =========================================================
    # Step 4: Copy HMI files from source
    # =========================================================
    source_hmi_path = find_source_hmi(source_lib_path, block_name, source_lib)
    if source_hmi_path:
        if not dry_run:
            target_hmi_path.mkdir(parents=True, exist_ok=True)

        hmi_files, hmi_errors = copy_hmi_files(
            source_hmi_path, target_hmi_path, block_name, dry_run
        )
        for hmi_file in hmi_files:
            result.files_copied.append(f"HMI/{block_name}/{hmi_file}")
        result.errors.extend(hmi_errors)

        # =========================================================
        # Step 5: Update HMI file namespaces
        # =========================================================
        if not dry_run and hmi_files:
            # Update namespace in all .cs files
            # Pass forked_blocks to handle cross-block references properly
            for cs_file in target_hmi_path.glob("*.cs"):
                success, changes = update_hmi_namespace(
                    cs_file, source_lib, target_lib, forked_blocks, dry_run
                )
                if success and changes:
                    result.files_modified.append(f"HMI/{block_name}/{cs_file.name}")
                    for change in changes:
                        result.warnings.append(f"{cs_file.name}: {change}")
                elif not success:
                    result.errors.extend(changes)
    else:
        # No source HMI files found - try decompilation first
        decompile_dir = decompile_hmi_dll(source_lib_path, source_lib)
        hmi_extracted = False

        if decompile_dir:
            # Check if block exists in decompiled output
            faceplates_dir = decompile_dir / f"{source_lib}.Faceplates.{block_name}"
            symbols_dir = decompile_dir / f"{source_lib}.Symbols.{block_name}"

            if faceplates_dir.exists() or symbols_dir.exists():
                # Extract from decompiled HMI
                # Pass forked_blocks to handle cross-block references properly
                result.warnings.append(f"Extracting HMI from decompiled DLL for {block_name}")
                decompiled_files, decompile_warnings = extract_decompiled_hmi(
                    decompile_dir, block_name, source_lib,
                    target_hmi_path, target_lib, forked_blocks, dry_run
                )
                for df in decompiled_files:
                    result.files_copied.append(f"HMI/{block_name}/{df}")
                result.warnings.extend(decompile_warnings)
                hmi_extracted = True
            else:
                result.warnings.append(f"Block {block_name} not found in decompiled HMI - generating stubs")

        if not hmi_extracted:
            # Decompilation not available or block not found - generate stubs
            if not decompile_dir:
                result.warnings.append(f"HMI decompilation not available - generating stubs")

            # Try to discover symbols from .cfg file
            cfg_file = target_iec_path / f"{block_name}.cfg"
            symbols = []
            if cfg_file.exists():
                try:
                    tree = ET.parse(cfg_file)
                    root = tree.getroot()
                    # Look for Symbol elements (with or without namespace)
                    for symbol in list(root.iter("Symbol")) + list(root.iter("{http://www.nxtcontrol.com/IEC61499.xsd}Symbol")):
                        symbol_name = symbol.get("Name", "")
                        if symbol_name:
                            symbols.append(symbol_name)
                except Exception:
                    pass

            if not symbols:
                symbols = ["fpDefault", "sDefault"]  # Default symbols

            stub_files, stub_warnings = generate_hmi_stubs(
                target_hmi_path, block_name, target_lib, symbols, dry_run
            )
            for stub_file in stub_files:
                result.files_copied.append(f"HMI/{block_name}/{stub_file} (stub)")
            result.warnings.extend(stub_warnings)

    if not result.errors:
        result.success = True

    return result


def fork_with_hierarchy(block_name: str, source_lib: str, target_lib: str,
                        project_path: Path, dry_run: bool = False) -> List[ForkResult]:
    """Fork a block and its hierarchy (Base -> BaseExt -> Full)."""

    results = []

    # Find source library
    source_lib_path = find_library_version(source_lib)
    if not source_lib_path:
        results.append(ForkResult(
            success=False,
            message=f"Source library not found: {source_lib}",
            errors=[f"Searched in: {LIBRARIES_PATH}"]
        ))
        return results

    # Find source block
    source_block_path = find_source_block(source_lib_path, block_name)
    if not source_block_path:
        results.append(ForkResult(
            success=False,
            message=f"Block not found: {block_name}",
            errors=[f"Searched in: {source_lib_path / 'Files'}"]
        ))
        return results

    # Detect hierarchy
    hierarchy = detect_hierarchy(block_name, source_block_path, source_lib)
    forked_blocks = set(hierarchy)

    print(f"Detected hierarchy: {' -> '.join(hierarchy)}")

    # Fork each block in order (base first)
    for block in hierarchy:
        result = fork_block(block, source_lib, target_lib, project_path, forked_blocks, dry_run)
        results.append(result)

    return results


def list_library_blocks(library_name: str) -> Optional[List[str]]:
    """List all blocks in a library."""
    lib_path = find_library_version(library_name)
    if not lib_path:
        return None

    files_path = lib_path / "Files"
    if not files_path.exists():
        return None

    blocks = []
    for item in files_path.iterdir():
        if item.is_dir() and (item / f"{item.name}.fbt").exists():
            blocks.append(item.name)

    return sorted(blocks)


def print_fork_report(results: List[ForkResult]) -> None:
    """Print formatted fork report."""
    print(f"\n{'='*60}")
    print("Fork Operation Report")
    print(f"{'='*60}\n")

    total_success = sum(1 for r in results if r.success)

    for result in results:
        status = "[OK]" if result.success else "[FAIL]"
        print(f"{status} {result.message}")

        if result.files_copied:
            print(f"    Files copied: {', '.join(result.files_copied)}")

        if result.files_modified:
            print(f"    Files modified: {', '.join(result.files_modified)}")

        for info in result.warnings:
            print(f"    - {info}")

        for error in result.errors:
            print(f"    [ERROR] {error}")

        print()

    print(f"{'='*60}")
    print(f"RESULT: {total_success}/{len(results)} blocks forked successfully")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Fork EAE function blocks from Schneider Electric libraries"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Fork command
    fork_parser = subparsers.add_parser("fork", help="Fork a block")
    fork_parser.add_argument("block_name", help="Block to fork (e.g., AnalogInput)")
    fork_parser.add_argument("source_lib", help="Source library (e.g., SE.App2CommonProcess)")
    fork_parser.add_argument("target_lib", help="Target library (e.g., SE.ScadapackWWW)")
    fork_parser.add_argument("--project-path", "-p", help="Project path (auto-detected if not specified)")
    fork_parser.add_argument("--hierarchy", "-H", action="store_true",
                             help="Fork entire hierarchy (Base -> BaseExt -> Full)")
    fork_parser.add_argument("--dry-run", "-n", action="store_true",
                             help="Show what would be done without making changes")

    # List command
    list_parser = subparsers.add_parser("list", help="List blocks in a library")
    list_parser.add_argument("library_name", help="Library name (e.g., SE.App2CommonProcess)")

    args = parser.parse_args()

    if args.command == "list":
        blocks = list_library_blocks(args.library_name)
        if blocks is None:
            print(f"Library not found: {args.library_name}")
            sys.exit(1)
        print(f"\nBlocks in {args.library_name} ({len(blocks)} total):\n")
        for block in blocks:
            print(f"  {block}")
        sys.exit(0)

    elif args.command == "fork":
        # Find project path
        if args.project_path:
            project_path = Path(args.project_path)
        else:
            project_path = Path.cwd()
            # Walk up to find project root
            for parent in [project_path] + list(project_path.parents):
                if (parent / "IEC61499").exists() or list(parent.glob("*.eaproj")):
                    project_path = parent
                    break

        print(f"Project path: {project_path}")
        print(f"Source: {args.source_lib}")
        print(f"Target: {args.target_lib}")

        if args.dry_run:
            print("\n[DRY RUN - No changes will be made]\n")

        if args.hierarchy:
            results = fork_with_hierarchy(
                args.block_name, args.source_lib, args.target_lib,
                project_path, args.dry_run
            )
        else:
            forked_blocks = {args.block_name}
            result = fork_block(
                args.block_name, args.source_lib, args.target_lib,
                project_path, forked_blocks, args.dry_run
            )
            results = [result]

        print_fork_report(results)

        # Exit code
        all_success = all(r.success for r in results)
        sys.exit(0 if all_success else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
