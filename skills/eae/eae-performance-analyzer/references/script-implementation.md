# Script Implementation Details

Technical documentation for the 4 autonomous Python scripts that power eae-performance-analyzer.

---

## Architecture Overview

```
analyze_event_flow.py ──┐
                        │
estimate_cpu_load.py ───┼──→ JSON Results ──→ Synthesis (Claude) ──→ Report
                        │
predict_queue_depth.py ─┤      ↑
                        │      │ (depends on event flow results)
detect_storm_patterns.py┘
```

**Design Principles**:
1. **Independence**: Scripts run standalone or together (except queue predictor depends on event flow)
2. **Standard Library Only**: No external dependencies (portability)
3. **Structured Output**: JSON for machine parsing, human-readable stderr logging
4. **Semantic Exit Codes**: 0=safe, 10=moderate, 11=critical, 1=error
5. **Self-Verification**: Input validation, sanity checks, graceful degradation

---

## 1. analyze_event_flow.py

### Algorithm: Event Cascade Tracing

```python
def trace_event_cascade(fb_network, event_source):
    """
    BFS traversal of event propagation graph.
    Returns all paths from source to leaf FBs with event counts.
    """
    queue = [(event_source, [event_source], 1)]  # (current_fb, path, event_count)
    cascade_paths = []
    visited = set()

    while queue:
        current_fb, path, events = queue.pop(0)

        # Get all output events from current FB
        output_events = get_output_events(current_fb)

        for out_event in output_events:
            # Find target FBs connected to this event
            targets = find_connected_fbs(fb_network, current_fb, out_event)

            for target_fb in targets:
                new_path = path + [target_fb]
                new_events = events + 1  # Each connection adds 1 event

                if target_fb not in visited:
                    visited.add(target_fb)
                    queue.append((target_fb, new_path, new_events))

                    # If target has no output events, it's a leaf
                    if not has_output_events(target_fb):
                        cascade_paths.append({
                            "source": event_source,
                            "path": new_path,
                            "events_generated": new_events
                        })

    return cascade_paths
```

### Multiplication Factor Calculation

```python
def calculate_multiplication_factor(cascade_paths):
    """
    Multiplication = Total events generated across all paths / 1 source event
    """
    total_events = sum(path["events_generated"] for path in cascade_paths)
    return total_events / 1.0  # Divide by 1 source event
```

### Cycle Detection (TIGHT_EVENT_LOOP)

```python
def detect_cycles(fb_network, max_depth=2):
    """
    DFS with depth limit to find cycles.
    Returns True if FB event loops back to itself within max_depth hops.
    """
    for source_fb in fb_network.nodes:
        visited_stack = []

        def dfs(current_fb, depth):
            if depth > max_depth:
                return False
            if current_fb == source_fb and depth > 0:
                return True  # Cycle detected

            visited_stack.append(current_fb)
            targets = get_connected_fbs(fb_network, current_fb)

            for target in targets:
                if target not in visited_stack:
                    if dfs(target, depth + 1):
                        return True

            visited_stack.pop()
            return False

        if dfs(source_fb, 0):
            return True, source_fb  # Cycle found

    return False, None
```

### File Parsing

**IEC 61499 .fbt File Structure**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<FBType Name="ControllerFB" Comment="Main controller">
  <InterfaceList>
    <EventInputs>
      <Event Name="INIT" Comment="Initialize"/>
      <Event Name="START" Comment="Start process"/>
    </EventInputs>
    <EventOutputs>
      <Event Name="INITO" Comment="Initialization complete"/>
      <Event Name="READY" Comment="Ready for processing"/>
    </EventOutputs>
    <InputVars>
      <VarDeclaration Name="iSetpoint" Type="REAL"/>
    </InputVars>
    <OutputVars>
      <VarDeclaration Name="oStatus" Type="BOOL"/>
    </OutputVars>
  </InterfaceList>
  <FBNetwork>
    <FB Name="ProcessFB1" Type="ProcessController"/>
    <FB Name="LoggerFB" Type="DataLogger"/>
    <EventConnections>
      <Connection Source="INIT" Destination="ProcessFB1.INIT"/>
      <Connection Source="ProcessFB1.DONE" Destination="LoggerFB.LOG"/>
    </EventConnections>
  </FBNetwork>
