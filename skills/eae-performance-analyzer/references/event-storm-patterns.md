# Event Storm Anti-Patterns Catalog

Comprehensive reference for known event storm patterns identified in SE Application Design Guidelines (EIO0000004686.06) and field experience.

---

## Pattern Classification

| Severity | Description | Action Required |
|----------|-------------|-----------------|
| **CRITICAL** | Immediate system instability, Error Halt risk | Fix before deployment |
| **WARNING** | High storm probability under load | Address high-priority |
| **INFO** | Potential issue, monitor under real conditions | Optional optimization |

---

## CRITICAL Patterns

### TIGHT_EVENT_LOOP

**Description**: Event loop with cycle length ≤2 hops creates unstoppable cascade.

**Detection Rule**:
```python
def detect_tight_loop(event_graph):
    for source_fb in event_graph.nodes:
        paths = find_cycles(source_fb, max_depth=2)
        if paths:
            return CRITICAL, paths
```

**Example Scenario**:
```
ControllerFB.ProcessComplete
  → MonitorFB.Update
    → MonitorFB.StatusChanged
      → ControllerFB.ProcessStart  ← LOOP (2 hops)
```

**Root Cause**: Lack of state guard or termination condition.

**Consequences**:
- Infinite event generation
- Queue overflow in <1 second
- Resource enters Error Halt
- System unresponsive until restart

**Mitigation Strategies**:

1. **State Guard Pattern**:
```st
VAR
  m_Processing : BOOL := FALSE;
END_VAR

IF NOT m_Processing THEN
  m_Processing := TRUE;
  // Generate event
END_IF

// Reset on different event path
IF StopCondition THEN
  m_Processing := FALSE;
END_IF
```

2. **Counter-Based Limit**:
```st
VAR
  m_LoopCount : INT := 0;
  MAX_LOOPS : INT := 10;
END_VAR

IF m_LoopCount < MAX_LOOPS THEN
  m_LoopCount := m_LoopCount + 1;
  // Generate event
END_IF
```

3. **Timer-Based Debouncing**:
```
Use TON (timer on-delay) with 100ms minimum between events
```

**Real-World Example**: Alarm acknowledgment loop where ACK event triggers status update which re-triggers alarm check.

---

## WARNING Patterns

### UNCONTROLLED_IO_MULTIPLICATION

**Description**: Single I/O state change triggers >30 downstream events due to broadcast or cascading logic.

**Detection Rule**:
```python
def detect_io_multiplication(io_sources, event_graph):
    for io_source in io_sources:
        total_events = count_downstream_events(event_graph, io_source)
        if total_events > 30:
            return WARNING, io_source, total_events
```

**Example Scenario**:
```
DI_Emergency_Stop changes (rising edge)
  → SafetyController validates (5 events to 5 zones)
    → Each zone triggers:
      - AlarmFB (generates 2 events: local alarm + central alarm)
      - LoggerFB (1 event)
      - HMIFB (1 event)
    → 5 zones × 4 events/zone = 20 events
  → Central alarm triggers:
    - NotificationFB to 10 operators (10 events)
    - HistorianFB (1 event)
    - MESIntegrationFB (1 event)

Total: 1 (source) + 5 + 20 + 12 = 38 events from 1 I/O change
```

**Root Cause**: Broadcast patterns without consolidation.

**Consequences**:
- I/O events occur at bus cycle rate (10-100ms)
- 38 events × 10 Hz = 380 events/second baseline load
- Leaves minimal headroom for other sources
- Burst scenarios (multiple I/O simultaneously) cause saturation

**Mitigation Strategies**:

1. **EventChainHead Consolidation** (SE.AppSequence library):
```
Instead of: IO → 30 FBs (30 events)
Use:        IO → EventChainHead → CHAIN_EVENT → 30 FBs
Result:     3 events (input, consolidation, output)
```

2. **Adapter Encapsulation**:
```
Create Composite FB "EmergencyStopHandler":
  - Input: IEmergencyStop adapter (Socket)
  - Internal: All 30 FB instances (hidden)
  - Output: IEmergencyResponse adapter (Plug)

External view: IO → Socket → Plug → Next stage (3 visible events)
Internal reality: 30 events contained within Composite
```

