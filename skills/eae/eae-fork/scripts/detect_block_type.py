#!/usr/bin/env python3
"""
Detect the type of an EAE IEC 61499 block from source files.

This script examines the structure and content of block files to determine
the block type, which is used by eae-fork to orchestrate the appropriate
registration sub-skill.

Block Types and Detection:
- CAT: Has .cfg file with HMIInterface elements
- Composite FB: .fbt with Format="2.0" and <FBNetwork> element
- Basic FB: .fbt with <BasicFB> element
- Adapter: .adp file extension
- DataType: .dt file extension

Usage:
    python detect_block_type.py <block_name> <library_name>
    python detect_block_type.py AnalogInput SE.App2CommonProcess
    python detect_block_type.py --json AnalogInput SE.App2CommonProcess

Exit codes:
    0: Success
    1: Block not found
    2: Unable to determine type
    10: Invalid arguments
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any

# Library location
LIBRARIES_PATH = Path(r"C:\ProgramData\Schneider Electric\Libraries")


@dataclass
class BlockTypeResult:
    """Result of block type detection."""
    success: bool
    block_name: str
    library: str
    block_type: Optional[str] = None  # cat, composite, basic, adapter, datatype
    confidence: float = 0.0  # 0.0 to 1.0
    evidence: List[str] = field(default_factory=list)
    sub_skill: Optional[str] = None  # eae-cat, eae-composite-fb, etc.
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


def find_library_version(library_name: str) -> Optional[Path]:
    """Find the latest version of a library in the Libraries folder."""
    if not LIBRARIES_PATH.exists():
        return None

    pattern = f"{library_name}-*"
    matches = list(LIBRARIES_PATH.glob(pattern))

    if not matches:
        return None

    def version_key(p: Path) -> tuple:
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


def detect_cat_type(block_path: Path, block_name: str) -> tuple[bool, List[str], Dict]:
    """
    Detect if block is a CAT (Composite Application Type).

    CAT indicators:
    - Has .cfg file
    - .cfg contains HMIInterface elements
    - Has associated HMI symbols/faceplates
    """
    evidence = []
    metadata = {}

    cfg_file = block_path / f"{block_name}.cfg"
    if not cfg_file.exists():
        return False, [], {}

    evidence.append(f"Has .cfg file: {cfg_file.name}")

    try:
        tree = ET.parse(cfg_file)
        root = tree.getroot()

        # Check for HMIInterface element (primary CAT indicator)
        hmi_interfaces = list(root.iter("HMIInterface")) + \
                        list(root.iter("{http://www.nxtcontrol.com/IEC61499.xsd}HMIInterface"))

        if hmi_interfaces:
            evidence.append(f"Found {len(hmi_interfaces)} HMIInterface element(s)")

            # Extract symbol/faceplate info
            symbols = []
            faceplates = []
            for hmi in hmi_interfaces:
                for symbol in list(hmi.iter("Symbol")) + \
                             list(hmi.iter("{http://www.nxtcontrol.com/IEC61499.xsd}Symbol")):
                    name = symbol.get("Name", "")
                    is_fp = symbol.get("IsFaceplate", "false").lower() == "true"
                    if is_fp:
                        faceplates.append(name)
                    else:
                        symbols.append(name)

            metadata["symbols"] = symbols
            metadata["faceplates"] = faceplates
            metadata["hmi_interface_count"] = len(hmi_interfaces)

            return True, evidence, metadata

        # Check for SubCAT elements (another CAT indicator)
        subcats = list(root.iter("SubCAT")) + \
                 list(root.iter("{http://www.nxtcontrol.com/IEC61499.xsd}SubCAT"))

        if subcats:
            evidence.append(f"Found {len(subcats)} SubCAT element(s)")
            subcat_names = [sc.get("Name", "") for sc in subcats]
            metadata["subcats"] = subcat_names
            return True, evidence, metadata

    except ET.ParseError as e:
        evidence.append(f"XML parse error in .cfg: {e}")

    return False, evidence, metadata


def detect_composite_type(block_path: Path, block_name: str) -> tuple[bool, List[str], Dict]:
    """
    Detect if block is a Composite FB.

    Composite FB indicators:
    - .fbt file exists
    - FBType Format="2.0" attribute
    - Contains <FBNetwork> element
    - Does NOT contain <BasicFB> element
    """
    evidence = []
    metadata = {}

    fbt_file = block_path / f"{block_name}.fbt"
    if not fbt_file.exists():
        return False, [], {}

    evidence.append(f"Has .fbt file: {fbt_file.name}")

    try:
        tree = ET.parse(fbt_file)
        root = tree.getroot()

        # Check for Format="2.0" (Composite FB format)
        format_attr = root.get("Format", "")
        if format_attr == "2.0":
            evidence.append("FBType Format=\"2.0\" (Composite format)")

        # Check for FBNetwork element (primary Composite indicator)
        fb_network = root.find(".//FBNetwork") or \
                    root.find(".//{http://www.nxtcontrol.com/IEC61499.xsd}FBNetwork")

        if fb_network is not None:
            evidence.append("Contains <FBNetwork> element")

            # Count internal FBs
            fbs = list(fb_network.iter("FB")) + \
                 list(fb_network.iter("{http://www.nxtcontrol.com/IEC61499.xsd}FB"))
            metadata["internal_fb_count"] = len(fbs)

            # Extract FB types
            fb_types = list(set(fb.get("Type", "") for fb in fbs))
            metadata["internal_fb_types"] = fb_types

        # Check that it's NOT a Basic FB
        basic_fb = root.find(".//BasicFB") or \
                  root.find(".//{http://www.nxtcontrol.com/IEC61499.xsd}BasicFB")

        if basic_fb is not None:
            # Has BasicFB - this is a Basic FB, not Composite
            return False, evidence, metadata

        # If has FBNetwork and no BasicFB, it's a Composite
        if fb_network is not None:
            return True, evidence, metadata

    except ET.ParseError as e:
        evidence.append(f"XML parse error in .fbt: {e}")

    return False, evidence, metadata


def detect_basic_type(block_path: Path, block_name: str) -> tuple[bool, List[str], Dict]:
    """
    Detect if block is a Basic FB.

    Basic FB indicators:
    - .fbt file exists
    - Contains <BasicFB> element
    - Has ECC (Execution Control Chart)
    - Has ST/IL/LD algorithms
    """
    evidence = []
    metadata = {}

    fbt_file = block_path / f"{block_name}.fbt"
    if not fbt_file.exists():
        return False, [], {}

    evidence.append(f"Has .fbt file: {fbt_file.name}")

    try:
        tree = ET.parse(fbt_file)
        root = tree.getroot()

        # Check for BasicFB element (primary indicator)
        basic_fb = root.find(".//BasicFB") or \
                  root.find(".//{http://www.nxtcontrol.com/IEC61499.xsd}BasicFB")

        if basic_fb is None:
            return False, evidence, metadata

        evidence.append("Contains <BasicFB> element")

        # Check for ECC
        ecc = basic_fb.find(".//ECC") or \
             basic_fb.find(".//{http://www.nxtcontrol.com/IEC61499.xsd}ECC")

        if ecc is not None:
            evidence.append("Has ECC (Execution Control Chart)")

            # Count states
            states = list(ecc.iter("ECState")) + \
                    list(ecc.iter("{http://www.nxtcontrol.com/IEC61499.xsd}ECState"))
            metadata["ecc_state_count"] = len(states)

            # Count transitions
            transitions = list(ecc.iter("ECTransition")) + \
                         list(ecc.iter("{http://www.nxtcontrol.com/IEC61499.xsd}ECTransition"))
            metadata["ecc_transition_count"] = len(transitions)

        # Check for algorithms
        algorithms = list(basic_fb.iter("Algorithm")) + \
                    list(basic_fb.iter("{http://www.nxtcontrol.com/IEC61499.xsd}Algorithm"))

        if algorithms:
            evidence.append(f"Has {len(algorithms)} algorithm(s)")
            algo_names = [a.get("Name", "") for a in algorithms]
            metadata["algorithms"] = algo_names

        return True, evidence, metadata

    except ET.ParseError as e:
        evidence.append(f"XML parse error in .fbt: {e}")

    return False, evidence, metadata


def detect_adapter_type(block_path: Path, block_name: str) -> tuple[bool, List[str], Dict]:
    """
    Detect if block is an Adapter.

    Adapter indicators:
    - .adp file exists (primary)
    - OR .fbt file with AdapterType element
    """
    evidence = []
    metadata = {}

    # Check for .adp file (direct indicator)
    adp_file = block_path / f"{block_name}.adp"
    if adp_file.exists():
        evidence.append(f"Has .adp file: {adp_file.name}")

        try:
            tree = ET.parse(adp_file)
            root = tree.getroot()

            # Get adapter interface info
            socket = root.find(".//Socket") or \
                    root.find(".//{http://www.nxtcontrol.com/IEC61499.xsd}Socket")
            plug = root.find(".//Plug") or \
                  root.find(".//{http://www.nxtcontrol.com/IEC61499.xsd}Plug")

            if socket is not None:
                evidence.append("Has Socket interface")
            if plug is not None:
                evidence.append("Has Plug interface")

            metadata["has_socket"] = socket is not None
            metadata["has_plug"] = plug is not None

        except ET.ParseError as e:
            evidence.append(f"XML parse error in .adp: {e}")

        return True, evidence, metadata

    # Check for AdapterType in .fbt file
    fbt_file = block_path / f"{block_name}.fbt"
    if fbt_file.exists():
        try:
            tree = ET.parse(fbt_file)
            root = tree.getroot()

            # Check root element name
            if root.tag.endswith("AdapterType") or "AdapterType" in root.tag:
                evidence.append("FBT file is AdapterType")
                return True, evidence, metadata

        except ET.ParseError:
            pass

    return False, evidence, metadata


def detect_datatype_type(block_path: Path, block_name: str) -> tuple[bool, List[str], Dict]:
    """
    Detect if block is a DataType.

    DataType indicators:
    - .dt file exists
    - Contains structure/enum/array definitions
    """
    evidence = []
    metadata = {}

    dt_file = block_path / f"{block_name}.dt"
    if not dt_file.exists():
        return False, [], {}

    evidence.append(f"Has .dt file: {dt_file.name}")

    try:
        tree = ET.parse(dt_file)
        root = tree.getroot()

        # Detect DataType kind
        struct = root.find(".//StructuredType") or \
                root.find(".//{http://www.nxtcontrol.com/IEC61499.xsd}StructuredType")
        enum = root.find(".//EnumeratedType") or \
              root.find(".//{http://www.nxtcontrol.com/IEC61499.xsd}EnumeratedType")
        array = root.find(".//ArrayType") or \
               root.find(".//{http://www.nxtcontrol.com/IEC61499.xsd}ArrayType")
        subrange = root.find(".//SubrangeType") or \
                  root.find(".//{http://www.nxtcontrol.com/IEC61499.xsd}SubrangeType")

        if struct is not None:
            evidence.append("DataType kind: StructuredType")
            metadata["datatype_kind"] = "structured"

            # Count members
            members = list(struct.iter("VarDeclaration")) + \
                     list(struct.iter("{http://www.nxtcontrol.com/IEC61499.xsd}VarDeclaration"))
            metadata["member_count"] = len(members)

        elif enum is not None:
            evidence.append("DataType kind: EnumeratedType")
            metadata["datatype_kind"] = "enumerated"

        elif array is not None:
            evidence.append("DataType kind: ArrayType")
            metadata["datatype_kind"] = "array"

        elif subrange is not None:
            evidence.append("DataType kind: SubrangeType")
            metadata["datatype_kind"] = "subrange"

        return True, evidence, metadata

    except ET.ParseError as e:
        evidence.append(f"XML parse error in .dt: {e}")

    return False, evidence, metadata


def detect_block_type(block_name: str, library_name: str) -> BlockTypeResult:
    """
    Main detection function. Examines block files and determines type.

    Detection priority:
    1. DataType (.dt file) - most specific
    2. Adapter (.adp file) - most specific
    3. CAT (.cfg with HMI) - requires .cfg
    4. Basic FB (BasicFB element) - in .fbt
    5. Composite FB (FBNetwork, no BasicFB) - in .fbt
    """
    result = BlockTypeResult(
        success=False,
        block_name=block_name,
        library=library_name
    )

    # Find library
    lib_path = find_library_version(library_name)
    if not lib_path:
        result.message = f"Library not found: {library_name}"
        return result

    # Find block
    block_path = find_source_block(lib_path, block_name)
    if not block_path:
        result.message = f"Block not found: {block_name} in {library_name}"
        return result

    result.evidence.append(f"Block path: {block_path}")

    # Detection chain (order matters - most specific first)
    detectors = [
        ("datatype", detect_datatype_type, "eae-datatype"),
        ("adapter", detect_adapter_type, "eae-adapter"),
        ("cat", detect_cat_type, "eae-cat"),
        ("basic", detect_basic_type, "eae-basic-fb"),
        ("composite", detect_composite_type, "eae-composite-fb"),
    ]

    for block_type, detector, sub_skill in detectors:
        is_type, evidence, metadata = detector(block_path, block_name)

        if is_type:
            result.success = True
            result.block_type = block_type
            result.sub_skill = sub_skill
            result.evidence.extend(evidence)
            result.metadata.update(metadata)
            result.confidence = 1.0  # Definitive detection
            result.message = f"Detected {block_type.upper()} block"
            return result
        elif evidence:
            # Partial evidence but not conclusive
            result.evidence.extend(evidence)

    # Unable to determine
    result.message = "Unable to determine block type"
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Detect EAE block type from source files"
    )
    parser.add_argument("block_name", help="Block name (e.g., AnalogInput)")
    parser.add_argument("library_name", help="Library name (e.g., SE.App2CommonProcess)")
    parser.add_argument("--json", "-j", action="store_true",
                       help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Show detailed evidence")

    args = parser.parse_args()

    result = detect_block_type(args.block_name, args.library_name)

    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print(f"\n{'='*50}")
        print(f"Block Type Detection: {args.block_name}")
        print(f"{'='*50}")
        print(f"Library: {args.library_name}")
        print(f"Status: {'SUCCESS' if result.success else 'FAILED'}")

        if result.success:
            print(f"\nDetected Type: {result.block_type.upper()}")
            print(f"Sub-skill: {result.sub_skill}")
            print(f"Confidence: {result.confidence * 100:.0f}%")

        print(f"\n{result.message}")

        if args.verbose and result.evidence:
            print(f"\nEvidence:")
            for ev in result.evidence:
                print(f"  - {ev}")

        if result.metadata:
            print(f"\nMetadata:")
            for key, value in result.metadata.items():
                print(f"  {key}: {value}")

    # Exit code
    if result.success:
        sys.exit(0)
    elif result.block_type is None:
        sys.exit(2)  # Unable to determine type
    else:
        sys.exit(1)  # Block not found


if __name__ == "__main__":
    main()
