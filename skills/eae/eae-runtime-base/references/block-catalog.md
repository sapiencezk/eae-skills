# Runtime.Base Block Catalog

Complete reference for all ~100 function blocks in the Runtime.Base library.

---

## Basics (14 blocks)

Core event routing primitives from IEC 61499.

| Block | Type | Description |
|-------|------|-------------|
| **DS_SELECTX** | Basic | Extended data selector |
| **E_CTU** | Basic | Event-driven up counter |
| **E_D_FF** | Basic | Event-driven D flip-flop |
| **E_DEMUX** | Basic | Event demultiplexer (1 to N) |
| **E_MERGE** | Basic | Event merge (N to 1) |
| **E_PERMIT** | Basic | Event gate/permit |
| **E_REND** | Basic | Event rendezvous (synchronization) |
| **E_RS** | Basic | Event-driven RS flip-flop (Reset dominant) |
| **E_SELECT** | Basic | Event selector |
| **E_SPLIT** | Basic | Event splitter (1 to 2) |
| **E_SR** | Basic | Event-driven SR flip-flop (Set dominant) |
| **E_SWITCH** | Basic | Event switch (boolean routing) |
| **FORCE_IND** | Basic | Force indication |
| **SMOOTH** | Basic | Signal smoothing/filtering |

### E_SPLIT Details

Splits one event into two simultaneous outputs.

```
Events:  EI → EO1, EO2
Data:    None
```

### E_MERGE Details

Merges two event inputs into one output.

```
Events:  EI1, EI2 → EO
Data:    None
```

### E_SELECT Details

Selects event path based on boolean guard.

```
Events:  EI0, EI1 → EO
Data:    G (BOOL) - guard, selects EI0 (FALSE) or EI1 (TRUE)
```

### E_SWITCH Details

Routes single event to one of two outputs based on boolean.

```
Events:  EI → EO0 (G=FALSE), EO1 (G=TRUE)
Data:    G (BOOL) - switch condition
```

### E_PERMIT Details

Gates events based on permit signal.

```
Events:  EI → EO (only if PERMIT=TRUE)
Data:    PERMIT (BOOL)
```

### E_DEMUX Details

Demultiplexes event to one of N outputs based on index.

```
Events:  EI → EO0..EOn (selected by K)
Data:    K (INT) - output index
```

### E_REND Details

Rendezvous - waits for both events before firing output.

```
Events:  EI1, EI2 → EO (when both received), R (reset)
Data:    QO (BOOL) - rendezvous state
```

### E_RS Details

Reset-dominant RS flip-flop.

```
Events:  R (reset), S (set) → EO
Data:    Q (BOOL) - flip-flop state
```

### E_SR Details

Set-dominant SR flip-flop.

```
Events:  S (set), R (reset) → EO
Data:    Q (BOOL) - flip-flop state
```

### E_D_FF Details

D-type flip-flop with clock.

```
Events:  CLK (clock) → EO
Data:    D (BOOL) - data input, Q (BOOL) - output
```

### E_CTU Details

Event-driven up counter.

```
Events:  CU (count up), R (reset) → CUO, RO
Data:    PV (INT) - preset value, CV (INT) - current value, Q (BOOL)
```

---

## Composites (2 blocks)

Pre-built composite function blocks.

| Block | Type | Description |
|-------|------|-------------|
| **E_F_TRIG** | Composite | Falling edge trigger |
| **E_R_TRIG** | Composite | Rising edge trigger |

### E_R_TRIG Details

Fires output on rising edge (FALSE → TRUE transition).

```
Events:  EI → EO (on rising edge of QI)
Data:    QI (BOOL) - input signal
```

### E_F_TRIG Details

Fires output on falling edge (TRUE → FALSE transition).

```
Events:  EI → EO (on falling edge of QI)
Data:    QI (BOOL) - input signal
```

---

## Services (80+ blocks)

Main library of service function blocks.

