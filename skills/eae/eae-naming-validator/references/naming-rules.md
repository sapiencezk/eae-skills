# EAE Naming Rules - Complete Catalog

Comprehensive reference for all Schneider Electric Application Design Guideline naming conventions enforced by the eae-naming-validator skill.

**Source**: EAE Application Design Guidelines (EIO0000004686.06, Section 1.5: Colors and Naming Convention)

---

## Rule Catalog

### Rule 1: CAT (Composite Application Type)

**Convention**: PascalCase

**Pattern**: `^[A-Z][a-zA-Z0-9]*$`

**Rationale**: CATs are high-level application components visible in system architecture. PascalCase provides clear visual distinction and aligns with object-oriented naming conventions for classes/types.

**Severity**: ERROR

**Examples**:

✅ **Compliant**:
- `AnalogInput`
- `DiscreteOutput`
- `SpMon`
- `OosMode`
- `SeqManager`

❌ **Non-Compliant**:
- `analogInput` (starts with lowercase)
- `analog_input` (uses underscores)
- `ANALOGINPUT` (all uppercase)
- `1AnalogInput` (starts with number)

**Edge Cases**:
- Acronyms: Prefer `HttpServer` over `HTTPServer` for readability
- Numbers: `Motor2Control` is allowed (number not at start)

**SE ADG Reference**: Section 1.5.0_1, CAT and SubApp

---

### Rule 2: SubApp (Sub-Application)

**Convention**: PascalCase

**Pattern**: `^[A-Z][a-zA-Z0-9]*$`

**Rationale**: SubApps are containers for modular functionality, treated similarly to CATs in architectural hierarchy.

**Severity**: ERROR

**Examples**:

✅ **Compliant**:
- `SeqManager`
- `AlarmHandling`
- `ProcessControl`

❌ **Non-Compliant**:
- `seqManager` (starts with lowercase)
- `seq_manager` (uses underscores)

**SE ADG Reference**: Section 1.5.0_1, CAT and SubApp

---

### Rule 3: Basic Function Block

**Convention**: camelCase

**Pattern**: `^[a-z][a-zA-Z0-9]*$`

**Rationale**: Basic Function Blocks are low-level logic components with ECC state machines. camelCase distinguishes them from higher-level CATs and aligns with method/function naming in many languages.

**Severity**: ERROR

**Examples**:

✅ **Compliant**:
- `scaleLogic`
- `stateDevice`
- `pidController`
- `camelCaseNaming`

❌ **Non-Compliant**:
- `ScaleLogic` (starts with uppercase)
- `scale_logic` (uses underscores)
- `SCALELOGIC` (all uppercase)

**Edge Cases**:
- Single-word names: `scale` is valid but `scaleLogic` is preferred for clarity
- Acronyms: `httpClient` (not `HTTPClient`)

**SE ADG Reference**: Section 1.5.0_2, Basic, Composite and Function

---

### Rule 4: Composite Function Block

**Convention**: camelCase

**Pattern**: `^[a-z][a-zA-Z0-9]*$`

**Rationale**: Composite FBs are compositions of other function blocks. Same convention as Basic FBs to maintain consistency within the FB type hierarchy.

**Severity**: ERROR

**Examples**:

✅ **Compliant**:
- `motorControl`
- `valveSequence`
- `temperatureLoop`

❌ **Non-Compliant**:
- `MotorControl` (PascalCase)
- `motor_control` (snake_case)

**SE ADG Reference**: Section 1.5.0_2, Basic, Composite and Function

---

### Rule 5: Function

**Convention**: camelCase

**Pattern**: `^[a-z][a-zA-Z0-9]*$`

**Rationale**: Functions are stateless operations, similar to methods in programming languages. camelCase is the standard for functions/methods across most languages.

**Severity**: ERROR

**Examples**:

✅ **Compliant**:
- `calculateAverage`
- `convertTemperature`
- `validateInput`

❌ **Non-Compliant**:
- `CalculateAverage` (PascalCase)
- `calculate_average` (snake_case)