</FBType>
```

**Parsing Strategy**:
```python
import xml.etree.ElementTree as ET

def parse_fbt_file(filepath):
    tree = ET.parse(filepath)
    root = tree.getroot()

    fb_type = {
        "name": root.get("Name"),
        "event_inputs": [],
        "event_outputs": [],
        "fb_network": [],
        "event_connections": []
    }

    # Parse interface
    interface = root.find("InterfaceList")
    for event in interface.findall(".//EventInputs/Event"):
        fb_type["event_inputs"].append(event.get("Name"))
    for event in interface.findall(".//EventOutputs/Event"):
        fb_type["event_outputs"].append(event.get("Name"))

    # Parse FBNetwork
    fbnetwork = root.find("FBNetwork")
    if fbnetwork:
        for fb in fbnetwork.findall("FB"):
            fb_type["fb_network"].append({
                "name": fb.get("Name"),
                "type": fb.get("Type")
            })
        for conn in fbnetwork.findall(".//EventConnections/Connection"):
            fb_type["event_connections"].append({
                "source": conn.get("Source"),
                "destination": conn.get("Destination")
            })

    return fb_type
```

### Output Format

```json
{
  "multiplication_factors": {
    "INIT": 5.0,
    "START": 12.5,
    "DI_EmergencyStop": 38.0
  },
  "cascade_paths": [
    {
      "source": "INIT",
      "path": ["ControllerFB", "ProcessFB1", "LoggerFB"],
      "events_generated": 3
    },
    {
      "source": "START",
      "path": ["ControllerFB", "ProcessFB1", "ProcessFB2", "AlarmFB"],
      "events_generated": 4
    }
  ],
  "explosive_patterns": [
    {
      "source": "DI_EmergencyStop",
      "multiplication": 38.0,
      "severity": "WARNING",
      "recommendation": "Use EventChainHead or adapter consolidation"
    }
  ],
  "resource_breakdown": {
    "Resource_PLC1": {
      "avg_multiplication": 8.5,
      "max_multiplication": 38.0,
      "event_sources": ["INIT", "START", "DI_EmergencyStop"]
    }
  },
  "cycles_detected": [
    {
      "fb": "ControllerFB",
      "cycle_path": ["ControllerFB", "ProcessFB", "ControllerFB"],
      "severity": "CRITICAL"
    }
  ]
}
```

---

## 2. estimate_cpu_load.py

### Algorithm: ST Code Complexity Analysis

```python
def calculate_cyclomatic_complexity(st_code):
    """
    Simplified cyclomatic complexity for ST algorithms.
    CC = 1 + number of decision points (IF, CASE, FOR, WHILE, REPEAT)
    """
    decision_keywords = ["IF", "ELSIF", "CASE", "FOR", "WHILE", "REPEAT"]
    complexity = 1

    for keyword in decision_keywords:
        # Count occurrences (case-insensitive)
        complexity += st_code.upper().count(keyword)

    return complexity
```

### Execution Time Estimation

```python
def estimate_execution_time(st_code, complexity):
    """
    Heuristic execution time estimation.
    Base time: 10μs per complexity point
    + 1μs per arithmetic/logic operation
    + 0.5μs per variable access
    """
    # Count operations (simplified regex patterns)
    arithmetic_ops = count_pattern(st_code, r'[\+\-\*/]')
    logical_ops = count_pattern(st_code, r'(AND|OR|XOR|NOT)')
    comparisons = count_pattern(st_code, r'(<|>|=|<=|>=|<>)')
    var_accesses = count_pattern(st_code, r'\b[a-z_][a-z0-9_]*\b', re.I)

    base_time = complexity * 10  # μs
    operation_time = (arithmetic_ops + logical_ops + comparisons) * 1  # μs
    access_time = var_accesses * 0.5  # μs

    total_time = base_time + operation_time + access_time
    return total_time  # μs
```

### Platform Adjustment Factors

```python
PLATFORM_FACTORS = {
    "soft-dpac-windows": 1.0,  # Baseline (high-end x86)
    "soft-dpac-linux": 0.9,     # Slightly faster (no Windows overhead)
    "hard-dpac-m262": 1.2,      # Faster embedded CPU
    "hard-dpac-m251": 1.5,      # Slower embedded CPU
    "unknown": 1.0              # Default to baseline
}

