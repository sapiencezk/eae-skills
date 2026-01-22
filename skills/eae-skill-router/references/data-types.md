# EAE Data Types Reference

## IEC 61499 Primitive Types

| Type | Description | Range/Size |
|------|-------------|------------|
| `BOOL` | Boolean | TRUE / FALSE |
| `BYTE` | 8-bit unsigned | 0 to 255 |
| `WORD` | 16-bit unsigned | 0 to 65535 |
| `DWORD` | 32-bit unsigned | 0 to 2^32-1 |
| `LWORD` | 64-bit unsigned | 0 to 2^64-1 |
| `SINT` | 8-bit signed | -128 to 127 |
| `INT` | 16-bit signed | -32768 to 32767 |
| `DINT` | 32-bit signed | -2^31 to 2^31-1 |
| `LINT` | 64-bit signed | -2^63 to 2^63-1 |
| `USINT` | 8-bit unsigned | 0 to 255 |
| `UINT` | 16-bit unsigned | 0 to 65535 |
| `UDINT` | 32-bit unsigned | 0 to 2^32-1 |
| `ULINT` | 64-bit unsigned | 0 to 2^64-1 |
| `REAL` | 32-bit float | IEEE 754 single |
| `LREAL` | 64-bit float | IEEE 754 double |
| `STRING` | Character string | Variable length |
| `WSTRING` | Wide string | Unicode |
| `TIME` | Duration | T#0s to T#... |
| `DATE` | Calendar date | D#... |
| `TIME_OF_DAY` | Time of day | TOD#... |
| `DATE_AND_TIME` | Timestamp | DT#... |

## Common Custom Types (SE.App2Base)

| Type | Description | Fields |
|------|-------------|--------|
| `VTQREAL` | Value + Timestamp + Quality | Value (REAL), Timestamp, Quality |
| `VTQBOOL` | Boolean with VTQ | Value (BOOL), Timestamp, Quality |
| `VTQINT` | Integer with VTQ | Value (INT), Timestamp, Quality |
| `Status` | Alarm/status flags | Various alarm flags |
| `Quality` | OPC-UA quality code | Good, Bad, Uncertain |

## Common Adapter Types (SE.App2Base)

| Adapter | Description | Key Ports |
|---------|-------------|-----------|
| `IAnalog` | Analog signal interface | Value, ValueMin, ValueMax, Status |
| `IDigital` | Digital signal interface | Value, Status |
| `IDevice` | Device control interface | Command, Status, Feedback |
| `IAlarm` | Alarm interface | AlarmStatus, Acknowledge |

## Type Declaration Syntax

### Simple Type
```xml
<VarDeclaration Name="MyVar" Type="REAL" Comment="Description" />
```

### With Initial Value
```xml
<VarDeclaration Name="MyVar" Type="REAL" InitialValue="0.0" Comment="Description" />
```

### Custom Type (from another namespace)
```xml
<VarDeclaration Name="Pv" Type="VTQREAL" Namespace="SE.App2Base" Comment="Process value" />
```

### Array Type
```xml
<VarDeclaration Name="Values" Type="REAL" ArraySize="10" Comment="Array of 10 reals" />
```

## Type Compatibility

When connecting variables:
- Types must match exactly OR
- Implicit conversion is supported (INT → REAL, etc.)
- Custom types require same Type AND Namespace