**SE ADG Reference**: Section 1.5.0_2, Basic, Composite and Function

---

### Rule 6: Adapter

**Convention**: IPascalCase (uppercase 'I' prefix)

**Pattern**: `^I[A-Z][a-zA-Z0-9]*$`

**Rationale**: The 'I' prefix denotes "Interface" (socket/plug pattern). Follows interface naming conventions from languages like C#, Java, TypeScript.

**Severity**: ERROR

**Examples**:

✅ **Compliant**:
- `IPv`
- `IAnalogValue`
- `IMotorControl`
- `IPressureSensor`

❌ **Non-Compliant**:
- `AnalogValue` (missing 'I' prefix)
- `iAnalogValue` (lowercase 'i')
- `I_AnalogValue` (underscore after prefix)
- `IANALOGVALUE` (all uppercase)

**Edge Cases**:
- Single-letter after I: `IV` is technically valid but discouraged
- Acronyms: `IHttpClient` (not `IHTTPClient`)

**SE ADG Reference**: Section 1.5.0_3, Adapter

---

### Rule 7: Event

**Convention**: SNAKE_CASE (all uppercase with underscores)

**Pattern**: `^[A-Z_]+$`

**Rationale**: Events are discrete signals that trigger state transitions. ALL_CAPS makes them visually distinct and emphasizes their importance as control flow triggers.

**Severity**: ERROR

**Examples**:

✅ **Compliant**:
- `START_MOTOR`
- `STOP_PROCESS`
- `ALARM_TRIGGERED`
- `RESET`
- `INIT` (reserved)
- `INITO` (reserved)

❌ **Non-Compliant**:
- `StartMotor` (PascalCase)
- `start_motor` (lowercase with underscores)
- `START-MOTOR` (hyphen instead of underscore)

**Special Cases**:
- **Reserved Events**: `INIT` and `INITO` are standard initialization events and always valid
- Single word events: `START`, `STOP`, `RESET` are acceptable
- Avoid excessive length: `EMERGENCY_SHUTDOWN_SEQUENCE_INITIATED` is technically valid but unwieldy

**SE ADG Reference**: Section 1.5.0_4, Event

---

### Rule 8: Structure Data Type

**Convention**: strPascalCase (lowercase 'str' prefix)

**Pattern**: `^str[A-Z][a-zA-Z0-9]*$`

**Rationale**: The 'str' prefix immediately identifies the type as a structure (composite data type). PascalCase after prefix maintains readability.

**Severity**: ERROR

**Examples**:

✅ **Compliant**:
- `strMotorData`
- `strRecipeParms`
- `strProcessValues`
- `strSensorConfig`

❌ **Non-Compliant**:
- `MotorData` (missing 'str' prefix)
- `StrMotorData` (uppercase 'S' in prefix)
- `str_MotorData` (underscore after prefix)
- `strmotordata` (not PascalCase after prefix)

**Edge Cases**:
- Avoid redundancy: `strDataStructure` is redundant (structure is implied by 'str')
- Keep suffix meaningful: `strMotorData` not `strMotor` unless truly minimal

**SE ADG Reference**: Section 1.5.0_8, User Data Type (Structure)

---

### Rule 9: Alias Data Type

**Convention**: aPascalCase (lowercase 'a' prefix)

**Pattern**: `^a[A-Z][a-zA-Z0-9]*$`

**Rationale**: The 'a' prefix denotes an alias (type synonym). Distinguishes aliases from base types and structures.

**Severity**: WARNING

**Examples**:

✅ **Compliant**:
- `aFrame`
- `aSymbol`
- `aTimestamp`

❌ **Non-Compliant**:
- `Frame` (missing 'a' prefix)
- `AFrame` (uppercase 'A' in prefix)

**Note**: Severity is WARNING rather than ERROR because aliases are less commonly used and violations have minimal functional impact.

**SE ADG Reference**: Section 1.5.0_8, User Data Type (Alias)

---

### Rule 10: Enumeration Data Type

**Convention**: ePascalCase (lowercase 'e' prefix)

