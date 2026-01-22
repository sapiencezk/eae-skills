#!/usr/bin/env python3
"""
Lookup blocks in the Runtime.Base library by keyword, category, or list all blocks.

Usage:
    python lookup_block.py "delay"           # Search for blocks matching "delay"
    python lookup_block.py "mqtt" --category # Show categories for matches
    python lookup_block.py --list-categories # List all categories
    python lookup_block.py --list-all        # List all blocks
    python lookup_block.py "timer" --json    # JSON output

Exit codes:
    0  - Success (matches found or list completed)
    1  - Error (invalid arguments)
    2  - No matches found
"""

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from typing import List


@dataclass
class Block:
    """Represents a Runtime.Base function block."""
    name: str
    category: str
    block_type: str  # Basic, Composite, Service, Resource
    description: str
    keywords: List[str] = field(default_factory=list)


@dataclass
class SearchResult:
    """Result of a block search."""
    query: str
    matches: List[Block]
    total_blocks: int
    categories_searched: List[str]


# Runtime.Base Block Database
BLOCKS = [
    # === Basics (14 blocks) ===
    Block("DS_SELECTX", "Basics", "Basic", "Extended data selector", ["select", "data", "mux"]),
    Block("E_CTU", "Basics", "Basic", "Event-driven up counter", ["counter", "count", "up"]),
    Block("E_D_FF", "Basics", "Basic", "Event-driven D flip-flop", ["flipflop", "latch", "d", "clock"]),
    Block("E_DEMUX", "Basics", "Basic", "Event demultiplexer (1 to N)", ["demux", "demultiplex", "route"]),
    Block("E_MERGE", "Basics", "Basic", "Event merge (N to 1)", ["merge", "combine", "join"]),
    Block("E_PERMIT", "Basics", "Basic", "Event gate/permit", ["gate", "permit", "block", "allow"]),
    Block("E_REND", "Basics", "Basic", "Event rendezvous (synchronization)", ["sync", "synchronize", "rendezvous", "wait"]),
    Block("E_RS", "Basics", "Basic", "Event-driven RS flip-flop (Reset dominant)", ["flipflop", "latch", "reset", "set"]),
    Block("E_SELECT", "Basics", "Basic", "Event selector", ["select", "choose", "route"]),
    Block("E_SPLIT", "Basics", "Basic", "Event splitter (1 to 2)", ["split", "divide", "fork"]),
    Block("E_SR", "Basics", "Basic", "Event-driven SR flip-flop (Set dominant)", ["flipflop", "latch", "set", "reset"]),
    Block("E_SWITCH", "Basics", "Basic", "Event switch (boolean routing)", ["switch", "route", "boolean"]),
    Block("FORCE_IND", "Basics", "Basic", "Force indication", ["force", "indicate"]),
    Block("SMOOTH", "Basics", "Basic", "Signal smoothing/filtering", ["smooth", "filter", "average"]),

    # === Composites (2 blocks) ===
    Block("E_F_TRIG", "Composites", "Composite", "Falling edge trigger", ["edge", "falling", "trigger", "negative"]),
    Block("E_R_TRIG", "Composites", "Composite", "Rising edge trigger", ["edge", "rising", "trigger", "positive"]),

    # === Timing Services ===
    Block("E_CYCLE", "Timing", "Service", "Cyclic event generator", ["cycle", "periodic", "timer", "repeat"]),
    Block("E_HRCYCLE", "Timing", "Service", "High-resolution cyclic generator with phase", ["cycle", "highres", "precision", "phase"]),
    Block("E_DELAY", "Timing", "Service", "Single event delay", ["delay", "wait", "timer", "timeout"]),
    Block("E_DELAYR", "Timing", "Service", "Retriggerable delay", ["delay", "retrigger", "timer"]),
    Block("E_N_TABLE", "Timing", "Service", "N-entry time table", ["table", "schedule", "sequence"]),
    Block("E_RESTART", "Timing", "Service", "Restart detection", ["restart", "detect", "boot"]),
    Block("E_TABLE", "Timing", "Service", "Scheduled time table", ["table", "schedule", "time"]),
    Block("E_TRAIN", "Timing", "Service", "Event train (burst) generator", ["train", "burst", "pulse", "sequence"]),

    # === Arithmetic Services ===
    Block("ADD", "Arithmetic", "Service", "Addition (IN1 + IN2)", ["add", "plus", "sum", "math"]),
    Block("SUB", "Arithmetic", "Service", "Subtraction (IN1 - IN2)", ["subtract", "minus", "difference", "math"]),
    Block("MUL", "Arithmetic", "Service", "Multiplication (IN1 * IN2)", ["multiply", "times", "product", "math"]),
    Block("DIV", "Arithmetic", "Service", "Division (IN1 / IN2)", ["divide", "quotient", "math"]),
    Block("ANAMATH", "Arithmetic", "Service", "Analog math operations", ["analog", "math", "calculate"]),
    Block("CALC_FORMULAR", "Arithmetic", "Service", "Formula string evaluation", ["formula", "expression", "calculate", "eval"]),
    Block("RNBR", "Arithmetic", "Service", "Random number generator", ["random", "number", "generate"]),

    # === Logic Services ===
    Block("AND", "Logic", "Service", "Logical AND", ["and", "logic", "boolean"]),
    Block("OR", "Logic", "Service", "Logical OR", ["or", "logic", "boolean"]),
    Block("NOT", "Logic", "Service", "Logical NOT", ["not", "invert", "logic", "boolean"]),
    Block("XOR", "Logic", "Service", "Exclusive OR", ["xor", "exclusive", "logic", "boolean"]),
    Block("COMPARE", "Logic", "Service", "Value comparison (LT, EQ, GT)", ["compare", "equal", "greater", "less"]),
    Block("SELECT", "Logic", "Service", "Conditional data selection", ["select", "choose", "conditional"]),

    # === Bit Manipulation ===
    Block("BITMAN", "BitManipulation", "Service", "General bit manipulation", ["bit", "manipulate", "mask"]),
    Block("SHL", "BitManipulation", "Service", "Shift left", ["shift", "left", "bit"]),
    Block("SHR", "BitManipulation", "Service", "Shift right", ["shift", "right", "bit"]),
    Block("ROL", "BitManipulation", "Service", "Rotate left", ["rotate", "left", "bit"]),
    Block("ROR", "BitManipulation", "Service", "Rotate right", ["rotate", "right", "bit"]),

    # === Communication - MQTT ===
    Block("MQTT_CONNECTION", "MQTT", "Service", "MQTT broker connection management", ["mqtt", "connection", "broker", "iot"]),
    Block("MQTT_PUBLISH", "MQTT", "Service", "Publish to MQTT topics", ["mqtt", "publish", "send", "message"]),
    Block("MQTT_SUBSCRIBE", "MQTT", "Service", "Subscribe to MQTT topics", ["mqtt", "subscribe", "receive", "listen"]),

    # === Communication - Other ===
    Block("WEBSOCKET_SERVER", "Communication", "Service", "WebSocket server", ["websocket", "server", "realtime"]),
    Block("NETIO", "Communication", "Service", "Network I/O (TCP/UDP)", ["network", "tcp", "udp", "socket"]),
    Block("SERIALIO", "Communication", "Service", "Serial port communication", ["serial", "rs232", "rs485", "uart"]),
    Block("QUERY_CONNECTION", "Communication", "Service", "HTTP/REST client", ["http", "rest", "api", "query"]),

    # === Data Handling ===
    Block("BUFFER", "DataHandling", "Service", "Data buffer", ["buffer", "queue", "store"]),
    Block("BUFFERP", "DataHandling", "Service", "Persistent data buffer", ["buffer", "persistent", "store"]),
    Block("ANY2ANY", "DataHandling", "Service", "Type conversion (any to any)", ["convert", "type", "cast"]),
    Block("SPLIT", "DataHandling", "Service", "Split data into parts", ["split", "divide", "parse"]),
    Block("AGGREGATE", "DataHandling", "Service", "Combine data parts", ["aggregate", "combine", "merge"]),
    Block("DATA_CRYPTO", "DataHandling", "Service", "Data encryption/decryption", ["encrypt", "decrypt", "crypto", "security"]),

    # === JSON Services ===
    Block("JSON_BUILDER", "JSON", "Service", "Build JSON from key/value pairs", ["json", "build", "create", "serialize"]),
    Block("JSON_PARSER", "JSON", "Service", "Parse JSON to values", ["json", "parse", "deserialize"]),
    Block("JSON_FORMAT", "JSON", "Service", "Format/pretty-print JSON", ["json", "format", "pretty"]),

    # === Configuration Services ===
    Block("CFG_ANY_GET", "Configuration", "Service", "Get configuration parameter (any type)", ["config", "get", "parameter"]),
    Block("CFG_ANY_SET", "Configuration", "Service", "Set configuration parameter (any type)", ["config", "set", "parameter"]),
    Block("CFG_DIRECT_GET", "Configuration", "Service", "Direct parameter read", ["config", "direct", "read"]),
    Block("CFG_DIRECT_SET", "Configuration", "Service", "Direct parameter write", ["config", "direct", "write"]),
    Block("PERSISTENCE", "Configuration", "Service", "Value persistence (save/load)", ["persist", "save", "load", "store"]),

    # === Process Data (I/O) ===
    Block("PD_ANY_IN", "ProcessData", "Service", "Process data input (any type)", ["process", "input", "io"]),
    Block("PD_ANY_OUT", "ProcessData", "Service", "Process data output (any type)", ["process", "output", "io"]),
    Block("PD_DIRECT_IN", "ProcessData", "Service", "Direct hardware input", ["process", "direct", "hardware", "input"]),
    Block("PD_DIRECT_OUT", "ProcessData", "Service", "Direct hardware output", ["process", "direct", "hardware", "output"]),
    Block("PD_COPY", "ProcessData", "Service", "Copy process data", ["process", "copy", "transfer"]),
    Block("PD_OCTET_STRING_IN", "ProcessData", "Service", "Octet string input", ["octet", "string", "input"]),
    Block("PD_OCTET_STRING_OUT", "ProcessData", "Service", "Octet string output", ["octet", "string", "output"]),

    # === Bus Communication ===
    Block("BM_FILE", "Bus", "Service", "File-based bus master", ["bus", "file", "master"]),
    Block("BM_MODBUS", "Bus", "Service", "Modbus bus master", ["modbus", "bus", "master"]),
    Block("BM_RIO", "Bus", "Service", "Remote I/O bus master", ["rio", "remote", "io", "bus"]),
    Block("BUSCOUPLER", "Bus", "Service", "Bus coupler interface", ["bus", "coupler"]),
    Block("BUSDEVICE", "Bus", "Service", "Bus device interface", ["bus", "device"]),
    Block("BUSDEVICECONFIG", "Bus", "Service", "Bus device configuration", ["bus", "device", "config"]),

    # === System Services ===
    Block("LOGGER", "System", "Service", "Local logging", ["log", "debug", "trace"]),
    Block("SYSLOGLOGGER", "System", "Service", "Remote syslog logging", ["syslog", "remote", "log"]),
    Block("CPUTICK", "System", "Service", "CPU tick counter (timing)", ["cpu", "tick", "timing", "performance"]),
    Block("REPORT_APP_STATE", "System", "Service", "Application state reporting", ["state", "report", "status"]),
    Block("ALARM_BIT", "System", "Service", "Bit-based alarm handling", ["alarm", "bit", "alert"]),
    Block("MIBGET", "System", "Service", "SNMP MIB get", ["snmp", "mib", "network"]),

    # === Event Scheduling ===
    Block("EVENTCHAIN", "EventScheduling", "Service", "Event chain link", ["event", "chain", "link"]),
    Block("EVENTCHAINHEAD", "EventScheduling", "Service", "Event chain head", ["event", "chain", "head"]),
    Block("EVENTSCHEDULER", "EventScheduling", "Service", "Event scheduler", ["event", "schedule", "order"]),
    Block("PRIOSCHEDULER", "EventScheduling", "Service", "Priority scheduler", ["priority", "schedule"]),

    # === Value Encoding ===
    Block("VTQ_ENCODE", "ValueEncoding", "Service", "Encode Value+Time+Quality", ["vtq", "encode", "quality"]),
    Block("VTQ_DECODE", "ValueEncoding", "Service", "Decode VTQ", ["vtq", "decode", "quality"]),
    Block("VALFORMAT", "ValueEncoding", "Service", "Format value to string", ["format", "value", "string"]),
    Block("VALSCAN", "ValueEncoding", "Service", "Parse string to value", ["parse", "scan", "string", "value"]),

    # === Symbolic Links ===
    Block("SYMLINKMULTIVARDST", "SymbolicLinks", "Service", "Multi-variable symbolic link destination", ["symbolic", "link", "destination"]),
    Block("SYMLINKMULTIVARSRC", "SymbolicLinks", "Service", "Multi-variable symbolic link source", ["symbolic", "link", "source"]),

    # === Resources (2 blocks) ===
    Block("EMB_RES_ECO", "Resources", "Resource", "Economy embedded resource", ["resource", "economy", "embedded"]),
    Block("EMB_RES_ENH", "Resources", "Resource", "Enhanced embedded resource", ["resource", "enhanced", "embedded"]),
]

