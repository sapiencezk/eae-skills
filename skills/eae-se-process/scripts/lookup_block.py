#!/usr/bin/env python3
"""
Lookup blocks in SE.App2Base and SE.App2CommonProcess libraries by keyword, category, or list all.

Usage:
    python lookup_block.py "motor"           # Search for blocks matching "motor"
    python lookup_block.py "pid" --category  # Show categories for matches
    python lookup_block.py "valve" --library # Show library (App2Base/App2CommonProcess)
    python lookup_block.py --list-categories # List all categories
    python lookup_block.py --list-all        # List all blocks
    python lookup_block.py "pump" --json     # JSON output

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
    """Represents an SE Process library function block."""
    name: str
    library: str  # SE.App2Base or SE.App2CommonProcess
    category: str
    block_type: str  # Basic, Composite, CAT, Adapter, DataType, Function
    description: str
    keywords: List[str] = field(default_factory=list)


@dataclass
class SearchResult:
    """Result of a block search."""
    query: str
    matches: List[Block]
    total_blocks: int
    libraries: List[str]


# SE Process Libraries Block Database
BLOCKS = [
    # =============================================
    # SE.App2Base - Basics
    # =============================================
    Block("alarmCalc", "SE.App2Base", "AlarmCalculation", "Basic", "Alarm calculation", ["alarm", "calculate"]),
    Block("alarmCalcBasic", "SE.App2Base", "AlarmCalculation", "Basic", "Basic alarm calculation", ["alarm", "basic"]),
    Block("alarmEdgeDelayCalc", "SE.App2Base", "AlarmCalculation", "Basic", "Alarm with edge delay", ["alarm", "edge", "delay"]),
    Block("alarmStateCalc", "SE.App2Base", "AlarmCalculation", "Basic", "State-based alarm calculation", ["alarm", "state"]),
    Block("analogSelector", "SE.App2Base", "SignalSelection", "Basic", "Analog signal selector", ["analog", "select", "signal"]),
    Block("anaThreshold", "SE.App2Base", "SignalProcessing", "Basic", "Analog threshold detection", ["analog", "threshold"]),
    Block("counterBasic", "SE.App2Base", "Counter", "Basic", "Basic counter", ["counter", "count"]),
    Block("deviationCalc", "SE.App2Base", "Calculation", "Basic", "Deviation calculation", ["deviation", "calculate"]),
    Block("limitValue", "SE.App2Base", "Calculation", "Basic", "Value limiter", ["limit", "clamp"]),
    Block("modeBase", "SE.App2Base", "ModeControl", "Basic", "Mode base control", ["mode", "auto", "manual"]),
    Block("ownerBasic", "SE.App2Base", "OwnerControl", "Basic", "Basic owner control", ["owner", "control"]),
    Block("ownerControl", "SE.App2Base", "OwnerControl", "Basic", "Owner control", ["owner", "control", "program"]),
    Block("rampCalc", "SE.App2Base", "Calculation", "Basic", "Ramp calculation", ["ramp", "rate"]),
    Block("rocCalc", "SE.App2Base", "Calculation", "Basic", "Rate of change calculation", ["roc", "rate", "change"]),
    Block("totalizerBasic", "SE.App2Base", "Totalizer", "Basic", "Basic totalizer", ["total", "sum", "accumulate"]),

    # =============================================
    # SE.App2Base - Composites
    # =============================================
    Block("aISignal", "SE.App2Base", "SignalProcessing", "Composite", "Analog input signal", ["analog", "input", "signal"]),
    Block("aOSignal", "SE.App2Base", "SignalProcessing", "Composite", "Analog output signal", ["analog", "output", "signal"]),
    Block("dISignal", "SE.App2Base", "SignalProcessing", "Composite", "Digital input signal", ["digital", "input", "signal"]),
    Block("dOSignal", "SE.App2Base", "SignalProcessing", "Composite", "Digital output signal", ["digital", "output", "signal"]),
    Block("plcStart", "SE.App2Base", "System", "Composite", "PLC start sequence", ["plc", "start", "init"]),
    Block("pulse", "SE.App2Base", "Timing", "Composite", "Pulse generator", ["pulse", "generate"]),
    Block("timeCalc", "SE.App2Base", "Timing", "Composite", "Time calculation", ["time", "calculate"]),

    # =============================================
    # SE.App2Base - Adapters
    # =============================================
    Block("IAnalog", "SE.App2Base", "Adapter", "Adapter", "Analog signal interface (Value, Status, Quality)", ["analog", "interface", "adapter"]),
    Block("IDigital", "SE.App2Base", "Adapter", "Adapter", "Digital signal interface (State, Status)", ["digital", "interface", "adapter"]),
    Block("IDInt", "SE.App2Base", "Adapter", "Adapter", "Double integer signal interface", ["dint", "integer", "adapter"]),
    Block("IString", "SE.App2Base", "Adapter", "Adapter", "String signal interface", ["string", "interface", "adapter"]),
    Block("ITime", "SE.App2Base", "Adapter", "Adapter", "Time signal interface", ["time", "interface", "adapter"]),

    # =============================================
    # SE.App2Base - DataTypes
    # =============================================
    Block("ActiveState", "SE.App2Base", "DataType", "DataType", "Active/inactive state enumeration", ["state", "active", "enum"]),
    Block("OwnerState", "SE.App2Base", "DataType", "DataType", "Owner state enumeration (Manual, Auto, Program)", ["owner", "mode", "enum"]),
    Block("Status", "SE.App2Base", "DataType", "DataType", "Signal quality status (Good, Bad, Uncertain)", ["status", "quality", "enum"]),

    # =============================================
    # SE.App2Base - Display CATs
    # =============================================
    Block("DisplayBool", "SE.App2Base", "Display", "CAT", "Display boolean value", ["display", "bool", "hmi"]),
    Block("DisplayDint", "SE.App2Base", "Display", "CAT", "Display DINT value", ["display", "dint", "hmi"]),
    Block("DisplayInt", "SE.App2Base", "Display", "CAT", "Display INT value", ["display", "int", "hmi"]),
    Block("DisplayReal", "SE.App2Base", "Display", "CAT", "Display REAL value", ["display", "real", "hmi"]),
    Block("DisplayString", "SE.App2Base", "Display", "CAT", "Display STRING value", ["display", "string", "hmi"]),
    Block("DisplayTime", "SE.App2Base", "Display", "CAT", "Display TIME value", ["display", "time", "hmi"]),

    # =============================================
    # SE.App2Base - Set CATs
    # =============================================
    Block("SetBool", "SE.App2Base", "Set", "CAT", "Set boolean value", ["set", "bool", "hmi", "input"]),
    Block("SetDint", "SE.App2Base", "Set", "CAT", "Set DINT value", ["set", "dint", "hmi", "input"]),
    Block("SetInt", "SE.App2Base", "Set", "CAT", "Set INT value", ["set", "int", "hmi", "input"]),
    Block("SetReal", "SE.App2Base", "Set", "CAT", "Set REAL value", ["set", "real", "hmi", "input"]),
    Block("SetString", "SE.App2Base", "Set", "CAT", "Set STRING value", ["set", "string", "hmi", "input"]),
    Block("SetTime", "SE.App2Base", "Set", "CAT", "Set TIME value", ["set", "time", "hmi", "input"]),

    # =============================================
    # SE.App2Base - Alarm CATs
    # =============================================
    Block("DeviationAlarm", "SE.App2Base", "Alarm", "CAT", "Deviation alarm", ["alarm", "deviation"]),
    Block("DiSignalAlarm", "SE.App2Base", "Alarm", "CAT", "Digital signal alarm", ["alarm", "digital", "signal"]),
    Block("LimitAlarm", "SE.App2Base", "Alarm", "CAT", "Limit alarm (high/low)", ["alarm", "limit", "high", "low"]),
    Block("ROCAlarm", "SE.App2Base", "Alarm", "CAT", "Rate of change alarm", ["alarm", "roc", "rate"]),
    Block("StateAlarm", "SE.App2Base", "Alarm", "CAT", "State alarm", ["alarm", "state"]),

    # =============================================
    # SE.App2Base - Other CATs
    # =============================================
    Block("AISignalScaling", "SE.App2Base", "SignalProcessing", "CAT", "Analog input scaling", ["analog", "scale", "input"]),
    Block("Mode", "SE.App2Base", "ModeControl", "CAT", "Mode control (Auto/Manual/Program)", ["mode", "auto", "manual"]),
    Block("Owner", "SE.App2Base", "OwnerControl", "CAT", "Owner control", ["owner", "control"]),
    Block("SignalDelay", "SE.App2Base", "SignalProcessing", "CAT", "Signal delay", ["signal", "delay"]),

    # =============================================
    # SE.App2CommonProcess - Signal Processing CATs
    # =============================================
    Block("AnalogInput", "SE.App2CommonProcess", "SignalProcessing", "CAT", "Analog input signal monitoring", ["analog", "input", "monitor", "ai"]),
    Block("AnalogOutput", "SE.App2CommonProcess", "SignalProcessing", "CAT", "Analog output signal conditioning", ["analog", "output", "ao"]),
    Block("DigitalInput", "SE.App2CommonProcess", "SignalProcessing", "CAT", "Digital input signal monitoring", ["digital", "input", "monitor", "di"]),
    Block("DigitalOutput", "SE.App2CommonProcess", "SignalProcessing", "CAT", "Digital output signal conditioning", ["digital", "output", "do"]),
    Block("MultiAnalogInput", "SE.App2CommonProcess", "SignalProcessing", "CAT", "Multiple analog input (up to 4)", ["analog", "multi", "input"]),
    Block("Total", "SE.App2CommonProcess", "SignalProcessing", "CAT", "Totalizer (flow totalization)", ["total", "flow", "accumulate"]),

    # =============================================
    # SE.App2CommonProcess - Motor CATs
    # =============================================
    Block("Motor", "SE.App2CommonProcess", "Motor", "CAT", "Unidirectional single-speed motor", ["motor", "single", "speed"]),
    Block("Motor2D", "SE.App2CommonProcess", "Motor", "CAT", "Two-direction motor", ["motor", "two", "direction", "reversing"]),
    Block("Motor2S", "SE.App2CommonProcess", "Motor", "CAT", "Two-speed motor", ["motor", "two", "speed"]),
    Block("MotorCyc", "SE.App2CommonProcess", "Motor", "CAT", "Cyclic motor operation", ["motor", "cyclic", "intermittent"]),
    Block("MotorVs", "SE.App2CommonProcess", "Motor", "CAT", "Variable speed motor", ["motor", "variable", "speed", "vfd"]),

    # =============================================
    # SE.App2CommonProcess - Valve CATs
    # =============================================
    Block("Valve", "SE.App2CommonProcess", "Valve", "CAT", "On/Off valve with single output", ["valve", "onoff", "solenoid"]),
    Block("Valve2Op", "SE.App2CommonProcess", "Valve", "CAT", "Valve with separate open/close commands", ["valve", "two", "output", "open", "close"]),
    Block("ValveControl", "SE.App2CommonProcess", "Valve", "CAT", "Control valve with analog position", ["valve", "control", "analog", "modulating"]),
    Block("ValveHand", "SE.App2CommonProcess", "Valve", "CAT", "Hand valve (monitor only)", ["valve", "hand", "manual", "monitor"]),
    Block("ValveM", "SE.App2CommonProcess", "Valve", "CAT", "Motorized valve", ["valve", "motor", "actuator"]),
    Block("ValveMPos", "SE.App2CommonProcess", "Valve", "CAT", "Motorized valve with positioner", ["valve", "motor", "positioner"]),

    # =============================================
    # SE.App2CommonProcess - Process Control CATs
    # =============================================
    Block("PID", "SE.App2CommonProcess", "ProcessControl", "CAT", "Standard PID controller", ["pid", "control", "loop"]),
    Block("PIDMultiplexer", "SE.App2CommonProcess", "ProcessControl", "CAT", "PID with two parameter sets", ["pid", "multiplex", "tuning"]),
    Block("LeadLag", "SE.App2CommonProcess", "ProcessControl", "CAT", "Lead/Lag compensation", ["leadlag", "compensation", "dynamic"]),
    Block("Ramp", "SE.App2CommonProcess", "ProcessControl", "CAT", "Ramp setpoint generator", ["ramp", "setpoint", "rate"]),
    Block("Ratio", "SE.App2CommonProcess", "ProcessControl", "CAT", "Ratio control", ["ratio", "control"]),
    Block("Split2Range", "SE.App2CommonProcess", "ProcessControl", "CAT", "Split range control", ["split", "range", "control"]),
    Block("Step3", "SE.App2CommonProcess", "ProcessControl", "CAT", "3-point step control", ["step", "three", "point"]),
    Block("PWM", "SE.App2CommonProcess", "ProcessControl", "CAT", "Pulse Width Modulation output", ["pwm", "pulse", "modulation"]),

    # =============================================
    # SE.App2CommonProcess - Equipment CATs
    # =============================================
    Block("FlowCtl", "SE.App2CommonProcess", "Equipment", "CAT", "Flow control module", ["flow", "control", "equipment"]),
    Block("PumpAssets", "SE.App2CommonProcess", "Equipment", "CAT", "Pump asset management", ["pump", "asset", "management"]),
    Block("PumpSet", "SE.App2CommonProcess", "Equipment", "CAT", "Pump set management (duty/standby)", ["pump", "set", "duty", "standby"]),
    Block("Scheduler", "SE.App2CommonProcess", "Equipment", "CAT", "Time-based scheduler", ["schedule", "time", "calendar"]),
    Block("AlarmSummary", "SE.App2CommonProcess", "Equipment", "CAT", "Alarm summary monitor", ["alarm", "summary", "monitor"]),

    # =============================================
    # SE.App2CommonProcess - Positioner CATs
    # =============================================
    Block("PositionerServo", "SE.App2CommonProcess", "Positioner", "CAT", "Servo drive positioner", ["positioner", "servo", "drive"]),
    Block("PositionerVSD", "SE.App2CommonProcess", "Positioner", "CAT", "VSD (Variable Speed Drive) positioner", ["positioner", "vsd", "drive"]),

    # =============================================
    # SE.App2CommonProcess - Condition Blocks
    # =============================================
    Block("ilckCondItem", "SE.App2CommonProcess", "Condition", "Composite", "Interlock condition item", ["interlock", "condition", "safety"]),
    Block("IlckCondSum", "SE.App2CommonProcess", "Condition", "CAT", "Interlock condition summary", ["interlock", "summary"]),
    Block("failCondItem", "SE.App2CommonProcess", "Condition", "Composite", "Failure condition item", ["failure", "fault", "condition"]),
    Block("FailCondSum", "SE.App2CommonProcess", "Condition", "CAT", "Failure condition summary", ["failure", "summary"]),
    Block("permCondItem", "SE.App2CommonProcess", "Condition", "Composite", "Permissive condition item", ["permissive", "condition"]),
    Block("PermCondSum", "SE.App2CommonProcess", "Condition", "CAT", "Permissive condition summary", ["permissive", "summary"]),
    Block("DevMnt", "SE.App2CommonProcess", "Condition", "CAT", "Device preventive maintenance", ["maintenance", "preventive", "device"]),

    # =============================================
    # SE.App2CommonProcess - Local Panel CATs
    # =============================================
    Block("MotorLp", "SE.App2CommonProcess", "LocalPanel", "CAT", "Motor local panel", ["motor", "local", "panel"]),
    Block("Motor2SLp", "SE.App2CommonProcess", "LocalPanel", "CAT", "Two-speed motor local panel", ["motor", "two", "speed", "local", "panel"]),
    Block("Motor2DLp", "SE.App2CommonProcess", "LocalPanel", "CAT", "Two-direction motor local panel", ["motor", "two", "direction", "local", "panel"]),
    Block("MotorVsLp", "SE.App2CommonProcess", "LocalPanel", "CAT", "Variable speed motor local panel", ["motor", "variable", "speed", "local", "panel"]),
    Block("ValveLp", "SE.App2CommonProcess", "LocalPanel", "CAT", "Valve local panel", ["valve", "local", "panel"]),
    Block("ValveMPosLp", "SE.App2CommonProcess", "LocalPanel", "CAT", "Motorized valve with position local panel", ["valve", "motor", "position", "local", "panel"]),

    # =============================================
    # SE.App2CommonProcess - Device Logic Composites
    # =============================================
    Block("motorLogic", "SE.App2CommonProcess", "DeviceLogic", "Composite", "Motor logic", ["motor", "logic"]),
    Block("motor2DLogic", "SE.App2CommonProcess", "DeviceLogic", "Composite", "Two-direction motor logic", ["motor", "two", "direction", "logic"]),
    Block("motor2SLogic", "SE.App2CommonProcess", "DeviceLogic", "Composite", "Two-speed motor logic", ["motor", "two", "speed", "logic"]),
    Block("motorCycLogic", "SE.App2CommonProcess", "DeviceLogic", "Composite", "Cyclic motor logic", ["motor", "cyclic", "logic"]),
    Block("motorVsLogic", "SE.App2CommonProcess", "DeviceLogic", "Composite", "Variable speed motor logic", ["motor", "variable", "speed", "logic"]),
    Block("valveLogic", "SE.App2CommonProcess", "DeviceLogic", "Composite", "Valve logic", ["valve", "logic"]),
    Block("valve2OpLogic", "SE.App2CommonProcess", "DeviceLogic", "Composite", "Two-output valve logic", ["valve", "two", "output", "logic"]),
    Block("valveControlLogic", "SE.App2CommonProcess", "DeviceLogic", "Composite", "Control valve logic", ["valve", "control", "logic"]),
    Block("valveHandLogic", "SE.App2CommonProcess", "DeviceLogic", "Composite", "Hand valve logic", ["valve", "hand", "logic"]),
    Block("valveMLogic", "SE.App2CommonProcess", "DeviceLogic", "Composite", "Motorized valve logic", ["valve", "motor", "logic"]),
    Block("valveMPosLogic", "SE.App2CommonProcess", "DeviceLogic", "Composite", "Motorized valve with position logic", ["valve", "motor", "position", "logic"]),

    # =============================================
    # SE.App2CommonProcess - Process Control Composites
    # =============================================
    Block("PIDCtl", "SE.App2CommonProcess", "ProcessControl", "Composite", "PID control", ["pid", "control"]),
    Block("leadLagCtl", "SE.App2CommonProcess", "ProcessControl", "Composite", "Lead/Lag control", ["leadlag", "control"]),
    Block("rampCtl", "SE.App2CommonProcess", "ProcessControl", "Composite", "Ramp control", ["ramp", "control"]),
    Block("PWMCtl", "SE.App2CommonProcess", "ProcessControl", "Composite", "PWM control", ["pwm", "control"]),

    # =============================================
    # SE.App2CommonProcess - Adapters
    # =============================================
    Block("IDevice", "SE.App2CommonProcess", "Adapter", "Adapter", "Device command/status interface", ["device", "command", "status", "adapter"]),
    Block("IFailCondSum", "SE.App2CommonProcess", "Adapter", "Adapter", "Failure condition chain", ["failure", "chain", "adapter"]),
    Block("IIlckCondSum", "SE.App2CommonProcess", "Adapter", "Adapter", "Interlock condition chain", ["interlock", "chain", "adapter"]),
    Block("IPermCondSum", "SE.App2CommonProcess", "Adapter", "Adapter", "Permissive condition chain", ["permissive", "chain", "adapter"]),
    Block("ISeqData", "SE.App2CommonProcess", "Adapter", "Adapter", "Sequence data interface", ["sequence", "data", "batch", "adapter"]),
    Block("ICascadeLoop", "SE.App2CommonProcess", "Adapter", "Adapter", "Cascade loop interface", ["cascade", "pid", "loop", "adapter"]),
    Block("IEm", "SE.App2CommonProcess", "Adapter", "Adapter", "Equipment module interface", ["equipment", "module", "adapter"]),
    Block("IPumpAsset", "SE.App2CommonProcess", "Adapter", "Adapter", "Pump asset interface", ["pump", "asset", "adapter"]),
    Block("IPositioner", "SE.App2CommonProcess", "Adapter", "Adapter", "Positioner interface", ["positioner", "adapter"]),
]

CATEGORIES = sorted(set(b.category for b in BLOCKS))
LIBRARIES = sorted(set(b.library for b in BLOCKS))


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


def format_block(block: Block, show_category: bool = False, show_library: bool = False) -> str:
    """Format a block for display."""
    parts = [f"{block.name:25}"]
    if show_library:
        lib_short = "App2Base" if "App2Base" == block.library.split(".")[-1] else "App2CommonProcess"
        parts.append(f"[{lib_short:18}]")
    if show_category:
        parts.append(f"[{block.category:15}]")
    parts.append(block.description)
    return " ".join(parts)


def main():
    parser = argparse.ArgumentParser(
        description="Lookup blocks in SE.App2Base and SE.App2CommonProcess libraries"
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
        "--library", "-l",
        action="store_true",
        help="Show library information with results"
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
                "libraries": LIBRARIES,
                "total_categories": len(CATEGORIES),
                "total_blocks": len(BLOCKS)
            }
            print(json.dumps(result, indent=2))
        else:
            print("SE Process Libraries Block Categories:")
            print("-" * 50)
            for cat in CATEGORIES:
                count = len([b for b in BLOCKS if b.category == cat])
                print(f"  {cat:25} ({count} blocks)")
            print(f"\nLibraries: {', '.join(LIBRARIES)}")
            print(f"Total: {len(CATEGORIES)} categories, {len(BLOCKS)} blocks")
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
            print("SE Process Libraries Blocks:")
            print("-" * 80)
            for lib in LIBRARIES:
                print(f"\n{'=' * 40}")
                print(f"  {lib}")
                print(f"{'=' * 40}")
                lib_blocks = [b for b in BLOCKS if b.library == lib]
                current_cat = None
                for block in sorted(lib_blocks, key=lambda b: (b.category, b.name)):
                    if block.category != current_cat:
                        current_cat = block.category
                        print(f"\n  --- {current_cat} ---")
                    print(f"    {format_block(block)}")
            print(f"\nTotal: {len(BLOCKS)} blocks across {len(LIBRARIES)} libraries")
        return 0

    # Search query required for other operations
    if not args.query:
        parser.print_help()
        return 1

    # Search blocks
    matches = search_blocks(args.query)

    if args.json:
        output = {
            "query": args.query,
            "matches": [asdict(b) for b in matches],
            "match_count": len(matches),
            "total_blocks": len(BLOCKS)
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
        print("-" * 80)
        for block in matches:
            print(f"  {format_block(block, args.category, args.library)}")
        print(f"\nFound: {len(matches)} block(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
