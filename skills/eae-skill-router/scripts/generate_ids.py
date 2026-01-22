#!/usr/bin/env python3
"""
Generate GUIDs and hex IDs for EAE IEC 61499 blocks.

Usage:
    python generate_ids.py                    # Generate 1 GUID + 1 hex ID
    python generate_ids.py --hex 5            # Generate 5 hex IDs
    python generate_ids.py --guid 2           # Generate 2 GUIDs
    python generate_ids.py --hex 4 --guid 1   # Generate both
    python generate_ids.py --json             # Output as JSON

Exit codes:
    0: Success
    1: Error
"""

import argparse
import uuid
import json
import sys
from dataclasses import dataclass, asdict
from typing import List


@dataclass
class Result:
    """Standard result structure for EAE skill scripts."""
    success: bool
    message: str
    guids: List[str]
    hex_ids: List[str]

    def to_dict(self):
        return asdict(self)


def generate_guid() -> str:
    """Generate a standard GUID for FBType/AdapterType."""
    return str(uuid.uuid4())


def generate_hex_id() -> str:
    """Generate a 16-character uppercase hex ID for Events/VarDeclarations."""
    return uuid.uuid4().hex[:16].upper()


def main():
    parser = argparse.ArgumentParser(
        description="Generate GUIDs and hex IDs for EAE IEC 61499 blocks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s                    Generate 1 GUID + 1 hex ID
    %(prog)s --hex 5            Generate 5 hex IDs
    %(prog)s --guid 2           Generate 2 GUIDs
    %(prog)s --hex 4 --guid 1   Generate both
    %(prog)s --json             Output as JSON
        """
    )
    parser.add_argument("--guid", type=int, default=1, metavar="N",
                        help="Number of GUIDs to generate (default: 1)")
    parser.add_argument("--hex", type=int, default=1, metavar="N",
                        help="Number of hex IDs to generate (default: 1)")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")

    args = parser.parse_args()

    try:
        guids = [generate_guid() for _ in range(args.guid)]
        hex_ids = [generate_hex_id() for _ in range(args.hex)]

        result = Result(
            success=True,
            message=f"Generated {len(guids)} GUID(s) and {len(hex_ids)} hex ID(s)",
            guids=guids,
            hex_ids=hex_ids
        )

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print("=== GUIDs (for FBType/AdapterType) ===")
            for g in guids:
                print(f"  {g}")
            print()
            print("=== Hex IDs (for Events/VarDeclarations) ===")
            for h in hex_ids:
                print(f"  {h}")
            print()
            print(f"Generated {len(guids)} GUID(s) and {len(hex_ids)} hex ID(s)")

        return 0

    except Exception as e:
        result = Result(
            success=False,
            message=str(e),
            guids=[],
            hex_ids=[]
        )
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