### Timing Services

| Block | Description |
|-------|-------------|
| **E_CYCLE** | Cyclic event generator |
| **E_HRCYCLE** | High-resolution cyclic generator with phase |
| **E_DELAY** | Single event delay |
| **E_DELAYR** | Retriggerable delay |
| **E_N_TABLE** | N-entry time table |
| **E_RESTART** | Restart detection |
| **E_TABLE** | Scheduled time table |
| **E_TRAIN** | Event train (burst) generator |

#### E_CYCLE Details

```
Events:  START, STOP → EO
Data:    DT (TIME) - period
Usage:   START triggers, EO fires every DT until STOP
```

#### E_HRCYCLE Details

```
Events:  START, STOP → EO
Data:    DT (TIME) - period, PHASE (TIME) - phase offset
Usage:   High-precision timing with synchronization
```

#### E_DELAY Details

```
Events:  START, STOP → EO
Data:    DT (TIME) - delay duration
Usage:   START triggers timer, EO fires after DT
Note:    Not retriggerable - new START ignored if timer active
```

#### E_DELAYR Details

```
Events:  START, STOP → EO
Data:    DT (TIME) - delay duration
Usage:   Retriggerable - new START restarts timer
```

#### E_TRAIN Details

```
Events:  START, STOP → EO
Data:    DT (TIME) - interval, N (UINT) - count
Usage:   Fires N events at DT intervals
```

### Arithmetic Services

| Block | Description |
|-------|-------------|
| **ADD** | Addition (IN1 + IN2) |
| **SUB** | Subtraction (IN1 - IN2) |
| **MUL** | Multiplication (IN1 * IN2) |
| **DIV** | Division (IN1 / IN2) |
| **ANAMATH** | Analog math operations |
| **CALC_FORMULAR** | Formula string evaluation |
| **RNBR** | Random number generator |

### Logic Services

| Block | Description |
|-------|-------------|
| **AND** | Logical AND |
| **OR** | Logical OR |
| **NOT** | Logical NOT |
| **XOR** | Exclusive OR |
| **COMPARE** | Value comparison (LT, EQ, GT) |
| **SELECT** | Conditional data selection |

### Bit Manipulation

| Block | Description |
|-------|-------------|
| **BITMAN** | General bit manipulation |
| **SHL** | Shift left |
| **SHR** | Shift right |
| **ROL** | Rotate left |
| **ROR** | Rotate right |

### Communication - MQTT

| Block | Description |
|-------|-------------|
| **MQTT_CONNECTION** | MQTT broker connection management |
| **MQTT_PUBLISH** | Publish to MQTT topics |
| **MQTT_SUBSCRIBE** | Subscribe to MQTT topics |

#### MQTT_CONNECTION Details

```
Events:  INIT, CONNECT, DISCONNECT → INITO, CONNECTO, DISCONNECTO
Data:
  QI (BOOL) - input qualifier
  ServerURI (STRING) - mqtt://host:port
  ClientID (STRING) - unique client identifier
  User (STRING) - username
  Password (STRING) - password
  KeepAlive (TIME) - keep-alive interval
  CleanSession (BOOL) - clean session flag
  → QO (BOOL), STATUS (STRING)
```

#### MQTT_PUBLISH Details

```
Events:  INIT, PUBLISH_ALL, PUBLISH{n} → INITO, PUBLISH_ALLO, PUBLISHO{n}
Data:
  ConnectionID (STRING) - matches MQTT_CONNECTION
  RootPath (STRING) - topic prefix
  Topic{n} (STRING) - topic name
  Payload{n} (STRING) - message payload
  QoS{n} (USINT) - 0=at most once, 1=at least once, 2=exactly once
  Retain{n} (BOOL) - retain on server
  → STATUS (STRING)
```

### Communication - Other