def adjust_for_platform(execution_time_us, platform):
    factor = PLATFORM_FACTORS.get(platform, 1.0)
    return execution_time_us * factor
```

### Resource CPU Load Aggregation

```python
def aggregate_cpu_load(fbs_on_resource, event_frequencies):
    """
    CPU Load % = (Σ FB execution time × event frequency) / 1_000_000 μs/s × 100
    """
    total_load_us_per_second = 0

    for fb in fbs_on_resource:
        exec_time_us = fb["execution_time"]
        frequency_hz = get_event_frequency(fb, event_frequencies)
        load_us_per_second = exec_time_us * frequency_hz

        total_load_us_per_second += load_us_per_second

    cpu_load_percent = (total_load_us_per_second / 1_000_000) * 100
    return cpu_load_percent
```

### ST Code Parsing Example

```st
ALGORITHM algProcess
  (* Calculate scaled output *)
  IF iEnable THEN
    oScaledValue := iInputValue * iScaleFactor;

    (* Check limits *)
    IF oScaledValue > iMaxLimit THEN
      oScaledValue := iMaxLimit;
      oLimitExceeded := TRUE;
    ELSIF oScaledValue < iMinLimit THEN
      oScaledValue := iMinLimit;
      oLimitExceeded := TRUE;
    ELSE
      oLimitExceeded := FALSE;
    END_IF;
  ELSE
    oScaledValue := 0.0;
    oLimitExceeded := FALSE;
  END_IF;
END_ALGORITHM
```

**Analysis**:
- Cyclomatic Complexity: 1 + 1 (IF) + 1 (IF) + 1 (ELSIF) = 4
- Arithmetic ops: 1 (multiplication)
- Comparisons: 3 (>, <, enable check)
- Variable accesses: ~15

**Estimated Execution Time**:
```
Base: 4 × 10 = 40μs
Operations: (1 + 3) × 1 = 4μs
Access: 15 × 0.5 = 7.5μs
Total: 40 + 4 + 7.5 = 51.5μs
```

**CPU Load** (if executed at 10 Hz):
```
51.5μs × 10 Hz = 515μs/s = 0.0515% CPU
```

### Output Format

```json
{
  "fb_execution_estimates": {
    "ControllerFB": {
      "algorithm": "algProcess",
      "complexity": 4,
      "estimated_us": 51.5,
      "platform_adjusted_us": 61.8,
      "platform": "hard-dpac-m262",
      "uncertainty": "±50%"
    },
    "ProcessFB1": {
      "algorithm": "algCalculate",
      "complexity": 8,
      "estimated_us": 120.0,
      "platform_adjusted_us": 144.0,
      "platform": "hard-dpac-m262"
    }
  },
  "resource_cpu_load": {
    "Resource_PLC1": {
      "total_load_pct": 45.2,
      "headroom_pct": 54.8,
      "bottleneck_fbs": ["ProcessFB1", "DataLoggerFB"],
      "load_breakdown": {
        "ControllerFB": 5.2,
        "ProcessFB1": 15.8,
        "DataLoggerFB": 12.1,
        "OtherFBs": 12.1
      }
    }
  },
  "overall_assessment": {
    "highest_load_resource": "Resource_PLC1",
    "load_pct": 45.2,
    "status": "SAFE",
    "recommendation": "Ample headroom available"
  },
  "uncertainty_note": "Execution time estimates are heuristic-based and may vary ±50% due to compiler optimizations, cache effects, and OS scheduling."
}
```

---

## 3. predict_queue_depth.py

### Algorithm: Queue Simulation

```python
def simulate_queue_depth(event_sources, multiplication_factors, scenario="normal"):
    """
    Simulate queue behavior under different load scenarios.
    Models both external and internal queues per resource.
    """
    # Scenario multipliers
    scenario_multipliers = {
        "normal": 1.0,
        "burst": 2.0,     # 2× event rate for 5 seconds
        "worst-case": 5.0  # 5× rate + all timers aligned
    }

    multiplier = scenario_multipliers[scenario]
    simulation_duration_s = 10  # Simulate 10 seconds
    time_step_ms = 10  # 10ms resolution

    # Initialize queues per resource
    queues = {
        resource: {"external": 0, "internal": 0}
        for resource in get_all_resources()
    }

    peak_depths = {resource: {"external": 0, "internal": 0} for resource in queues}

    # Simulate time steps
    for t_ms in range(0, simulation_duration_s * 1000, time_step_ms):
        # Generate events from sources
        for source in event_sources:
            if should_fire(source, t_ms, multiplier):
                resource = source["resource"]
                queues[resource]["external"] += 1

        # Process events (simplified model)
        for resource in queues:
            # Process 1 external event per time step (if any)
            if queues[resource]["external"] > 0:
                queues[resource]["external"] -= 1

                # External event generates internal events (multiplication)
                mult_factor = get_multiplication_factor(resource, multiplication_factors)
                queues[resource]["internal"] += int(mult_factor)

            # Process internal events (higher rate)
            process_rate = 10  # Process up to 10 internal events per 10ms
            processed = min(queues[resource]["internal"], process_rate)
            queues[resource]["internal"] -= processed

            # Track peak depths
            if queues[resource]["external"] > peak_depths[resource]["external"]:
                peak_depths[resource]["external"] = queues[resource]["external"]
            if queues[resource]["internal"] > peak_depths[resource]["internal"]:
                peak_depths[resource]["internal"] = queues[resource]["internal"]

    return peak_depths