**Pattern**: `^e[A-Z][a-zA-Z0-9]*$`

**Rationale**: The 'e' prefix identifies enumerations, distinguishing them from other data types. Common convention across multiple languages.

**Severity**: ERROR

**Examples**:

✅ **Compliant**:
- `eProductType`
- `eSelectAction`
- `eOperationMode`
- `eAlarmPriority`

❌ **Non-Compliant**:
- `ProductType` (missing 'e' prefix)
- `EProductType` (uppercase 'E' in prefix)
- `e_ProductType` (underscore after prefix)

**Edge Cases**:
- Enum values: Individual enum members (e.g., `RUNNING`, `STOPPED`) should use SNAKE_CASE
- Example:
  ```xml
  <EnumeratedType Name="eOperationMode">
    <EnumeratedValue Name="IDLE" Value="0"/>
    <EnumeratedValue Name="RUNNING" Value="1"/>
    <EnumeratedValue Name="ERROR" Value="2"/>
  </EnumeratedType>
  ```

**SE ADG Reference**: Section 1.5.0_8, User Data Type (Enum)

---

### Rule 11: Array Data Type

**Convention**: arrPascalCase (lowercase 'arr' prefix)

**Pattern**: `^arr[A-Z][a-zA-Z0-9]*$`

**Rationale**: The 'arr' prefix explicitly identifies arrays, preventing confusion with single values or structures.

**Severity**: WARNING

**Examples**:

✅ **Compliant**:
- `arrRecipeBuffer`
- `arrSensorValues`
- `arrSetPoints`

❌ **Non-Compliant**:
- `RecipeBuffer` (missing 'arr' prefix)
- `ArrRecipeBuffer` (uppercase 'A' in prefix)

**Edge Cases**:
- Multi-dimensional arrays: `arrMatrix2D` is acceptable
- Array of structures: `arrMotorData` (structure prefix 'str' not needed)

**Note**: Severity is WARNING because array typing is often clear from context.

**SE ADG Reference**: Section 1.5.0_8, User Data Type (Array)

---

### Rule 12: Interface Variable (I/O)

**Convention**: PascalCase

**Pattern**: `^[A-Z][a-zA-Z0-9]*$`

**Rationale**: Interface variables are part of the public API of a function block. PascalCase makes them visually distinct from internal implementation details.

**Severity**: ERROR

**Examples**:

✅ **Compliant**:
- `PermitOn`
- `FeedbackOn`
- `SetPoint`
- `ProcessValue`

❌ **Non-Compliant**:
- `permitOn` (camelCase - this is for internal variables)
- `permit_on` (snake_case)
- `PERMIT_ON` (all uppercase - this is for events)

**Context Detection**:
The validator detects interface variables from their location in XML:
```xml
<InterfaceList>
  <InputVars>
    <VarDeclaration Name="PermitOn" Type="BOOL" /> <!-- Interface -->
  </InputVars>
</InterfaceList>
```

**SE ADG Reference**: Section 1.5.0_9, Variable (interface)

---

### Rule 13: Internal Variable

**Convention**: camelCase

**Pattern**: `^[a-z][a-zA-Z0-9]*$`

**Rationale**: Internal variables are private implementation details. camelCase distinguishes them from public interface variables.

**Severity**: WARNING

**Examples**:

✅ **Compliant**:
- `error`
- `outMinActiveLast`
- `calculatedValue`
- `tempBuffer`

❌ **Non-Compliant**:
- `Error` (PascalCase - this is for interface variables)
- `out_min_active_last` (snake_case)

**Context Detection**:
The validator detects internal variables from:
```xml
<BasicFB>
  <InternalVars>
    <VarDeclaration Name="outMinActiveLast" Type="BOOL" /> <!-- Internal -->
  </InternalVars>
</BasicFB>
```

**Note**: Severity is WARNING because internal variable naming has less impact on maintainability than interface naming.

**SE ADG Reference**: Section 1.5.0_9, Variable (internal to Basic FB)

---

### Rule 14: Folder

**Convention**: PascalCase, preferably single word

