# EAE Concepts Primer

**Purpose**: Foundational concepts for EcoStruxure Automation Expert (EAE) and IEC 61499.

**Audience**: Developers, automation engineers, and Claude when working with EAE skills.

**Format**: Conceptual guide with examples and comparison tables.

---

## Table of Contents

1. [EcoStruxure Automation Expert Ecosystem](#ecostruxure-automation-expert-ecosystem)
2. [IEC 61499 Fundamentals](#iec-61499-fundamentals)
3. [Function Block Types](#function-block-types)
4. [Adapters (Socket/Plug Pattern)](#adapters-socketplug-pattern)
5. [CAT Block Structure](#cat-block-structure)
6. [Type System](#type-system)
7. [Standard Libraries](#standard-libraries)
8. [Development Workflow](#development-workflow)
9. [Quick Reference Tables](#quick-reference-tables)
10. [Glossary](#glossary)

---

## EcoStruxure Automation Expert Ecosystem

### What is EAE?

**EcoStruxure Automation Expert** is Schneider Electric's ecosystem for industrial automation, conforming to the IEC 61499 standard. It offers an automation paradigm based on object-oriented models and event-driven mechanisms.

### Ecosystem Components

| Component | Description | Role |
|-----------|-------------|------|
| **EAE Buildtime** | Engineering tool | Design, commission, and maintain applications |
| **dPACs** | Distributed Programmable Automation Controllers | Host running applications |
| **HMI** | Human-Machine Interface | Operator interaction during runtime |
| **Archive Engine** | Historization system | Trend and alarm management |
| **ASP Interface** | AVEVA System Platform | Supervisory level integration |

### Core Principles

| Principle | Description | Benefit |
|-----------|-------------|---------|
| **Asset-Centric** | Real devices and applications represented as software objects (CATs) | Control intelligence + visualization unified, reusable with low effort |
| **Hardware Independent** | Application logic designed at application level | Run on one or more dPACs, change structure with low effort |
| **Event-Driven** | Execute on-demand as events occur | Efficient resource usage, dedicated dPACs for high-load parts |
| **Distributed Control** | Fixed system structure not required | Communications between dPACs transparently managed |

**Key Distinction from IEC 61131-3**:
- **IEC 61131-3** (traditional PLCs): Cyclic scan-based execution, device-centric
- **IEC 61499** (EAE): Event-driven execution, application-centric, portable across devices

---

## IEC 61499 Fundamentals

### Function Block Model

Every function block in IEC 61499 has a defined structure:

```
┌─────────────────────────────────────┐
│  HEAD (Event Interface)             │
│  ← EventIn1    EventOut1 →          │
│  ← EventIn2    EventOut2 →          │
├─────────────────────────────────────┤
│  BODY (Data Interface)              │
│  ← DataIn1     DataOut1 →           │
│  ← DataIn2     DataOut2 →           │
│     (Type)       (Type)             │
└─────────────────────────────────────┘
```

**Components**:
- **Event Inputs** (left side of head): Trigger processing of algorithms
- **Event Outputs** (right side of head): Fire after algorithm execution
- **Data Inputs** (left side of body): Values to be processed
- **Data Outputs** (right side of body): Results after processing

**Execution Model**:
1. Event arrives at event input
2. Associated data inputs are sampled
3. Internal algorithm executes
4. Data outputs are updated
5. Event output fires
6. FB returns to idle state

**WITH Associations**: Events can be associated with specific data variables (e.g., "REQ event carries Temperature and Setpoint data").

---

## Function Block Types

IEC 61499 defines three standard types, with EAE adding specific extensions:

### Basic Function Block

**Purpose**: Encapsulates event-driven behavior with internal state machine.

**Structure**:
- **InterfaceList**: Event inputs/outputs, data inputs/outputs
- **ECC (Execution Control Chart)**: Internal state machine controlling execution
- **Algorithms**: Structured Text (ST) code invoked by ECC actions
- **InternalVars**: Private state variables (not visible externally)

**When to Use**:
- Implementing reusable logic components
- State-based behavior (pumps, valves, motors, timers)
- Low-level control algorithms (PID, edge detection, filtering)

**Example**: PID controller with states: INIT → READY → EXECUTING → DONE

**File Extension**: `.fbt`

**ECC Structure**:
```
States:
  START (required, only one per FB)
  INIT (common pattern for initialization)
  REQ (common pattern for request processing)

Transitions:
  START →[INIT event]→ INIT state
    Actions: Run InitAlgorithm, emit INITO
  INIT →[REQ event]→ REQ state
    Actions: Run ProcessAlgorithm, emit CNF
  REQ →[always]→ INIT state
```

**Key Validation**: ECC must have exactly one START state, all states reachable from START, no dead-end states.

### Service Function Block

**Purpose**: Represents hardware interfaces (I/O, communication, timers).

**Characteristics**:
- Pre-defined by EAE platform
- Hardware-specific implementations
- Typically not user-created (use library FBs)

**Examples**: Digital input/output, analog input/output, Ethernet communication

### Composite Function Block

**Purpose**: Combines multiple FBs into a reusable network without internal state machine.

**Structure**:
- **InterfaceList**: Event inputs/outputs, data inputs/outputs (same as Basic FB)
- **FBNetwork**: Contains FB instances with event and data connections
- **No ECC**: Behavior emerges from internal FB network, not state machine
- **No Algorithms**: Logic provided by internal FBs

**When to Use**:
- Modular design (compose complex behavior from simpler FBs)
- Reusable subsystems without needing state machine
- Encapsulating common FB patterns

**Example**: Temperature control system combining sensor FB, PID FB, and output FB

**File Extension**: `.fbt`

**Key Difference from Basic FB**: Composite FB has no internal algorithms or ECC—it's purely a container for other FBs.

### Composite Automation Type (CAT)

**Purpose**: Top-level application block unifying control logic and HMI visualization, with OPC-UA and persistence.

**Structure** (two perspectives):

| Perspective | Components | Purpose |
|-------------|------------|---------|
| **Control** | Composite FB containing Basic, Service, or other Composite FBs | Application logic |
| **HMI** | Symbols, canvases, faceplates | Visualization and operator interaction |

**Additional Features**:
- **Service FB (HMI bridge)**: Gathers control part and HMI
- **OPC-UA Server**: Exposes variables/events to external systems
- **Offline Parametrization**: Initial parameter values for deployment
- **Persistence**: State saving across restarts

**When to Use**:
- Application-level components (not reusable library FBs)
- Requires HMI visualization (canvases, faceplates)
- Needs OPC-UA integration for supervisory systems
- State persistence required

**Example**: `PackagingLine_CAT`, `ConveyorControl_CAT`, `FillingTank_CAT`

**File Structure**: 19 total files (11 IEC 61499 + 8 HMI C# files)

**CAT Editors** (six main editors):

| Editor | Purpose |
|--------|---------|
| **Interface** | Summary of events, data inputs/outputs, sockets/plugs |
| **Function Blocks Network** | Visual FB wiring (like Composite FB) |
| **Offline Parametrization** | Define initial values for all FB parameters |
| **OPC UA Server** | Configure variable exposition to OPC-UA clients |
| **Meta Info** | Metadata about the CAT |
| **Documentation** | Background information |

### SubCAT

**Purpose**: Nested CAT block (CAT within CAT).

**Structure**: Same as CAT (19 files, same editors), but intended to be instantiated inside another CAT.

**When to Use**:
- Modular application design with hierarchical structure
- Reusable application components that include HMI
- Breaking down complex applications into manageable pieces

**Example**: `ConveyorSection_SubCAT` inside `WarehouseSystem_CAT`

**Key Difference from CAT**: SubCAT is designed for nesting, CAT is typically top-level.

### Comparison Table: FB Types

| Feature | Basic FB | Service FB | Composite FB | CAT | SubCAT |
|---------|----------|------------|--------------|-----|--------|
| **Has ECC** | ✅ Yes | Implementation-defined | ❌ No | ❌ No | ❌ No |
| **Has Algorithms** | ✅ Yes (ST code) | Implementation-defined | ❌ No | ❌ No | ❌ No |
| **Has FBNetwork** | ❌ No | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| **Has HMI** | ❌ No | ❌ No | ❌ No | ✅ Yes | ✅ Yes |
| **OPC-UA Server** | ❌ No | ❌ No | ❌ No | ✅ Yes | ✅ Yes |
| **Persistence** | ❌ No | ❌ No | ❌ No | ✅ Yes | ✅ Yes |
| **InternalVars** | ✅ Yes | ❌ No | ❌ No | ❌ No | ❌ No |
| **Reusable** | ✅ Yes | ✅ Yes | ✅ Yes | ⚠️ Limited | ✅ Yes |
| **Files** | 1 (.fbt) | Platform | 1 (.fbt) | 19 | 19 |
| **Typical Use** | Logic component | HW interface | Subsystem | Application | Nested app |

---

## Adapters (Socket/Plug Pattern)

### What is an Adapter?

An **Adapter** is a **bidirectional interface** for transmitting information between two function blocks. It bundles multiple event and data connections into a single orange link.

**Key Concept**: Adapters enable simultaneous sending and receiving through one connection.

### Socket and Plug

Adapters have two complementary sides:

| Aspect | Socket | Plug |
|--------|--------|------|
| **Visual** | Two arrows pointing IN (←←) | Two arrows pointing OUT (→→) |
| **Event direction** | Has event **inputs** | Has event **outputs** (reversed) |
| **Data direction** | Has data **outputs** | Has data **inputs** (reversed) |
| **Role** | "Server" side (interface definition) | "Client" side (connects to interface) |
| **Example** | Motor interface (receives commands) | Controller (sends commands) |

**Symmetry**: Socket and Plug are **inversely matched**—what's an output on Socket is an input on Plug.

**Example**:
```
AdapterExample (Socket side):
  Event Inputs: REQD, RSPD
  Event Outputs: CNFD, INDD

AdapterExample (Plug side):
  Event Inputs: CNFD, INDD  (reversed!)
  Event Outputs: REQD, RSPD (reversed!)
```

### How Adapters Work

**Bidirectional Communication**:
- **Left side (input) of adapter**: Sends information to connected adapter
- **Right side (output) of adapter**: Receives information from connected adapter

**Example Flow**:
```
Plug.CNFD (input) → transmits → Socket.CNFD (output)
Socket.REQD (input) → transmits → Plug.REQD (output)
```

Both directions operate **simultaneously** through one orange connection link.

### Advantages of Adapters

| Advantage | Description | Impact |
|-----------|-------------|--------|
| **Clean Connections** | Many variables/events in one link | Cleaner FBNetwork editor, easier maintenance |
| **Hardware Independence** | Adapter works across logical devices | Flexible deployment, sequence and instruments can be mapped to different dPACs |
| **Reusable Protocols** | Standardize FB interfaces | Consistent patterns across application |

**File Extension**: `.adp`

---

## CAT Block Structure

### File Organization

CAT blocks require 19 files across two directories:

#### IEC 61499 Directory (`IEC61499/{CATName}/`)

11 files defining control logic:

| File | Purpose |
|------|---------|
| `{name}.cfg` | Configuration file (references all other files) |
| `{name}.fbt` | Main CAT definition (interface + FBNetwork) |
| `{name}.doc.xml` | Documentation |
| `{name}.meta.xml` | Metadata |
| `{name}_CAT.offline.xml` | Offline configuration |
| `{name}_CAT.opcua.xml` | OPC-UA mappings |
| `{name}_HMI.fbt` | HMI interface FB |
| `{name}_HMI.doc.xml` | HMI documentation |
| `{name}_HMI.meta.xml` | HMI metadata |
| `{name}_HMI.offline.xml` | HMI offline config |
| `{name}_HMI.opcua.xml` | HMI OPC-UA |

#### HMI Directory (`HMI/{CATName}/`)

8 C# files defining visualization:

| File | Purpose |
|------|---------|
| `{name}.def.cs` | Symbol definitions (inherits from SymbolDefinition) |
| `{name}.event.cs` | Event definitions (partial class with C# events) |
| `{name}.Design.resx` | Design resources |
| `{name}_sDefault.cnv.cs` | Converter (inherits from UserControl) |
| `{name}_sDefault.cnv.Designer.cs` | Converter designer code |
| `{name}_sDefault.cnv.resx` | Converter resources |
| `{name}_sDefault.cnv.xml` | Converter metadata |
| `{name}_sDefault.doc.xml` | Converter documentation |

**Critical**: All 19 files must exist and reference each other correctly. Use `validate_cat.py` to verify.

### CAT Naming Convention

- **CAT name**: Must be consistent across all files
- **IEC 61499 namespace**: Typically hierarchical (e.g., `MyProject.Storage.Tanks`)
- **HMI namespace**: Must match IEC 61499 namespace for symbol binding

---

## Type System

### Basic Types

| Type | Size | Range | Typical Use |
|------|------|-------|-------------|
| `BOOL` | 1 bit | TRUE/FALSE | Sensor states, flags |
| `BYTE` | 8 bits | 0..255 | Raw data, small integers |
| `WORD` | 16 bits | 0..65535 | Register values |
| `DWORD` | 32 bits | 0..4294967295 | Large counters |
| `INT` | 16 bits | -32768..32767 | Temperatures, setpoints |
| `DINT` | 32 bits | -2147483648..2147483647 | Large counts, milliseconds |
| `REAL` | 32 bits | IEEE 754 single | Process values |
| `LREAL` | 64 bits | IEEE 754 double | High-precision calculations |
| `STRING` | Variable | Text | Names, messages |
| `TIME` | 32 bits | Duration | Delays, timeouts (T#5s, T#100ms) |

### Type Compatibility

**Widening (Automatic, Lossless)**:

| From | To | Rationale |
|------|----|----|
| `INT` | `DINT` | 16-bit to 32-bit integer (safe) |
| `INT` | `REAL` | Integer to float (safe for typical ranges) |
| `REAL` | `LREAL` | Single to double precision (safe) |

**Narrowing (NOT Allowed Automatically)**:

| From | To | Why NOT Allowed |
|------|----|----|
| `DINT` | `INT` | Potential overflow |
| `REAL` | `INT` | Loses fractional part |
| `BOOL` | `INT` | Semantic mismatch |
| `BOOL` | `REAL` | Semantic mismatch |

**Why This Matters**: FBNetwork validators (`validate_fbnetwork.py`) check these rules to prevent runtime type errors. Connections like `BOOL` output → `REAL` input will fail validation.

### ANY Types (Generic Polymorphism)

| ANY Type | Includes | Use Case |
|----------|----------|----------|
| `ANY_INT` | INT, DINT, LINT | Generic integer operations |
| `ANY_REAL` | REAL, LREAL | Generic floating-point |
| `ANY_NUM` | ANY_INT + ANY_REAL | Arithmetic operations |
| `ANY_BIT` | BOOL, BYTE, WORD, DWORD | Bit manipulation |

**Polymorphism**: FBs can use ANY types for generic operations, but the actual type must be resolved at instantiation time.

### Custom Data Types

| Type | Purpose | File Extension |
|------|---------|----------------|
| **Struct** | Composite type with named fields | `.dtp` |
| **Enum** | Named integer constants | `.dtp` |
| **Array** | Fixed-size collection | `.dtp` |
| **Subrange** | Constrained numeric range | `.dtp` |

**Example Struct**:
```
STRUCT RecipeData:
  Temperature: REAL
  Duration: TIME
  Mode: OperationMode  (ENUM)
END_STRUCT
```

---

## Standard Libraries

EAE provides standard libraries for common automation tasks. These libraries are referenced in projects and provide reusable FBs.

### SE.AppSequence

**Purpose**: Step-by-step sequence control (state machine for processes).

**Key FBs**:

| FB | Role | Description |
|----|------|-------------|
| **SeqHead** | Sequence coordinator | Manages overall sequence state (Running, Stopped, Held, Completed) |
| **SeqStep** | Individual step | Activation → Action → Wait for condition → Deactivation |
| **SeqTerminate** | Sequence end | Signals completion |

**Pattern** (each step):
1. Activation (step becomes active)
2. Action (perform operation, e.g., open valve)
3. Wait for transition condition (e.g., level reached)
4. Deactivation (step completes, next step activates)

**When to Use**: Batch processes, filling sequences, state-based operations

**Example**: Filling tank sequence (open inlet → turn on agitator → wait for level → close inlet → turn off agitator)

**Learn More**: Use `/eae-cat` skill to create CATs with SE.AppSequence

### SE.App2CommonProcess

**Purpose**: Standard process equipment FBs (motors, valves, sensors, PID controllers).

**Key FB Categories**:
- **Motors**: Cyclic motors, VFDs
- **Valves**: Digital valves, analog valves
- **Sensors**: Analog inputs, digital inputs, level sensors
- **Controllers**: PID, on/off control
- **Equipment Modules**: Composite equipment (tanks, pumps)

**When to Use**: Industrial process automation, P&ID implementation

**Learn More**: See `/eae-se-process` skill documentation

### Runtime.Base

**Purpose**: Low-level utility FBs (~100 built-in IEC 61499 blocks).

**Key FB Categories**:
- **Timers**: TON, TOF, TP
- **Counters**: CTU, CTD, CTUD
- **Logic**: AND, OR, NOT, RS, SR
- **Arithmetic**: ADD, SUB, MUL, DIV, MOD
- **Comparison**: GT, LT, EQ, GE, LE, NE
- **Type Conversion**: Real to INT, DINT to REAL, etc.
- **String Operations**: Concatenation, substring, conversion

**When to Use**: Building blocks for any FB logic

**Learn More**: See `/eae-runtime-base` skill documentation

---

## Development Workflow

### Typical EAE Project Flow

```
1. Requirements Analysis
   ↓
2. P&ID Review (if process industry)
   │ - Identify equipment
   │ - Map instruments to FBs
   ↓
3. Design Phase
   │ - Choose FB types (Basic, Composite, CAT)
   │ - Define interfaces (InterfaceList)
   │ - Sketch FBNetwork structure
   │ - Identify needed adapters
   │ - Select libraries (SE.AppSequence, SE.App2CommonProcess, etc.)
   ↓
4. Implementation Phase (use eae-* skills)
   │ - Create DataTypes (if custom structures needed)
   │ - Create Adapters (if standardizing interfaces)
   │ - Implement Basic FBs (ECC + ST algorithms)
   │ - Assemble Composite FBs (FBNetwork)
   │ - Build CAT blocks (FBNetwork + HMI)
   ↓
5. Validation Phase (automated scripts)
   │ - validate_ecc.py (ECC correctness)
   │ - validate_st_algorithm.py (algorithm consistency)
   │ - validate_fbnetwork.py (connections, types)
   │ - validate_layout.py (visual guidelines)
   │ - validate_cat.py (multi-file consistency)
   │ - validate_hmi.py (HMI structure)
   ↓
6. EAE Compilation (in Buildtime)
   │ - Full ST syntax checking
   │ - Resource allocation
   │ - Generate runtime code
   ↓
7. Deployment & Testing
   │ - Download to dPACs
   │ - Commission hardware
   │ - Integration testing
   │ - Performance tuning
   ↓
8. Operation & Maintenance
   - Monitor via HMI
   - OPC-UA integration
   - Trend analysis
   - Updates and changes
```

### EAE Skills Integration

The eae-* skills automate **Design** and **Implementation** phases:

| Skill | Automates | Output |
|-------|-----------|--------|
| `/eae-basic-fb` | Basic FB design | `.fbt` file with ECC, algorithms, InternalVars |
| `/eae-composite-fb` | Composite FB assembly | `.fbt` file with FBNetwork |
| `/eae-cat` | CAT block creation | 19 files (IEC 61499 + HMI) |
| `/eae-adapter` | Adapter interface design | `.adp` file with Socket/Plug definitions |
| `/eae-datatype` | Custom DataType creation | `.dtp` file with Struct/Enum/Array/Subrange |

**Value Proposition**: Catch 90% of structural errors before opening EAE IDE, saving compilation cycles and development time.

---

## Quick Reference Tables

### File Extensions

| Extension | FB Type | Description |
|-----------|---------|-------------|
| `.fbt` | Basic, Composite, CAT | Function Block Type |
| `.adp` | Adapter | Socket/Plug bidirectional interface |
| `.dtp` | DataType | Struct, Enum, Array, Subrange |
| `.cfg` | CAT config | Configuration file (references) |
| `.cs` | CAT HMI | C# code for visualization |
| `.resx` | CAT HMI | C# resource files |

### Common Event/Data Patterns

| Pattern | Structure | Example Use |
|---------|-----------|-------------|
| **Request-Confirm** | REQ event in → process → CNF event out | Motor start command |
| **Initialization** | INIT event → setup → INITO event | FB startup |
| **Indication** | Continuous data monitoring → IND event on change | Alarm notification |
| **Cyclic** | Timer triggers REQ repeatedly | Sampling, polling |
| **Pipeline** | FB1.CNF → FB2.REQ → FB3.REQ | Sequential processing |
| **Fan-out** | One event triggers multiple FBs | Broadcast notification |

### Validation Exit Codes

| Exit Code | Meaning | Action Required |
|-----------|---------|-----------------|
| `0` | Success | No issues, ready to proceed |
| `1` | General error | File not found, parse error, fix immediately |
| `10` | Validation failed | Errors found (MUST fix before compilation) |
| `11` | Passed with warnings | Warnings found (SHOULD review, non-blocking) |

### Socket vs. Plug Quick Guide

| Aspect | Socket | Plug |
|--------|--------|------|
| **Visual identifier** | ←← (arrows IN) | →→ (arrows OUT) |
| **Event direction** | Inputs (receives) | Outputs (sends) - reversed |
| **Data direction** | Outputs (provides) | Inputs (consumes) - reversed |
| **Typical role** | Interface provider | Interface consumer |
| **Memory aid** | Like electrical socket (fixed) | Like electrical plug (connects) |

---

## Glossary

| Term | Definition |
|------|------------|
| **Buildtime** | EAE engineering tool for design, commission, and maintenance |
| **CAT** | Composite Automation Type—top-level with control + HMI + OPC-UA + persistence |
| **Canvases** | HMI visualization screens showing process overview |
| **dPAC** | Distributed Programmable Automation Controller—runtime hardware |
| **ECC** | Execution Control Chart—state machine in Basic FB controlling algorithm execution |
| **Event** | Trigger signal in IEC 61499 (not data, just notification) |
| **Faceplates** | Detailed HMI views for individual equipment (CAT symbols) |
| **FBNetwork** | Visual connection graph of FB instances in Composite FB or CAT |
| **InterfaceList** | External interface definition (events, data, adapters) for any FB type |
| **InternalVars** | Private variables inside Basic FB (not visible externally) |
| **P&ID** | Piping & Instrumentation Diagram—process industry standard for equipment layout |
| **Plug** | Adapter interface side with reversed event/data directions (consumer) |
| **Service FB** | Hardware interface FB (I/O, communication) |
| **Socket** | Adapter interface side defining the protocol (provider) |
| **ST** | Structured Text—IEC 61131-3 programming language for algorithms |
| **SubCAT** | CAT designed to be nested inside another CAT |
| **WITH association** | Event-data binding (event carries specific variables) |

---

## Additional Resources

### EAE Skill Collection

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| **eae-skill-router** | Entry point | Routes to specialized skills |
| **eae-basic-fb** | Create Basic FBs | Need ECC + ST algorithms |
| **eae-composite-fb** | Create Composite FBs | Combine existing FBs |
| **eae-cat** | Create CAT blocks | Need HMI + OPC-UA + persistence |
| **eae-adapter** | Create Adapters | Standardize bidirectional interfaces |
| **eae-datatype** | Create DataTypes | Custom structures, enums |
| **eae-runtime-base** | Reference guide | Find Runtime.Base library FBs |
| **eae-se-process** | Reference guide | Find SE.App2CommonProcess FBs |

### Official Documentation

- **EcoStruxure Automation Expert Getting Started** (EAE_GS): Tutorial walkthrough
- **EAE User Manual**: Comprehensive reference (press F1 in Buildtime)
- **IEC 61499 Standard**: Official specification (purchase from IEC)
- **4DIAC**: Open-source IEC 61499 IDE (compatible concepts)

---

## Document Version

- **Version**: 1.0.0
- **Created**: 2026-01-20
- **Based on**: EcoStruxure Automation Expert Getting Started (EIO0000004453.06, 10/2025)
- **Purpose**: Supporting EAE skills collection agentic capabilities

---

**Feedback**: This primer is a living document. Suggest improvements via the EAE skills collection repository or update directly when new EAE features are released.