```

### Event Source Modeling

```python
def should_fire(event_source, time_ms, scenario_multiplier):
    """
    Determine if event source fires at given time.
    """
    source_type = event_source["type"]

    if source_type == "IO":
        # I/O fires at bus cycle rate
        cycle_ms = event_source["bus_cycle_ms"]
        base_frequency = 1000 / cycle_ms  # Hz
        adjusted_frequency = base_frequency * scenario_multiplier
        period_ms = 1000 / adjusted_frequency
        return (time_ms % period_ms) < 1

    elif source_type == "TIMER":
        # Timer fires at specified interval
        interval_ms = event_source["interval_ms"]
        return (time_ms % interval_ms) < 1

    elif source_type == "HMI":
        # HMI fires randomly (Poisson distribution approximation)
        avg_rate_hz = event_source.get("avg_rate_hz", 0.5)
        adjusted_rate = avg_rate_hz * scenario_multiplier
        probability = adjusted_rate * (10 / 1000)  # 10ms time step
        return random.random() < probability

    elif source_type == "CROSS_COMM":
        # Cross-communication at specified rate
        rate_hz = event_source.get("rate_hz", 5)
        adjusted_rate = rate_hz * scenario_multiplier
        period_ms = 1000 / adjusted_rate
        return (time_ms % period_ms) < 1

    return False
```

### Output Format

```json
{
  "queue_predictions": {
    "Resource_PLC1": {
      "external_queue": {
        "normal": 12,
        "burst": 87,
        "worst_case": 245
      },
      "internal_queue": {
        "normal": 45,
        "burst": 320,
        "worst_case": 1250
      },
      "overflow_risk": "HIGH",
      "recommendation": "Worst-case scenario exceeds 1000 events. Reduce event multiplication or increase processing capacity."
    }
  },
  "event_sources_contribution": {
    "IO_CHANGE": "35%",
    "HMI_INTERACTION": "25%",
    "TIMERS": "20%",
    "CROSS_COMMUNICATION": "15%",
    "INTERNAL_LOGIC": "5%"
  },
  "recommendations": [
    "Reduce timer frequency on Resource_PLC1 (currently 148 Hz aggregate)",
    "Consolidate HMI events using adapter pattern",
    "Consider distributing high-load FBs to Resource_PLC2"
  ]
}
```

---

## 4. detect_storm_patterns.py

### Algorithm: Rule-Based Pattern Matching

```python
PATTERN_DEFINITIONS = {
    "TIGHT_EVENT_LOOP": {
        "severity": "CRITICAL",
        "detection_fn": detect_tight_loop,
        "threshold": 2,  # max hops
        "recommendation": "Break loop with state guard or timer debouncing"
    },
    "UNCONTROLLED_IO_MULTIPLICATION": {
        "severity": "WARNING",
        "detection_fn": detect_io_multiplication,
        "threshold": 30,  # max events
        "recommendation": "Use EventChainHead or adapter consolidation"
    },
    "CASCADING_TIMERS": {
        "severity": "WARNING",
        "detection_fn": detect_cascading_timers,
        "threshold": 100,  # Hz aggregate
        "recommendation": "Reduce timer frequencies or distribute across resources"
    },
    "HMI_BURST_AMPLIFICATION": {
        "severity": "INFO",
        "detection_fn": detect_hmi_burst,
        "threshold": 10,  # events per interaction
        "recommendation": "Add debouncing (100-200ms delay)"
    },
    "CROSS_RESOURCE_AMPLIFICATION": {
        "severity": "WARNING",
        "detection_fn": detect_cross_resource_amplification,
        "threshold": 15,  # events on target
        "recommendation": "Reduce cross-resource event frequency or use adapters"
    }
}

