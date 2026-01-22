# Namespace Migration Rules for EAE Block Forking

This document defines the rules for updating namespaces when forking blocks from Schneider Electric standard libraries to custom libraries.

---

## Core Principle

**Only update namespace references for blocks that are actually forked.** Keep original namespaces for all other references to maintain compatibility with the standard library ecosystem.

---

## Namespace Categories

### 1. MUST UPDATE (Forked Blocks)

These namespace references MUST be changed to the target namespace:

| Element | Attribute | When to Update |
|---------|-----------|----------------|
| `<FBType>` | `Namespace` | Always (root element) |
| `<FB>` | `Namespace` | Only if the referenced Type is forked |
| `<SubCAT>` | `Namespace` | Only if the referenced Type is forked |

**Example - Root FBType:**
```xml
<!-- BEFORE (source) -->
<FBType Name="AnalogInput" Namespace="SE.App2CommonProcess" GUID="...">

<!-- AFTER (forked) -->
<FBType Name="AnalogInput" Namespace="SE.ScadapackWWW" GUID="[NEW-GUID]">
```

**Example - Forked Sub-block:**
```xml
<!-- BEFORE -->
<FB Name="analogInputBaseExt" Type="AnalogInputBaseExt"
    Namespace="SE.App2CommonProcess" />

<!-- AFTER (if AnalogInputBaseExt is also forked) -->
<FB Name="analogInputBaseExt" Type="AnalogInputBaseExt"
    Namespace="SE.ScadapackWWW" />
```

### 2. MUST KEEP (Original Library References)

These namespace references MUST remain unchanged:

| Element | Type | Reason |
|---------|------|--------|
| `<Adapter>` / `<AdapterDeclaration>` | Interface types (IAnalog, IDigital, etc.) | Interfaces are not forked, they're shared |
| `<FB>` | Non-forked blocks (LimitAlarm, aISignal, etc.) | Still using original library implementation |
| `<VarDeclaration>` | DataTypes from original libraries | DataTypes are shared, not forked |
| Plugin references | Original project names | Plugins reference source libraries |

**Example - Adapter Interface (KEEP):**
```xml
<!-- ALWAYS KEEP ORIGINAL - interfaces are shared -->
<Adapter Name="IPv" Type="IAnalog" Namespace="SE.App2Base" />
<AdapterDeclaration Name="IRawPvIn" Type="IAnalog" Namespace="SE.App2Base" />
```

**Example - Non-forked Sub-block (KEEP):**
```xml
<!-- KEEP - LimitAlarm is not being forked -->
<FB Name="highHigh" Type="LimitAlarm" Namespace="SE.App2Base" />
<FB Name="rawPv" Type="aISignal" Namespace="SE.App2Base" />
```

**Example - DataType Reference (KEEP):**
```xml
<!-- KEEP - Status type comes from original library -->
<VarDeclaration Name="Status" Type="Status" Namespace="SE.App2Base" />
```

---

## Decision Tree

```
For each Namespace attribute in the file:
│
├── Is it the root <FBType> element?
│   └── YES → UPDATE to target namespace
│
├── Is it an <Adapter> or <AdapterDeclaration>?
│   └── YES → KEEP original namespace (interfaces are shared)
│
├── Is it a <VarDeclaration> with Type from original library?
│   └── YES → KEEP original namespace (DataTypes are shared)
│
├── Is it an <FB> element?
│   │
│   └── Is the Type also being forked?
│       ├── YES → UPDATE to target namespace
│       └── NO → KEEP original namespace
│
└── Is it a <SubCAT> element?
    │
    └── Is the Type also being forked?
        ├── YES → UPDATE to target namespace
        └── NO → KEEP original namespace
```

---

## GUID Generation

When forking a block, you MUST generate a new GUID:

```xml
<!-- BEFORE -->
<FBType GUID="422cce07-335e-414d-823c-03c2d1ac0ef6" Name="AnalogInput"
        Namespace="SE.App2CommonProcess">

<!-- AFTER -->
<FBType GUID="[NEW-UNIQUE-GUID]" Name="AnalogInput"
        Namespace="SE.ScadapackWWW">
```

**Why:** GUIDs identify block instances globally. Reusing the source GUID causes conflicts.

**How to generate:**
- Python: `import uuid; str(uuid.uuid4())`
- PowerShell: `[guid]::NewGuid().ToString()`
- CLI: `uuidgen`

---

## Common Source Libraries and Their Elements

### SE.App2Base (Keep namespace for these)
- Adapter interfaces: `IAnalog`, `IDigital`, `IDevice`, `IOpCondS`, `IOpCondP`
- Basic blocks: `LimitAlarm`, `DeviationAlarm`, `ROCAlarm`, `aISignal`, `plcStart`
- DataTypes: `Status`, `VTQREAL`, `VTQBOOL`, basic alarm types