3. **Event Filtering**:
```st
// Only propagate on rising edge, not every cycle
VAR
  m_LastState : BOOL := FALSE;
END_VAR

IF iInputState AND NOT m_LastState THEN
  // State changed to TRUE - propagate
  m_LastState := TRUE;
ELSIF NOT iInputState AND m_LastState THEN
  // State changed to FALSE - different handling
  m_LastState := FALSE;
END_IF
```

**Real-World Example**: Emergency stop in multi-zone factory triggers all zones simultaneously, each logging and alarming independently.

---

### CASCADING_TIMERS

**Description**: Multiple fast timers (E_CYCLE <50ms) on same resource create high baseline event frequency.

**Detection Rule**:
```python
def detect_cascading_timers(resource_fbs):
    timer_frequencies = []
    for fb in resource_fbs:
        if fb.has_e_cycle:
            freq_hz = 1000 / fb.cycle_time_ms
            timer_frequencies.append(freq_hz)

    total_freq = sum(timer_frequencies)
    if total_freq > 100:  # >100 Hz aggregate
        return WARNING, timer_frequencies, total_freq
```

**Example Scenario**:
```
Resource_PLC1:
  - TrendFB: E_CYCLE at 20ms (50 Hz)
  - PIDController: E_CYCLE at 25ms (40 Hz)
  - DataLoggerFB: E_CYCLE at 30ms (33 Hz)
  - WatchdogFB: E_CYCLE at 40ms (25 Hz)

Total: 50 + 40 + 33 + 25 = 148 Hz baseline load
```

**Root Cause**: Lack of timer frequency budgeting per resource.

**Consequences**:
- Constant event load (148 events/second) before any I/O, HMI, or logic events
- CPU spends most time on timer events, little headroom for critical events
- Jitter in control loops due to resource contention

**Mitigation Strategies**:

1. **Frequency Reduction** (criticality-based):
```
Safety/Control: Keep fast (10-50ms) - deterministic behavior required
Trending:       Slow to 200-500ms - data collection, not real-time
Logging:        Slow to 500-1000ms - persistence, not time-critical
Heartbeats:     Slow to 1000-5000ms - alive check, not frequent
```

2. **Timer Consolidation**:
```
Instead of: 4 FBs with separate timers (148 Hz)
Use:        1 MasterTimer FB at 25ms (40 Hz)
            - Divider logic for slower rates (2x, 4x, 8x)
            - Synchronized tick events to other FBs

Result: 40 Hz + 4 divider events = 44 Hz total
```

3. **Resource Distribution**:
```
Move non-critical timers to dedicated "BackgroundProcessing" resource:
  Resource_PLC1 (critical): PIDController only (40 Hz)
  Resource_PLC2 (background): Trending, Logging, Watchdog (108 Hz)
```

**Real-World Example**: Data logging system with trending (20ms), alarming (30ms), historian (40ms), and backup (50ms) all on same PLC.

---

### CROSS_RESOURCE_AMPLIFICATION

**Description**: Event crossing resource boundary (via OPC-UA) triggers >15 events on target resource due to cascade amplification + network latency.

**Detection Rule**:
```python
def detect_cross_resource_amplification(connections):
    for conn in connections:
        if conn.source_resource != conn.target_resource:
            target_events = count_downstream_events(
                event_graph, conn.target_fb
            )
            if target_events > 15:
                return WARNING, conn, target_events
```

**Example Scenario**:
```
Resource_HMI.SetpointChanged
  → [OPC-UA: 10-50ms network latency]
    → Resource_PLC1.SetpointController
      → Validates setpoint (2 events)
      → Updates 5 process zones (5 events)
        → Each zone triggers FB cascade (2 events × 5 = 10 events)

Total on Resource_PLC1: 1 (received) + 2 + 5 + 10 = 18 events
```

**Root Cause**: Cross-resource connections treated same as local connections without considering network latency and target-side multiplication.

**Consequences**:
- Network latency (10-100ms) delays event delivery
- Target resource receives burst of delayed events
- Multiplication on target side amplifies single cross-resource event
- Can saturate target resource while source is idle