def detect_all_patterns(fb_network, event_graph):
    detected = []

    for pattern_name, pattern_def in PATTERN_DEFINITIONS.items():
        detection_fn = pattern_def["detection_fn"]
        result = detection_fn(fb_network, event_graph, pattern_def["threshold"])

        if result["found"]:
            detected.append({
                "pattern": pattern_name,
                "severity": pattern_def["severity"],
                "locations": result["locations"],
                "description": result["description"],
                "recommendation": pattern_def["recommendation"]
            })

    return detected
```

### Pattern Detection Functions

```python
def detect_tight_loop(fb_network, event_graph, max_depth):
    """Detect event cycles with depth ≤ max_depth."""
    cycles = []
    for source_fb in fb_network.nodes:
        cycle_path = find_cycle_dfs(event_graph, source_fb, max_depth)
        if cycle_path:
            cycles.append({
                "fb": source_fb,
                "path": cycle_path,
                "file": get_fb_file(source_fb)
            })

    if cycles:
        return {
            "found": True,
            "locations": cycles,
            "description": f"Event loops back to source within {max_depth} hops"
        }
    return {"found": False}

def detect_io_multiplication(fb_network, event_graph, threshold):
    """Detect I/O events with high multiplication."""
    io_sources = get_io_event_sources(fb_network)
    violations = []

    for io_source in io_sources:
        total_events = count_downstream_events(event_graph, io_source)
        if total_events > threshold:
            violations.append({
                "io_channel": io_source,
                "multiplier": total_events,
                "file": get_io_config_file()
            })

    if violations:
        return {
            "found": True,
            "locations": violations,
            "description": f"Single I/O event triggers >{threshold} downstream events"
        }
    return {"found": False}

def detect_cascading_timers(fb_network, event_graph, threshold_hz):
    """Detect high aggregate timer frequency per resource."""
    violations = []
    resources = get_all_resources(fb_network)

    for resource in resources:
        timers = get_timers_on_resource(resource, fb_network)
        total_freq_hz = sum(1000 / timer["interval_ms"] for timer in timers)

        if total_freq_hz > threshold_hz:
            violations.append({
                "resource": resource,
                "aggregate_freq_hz": total_freq_hz,
                "timers": timers
            })

    if violations:
        return {
            "found": True,
            "locations": violations,
            "description": f"Aggregate timer frequency >{threshold_hz} Hz on single resource"
        }
    return {"found": False}
```

### Output Format

```json
{
  "detected_patterns": [
    {
      "pattern": "TIGHT_EVENT_LOOP",
      "severity": "CRITICAL",
      "description": "FB generates event that loops back to itself within 2 hops",
      "locations": [
        {
          "fb": "ControllerFB",
          "path": ["ControllerFB", "ProcessFB", "ControllerFB"],
          "file": "Controller.fbt",
          "line": 45
        }
      ],
      "recommendation": "Break loop with state guard or timer-based debouncing"
    },
    {
      "pattern": "UNCONTROLLED_IO_MULTIPLICATION",
      "severity": "WARNING",
      "description": "Single I/O event triggers >30 downstream events",
      "locations": [
        {
          "io_channel": "DI_Emergency_Stop",
          "multiplier": 38,
          "bus_cycle_ms": 10
        }
      ],
      "recommendation": "Use EventChainHead (SE.AppSequence) or adapter consolidation"
    }
  ],
  "pattern_summary": {
    "CRITICAL": 1,
    "WARNING": 1,
    "INFO": 0,
    "total": 2
  }
}
```

---

## Common Patterns and Utilities

### Result Dataclass

All scripts use a consistent Result pattern:

```python
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