### SE.App2CommonProcess (Keep namespace for non-forked)
- Sequence blocks: `analogInSeqData`
- Helper blocks: `analogInputLogic`
- DataTypes: Process-specific structures

### Runtime.Base (Always keep namespace)
- Runtime types and interfaces
- Never fork Runtime.Base elements

---

## .cfg File Rules

The `.cfg` file contains `<SubCAT>` references that follow the same rules:

```xml
<CAT Name="AnalogInput" CATFile="AnalogInput\AnalogInput.fbt">

  <!-- UPDATE - AnalogInputBaseExt is forked -->
  <SubCAT Name="analogInputBaseExt" Type="AnalogInputBaseExt"
          Namespace="SE.ScadapackWWW" UsedInCAT="true" />

  <!-- KEEP - LimitAlarm is not forked -->
  <SubCAT Name="highHigh" Type="LimitAlarm"
          Namespace="SE.App2Base" UsedInCAT="true" />

  <!-- Plugin references - KEEP original project names -->
  <Plugin Name="Plugin=OfflineParametrizationEditor;..."
          Project="SE.App2CommonProcess"
          Value="AnalogInput\AnalogInput_CAT.offline.xml" />
</CAT>
```

---

## HMI File Namespace Patterns

### C# Namespace Convention

```csharp
// Faceplates namespace
namespace SE.ScadapackWWW.Faceplates.AnalogInput
{
    partial class fpDefault { }
    partial class fpParameter { }
}

// Symbols namespace
namespace SE.ScadapackWWW.Symbols.AnalogInput
{
    partial class sDefault { }
    partial class sVertical { }
    partial class sDisplayPv { }
}
```

### Pattern
- Faceplates: `{TargetLib}.Faceplates.{BlockName}`
- Symbols: `{TargetLib}.Symbols.{BlockName}`

---

## Complete Example: Forking AnalogInput

### Source File (SE.App2CommonProcess)
```xml
<FBType GUID="422cce07-..." Name="AnalogInput" Namespace="SE.App2CommonProcess">
  <InterfaceList>
    <AdapterOutputs>
      <Adapter Name="IPv" Type="IAnalog" Namespace="SE.App2Base" />
    </AdapterOutputs>
  </InterfaceList>
  <FBNetwork>
    <FB Name="analogInputBaseExt" Type="AnalogInputBaseExt"
        Namespace="SE.App2CommonProcess" />
    <FB Name="highHigh" Type="LimitAlarm" Namespace="SE.App2Base" />
    <FB Name="rawPv" Type="aISignal" Namespace="SE.App2Base" />
    <FB Name="sc" Type="analogInSeqData" Namespace="SE.App2CommonProcess" />
  </FBNetwork>
</FBType>
```

### Forked File (SE.ScadapackWWW)

Assuming we fork: AnalogInput, AnalogInputBaseExt, AnalogInputBase

```xml
<FBType GUID="[NEW-GUID]" Name="AnalogInput" Namespace="SE.ScadapackWWW">
  <InterfaceList>
    <AdapterOutputs>
      <!-- KEEP - IAnalog is an interface, not forked -->
      <Adapter Name="IPv" Type="IAnalog" Namespace="SE.App2Base" />
    </AdapterOutputs>
  </InterfaceList>
  <FBNetwork>
    <!-- UPDATE - AnalogInputBaseExt IS forked -->
    <FB Name="analogInputBaseExt" Type="AnalogInputBaseExt"
        Namespace="SE.ScadapackWWW" />
    <!-- KEEP - LimitAlarm is NOT forked -->
    <FB Name="highHigh" Type="LimitAlarm" Namespace="SE.App2Base" />
    <!-- KEEP - aISignal is NOT forked -->
    <FB Name="rawPv" Type="aISignal" Namespace="SE.App2Base" />
    <!-- KEEP - analogInSeqData is NOT forked -->
    <FB Name="sc" Type="analogInSeqData" Namespace="SE.App2CommonProcess" />
  </FBNetwork>
</FBType>
```

---

## Validation Checklist

After forking, verify:

- [ ] Root `<FBType>` has target namespace
- [ ] Root `<FBType>` has new unique GUID
- [ ] All `<Adapter>` elements keep original namespaces
- [ ] All forked `<FB>` elements have target namespace
- [ ] All non-forked `<FB>` elements keep original namespace
- [ ] `.cfg` `<SubCAT>` elements follow same rules
- [ ] HMI files use correct C# namespace pattern
- [ ] No broken references (all referenced blocks exist)

Use the validation script:
```bash
python scripts/validate_fork.py SE.ScadapackWWW AnalogInput
```