**Mitigation Strategies**:

1. **Rate Limiting on Source**:
```st
// HMI side: Limit setpoint updates to 1 per second
VAR
  m_LastSentTime : TIME;
  MIN_INTERVAL : TIME := T#1s;
END_VAR

IF (CurrentTime - m_LastSentTime) >= MIN_INTERVAL THEN
  // Send setpoint change
  m_LastSentTime := CurrentTime;
END_IF
```

2. **Adapter Consolidation on Target**:
```
Instead of: CrossResourceEvent → 18 FBs directly
Use:        CrossResourceEvent → AdapterComposite → Consolidation
Result:     3 events visible externally, 18 internal to Composite
```

3. **Minimize Cross-Resource Events**:
```
Design principle: Keep tightly-coupled FBs on same resource
- Control loops: Same resource (no network delay)
- HMI updates: Batch multiple changes into single event
- Cross-resource: Only for loosely-coupled subsystems
```

**Real-World Example**: HMI running on separate PC sends setpoint changes over Ethernet to PLC, triggering validation + 10 zone updates + alarming.

---

## INFO Patterns

### HMI_BURST_AMPLIFICATION

**Description**: HMI operator interaction triggers >10 downstream events, which is normal but can create bursts under rapid interaction.

**Detection Rule**:
```python
def detect_hmi_burst(hmi_sources, event_graph):
    for hmi_source in hmi_sources:
        total_events = count_downstream_events(event_graph, hmi_source)
        if total_events > 10:
            return INFO, hmi_source, total_events
```

**Example Scenario**:
```
HMI Button "Start Production"
  → ControllerFB.StartSequence (2 events)
    → 5 ProcessFBs initialize (5 events)
      → Each logs startup (5 events)
        → Central monitor updated (1 event)

Total: 1 + 2 + 5 + 5 + 1 = 14 events
```

**Root Cause**: Normal application logic, but vulnerable to rapid operator actions (button mashing, slider dragging).

**Consequences**:
- Single button click: 14 events (acceptable)
- Rapid clicking (5 clicks in 1 second): 70 events (burst)
- Slider dragging (50 updates in 2 seconds): 700 events (saturation)

**Mitigation Strategies**:

1. **Debouncing**:
```
Add 100-200ms delay after HMI event before accepting next
Prevents button mashing
```

2. **Rate Limiting**:
```
Accept max 5 events per second from any single HMI control
```

3. **Operator Training**:
```
Educate operators on proper interaction patterns
```

**Note**: This is INFO severity because it's expected behavior, only becomes problematic under abuse.

---

## Pattern Interaction Matrix

Multiple patterns can co-occur, amplifying storm risk:

| Pattern 1 | Pattern 2 | Combined Effect |
|-----------|-----------|-----------------|
| CASCADING_TIMERS (148 Hz) | UNCONTROLLED_IO (38 events) | 148 + 380 = 528 events/second baseline |
| CROSS_RESOURCE_AMPLIFICATION (18 events) | HMI_BURST (14 events) | Cross-resource HMI creates 252 events (18 × 14) |
| TIGHT_EVENT_LOOP | ANY OTHER PATTERN | Infinite multiplication, immediate failure |

**Detection**: `detect_storm_patterns.py` identifies all patterns independently, synthesis phase combines severity levels.

---

## Pattern Evolution

As EAE applications grow in complexity, new patterns may emerge. Extension mechanism:

1. Add pattern definition to `detect_storm_patterns.py`:
```python
PATTERN_DEFINITIONS = {
    "NEW_PATTERN_NAME": {
        "severity": "WARNING",
        "threshold": 25,
        "description": "Pattern description",
        "detection_fn": detect_new_pattern,
        "recommendation": "Fix recommendation"
    }
}
```

2. Update this reference document with detailed analysis

3. Report pattern to SE for potential inclusion in future Application Design Guidelines

---

## References

- SE Application Design Guidelines (EIO0000004686.06) - Section 4: "Event Storms Risk Mitigation"
- IEC 61499 Standard - Event-driven execution model
- SE.AppSequence Library Documentation - EventChainHead usage