CATEGORIES = sorted(set(b.category for b in BLOCKS))


def search_blocks(query: str) -> List[Block]:
    """Search blocks by name, description, or keywords."""
    query_lower = query.lower()
    matches = []

    for block in BLOCKS:
        # Check name
        if query_lower in block.name.lower():
            matches.append(block)
            continue
        # Check description
        if query_lower in block.description.lower():
            matches.append(block)
            continue
        # Check keywords
        if any(query_lower in kw.lower() for kw in block.keywords):
            matches.append(block)
            continue

    return matches


def format_block(block: Block, show_category: bool = False) -> str:
    """Format a block for display."""
    if show_category:
        return f"{block.name:25} [{block.category:15}] {block.description}"
    return f"{block.name:25} {block.description}"


def main():
    parser = argparse.ArgumentParser(
        description="Lookup blocks in the Runtime.Base library"
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Search query (block name, keyword, or description)"
    )
    parser.add_argument(
        "--category", "-c",
        action="store_true",
        help="Show category information with results"
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List all block categories"
    )
    parser.add_argument(
        "--list-all",
        action="store_true",
        help="List all blocks"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )

    args = parser.parse_args()

    # List categories
    if args.list_categories:
        if args.json:
            result = {
                "categories": CATEGORIES,
                "total": len(CATEGORIES)
            }
            print(json.dumps(result, indent=2))
        else:
            print("Runtime.Base Block Categories:")
            print("-" * 40)
            for cat in CATEGORIES:
                count = len([b for b in BLOCKS if b.category == cat])
                print(f"  {cat:20} ({count} blocks)")
            print(f"\nTotal: {len(CATEGORIES)} categories, {len(BLOCKS)} blocks")
        return 0

    # List all blocks
    if args.list_all:
        if args.json:
            result = {
                "blocks": [asdict(b) for b in BLOCKS],
                "total": len(BLOCKS)
            }
            print(json.dumps(result, indent=2))
        else:
            print("Runtime.Base Blocks:")
            print("-" * 70)
            current_cat = None
            for block in sorted(BLOCKS, key=lambda b: (b.category, b.name)):
                if block.category != current_cat:
                    current_cat = block.category
                    print(f"\n=== {current_cat} ===")
                print(f"  {format_block(block)}")
            print(f"\nTotal: {len(BLOCKS)} blocks")
        return 0

    # Search query required for other operations
    if not args.query:
        parser.print_help()
        return 1

    # Search blocks
    matches = search_blocks(args.query)

    if args.json:
        result = SearchResult(
            query=args.query,
            matches=matches,
            total_blocks=len(BLOCKS),
            categories_searched=CATEGORIES
        )
        output = {
            "query": result.query,
            "matches": [asdict(b) for b in result.matches],
            "match_count": len(result.matches),
            "total_blocks": result.total_blocks
        }
        print(json.dumps(output, indent=2))
    else:
        if not matches:
            print(f"No blocks found matching '{args.query}'")
            print("\nTry:")
            print("  --list-categories  to see available categories")
            print("  --list-all         to see all blocks")
            return 2

        print(f"Blocks matching '{args.query}':")
        print("-" * 70)
        for block in matches:
            print(f"  {format_block(block, args.category)}")
        print(f"\nFound: {len(matches)} block(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
