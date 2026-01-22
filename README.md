# EAE Claude Skills

Claude Code skills for **EcoStruxure Automation Expert (EAE)** development.

These skills help you create and modify IEC 61499 function blocks using natural language prompts with [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

## Quick Start

### Installation

Install using the [skills.sh](https://skills.sh) CLI:

```bash
npx skills add eae-acc/eae-claude-skills
```

This installs all EAE skills to your Claude Code environment.

### Verify Installation

In Claude Code, type `/eae-skill-router` - if the skill loads, installation was successful.

### Usage

Invoke skills using slash commands or natural language:

```
/eae-skill-router             # Router - shows what skill to use
/eae-cat                      # Create CAT block with HMI
/eae-basic-fb                 # Create Basic FB with algorithms
/eae-composite-fb             # Create Composite FB
/eae-datatype                 # Create DataType (struct/enum/array)
/eae-adapter                  # Create Adapter interface
/eae-fork                     # Fork block from SE library to custom library
```

Or just describe what you need:

```
User: Create a Basic FB called MotorController that controls speed
Claude: [Invokes eae-basic-fb, generates .fbt with ECC + algorithms]

User: Create an enumeration for machine states
Claude: [Invokes eae-datatype, generates .dt in DataType/ folder]
```

## Available Skills

### Creation Skills

| Skill | Command | Description |
|-------|---------|-------------|
| **eae-skill-router** | `/eae-skill-router` | Router - guides you to the right skill |
| **eae-cat** | `/eae-cat` | CAT blocks with HMI, OPC-UA, persistence |
| **eae-basic-fb** | `/eae-basic-fb` | Basic FB with ECC state machine + ST algorithms |
| **eae-composite-fb** | `/eae-composite-fb` | Composite FB with FBNetwork layout |
| **eae-datatype** | `/eae-datatype` | DataTypes: structures, enums, arrays, subranges |
| **eae-adapter** | `/eae-adapter` | Adapter types for socket/plug interfaces |
| **eae-fork** | `/eae-fork` | Fork blocks from SE libraries with namespace migration |

### Validation Skills

| Skill | Command | Description |
|-------|---------|-------------|
| **eae-naming-validator** | `/eae-naming-validator` | Enforce SE ADG naming conventions (14+ rules) |
| **eae-performance-analyzer** | `/eae-performance-analyzer` | Prevent event storms before deployment (4D analysis) |

### Reference Skills

| Skill | Command | Description |
|-------|---------|-------------|
| **eae-runtime-base** | `/eae-runtime-base` | Find standard Runtime.Base blocks (~100 blocks) |
| **eae-se-process** | `/eae-se-process` | Find SE process blocks (motors, valves, PID, etc.) |

### Decision Tree

```
What are you doing?
│
├── Forking block from SE library?         → /eae-fork
│
├── Creating a NEW block from scratch?
│   ├── Full block with HMI visualization? → /eae-cat (most common)
│   ├── State machine with algorithms?     → /eae-basic-fb
│   ├── Network of existing FBs?           → /eae-composite-fb
│   ├── Custom data type (enum, struct)?   → /eae-datatype
│   └── Reusable interface pattern?        → /eae-adapter
│
└── Looking up existing blocks?            → /eae-runtime-base, /eae-se-process
```

## Features

- **Correct XML structure** - Generates valid EAE XML with proper DOCTYPE, IDs, and attributes
- **dfbproj registration** - Automatically registers blocks in the library project file
- **FBNetwork layout** - Smart positioning guidelines for clean, readable composite blocks
- **All block types** - CAT, Basic, Composite, DataType, Adapter
- **Templates included** - XML templates for all block types

## Project Structure

```
.claude/skills/
├── eae-skill-router/           # Router + shared resources
│   ├── SKILL.md
│   ├── references/
│   │   └── common-rules.md     # Shared rules (IDs, registration)
│   └── assets/templates/       # XML templates for all block types
│
├── eae-cat/                    # CAT blocks
├── eae-basic-fb/               # Basic function blocks
├── eae-composite-fb/           # Composite function blocks
├── eae-datatype/               # Data types
├── eae-adapter/                # Adapter interfaces
├── eae-fork/                   # Fork blocks from SE libraries
│   ├── SKILL.md
│   ├── scripts/                # Python automation scripts
│   └── references/             # Namespace migration rules
├── eae-runtime-base/           # Runtime.Base library reference
└── eae-se-process/             # SE process blocks reference
```

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI or VS Code extension
- EcoStruxure Automation Expert (for testing generated blocks)

## Examples

### Create a Basic FB

```
User: Create a Basic FB called Calculator in MyLib namespace that adds two REAL values

Claude: I'll create a Basic FB with:
- Inputs: Value1 (REAL), Value2 (REAL)
- Output: Result (REAL)
- Algorithm: Result := Value1 + Value2

[Generates Calculator.fbt, Calculator.doc.xml, Calculator.meta.xml]
[Registers in MyLib.dfbproj]
```

### Create a Composite FB

```
User: Create a Composite FB that chains two Calculator blocks

Claude: I'll create a Composite FB with:
- Two Calculator instances wired together
- First result feeds into second input
- Proper FBNetwork layout

[Generates ChainedCalc.fbt with FBNetwork]
```

### Create an Enumeration

```
User: Create an enum for MachineState with Idle, Running, Error

Claude: I'll create a DataType enumeration:
[Generates IEC61499/DataType/MachineState.dt]
```

### Validate Naming Conventions

```
User: Validate my EAE application naming

Claude: [Invokes eae-naming-validator]
python scripts/validate_names.py --app-dir IEC61499/MyLibrary

✅ AnalogInput (CAT) - PascalCase compliant
❌ motorController (CAT) - Should be PascalCase: MotorController
✅ scaleLogic (Basic FB) - camelCase compliant
❌ MotorInterface (Adapter) - Missing 'I' prefix: Should be IMotorInterface
```

### Analyze Performance

```
User: Check my application for event storms

Claude: [Invokes eae-performance-analyzer]
python scripts/analyze_event_flow.py --app-dir IEC61499/MyApp

⚠️ Event multiplication detected: 15.2x (threshold: 10x)
❌ CRITICAL: Tight event loop detected in ControllerBlock
  FB1 → FB2 → FB1 (2-hop cycle)
  Recommendation: Add state guard (RS flip-flop)
```

---

## SE ADG Compliance

All skills enforce compliance with **Schneider Electric Application Design Guidelines EIO0000004686.06**.

### Naming Conventions (Section 1.5)

| Artifact | Convention | Example | Validated By |
|----------|------------|---------|--------------|
| CAT | PascalCase | `MotorController` | eae-naming-validator |
| Basic FB | camelCase | `scaleLogic` | eae-naming-validator |
| Composite FB | camelCase | `dataProcessor` | eae-naming-validator |
| Adapter | IPascalCase | `IMotorControl` | eae-naming-validator |
| Interface Variables | PascalCase | `PermitOn`, `Value` | eae-naming-validator |
| Internal Variables | camelCase | `error`, `timerActive` | eae-naming-validator |
| Events | SNAKE_CASE | `START_MOTOR`, `INIT` | eae-naming-validator |
| Structures | strPascalCase | `strMotorData` | eae-naming-validator |
| Enumerations | ePascalCase | `eProductType` | eae-naming-validator |

**Enforcement:** Run `eae-naming-validator` before committing code.

### Performance Thresholds

| Metric | Safe | Moderate | Critical | Validated By |
|--------|------|----------|----------|--------------|
| Event Multiplication | <10x | 10-20x | >20x | eae-performance-analyzer |
| CPU Load | <70% | 70-90% | >90% | eae-performance-analyzer |
| Queue Depth | <100 | 100-500 | >500 | eae-performance-analyzer |
| Timer Frequency (HMI) | ≥500ms | 100-500ms | <100ms | eae-performance-analyzer |

**Best Practice:** Run `eae-performance-analyzer` during design reviews.

---

## Integration Patterns

### Pattern 1: Creation → Validation Pipeline

Recommended workflow for creating and validating artifacts:

```bash
# 1. Create artifact
/eae-cat MotorController

# 2. Validate naming
python .claude/skills/eae-naming-validator/scripts/validate_names.py \
  --app-dir IEC61499/MyLibrary

# 3. Validate performance (if has FBNetwork)
python .claude/skills/eae-performance-analyzer/scripts/analyze_event_flow.py \
  --app-dir IEC61499/MyLibrary

# 4. Run artifact-specific validation
python .claude/skills/eae-cat/scripts/validate_cat.py IEC61499/MotorController
```

### Pattern 2: CAT with Process Blocks

Build a CAT block using SE process library blocks:

```
1. /eae-cat → Create CAT block
2. /eae-se-process → Find Motor block from SE.App2CommonProcess
3. Add Motor instance to CAT FBNetwork
4. /eae-runtime-base → Find E_CYCLE for periodic HMI updates (500ms)
5. /eae-performance-analyzer → Validate no event storms
```

### Pattern 3: Composite with Timing

Create a composite FB with periodic execution:

```
1. /eae-composite-fb → Create composite
2. /eae-runtime-base → Find E_CYCLE for 100ms periodic trigger
3. Add E_CYCLE to FBNetwork
4. Validate layout: python scripts/validate_layout.py
5. Check event multiplication: /eae-performance-analyzer
```

---

## CI/CD Integration

### Pre-Commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash

# Validate naming conventions
python .claude/skills/eae-naming-validator/scripts/validate_names.py \
  --app-dir IEC61499/MyLibrary \
  --json

if [ $? -ne 0 ]; then
  echo "❌ Naming validation failed"
  exit 1
fi

# Detect critical event storm patterns
python .claude/skills/eae-performance-analyzer/scripts/detect_storm_patterns.py \
  --app-dir IEC61499/MyLibrary \
  --json

if [ $? -eq 11 ]; then
  echo "❌ Critical anti-patterns detected"
  exit 1
fi

echo "✅ All validations passed"
exit 0
```

### GitHub Actions

Create `.github/workflows/eae-validation.yml`:

```yaml
name: EAE Validation

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.x'

      - name: Validate Naming
        run: |
          python .claude/skills/eae-naming-validator/scripts/validate_names.py \
            --app-dir IEC61499/MyLibrary \
            --json \
            --output naming_results.json

      - name: Analyze Performance
        run: |
          python .claude/skills/eae-performance-analyzer/scripts/detect_storm_patterns.py \
            --app-dir IEC61499/MyLibrary \
            --json \
            --output performance_results.json

      - name: Upload Results
        uses: actions/upload-artifact@v2
        with:
          name: validation-results
          path: |
            naming_results.json
            performance_results.json
```

---

## Troubleshooting

### Common Issues

**Issue:** "CAT block won't load in EAE IDE"
- **Solution:** Verify all 11 IEC61499 files are present. Run: `python .claude/skills/eae-cat/scripts/validate_cat.py IEC61499/MyCATBlock`

**Issue:** "Naming validator flags adapter name"
- **Solution:** Adapters must start with uppercase 'I'. Rename `MotorControl` → `IMotorControl`

**Issue:** "Event storm in production"
- **Solution:** Run `analyze_event_flow.py`. Check for multiplication >20x. Add event consolidation.

**Issue:** "Composite FB has wrong Format attribute"
- **Solution:** Add `Format="2.0"` to `<FBType>` element in .fbt file

**Issue:** "Basic FB unreachable states"
- **Solution:** Run `validate_ecc.py`. Add transitions from START to all states.

**Issue:** "CPU load >90% on soft dPAC"
- **Solution:** Run `estimate_cpu_load.py`. Optimize ST algorithms (target cyclomatic complexity <10).

---

## Validation Scripts

All validation scripts follow a standard pattern:

### Exit Codes

| Code | Meaning | CI Action |
|------|---------|-----------|
| 0 | Success | Pass |
| 1 | Parse failure | Fail |
| 10 | Warnings (non-blocking) | Pass with warnings |
| 11 | Errors (blocking) | Fail |

### Naming Validator

```bash
# Validate entire application
python .claude/skills/eae-naming-validator/scripts/validate_names.py \
  --app-dir IEC61499/MyLibrary

# JSON output for CI
python .claude/skills/eae-naming-validator/scripts/validate_names.py \
  --app-dir IEC61499/MyLibrary \
  --json \
  --output naming_results.json
```

### Performance Analyzer

```bash
# Analyze event flow (multiplication factors)
python .claude/skills/eae-performance-analyzer/scripts/analyze_event_flow.py \
  --app-dir IEC61499/MyApp

# Estimate CPU load
python .claude/skills/eae-performance-analyzer/scripts/estimate_cpu_load.py \
  --app-dir IEC61499/MyApp \
  --platform soft-dpac-windows

# Predict queue depths
python .claude/skills/eae-performance-analyzer/scripts/predict_queue_depth.py \
  --app-dir IEC61499/MyApp \
  --event-flow-results event_flow.json

# Detect anti-patterns
python .claude/skills/eae-performance-analyzer/scripts/detect_storm_patterns.py \
  --app-dir IEC61499/MyApp
```

### Artifact-Specific Validators

```bash
# CAT validation
python .claude/skills/eae-cat/scripts/validate_cat.py IEC61499/MyCATBlock
python .claude/skills/eae-cat/scripts/validate_hmi.py HMI/MyCATBlock

# Basic FB validation
python .claude/skills/eae-basic-fb/scripts/validate_ecc.py MyBlock.fbt
python .claude/skills/eae-basic-fb/scripts/validate_st_algorithm.py MyBlock.fbt

# Composite FB validation
python .claude/skills/eae-composite-fb/scripts/validate_fbnetwork.py MyBlock.fbt
python .claude/skills/eae-composite-fb/scripts/validate_layout.py MyBlock.fbt
```

---

## Best Practices

### Naming

✅ **DO:**
- Use PascalCase for CAT blocks: `MotorController`
- Use camelCase for Basic/Composite FBs: `scaleLogic`
- Use IPascalCase for Adapters: `IMotorControl`
- Use SNAKE_CASE for events: `START_MOTOR`

❌ **DON'T:**
- Mix casing styles inconsistently
- Use generic names: `fb1`, `logic`, `data`
- Forget 'I' prefix on adapters
- Use camelCase for CAT blocks

### Performance

✅ **DO:**
- Keep event multiplication <10x
- Use E_CYCLE ≥100ms for HMI (500ms typical)
- Break event loops with state guards (RS flip-flop)
- Keep ST algorithm cyclomatic complexity <10

❌ **DON'T:**
- Create tight event loops (FB1 → FB2 → FB1)
- Use E_CYCLE <100ms without justification
- Trigger >30 downstream events from single source
- Create deeply nested IF statements (>3 levels)

### Structure

✅ **DO:**
- Add `Format="2.0"` to Composite FBs
- Use `Standard="61499-2"` for FBs
- Use `Standard="61499-1"` for Adapters
- Include all required files (.doc.xml, .meta.xml)

❌ **DON'T:**
- Mix BasicFB and FBNetwork in same file
- Use absolute paths in .cfg files
- Omit .cfg file from CAT blocks
- Create adapters without Service element

## Contributing

We welcome contributions from the EAE development community!

### How to Contribute

1. **Fork** this repository
2. **Create a branch** for your changes
3. **Test** your changes with Claude Code and EAE
4. **Submit a pull request**

### Contribution Ideas

- **New templates** - Add templates for block types not yet covered
- **Improved documentation** - Clarify instructions or add examples
- **Bug fixes** - Fix incorrect XML generation or registration patterns
- **Layout improvements** - Better FBNetwork positioning guidelines
- **New skills** - Skills for other EAE tasks (deployment, testing, etc.)

### Guidelines

1. **Test in EAE** - Verify generated blocks load correctly in EAE
2. **Follow existing patterns** - Match the style of existing skills
3. **Document changes** - Update SKILL.md files with any new features
4. **Keep it focused** - Each skill should do one thing well

### Reporting Issues

Found a bug or have a suggestion? [Open an issue](../../issues) with:
- EAE version you're using
- Steps to reproduce
- Expected vs actual behavior
- Any error messages from EAE

## Tested With

- EcoStruxure Automation Expert 26.0.0.0
- Claude Code (claude-opus-4-5-20251101)

## License

MIT License - See [LICENSE](LICENSE) for details.

## Acknowledgments

- Schneider Electric for EcoStruxure Automation Expert
- Anthropic for Claude Code
- The IEC 61499 community

---

**Note:** These skills generate EAE-compatible IEC 61499 XML. Always verify generated blocks in EAE before production use.
