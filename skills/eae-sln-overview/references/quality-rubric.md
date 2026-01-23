# Quality Scoring Rubric

Detailed scoring criteria for EAE project quality assessment.

## Overview

Total: **100 points** across 8 dimensions.

| Dimension | Points | Weight |
|-----------|--------|--------|
| Naming Compliance | 20 | 20% |
| Library Organization | 15 | 15% |
| Documentation | 15 | 15% |
| ISA88 Hierarchy | 15 | 15% |
| Protocol Configuration | 10 | 10% |
| Code Organization | 10 | 10% |
| Block Complexity | 10 | 10% |
| Reusability | 5 | 5% |

## Grade Scale

| Grade | Percentage | Description |
|-------|------------|-------------|
| A | 90-100% | Excellent - production ready |
| B | 80-89% | Good - minor improvements needed |
| C | 70-79% | Acceptable - some issues to address |
| D | 60-69% | Below standard - significant work needed |
| F | <60% | Failing - major problems |

---

## Dimension 1: Naming Compliance (20 points)

Checks adherence to Schneider Electric naming conventions from EIO0000004686.06.

### Scoring

| Score | Criteria |
|-------|----------|
| 20 | 100% compliance (0 violations) |
| 15 | 95-99% compliance |
| 10 | 90-94% compliance |
| 5 | 80-89% compliance |
| 0 | <80% compliance |

### Naming Patterns Checked

| Type | Pattern | Examples |
|------|---------|----------|
| CAT | PascalCase | `AnalogInput`, `DiscreteOutput` |
| Basic FB | camelCase | `scaleLogic`, `stateDevice` |
| Composite FB | camelCase | `motorControl`, `valveSequence` |
| Adapter | IPascalCase | `IAnalogValue`, `IMotorControl` |
| DataType (struct) | strPascalCase | `strMotorData`, `strRecipe` |
| DataType (enum) | ePascalCase | `eProductType`, `eState` |
| DataType (array) | arrPascalCase | `arrBuffer`, `arrValues` |
| Event | UPPER_SNAKE | `INIT`, `START_MOTOR` |
| Interface Variable | PascalCase | `PermitOn`, `SetPoint` |

### Integration

Uses patterns from `eae-naming-validator` skill for consistency.

---

## Dimension 2: Library Organization (15 points)

Evaluates SE library usage and custom library structure.

### Scoring

| Score | Criteria |
|-------|----------|
| 15 | Clear SE/custom separation, minimal custom code, explicit dependencies |
| 12 | Good organization, some unused library refs |
| 8 | Mixed organization, no circular dependencies |
| 4 | Disorganized, missing library references |
| 0 | Broken references, unable to resolve |

### Checks Performed

- SE libraries properly versioned
- Custom libraries have proper namespace prefix
- No orphan blocks (registered but missing files)
- No redundant library references
- Reasonable ratio of SE to custom libraries

### SE Library Categories

| Category | Libraries |
|----------|-----------|
| Runtime | `Runtime.Base` |
| Standard | `IEC61131.Standard`, `SE.Standard` |
| App Base | `SE.App2Base`, `SE.AppBase` |
| Process | `SE.App2CommonProcess` |
| Hardware | `SE.DPAC`, `SE.HwCommon`, `SE.FieldDevice` |
| I/O Modules | `SE.IoTMx`, `SE.IoATV` |
| Protocol | `Standard.IoModbus`, `Standard.IoEtherNetIP` |

---

## Dimension 3: Documentation (15 points)

Measures documentation coverage and quality.

### Scoring

| Score | Criteria |
|-------|----------|
| 15 | 90%+ blocks have .doc.xml, meaningful comments |
| 12 | 70-89% documentation coverage |
| 8 | 50-69% documentation coverage |
| 4 | 30-49% documentation coverage |
| 0 | <30% documentation coverage |

### What Counts as Documentation

- `.doc.xml` files for CAT blocks
- `Comment` attributes on VarDeclaration elements
- `VersionInfo` elements with meaningful content

### Partial Credit

Blocks with inline comments (but no .doc.xml) receive 0.5 credit.

---

## Dimension 4: ISA88 Hierarchy (15 points)

Evaluates ISA88 physical model implementation.

### Scoring

| Score | Criteria |
|-------|----------|
| 15 | Complete hierarchy (4+ levels), 90%+ CATs linked |
| 12 | Partial hierarchy (3 levels), 70%+ CATs linked |
| 8 | Basic hierarchy (2 levels), 50%+ CATs linked |
| 4 | Minimal structure, <50% CATs linked |
| 0 | Not configured (empty Assets.json) |

