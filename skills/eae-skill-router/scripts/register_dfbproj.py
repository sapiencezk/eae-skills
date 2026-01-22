#!/usr/bin/env python3
"""
Universal dfbproj registration for all EAE item types.

This script adds the necessary ItemGroup entries to make blocks
visible in the EAE library browser. Supports all item types:
- CAT (Composite Application Type)
- Composite (Composite Function Block)
- Basic (Basic Function Block)
- Adapter
- DataType

Usage:
    python register_dfbproj.py <block_name> <target_lib> --type <type> [options]

Example:
    python register_dfbproj.py AnalogInput SE.ScadapackWWW --type cat
    python register_dfbproj.py MyComposite SE.ScadapackWWW --type composite
    python register_dfbproj.py MyLogic SE.ScadapackWWW --type basic
    python register_dfbproj.py IAnalog SE.ScadapackWWW --type adapter
    python register_dfbproj.py Status SE.ScadapackWWW --type datatype
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class RegistrationResult:
    """Result of dfbproj registration."""
    success: bool
    message: str
    entries_added: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# Registration templates for each item type
TEMPLATES = {
    "cat": '''  <!-- {block_name} CAT Block -->
  <ItemGroup>
    <Compile Include="{block_name}\\{block_name}.fbt">
      <IEC61499Type>CAT</IEC61499Type>
    </Compile>
    <Compile Include="{block_name}\\{block_name}_HMI.fbt">
      <IEC61499Type>CAT</IEC61499Type>
      <Usage>Private</Usage>
      <DependentUpon>{block_name}.fbt</DependentUpon>
      <HMI>..\\HMI\\{block_name}\\{block_name}_sDefault.cnv.cs</HMI>
    </Compile>
  </ItemGroup>
  <ItemGroup>
    <None Include="{block_name}\\{block_name}.cfg">
      <DependentUpon>{block_name}.fbt</DependentUpon>
      <IEC61499Type>CAT</IEC61499Type>
    </None>
    <None Include="{block_name}\\{block_name}_CAT.offline.xml">
      <DependentUpon>{block_name}.fbt</DependentUpon>
      <Plugin>OfflineParametrizationEditor</Plugin>
      <IEC61499Type>CAT_OFFLINE</IEC61499Type>
    </None>
    <None Include="{block_name}\\{block_name}_CAT.opcua.xml">
      <DependentUpon>{block_name}.fbt</DependentUpon>
      <Plugin>OPCUAConfigurator</Plugin>
      <IEC61499Type>CAT_OPCUA</IEC61499Type>
    </None>
    <None Include="{block_name}\\{block_name}_CAT.aspmap.xml">
      <DependentUpon>{block_name}.fbt</DependentUpon>
      <IEC61499Type>CAT_ASPMAP</IEC61499Type>
    </None>
  </ItemGroup>
''',

    "composite": '''  <!-- {block_name} Composite FB -->
  <ItemGroup>
    <None Include="{block_name}\\{block_name}.doc.xml">
      <DependentUpon>{block_name}.fbt</DependentUpon>
    </None>
    <None Include="{block_name}\\{block_name}.meta.xml">
      <DependentUpon>{block_name}.fbt</DependentUpon>
    </None>
    <None Include="{block_name}\\{block_name}.composite.offline.xml">
      <DependentUpon>{block_name}.fbt</DependentUpon>
      <Plugin>OfflineParametrizationEditor</Plugin>
      <IEC61499Type>COMPOSITE_OFFLINE</IEC61499Type>
    </None>
  </ItemGroup>
  <ItemGroup>
    <Compile Include="{block_name}\\{block_name}.fbt">
      <IEC61499Type>Composite</IEC61499Type>
    </Compile>
  </ItemGroup>
''',

    "basic": '''  <!-- {block_name} Basic FB -->
  <ItemGroup>
    <None Include="{block_name}\\{block_name}.doc.xml">
      <DependentUpon>{block_name}.fbt</DependentUpon>
    </None>
    <None Include="{block_name}\\{block_name}.meta.xml">
      <DependentUpon>{block_name}.fbt</DependentUpon>
    </None>
  </ItemGroup>
  <ItemGroup>
    <Compile Include="{block_name}\\{block_name}.fbt">
      <IEC61499Type>Basic</IEC61499Type>
    </Compile>
  </ItemGroup>
''',

    "adapter": '''  <!-- {block_name} Adapter -->
  <ItemGroup>
    <None Include="{block_name}\\{block_name}.doc.xml">
      <DependentUpon>{block_name}.adp</DependentUpon>
    </None>
  </ItemGroup>
  <ItemGroup>
    <Compile Include="{block_name}\\{block_name}.adp">
      <IEC61499Type>Adapter</IEC61499Type>
    </Compile>
  </ItemGroup>
''',

    "datatype": '''  <!-- {block_name} DataType -->
  <ItemGroup>
    <None Include="DataType\\{block_name}.doc.xml">
      <DependentUpon>{block_name}.dt</DependentUpon>
    </None>
  </ItemGroup>
  <ItemGroup>
    <Compile Include="DataType\\{block_name}.dt">
      <IEC61499Type>DataType</IEC61499Type>
    </Compile>
  </ItemGroup>
''',
}

# File patterns for checking if already registered
CHECK_PATTERNS = {
    "cat": r'<Compile Include="{block_name}\\{block_name}\.fbt"',
    "composite": r'<Compile Include="{block_name}\\{block_name}\.fbt"',
    "basic": r'<Compile Include="{block_name}\\{block_name}\.fbt"',
    "adapter": r'<Compile Include="{block_name}\\{block_name}\.adp"',
    "datatype": r'<Compile Include="DataType\\{block_name}\.dt"',
}

# Entries list for reporting
ENTRIES = {
    "cat": [
        "{block_name}\\{block_name}.fbt (Compile/CAT)",
        "{block_name}\\{block_name}_HMI.fbt (Compile/CAT)",
        "{block_name}\\{block_name}.cfg (None/CAT)",
        "{block_name}\\{block_name}_CAT.offline.xml (None/CAT_OFFLINE)",
        "{block_name}\\{block_name}_CAT.opcua.xml (None/CAT_OPCUA)",
        "{block_name}\\{block_name}_CAT.aspmap.xml (None/CAT_ASPMAP)",
    ],
    "composite": [
        "{block_name}\\{block_name}.fbt (Compile/Composite)",
        "{block_name}\\{block_name}.doc.xml (None)",
        "{block_name}\\{block_name}.meta.xml (None)",
        "{block_name}\\{block_name}.composite.offline.xml (None/COMPOSITE_OFFLINE)",
    ],
    "basic": [
        "{block_name}\\{block_name}.fbt (Compile/Basic)",
        "{block_name}\\{block_name}.doc.xml (None)",
        "{block_name}\\{block_name}.meta.xml (None)",
    ],
    "adapter": [
        "{block_name}\\{block_name}.adp (Compile/Adapter)",
        "{block_name}\\{block_name}.doc.xml (None)",
    ],
    "datatype": [
        "DataType\\{block_name}.dt (Compile/DataType)",
        "DataType\\{block_name}.doc.xml (None)",
    ],
}


def find_dfbproj(target_lib: str, project_path: Path) -> Optional[Path]:
    """Find the .dfbproj file for the target library."""
    dfbproj_path = project_path / target_lib / "IEC61499" / f"{target_lib}.dfbproj"
    if dfbproj_path.exists():
        return dfbproj_path
    return None


def check_registration_exists(dfbproj_path: Path, block_name: str, item_type: str) -> bool:
    """Check if block is already registered in dfbproj."""
    try:
        with open(dfbproj_path, "r", encoding="utf-8") as f:
            content = f.read()

        pattern = CHECK_PATTERNS[item_type].format(block_name=block_name)
        return bool(re.search(pattern, content))
    except Exception:
        return False


def generate_registration_xml(block_name: str, item_type: str,
                              iec_path: Optional[Path] = None) -> str:
    """Generate the XML entries for registration.

    Args:
        block_name: Name of the block
        item_type: Type of item (cat, composite, basic, adapter, datatype)
        iec_path: Path to IEC61499 folder (needed for conditional file checks)
    """
    template = TEMPLATES.get(item_type)
    if not template:
        raise ValueError(f"Unknown item type: {item_type}")

    # For CAT blocks, conditionally include aspmap.xml based on file existence
    if item_type == "cat" and iec_path:
        aspmap_file = iec_path / block_name / f"{block_name}_CAT.aspmap.xml"

        if not aspmap_file.exists():
            # Generate template without aspmap.xml entry
            template = '''  <!-- {block_name} CAT Block -->
  <ItemGroup>
    <Compile Include="{block_name}\\{block_name}.fbt">
      <IEC61499Type>CAT</IEC61499Type>
    </Compile>
    <Compile Include="{block_name}\\{block_name}_HMI.fbt">
      <IEC61499Type>CAT</IEC61499Type>
      <Usage>Private</Usage>
      <DependentUpon>{block_name}.fbt</DependentUpon>
      <HMI>..\\HMI\\{block_name}\\{block_name}_sDefault.cnv.cs</HMI>
    </Compile>
  </ItemGroup>
  <ItemGroup>
    <None Include="{block_name}\\{block_name}.cfg">
      <DependentUpon>{block_name}.fbt</DependentUpon>
      <IEC61499Type>CAT</IEC61499Type>
    </None>
    <None Include="{block_name}\\{block_name}_CAT.offline.xml">
      <DependentUpon>{block_name}.fbt</DependentUpon>
      <Plugin>OfflineParametrizationEditor</Plugin>
      <IEC61499Type>CAT_OFFLINE</IEC61499Type>
    </None>
    <None Include="{block_name}\\{block_name}_CAT.opcua.xml">
      <DependentUpon>{block_name}.fbt</DependentUpon>
      <Plugin>OPCUAConfigurator</Plugin>
      <IEC61499Type>CAT_OPCUA</IEC61499Type>
    </None>
  </ItemGroup>
'''

    return template.format(block_name=block_name)


def get_entries_list(block_name: str, item_type: str,
                     iec_path: Optional[Path] = None) -> List[str]:
    """Get list of entries for reporting.

    Args:
        block_name: Name of the block
        item_type: Type of item
        iec_path: Path to IEC61499 folder (needed for conditional file checks)
    """
    entries = ENTRIES.get(item_type, [])
    formatted_entries = [e.format(block_name=block_name) for e in entries]

    # For CAT blocks, conditionally include aspmap.xml based on file existence
    if item_type == "cat" and iec_path:
        aspmap_file = iec_path / block_name / f"{block_name}_CAT.aspmap.xml"
        if not aspmap_file.exists():
            # Remove aspmap.xml entry from list
            formatted_entries = [e for e in formatted_entries if "aspmap.xml" not in e]

    return formatted_entries


def register_block(dfbproj_path: Path, block_name: str, item_type: str,
                   dry_run: bool = False) -> RegistrationResult:
    """Register a block in the dfbproj file."""
    result = RegistrationResult(success=False, message="")

    try:
        # Read current content
        with open(dfbproj_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check if already registered
        if check_registration_exists(dfbproj_path, block_name, item_type):
            result.success = True
            result.message = f"{item_type.upper()} block '{block_name}' is already registered"
            result.warnings.append("No changes needed")
            return result

        # Find the Import line to insert before
        import_pattern = r'(\s*<Import Project="\$\(SharpDevelopBinPath\)\\NxtControl\.Build\.61499\.Targets"\s*/>\s*)'
        match = re.search(import_pattern, content)

        if not match:
            result.message = "Could not find Import statement in dfbproj"
            result.errors.append("Expected: <Import Project=\"$(SharpDevelopBinPath)\\NxtControl.Build.61499.Targets\" />")
            return result

        # Get IEC61499 path for conditional file checks
        iec_path = dfbproj_path.parent

        # Generate registration XML
        registration_xml = generate_registration_xml(block_name, item_type, iec_path)
        entries = get_entries_list(block_name, item_type, iec_path)

        if dry_run:
            result.success = True
            result.message = f"[DRY RUN] Would register {item_type.upper()} block '{block_name}'"
            result.entries_added = entries
            return result

        # Insert before Import line
        new_content = content[:match.start()] + registration_xml + content[match.start():]

        # Write updated content
        with open(dfbproj_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        result.success = True
        result.message = f"Successfully registered {item_type.upper()} block '{block_name}' in dfbproj"
        result.entries_added = entries

    except Exception as e:
        result.message = f"Error registering block: {str(e)}"
        result.errors.append(str(e))

    return result


def verify_registration(dfbproj_path: Path, block_name: str, item_type: str) -> RegistrationResult:
    """Verify that a block is properly registered."""
    result = RegistrationResult(success=False, message="")

    try:
        with open(dfbproj_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Build checks based on item type
        checks = []
        if item_type == "cat":
            checks = [
                (f'<Compile Include="{block_name}\\{block_name}.fbt"', "Main .fbt Compile entry"),
                (f'<Compile Include="{block_name}\\{block_name}_HMI.fbt"', "HMI .fbt Compile entry"),
                (f'<None Include="{block_name}\\{block_name}.cfg"', ".cfg None entry"),
                ('<IEC61499Type>CAT</IEC61499Type>', "CAT type declaration"),
            ]
        elif item_type == "composite":
            checks = [
                (f'<Compile Include="{block_name}\\{block_name}.fbt"', "Main .fbt Compile entry"),
                ('<IEC61499Type>Composite</IEC61499Type>', "Composite type declaration"),
            ]
        elif item_type == "basic":
            checks = [
                (f'<Compile Include="{block_name}\\{block_name}.fbt"', "Main .fbt Compile entry"),
                ('<IEC61499Type>Basic</IEC61499Type>', "Basic type declaration"),
            ]
        elif item_type == "adapter":
            checks = [
                (f'<Compile Include="{block_name}\\{block_name}.adp"', "Main .adp Compile entry"),
                ('<IEC61499Type>Adapter</IEC61499Type>', "Adapter type declaration"),
            ]
        elif item_type == "datatype":
            checks = [
                (f'<Compile Include="DataType\\{block_name}.dt"', "Main .dt Compile entry"),
                ('<IEC61499Type>DataType</IEC61499Type>', "DataType type declaration"),
            ]

        missing = []
        found = []

        for pattern, description in checks:
            if pattern in content:
                found.append(description)
            else:
                missing.append(description)

        if not missing:
            result.success = True
            result.message = f"{item_type.upper()} block '{block_name}' is properly registered"
            result.entries_added = found
        else:
            result.message = f"{item_type.upper()} block '{block_name}' has incomplete registration"
            result.errors = [f"Missing: {item}" for item in missing]
            result.warnings = [f"Found: {item}" for item in found]

    except Exception as e:
        result.message = f"Error verifying registration: {str(e)}"
        result.errors.append(str(e))

    return result


def detect_item_type(block_name: str, project_path: Path, target_lib: str) -> Optional[str]:
    """Auto-detect item type from existing files."""
    iec_path = project_path / target_lib / "IEC61499"

    # Check for CAT (has .cfg file)
    if (iec_path / block_name / f"{block_name}.cfg").exists():
        return "cat"

    # Check for Composite/Basic (has .fbt)
    if (iec_path / block_name / f"{block_name}.fbt").exists():
        # Check for composite.offline.xml to distinguish
        if (iec_path / block_name / f"{block_name}.composite.offline.xml").exists():
            return "composite"
        # Check FBNetwork in .fbt to determine
        fbt_path = iec_path / block_name / f"{block_name}.fbt"
        try:
            with open(fbt_path, "r", encoding="utf-8") as f:
                content = f.read()
            if "<FBNetwork>" in content:
                return "composite"
            elif "<BasicFB>" in content or "<ECC>" in content:
                return "basic"
        except Exception:
            pass
        return "composite"  # Default to composite if .fbt exists

    # Check for Adapter
    if (iec_path / block_name / f"{block_name}.adp").exists():
        return "adapter"

    # Check for DataType
    if (iec_path / "DataType" / f"{block_name}.dt").exists():
        return "datatype"

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Universal dfbproj registration for all EAE item types"
    )

    parser.add_argument("block_name", help="Name of the block to register")
    parser.add_argument("target_lib", help="Target library name")
    parser.add_argument("--type", "-t", choices=["cat", "composite", "basic", "adapter", "datatype"],
                        help="Item type (auto-detected if not specified)")
    parser.add_argument("--project-path", "-p",
                        help="Project path (auto-detected if not specified)")
    parser.add_argument("--verify", "-v", action="store_true",
                        help="Verify registration instead of adding")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Show what would be done without making changes")
    parser.add_argument("--json", "-j", action="store_true",
                        help="Output as JSON")

    args = parser.parse_args()

    # Find project path
    if args.project_path:
        project_path = Path(args.project_path)
    else:
        project_path = Path.cwd()
        # Walk up to find project root
        for parent in [project_path] + list(project_path.parents):
            if (parent / args.target_lib).exists():
                project_path = parent
                break

    # Find dfbproj
    dfbproj_path = find_dfbproj(args.target_lib, project_path)
    if not dfbproj_path:
        print(f"ERROR: Could not find {args.target_lib}.dfbproj")
        print(f"Searched in: {project_path / args.target_lib / 'IEC61499'}")
        sys.exit(1)

    # Determine item type
    item_type = args.type
    if not item_type:
        item_type = detect_item_type(args.block_name, project_path, args.target_lib)
        if not item_type:
            print("ERROR: Could not auto-detect item type. Please specify --type")
            sys.exit(1)
        print(f"Auto-detected type: {item_type.upper()}")

    if not args.json:
        print(f"Project: {project_path}")
        print(f"dfbproj: {dfbproj_path}")
        print(f"Block: {args.block_name}")
        print(f"Type: {item_type.upper()}")
        print()

    if args.verify:
        result = verify_registration(dfbproj_path, args.block_name, item_type)
    else:
        result = register_block(dfbproj_path, args.block_name, item_type, args.dry_run)

    if args.json:
        import json
        output = {
            "success": result.success,
            "message": result.message,
            "entries": result.entries_added,
            "errors": result.errors,
            "warnings": result.warnings,
            "type": item_type,
        }
        print(json.dumps(output, indent=2))
    else:
        # Print result
        status = "[OK]" if result.success else "[FAIL]"
        print(f"{status} {result.message}")

        if result.entries_added:
            print("\nEntries:")
            for entry in result.entries_added:
                print(f"  + {entry}")

        for warning in result.warnings:
            print(f"  [WARN] {warning}")

        for error in result.errors:
            print(f"  [ERROR] {error}")

    # Exit code
    if result.success:
        sys.exit(0)
    elif result.errors:
        sys.exit(11)  # Registration issue
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