**Pattern**: `^[A-Z][a-zA-Z0-9]*$`

**Rationale**: Folders organize application structure. PascalCase provides consistency with other high-level organizational artifacts (CATs, SubApps).

**Severity**: WARNING

**Examples**:

✅ **Compliant**:
- `Motors`
- `Positioner`
- `SetPointManagement` (multi-word acceptable)
- `Valves`

❌ **Non-Compliant**:
- `motors` (lowercase)
- `set_point_management` (snake_case)

**Best Practices**:
- Prefer single words for simplicity: `Motors` over `MotorControl`
- Use plurals for collections: `Motors` (multiple motor components) vs `Motor` (single motor type)
- Avoid abbreviations unless universally understood: `IO` is OK, `MtrCtrl` is not

**Note**: Severity is WARNING because folder naming has minimal functional impact.

**SE ADG Reference**: Section 1.5.0_10, Folder

---

## Severity Definitions

| Severity | Meaning | Impact | Recommendation |
|----------|---------|--------|----------------|
| **ERROR** | Violates critical convention | Reduces readability significantly, blocks deployment | Must fix before release |
| **WARNING** | Violates recommended convention | Minor readability impact | Should fix, but not blocking |
| **INFO** | Suggestion or edge case | Minimal impact | Optional improvement |

**Exit Code Mapping**:
- All compliant → Exit 0
- Warnings only → Exit 10 (non-blocking)
- Any errors → Exit 11 (blocking)
- Parse failure → Exit 1

---

## Context-Specific Rules

### Variable Scope Context

The same name may have different requirements based on scope:

| Context | Location | Convention | Example |
|---------|----------|-----------|---------|
| Interface Input | `<InterfaceList><InputVars>` | PascalCase | `PermitOn` |
| Interface Output | `<InterfaceList><OutputVars>` | PascalCase | `FeedbackOn` |
| Internal (Basic FB) | `<BasicFB><InternalVars>` | camelCase | `outMinActiveLast` |
| Adapter Variable | `<Adapter><EventInputs with Var>` | PascalCase | `Value` |

**Validator Strategy**: Parse XML structure to determine scope before applying rule.

### DataType Category Context

DataType files (.dtp) can contain multiple type categories:

```xml
<!-- Structure -->
<StructuredType Name="strMotorData"> → Rule 8 (strPascalCase)

<!-- Enum -->
<EnumeratedType Name="eProductType"> → Rule 10 (ePascalCase)

<!-- Array -->
<ArrayType Name="arrRecipeBuffer"> → Rule 11 (arrPascalCase)

<!-- Alias -->
<DataType Name="aFrame" Comment="ALIAS"> → Rule 9 (aPascalCase)
```

**Validator Strategy**: Inspect XML element type to determine category.

---

## Reserved Keywords

### Event Names

- `INIT`: Standard initialization event (always valid)
- `INITO`: Initialization output event (always valid)
- `REQ`: Common request event (valid, follows SNAKE_CASE)
- `CNF`: Common confirmation event (valid, follows SNAKE_CASE)

These are part of the IEC 61499 standard and should never be flagged as violations.

### IEC 61131-3 Keywords

If a name conflicts with ST (Structured Text) keywords, it may cause compilation issues even if it follows naming conventions. The validator can optionally check for:

- `IF`, `THEN`, `ELSE`, `ELSIF`, `END_IF`
- `FOR`, `TO`, `BY`, `DO`, `END_FOR`
- `WHILE`, `END_WHILE`
- `REPEAT`, `UNTIL`, `END_REPEAT`
- `CASE`, `OF`, `END_CASE`
- `VAR`, `VAR_INPUT`, `VAR_OUTPUT`, `END_VAR`
- `FUNCTION`, `FUNCTION_BLOCK`, `END_FUNCTION`, `END_FUNCTION_BLOCK`
- `TRUE`, `FALSE`
- `AND`, `OR`, `NOT`, `XOR`

**Recommendation**: Avoid these keywords entirely, even with correct casing.

---

## Edge Cases and Exceptions

### Acronyms