### ISA88 Levels

1. Enterprise
2. Site
3. Area
4. ProcessCell
5. Unit
6. EquipmentModule
7. ControlModule

### Files Checked

- `AssetLinkData/Asset Manifest/Assets.json`
- `AssetLinkData/Asset Manifest/AssetRelations.json`
- `AssetLinkData/Asset Manifest/EcoRTDevices.json`

---

## Dimension 5: Protocol Configuration (10 points)

Assesses communication protocol setup.

### Scoring

| Score | Criteria |
|-------|----------|
| 10 | Proper OPC-UA exposure, clean Modbus config, no orphan connections |
| 7 | Minor issues (some over-exposure, unused connections) |
| 4 | Significant issues (security concerns, broken connections) |
| 0 | No protocol configuration or completely broken |

### Checks Performed

- **OPC-UA**: Not exposing entire tree (over-exposure check)
- **Modbus**: Proper slave addressing, no conflicts
- **EtherNet/IP**: Valid scanner configurations
- **General**: No orphan connections, clean configuration

### Over-Exposure Warning

If `System.opcua.xml` has `Exposed="True"` on root or near-root elements, a warning is generated and points deducted.

---

## Dimension 6: Code Organization (10 points)

Evaluates project structure and folder organization.

### Scoring

| Score | Criteria |
|-------|----------|
| 10 | Consistent folder structure, logical grouping, Folders.xml organized |
| 7 | Good structure with minor inconsistencies |
| 4 | Disorganized but functional |
| 0 | No organization, flat structure |

### Checks Performed

- `Folders.xml` has meaningful categories
- Block names match folder hierarchy
- Consistent naming patterns across project
- Multiple subdirectories under `IEC61499/`

---

## Dimension 7: Block Complexity (10 points)

Identifies overly complex function blocks.

### Scoring

| Score | Criteria |
|-------|----------|
| 10 | All blocks <100 vars, event fanout <10 |
| 7 | 1-5 blocks exceed thresholds |
| 4 | 6-15 blocks exceed thresholds |
| 0 | >15 blocks exceed thresholds |

### Thresholds

| Metric | Warning | Error |
|--------|---------|-------|
| Variables per block | 100 | 200 |
| Event fanout (out/in) | 10 | 20 |
| Composite nesting depth | 5 | 7 |

### Why It Matters

Complex blocks are:
- Harder to maintain
- Prone to bugs
- Difficult to test
- Performance bottlenecks

---

## Dimension 8: Reusability (5 points)

Evaluates use of reusable patterns.

### Scoring

| Score | Criteria |
|-------|----------|
| 5 | Extensive adapter usage, composition over inheritance, shared utilities |
| 3 | Some reusable patterns |
| 1 | Minimal reuse, mostly copy-paste |
| 0 | No adapters, no composition |

### Reusability Indicators

- **Adapters (3 points max)**:
  - 10+ adapters: 3 points
  - 5-9 adapters: 2 points
  - 1-4 adapters: 1 point

- **Composite FBs (2 points max)**:
  - 20+ composites: 2 points
  - 5-19 composites: 1 point

### Why Adapters Matter

Adapters enable:
- Interface contracts
- Loose coupling
- Substitutable implementations
- Better testability

---

## Recommendations

Quality scoring generates prioritized recommendations based on points lost:

### High Priority (>5 points lost)

Fix immediately before deployment.

### Medium Priority (3-5 points lost)

Address in next maintenance cycle.

### Low Priority (<3 points lost)

Consider for future improvements.

### Example Recommendations

1. **[Naming]** Fix 15 naming violations
2. **[ISA88]** Add more ISA88 hierarchy levels (Site, Area, ProcessCell, Unit)
3. **[Documentation]** Add documentation to 25 more blocks
4. **[Complexity]** Refactor 3 complex blocks
5. **[Reusability]** Consider using adapters for reusable interfaces

---

## Automation Integration

Use JSON output for CI/CD integration:

```bash
# Get JSON quality data
python scripts/calculate_quality.py --project-dir /path/to/project --json > quality.json

# Check quality in pipeline
quality=$(cat quality.json | jq '.percentage')
if [ $(echo "$quality < 70" | bc) -eq 1 ]; then
  echo "Quality check failed: $quality%"
  exit 1
fi
```

### Exit Codes for Automation

| Code | Quality | Action |
|------|---------|--------|
| 0 | >=70% | Pass |
| 10 | 50-69% | Warning |
| 11 | <50% | Fail |