@dataclass
class ValidationResult:
    """Structured result for script outputs."""
    success: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]
    exit_code: int = 0

    def to_json(self):
        """Convert to JSON-serializable dict."""
        return asdict(self)

    @property
    def severity(self):
        """Map exit code to severity."""
        if self.exit_code == 0:
            return "SAFE"
        elif self.exit_code == 10:
            return "CAUTION/WARNING"
        elif self.exit_code == 11:
            return "CRITICAL"
        else:
            return "ERROR"
```

### CLI Argument Parsing

```python
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Analyze event flow in EAE application"
    )
    parser.add_argument(
        "--app-dir",
        required=True,
        help="Path to EAE application directory"
    )
    parser.add_argument(
        "--resource",
        help="Specific resource name for incremental analysis"
    )
    parser.add_argument(
        "--output",
        help="Path for JSON report output (default: stdout)"
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Generate Graphviz DOT file for event flow diagram"
    )
    return parser.parse_args()
```

### File Discovery

```python
from pathlib import Path

def find_eae_files(app_dir, pattern="*.fbt"):
    """Recursively find EAE artifact files."""
    app_path = Path(app_dir)
    return list(app_path.rglob(pattern))

def find_all_artifacts(app_dir):
    """Find all EAE artifacts (.fbt, .cfg, .xml)."""
    return {
        "fbt": find_eae_files(app_dir, "*.fbt"),
        "cfg": find_eae_files(app_dir, "*.cfg"),
        "xml": find_eae_files(app_dir, "*.xml")
    }
```

### Error Handling

```python
def safe_parse_xml(filepath):
    """Parse XML with error handling."""
    try:
        tree = ET.parse(filepath)
        return tree.getroot(), None
    except ET.ParseError as e:
        return None, f"XML parsing error in {filepath}: {e}"
    except FileNotFoundError:
        return None, f"File not found: {filepath}"
    except Exception as e:
        return None, f"Unexpected error parsing {filepath}: {e}"
```

---

## Testing and Validation

### Unit Test Examples

```python
import unittest

class TestEventFlowAnalysis(unittest.TestCase):
    def test_multiplication_factor_calculation(self):
        """Test event multiplication calculation."""
        cascade_paths = [
            {"events_generated": 3},
            {"events_generated": 5},
            {"events_generated": 2}
        ]
        factor = calculate_multiplication_factor(cascade_paths)
        self.assertEqual(factor, 10.0)  # (3 + 5 + 2) / 1

    def test_cycle_detection(self):
        """Test tight loop detection."""
        # Create simple graph: A → B → A
        graph = {
            "A": ["B"],
            "B": ["A"]
        }
        has_cycle, node = detect_cycle(graph, "A", max_depth=2)
        self.assertTrue(has_cycle)
        self.assertEqual(node, "A")
```

### Integration Test

```bash
# Test on sample EAE application
python scripts/analyze_event_flow.py \
  --app-dir ./test/sample_app \
  --output ./test/results/event_flow.json

# Verify exit code
if [ $? -eq 0 ]; then
  echo "Analysis passed: SAFE"
elif [ $? -eq 10 ]; then
  echo "Analysis passed: MODERATE risk"
elif [ $? -eq 11 ]; then
  echo "Analysis passed: HIGH risk"
else
  echo "Analysis FAILED: Error"
  exit 1
fi

# Verify JSON output
python -m json.tool ./test/results/event_flow.json > /dev/null
```

---

## Performance Benchmarks

| Application Size | Analysis Time | Memory Usage |
|------------------|---------------|--------------|
| Small (<100 FBs) | <1 second | <50 MB |
| Medium (100-500 FBs) | <10 seconds | <200 MB |
| Large (500-1000 FBs) | <60 seconds | <500 MB |
| Very Large (>1000 FBs) | <120 seconds | <1 GB |

**Optimization Techniques**:
- Lazy loading of FB definitions (parse on-demand)
- Graph caching (avoid re-parsing same FBs)
- Incremental analysis (--resource flag)
- Parallel processing (future enhancement)

---

## References

- Python Standard Library Documentation
- IEC 61499 XML Schema
- SE EcoStruxure Automation Expert File Formats
- Graph Algorithms (BFS, DFS, Cycle Detection)