**Guideline**: Capitalize only the first letter when mid-name

❌ Avoid:
- `HTTPServer` → Hard to read
- `XMLParser` → Hard to read

✅ Prefer:
- `HttpServer`
- `XmlParser`

**Exception**: When acronym is the entire name, use appropriate case:
- Event: `HTTP` (all caps, if treated as event)
- Variable: `Id` (PascalCase for interface, `id` for internal)

### Numbers in Names

**Allowed**: Numbers anywhere except the first character
- ✅ `Motor2Control`
- ✅ `Analog4to20mA`
- ❌ `2MotorControl`

**Recommendation**: Spell out numbers where possible for clarity:
- `SecondMotorControl` instead of `Motor2Control`

### Single-Character Names

**Generally discouraged** but technically valid if pattern matches:
- ✅ `X` (interface variable in math/geometry context)
- ✅ `i` (internal loop counter)
- ❌ `a` (conflicts with alias prefix)
- ❌ `e` (conflicts with enum prefix)

**Recommendation**: Use descriptive names even for temporary variables.

### Legacy Code

**Problem**: Existing applications may have hundreds of non-compliant names that function correctly.

**Solution**: Gradual adoption strategy
```bash
# Phase 1: Report only (no blocking)
python scripts/validate_names.py --app-dir ./Legacy --min-severity INFO

# Phase 2: Block only new violations
python scripts/validate_names.py --app-dir ./Legacy --exclude "Legacy/*" --min-severity ERROR

# Phase 3: Full enforcement
python scripts/validate_names.py --app-dir ./Legacy --min-severity ERROR
```

---

## Pattern Testing Examples

### Test Cases for PascalCase

```python
Pattern: ^[A-Z][a-zA-Z0-9]*$

✅ Pass:
- "A" (single uppercase letter)
- "Motor"
- "MotorControl"
- "Motor2Control" (number mid-name)
- "M" (single char OK)

❌ Fail:
- "motor" (starts lowercase)
- "Motor_Control" (underscore)
- "MOTOR" (all uppercase, violates "mixed case")
- "2Motor" (starts with number)
- "" (empty string)
```

### Test Cases for camelCase

```python
Pattern: ^[a-z][a-zA-Z0-9]*$

✅ Pass:
- "motor"
- "motorControl"
- "calculateAverage"
- "m" (single char OK)

❌ Fail:
- "Motor" (starts uppercase)
- "motor_control" (underscore)
- "motorcontrol" (technically passes but discouraged - prefer clear word boundaries)
- "2motor" (starts with number)
```

### Test Cases for SNAKE_CASE

```python
Pattern: ^[A-Z_]+$

✅ Pass:
- "START"
- "START_MOTOR"
- "EMERGENCY_STOP"
- "INIT"

❌ Fail:
- "Start" (mixed case)
- "start_motor" (lowercase)
- "START-MOTOR" (hyphen)
- "START_MOTOR_" (trailing underscore - technically passes pattern but discouraged)
```

### Test Cases for Prefixed Types

```python
# strPascalCase
Pattern: ^str[A-Z][a-zA-Z0-9]*$

✅ Pass: "strMotorData", "strData"
❌ Fail: "MotorData", "StrMotorData", "str_MotorData", "strmotordata"

# IPascalCase
Pattern: ^I[A-Z][a-zA-Z0-9]*$

✅ Pass: "IAnalogValue", "IValue"
❌ Fail: "AnalogValue", "iAnalogValue", "I_AnalogValue"

# ePascalCase
Pattern: ^e[A-Z][a-zA-Z0-9]*$

✅ Pass: "eProductType", "eType"
❌ Fail: "ProductType", "EProductType", "e_ProductType"
```

---

## References

- **SE Application Design Guidelines**: EIO0000004686.06, Section 1.5 "Colors and Naming Convention"
- **IEC 61499 Standard**: Event-driven function block architecture
- **IEC 61131-3 Standard**: Structured Text (ST) programming language keywords
- **General Programming Conventions**: PascalCase, camelCase, SNAKE_CASE from common language style guides