| Block | Description |
|-------|-------------|
| **WEBSOCKET_SERVER** | WebSocket server |
| **NETIO** | Network I/O (TCP/UDP) |
| **SERIALIO** | Serial port communication |
| **QUERY_CONNECTION** | HTTP/REST client |

### Data Handling

| Block | Description |
|-------|-------------|
| **BUFFER** | Data buffer |
| **BUFFERP** | Persistent data buffer |
| **ANY2ANY** | Type conversion (any to any) |
| **SPLIT** | Split data into parts |
| **AGGREGATE** | Combine data parts |
| **DATA_CRYPTO** | Data encryption/decryption |

### JSON Services

| Block | Description |
|-------|-------------|
| **JSON_BUILDER** | Build JSON from key/value pairs |
| **JSON_PARSER** | Parse JSON to values |
| **JSON_FORMAT** | Format/pretty-print JSON |

### Configuration Services

| Block | Description |
|-------|-------------|
| **CFG_ANY_GET** | Get configuration parameter (any type) |
| **CFG_ANY_SET** | Set configuration parameter (any type) |
| **CFG_DIRECT_GET** | Direct parameter read |
| **CFG_DIRECT_SET** | Direct parameter write |
| **PERSISTENCE** | Value persistence (save/load) |

### Process Data (I/O)

| Block | Description |
|-------|-------------|
| **PD_ANY_IN** | Process data input (any type) |
| **PD_ANY_OUT** | Process data output (any type) |
| **PD_DIRECT_IN** | Direct hardware input |
| **PD_DIRECT_OUT** | Direct hardware output |
| **PD_COPY** | Copy process data |
| **PD_OCTET_STRING_IN** | Octet string input |
| **PD_OCTET_STRING_OUT** | Octet string output |

### Bus Communication

| Block | Description |
|-------|-------------|
| **BM_FILE** | File-based bus master |
| **BM_MODBUS** | Modbus bus master |
| **BM_RIO** | Remote I/O bus master |
| **BUSCOUPLER** | Bus coupler interface |
| **BUSDEVICE** | Bus device interface |
| **BUSDEVICECONFIG** | Bus device configuration |

### System Services

| Block | Description |
|-------|-------------|
| **LOGGER** | Local logging |
| **SYSLOGLOGGER** | Remote syslog logging |
| **CPUTICK** | CPU tick counter (timing) |
| **REPORT_APP_STATE** | Application state reporting |
| **ALARM_BIT** | Bit-based alarm handling |
| **MIBGET** | SNMP MIB get |

### Event Scheduling

| Block | Description |
|-------|-------------|
| **EVENTCHAIN** | Event chain link |
| **EVENTCHAINHEAD** | Event chain head |
| **EVENTSCHEDULER** | Event scheduler |
| **PRIOSCHEDULER** | Priority scheduler |

### Value Encoding

| Block | Description |
|-------|-------------|
| **VTQ_ENCODE** | Encode Value+Time+Quality |
| **VTQ_DECODE** | Decode VTQ |
| **VALFORMAT** | Format value to string |
| **VALSCAN** | Parse string to value |

### Symbolic Links

| Block | Description |
|-------|-------------|
| **SYMLINKMULTIVARDST** | Multi-variable symbolic link destination |
| **SYMLINKMULTIVARSRC** | Multi-variable symbolic link source |

---

## Resources (2 blocks)

IEC 61499 Resource types for application deployment.

| Block | Type | Description |
|-------|------|-------------|
| **EMB_RES_ECO** | Resource | Economy embedded resource |
| **EMB_RES_ENH** | Resource | Enhanced embedded resource |

### EMB_RES_ECO Details

Standard embedded resource type for typical applications.

### EMB_RES_ENH Details

Enhanced embedded resource with additional capabilities for high-performance applications.

---

## Namespace

All blocks are in namespace: `Runtime.Base`

To use in FBNetwork:

```xml
<FB ID="1" Name="timer" Type="E_CYCLE" Namespace="Runtime.Base" x="500" y="350" />
```
