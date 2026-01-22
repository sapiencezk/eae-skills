# SE.App2Base DataTypes Reference

Custom data types provided by the SE.App2Base library.

---

## Enumerations

### Status

Signal quality status indicator.

```xml
<VarDeclaration Name="signalStatus" Type="Status" Namespace="SE.App2Base" />
```

| Value | Meaning |
|-------|---------|
| `Good` | Signal is valid and reliable |
| `Bad` | Signal is invalid or failed |
| `Uncertain` | Signal quality is questionable |

**Usage:** Used by all signal processing blocks (AnalogInput, DigitalInput, etc.) to indicate signal health.

---

### OwnerState

Owner control state for device blocks.

```xml
<VarDeclaration Name="ownerMode" Type="OwnerState" Namespace="SE.App2Base" />
```

| Value | Meaning |
|-------|---------|
| `Manual` | Device under manual/local control |
| `Auto` | Device under automatic control |
| `Program` | Device under program/sequence control |
| `Maintenance` | Device in maintenance mode |

**Usage:** Used by Motor, Valve, and equipment CATs to track control ownership.

---

### ActiveState

Active/Inactive state indicator.

```xml
<VarDeclaration Name="state" Type="ActiveState" Namespace="SE.App2Base" />
```

| Value | Meaning |
|-------|---------|
| `Inactive` | Not active |
| `Active` | Currently active |

**Usage:** Used for binary state representation in process blocks.

---

### StateSel

State selection enumeration.

```xml
<VarDeclaration Name="selection" Type="StateSel" Namespace="SE.App2Base" />
```

| Value | Meaning |
|-------|---------|
| `State0` | First state option |
| `State1` | Second state option |
| `State2` | Third state option |
| `State3` | Fourth state option |

**Usage:** Multi-state selection for mode control.

---

### TimeFormat

Time format selection for display.

```xml
<VarDeclaration Name="format" Type="TimeFormat" Namespace="SE.App2Base" />
```

| Value | Meaning |
|-------|---------|
| `Seconds` | Display as seconds |
| `Minutes` | Display as minutes |
| `Hours` | Display as hours |
| `Days` | Display as days |
| `HHMMSS` | Display as HH:MM:SS |

**Usage:** Used by DisplayTime and SetTime CATs.

---

### AlarmPriority

Alarm priority levels.

```xml
<VarDeclaration Name="priority" Type="AlarmPriority" Namespace="SE.App2Base" />
```

| Value | Meaning |
|-------|---------|
| `Low` | Low priority alarm |
| `Medium` | Medium priority alarm |
| `High` | High priority alarm |
| `Critical` | Critical alarm requiring immediate attention |

**Usage:** Used by LimitAlarm, DeviationAlarm, ROCAlarm CATs.

---

### AlarmState

Alarm condition state.

```xml
<VarDeclaration Name="alarmState" Type="AlarmState" Namespace="SE.App2Base" />
```

| Value | Meaning |
|-------|---------|
| `Normal` | No alarm condition |
| `Alarm` | Alarm condition active |
| `Acknowledged` | Alarm acknowledged but still active |
| `Return` | Alarm returning to normal |

**Usage:** Tracks alarm lifecycle in alarm CATs.

---

## Structures

### Bool4

Four-boolean structure for packed boolean data.

```xml
<VarDeclaration Name="flags" Type="Bool4" Namespace="SE.App2Base" />
```

| Field | Type | Description |
|-------|------|-------------|
| `b0` | BOOL | First boolean |
| `b1` | BOOL | Second boolean |
| `b2` | BOOL | Third boolean |
| `b3` | BOOL | Fourth boolean |

**Usage:** Compact boolean grouping for status flags.

---

### AnalogSignal

Complete analog signal with value and quality.

```xml
<VarDeclaration Name="signal" Type="AnalogSignal" Namespace="SE.App2Base" />
```

| Field | Type | Description |
|-------|------|-------------|
| `Value` | REAL | Signal value |
| `Status` | Status | Signal quality |
| `Timestamp` | TIME | Last update time |

**Usage:** Standard analog signal representation.

---

### DigitalSignal

Complete digital signal with state and quality.

```xml
<VarDeclaration Name="signal" Type="DigitalSignal" Namespace="SE.App2Base" />
```

| Field | Type | Description |
|-------|------|-------------|
| `State` | BOOL | Signal state |
| `Status` | Status | Signal quality |
| `Timestamp` | TIME | Last update time |

**Usage:** Standard digital signal representation.

---

### ScalingParams

Analog signal scaling parameters.

```xml
<VarDeclaration Name="scaling" Type="ScalingParams" Namespace="SE.App2Base" />
```

| Field | Type | Description |
|-------|------|-------------|
| `RawLow` | REAL | Raw value low limit |
| `RawHigh` | REAL | Raw value high limit |
| `EngLow` | REAL | Engineering units low |
| `EngHigh` | REAL | Engineering units high |
| `Clamp` | BOOL | Clamp to limits |

**Usage:** Used by AISignalScaling and AnalogInput.

---

### AlarmLimits

Alarm limit configuration.

```xml
<VarDeclaration Name="limits" Type="AlarmLimits" Namespace="SE.App2Base" />
```

| Field | Type | Description |
|-------|------|-------------|
| `HiHi` | REAL | High-high alarm limit |
| `Hi` | REAL | High alarm limit |
| `Lo` | REAL | Low alarm limit |
| `LoLo` | REAL | Low-low alarm limit |
| `Deadband` | REAL | Alarm deadband |

**Usage:** Used by LimitAlarm CAT.

---

## Using DataTypes in FBNetwork

### In VarDeclaration

```xml
<VarDeclaration ID="{HEX-ID}" Name="motorStatus" Type="Status" Namespace="SE.App2Base" />
```

### In FB Connections

```xml
<DataConnections>
  <Connection Source="$aiBlock.Status" Destination="$display.StatusIn" />
</DataConnections>
```

### Creating Custom Types Using SE.App2Base Types

```xml
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE DataType SYSTEM "../DataType.dtd">
<DataType Name="MyMotorData" Namespace="MyLibrary" Comment="Custom motor data">
  <Identification Standard="1131-3" />
  <VersionInfo Organization="MyOrg" Version="1.0" Author="Claude" Date="01/16/2026" />
  <CompilerInfo />
  <StructuredType>
    <VarDeclaration Name="Speed" Type="REAL" Comment="Motor speed" />
    <VarDeclaration Name="Current" Type="REAL" Comment="Motor current" />
    <VarDeclaration Name="State" Type="OwnerState" Namespace="SE.App2Base" Comment="Control state" />
    <VarDeclaration Name="Quality" Type="Status" Namespace="SE.App2Base" Comment="Signal quality" />
  </StructuredType>
</DataType>
```

---

## Related References

- [Block Catalog](block-catalog.md) - Complete block listing
- [Common Patterns](common-patterns.md) - Usage patterns
- [eae-datatype skill](../../eae-datatype/SKILL.md) - Creating custom DataTypes
