# SE Process Libraries - Block Catalog

Complete catalog of function blocks in SE.App2Base and SE.App2CommonProcess.

---

## SE.App2Base

### Basics (46 blocks)

Basic function blocks for low-level calculations and control.

| Block | Description |
|-------|-------------|
| `alarmCalc` | Alarm calculation |
| `alarmCalcBasic` | Basic alarm calculation |
| `alarmEdgeDelayCalc` | Alarm with edge delay |
| `alarmStateCalc` | State-based alarm calculation |
| `analogSelector` | Analog signal selector |
| `anaThreshold` | Analog threshold detection |
| `aOSignalSel` | Analog output signal selector |
| `availableOwnerCalc` | Available owner calculation |
| `boolESel` | Boolean event selector |
| `boolValueChanged` | Boolean value change detector |
| `checkInitialization` | Initialization checker |
| `counterBasic` | Basic counter |
| `decodeStatus` | Status decoder |
| `devESel` | Device event selector |
| `deviationCalc` | Deviation calculation |
| `deviationCalcBasic` | Basic deviation calculation |
| `devInSel` | Device input selector |
| `devRealSel` | Device real selector |
| `devUIntSel` | Device unsigned int selector |
| `dintToTime` | DINT to TIME conversion |
| `dOSignalSel` | Digital output signal selector |
| `encodeStatus` | Status encoder |
| `externalRangeSel` | External range selector |
| `intToBool` | INT to BOOL conversion |
| `limitScaleValue` | Limit and scale value |
| `limitValue` | Value limiter |
| `maintCalc` | Maintenance calculation |
| `modeBase` | Mode base control |
| `ownerBasic` | Basic owner control |
| `ownerControl` | Owner control |
| `rampCalc` | Ramp calculation |
| `realParaSel` | Real parameter selector |
| `rendEmProgSel` | Rendezvous emergency program selector |
| `rendProgSel` | Rendezvous program selector |
| `rocCalc` | Rate of change calculation |
| `signalDelayBase` | Signal delay base |
| `spBoolSel` | Setpoint boolean selector |
| `spDintSel` | Setpoint DINT selector |
| `spIntSel` | Setpoint INT selector |
| `spRealSel` | Setpoint REAL selector |
| `timeCalcBasic` | Basic time calculation |
| `totalizerBasic` | Basic totalizer |
| `uintBitToEvent` | UINT bit to event |
| `uintSourceSel` | UINT source selector |
| `uintToEvent` | UINT to event |
| `vCtlSpCalc` | Value control setpoint calculation |

### Composites (15 blocks)

Composite function blocks for signal handling.

| Block | Description |
|-------|-------------|
| `aISignal` | Analog input signal |
| `aOSignal` | Analog output signal |
| `counterPersistance` | Counter with persistence |
| `countISignal` | Counter input signal |
| `deviationAlarmBasic` | Basic deviation alarm |
| `dISignal` | Digital input signal |
| `dISignalBasic` | Basic digital input signal |
| `dOSignal` | Digital output signal |
| `dOSignalBasic` | Basic digital output signal |
| `plcStart` | PLC start sequence |
| `pulse` | Pulse generator |
| `rocCompare` | Rate of change comparator |
| `stateAlarmBasic` | Basic state alarm |
| `timeCalc` | Time calculation |
| `timeCalcPersistence` | Time calculation with persistence |

### Adapters (5)

Standard signal adapters.

| Adapter | Description |
|---------|-------------|
| `IAnalog` | Analog signal interface (Value, Status, Quality) |
| `IDigital` | Digital signal interface (State, Status) |
| `IDInt` | Double integer signal interface |
| `IString` | String signal interface |
| `ITime` | Time signal interface |

### Functions (15)

Utility functions.

| Function | Description |
|----------|-------------|
| `findEqArrayDInt` | Find equal in DINT array |
| `findEqArrayInt` | Find equal in INT array |
| `findEqArrayUDInt` | Find equal in UDINT array |
| `findEqPArrayDInt` | Find equal in partial DINT array |
| `findEqPArrayUDInt` | Find equal in partial UDINT array |
| `findEqPArrayUInt` | Find equal in partial UINT array |
| `findGTArrayUDInt` | Find greater than in UDINT array |
| `findLTArrayUDInt` | Find less than in UDINT array |
| `fnProfile1PhaseData` | Profile 1 phase data |
| `fnProfile2PhaseData` | Profile 2 phase data |
| `fnProfile2PhaseDataDiscrete` | Profile 2 phase data discrete |
| `occuranceArrayUDInt` | Occurrence count in UDINT array |
| `scale` | Value scaling |
| `sortDecArrayUDInt` | Sort UDINT array descending |
| `sortIncArrayUDInt` | Sort UDINT array ascending |

### DataTypes (10)

User-defined data types.

| Type | Description |
|------|-------------|
| `ActiveState` | Active/inactive state enumeration |
| `AnalogInSel` | Analog input selection enumeration |
| `Bool4` | Array of 4 booleans |
| `LReal20` | Array of 20 LREAL values |
| `OwnerState` | Owner state enumeration (Manual, Auto, Program) |
| `Real20` | Array of 20 REAL values |
| `Real4` | Array of 4 REAL values |
| `StateSel` | State selection enumeration |
| `Status` | Signal quality status (Good, Bad, Uncertain) |
| `TimeFormat` | Time format enumeration |

### CATs (24)

Composite Automation Types with HMI symbols.

#### Display CATs

| CAT | Description |
|-----|-------------|
| `DisplayBool` | Display boolean value |
| `DisplayDint` | Display DINT value |
| `DisplayInt` | Display INT value |
| `DisplayReal` | Display REAL value |
| `DisplayString` | Display STRING value |
| `DisplayTime` | Display TIME value |

#### Set CATs

| CAT | Description |
|-----|-------------|
| `SetBool` | Set boolean value |
| `SetDint` | Set DINT value |
| `SetInt` | Set INT value |
| `SetReal` | Set REAL value |
| `SetString` | Set STRING value |
| `SetTime` | Set TIME value |

#### Alarm CATs

| CAT | Description |
|-----|-------------|
| `DeviationAlarm` | Deviation alarm |
| `DiSignalAlarm` | Digital signal alarm |
| `LimitAlarm` | Limit alarm (high/low) |
| `ROCAlarm` | Rate of change alarm |
| `StateAlarm` | State alarm |

#### Other CATs

| CAT | Description |
|-----|-------------|
| `AISignalScaling` | Analog input scaling |
| `EChainControl` | Event chain control |
| `MathVar` | Math variable |
| `Mode` | Mode control (Auto/Manual/Program) |
| `Owner` | Owner control |
| `SignalDelay` | Signal delay |

---

## SE.App2CommonProcess

### Application CATs

#### Signal Processing

| CAT | Description |
|-----|-------------|
| `AnalogInput` | Analog input signal monitoring |
| `AnalogOutput` | Analog output signal conditioning |
| `DigitalInput` | Digital input signal monitoring |
| `DigitalOutput` | Digital output signal conditioning |
| `MultiAnalogInput` | Multiple analog input (up to 4) |
| `Total` | Totalizer (flow totalization) |

#### Motors

| CAT | Description |
|-----|-------------|
| `Motor` | Unidirectional single-speed motor |
| `Motor2D` | Two-direction motor |
| `Motor2S` | Two-speed motor |
| `MotorCyc` | Cyclic motor operation |
| `MotorVs` | Variable speed motor |

#### Valves

| CAT | Description |
|-----|-------------|
| `Valve` | On/Off valve with single output |
| `Valve2Op` | Valve with separate open/close commands |
| `ValveControl` | Control valve with analog position |
| `ValveHand` | Hand valve (monitor only) |
| `ValveM` | Motorized valve |
| `ValveMPos` | Motorized valve with positioner |

#### Positioners

| CAT | Description |
|-----|-------------|
| `PositionerServo` | Servo drive positioner |
| `PositionerVSD` | VSD (Variable Speed Drive) positioner |

#### Process Control

| CAT | Description |
|-----|-------------|
| `LeadLag` | Lead/Lag compensation |
| `PID` | Standard PID controller |
| `PIDMultiplexer` | PID with two parameter sets |
| `PWM` | Pulse Width Modulation output |
| `Ramp` | Ramp setpoint generator |
| `Ratio` | Ratio control |
| `Split2Range` | Split range control |
| `Step3` | 3-point step control |

#### Equipment Modules

| CAT | Description |
|-----|-------------|
| `FlowCtl` | Flow control module |
| `PumpAssets` | Pump asset management |
| `PumpSet` | Pump set management (duty/standby) |

#### Auxiliary

| CAT | Description |
|-----|-------------|
| `AlarmSummary` | Alarm summary monitor |
| `MessageBox` | Operator message display |
| `Scheduler` | Time-based scheduler |

#### Calculation

| CAT | Description |
|-----|-------------|
| `Alinear` | Analog linearization |

### Common Services

#### Interlocks

| Block | Type | Description |
|-------|------|-------------|
| `ilckCondItem` | Composite | Interlock condition item |
| `IlckCondSum` | CAT | Interlock condition summary |

#### Failures

| Block | Type | Description |
|-------|------|-------------|
| `failCondItem` | Composite | Failure condition item |
| `FailCondSum` | CAT | Failure condition summary |

#### Permissives

| Block | Type | Description |
|-------|------|-------------|
| `permCondItem` | Composite | Permissive condition item |
| `PermCondSum` | CAT | Permissive condition summary |

#### Maintenance

| Block | Type | Description |
|-------|------|-------------|
| `DevMnt` | CAT | Device preventive maintenance |

#### Local Panel

| Block | Type | Description |
|-------|------|-------------|
| `MotorLp` | CAT | Motor local panel |
| `Motor2SLp` | CAT | Two-speed motor local panel |
| `Motor2DLp` | CAT | Two-direction motor local panel |
| `MotorVsLp` | CAT | Variable speed motor local panel |
| `ValveLp` | CAT | Valve local panel |
| `ValveMPosLp` | CAT | Motorized valve with position local panel |

### Basic Function Blocks (57)

Organized by category.

#### Condition

| Block | Description |
|-------|-------------|
| `condDataSel` | Condition data selector |
| `condDevCtl` | Condition device control |
| `condItemCalc` | Condition item calculation |
| `condSignalSel` | Condition signal selector |
| `firstCond` | First condition |
| `permDevCtl` | Permissive device control |
| `permItemCalc` | Permissive item calculation |

#### Device

| Block | Description |
|-------|-------------|
| `devControlBasic` | Basic device control |
| `devCtlMPos` | Device control with position |
| `externalOwnerSel` | External owner selector |
| `mVPosReactAlmCalc` | Motor valve position reactive alarm calc |
| `valveHandBasic` | Basic hand valve |
| `valveSpControl` | Valve setpoint control |

#### Equipment Module Basics

| Block | Description |
|-------|-------------|
| `assetDataCalc` | Asset data calculation |
| `emSeqCtrl` | Equipment module sequence control |
| `flowConfig` | Flow configuration |
| `pumpAssetSeqCtlBasic` | Pump asset sequence control basic |
| `pumpAssetStateCtl` | Pump asset state control |
| `pumpEmStateCtl` | Pump equipment module state control |
| `pumpReconfig` | Pump reconfiguration |
| `pumpSetQStop` | Pump set quick stop |
| `pumpSetStop` | Pump set stop |

#### Local Panel

| Block | Description |
|-------|-------------|
| `localPanel` | Local panel |
| `localPanelPos` | Local panel with position |
| `lpDataSel` | Local panel data selector |

#### Signal Processing

| Block | Description |
|-------|-------------|
| `analogInCalcBasic` | Basic analog input calculation |
| `analogOutBasic` | Basic analog output |
| `digitalInBasic` | Basic digital input |
| `digitalOutBasic` | Basic digital output |
| `digitalOutCycBasic` | Basic cyclic digital output |
| `frequencyDigital` | Digital frequency |
| `split2RangeCtl` | Split 2 range control |

#### Type Conversion

| Block | Description |
|-------|-------------|
| `boolToIDigital` | BOOL to IDigital adapter |
| `boolToIlckState` | BOOL to interlock state |
| `stateToBool` | State to BOOL |
| `decodeIAnalog` | Decode IAnalog |
| `decodeIDigital` | Decode IDigital |
| `decodeState` | Decode state |
| `encodeIAnalog` | Encode IAnalog |
| `encodeIDigital` | Encode IDigital |
| `encodeState` | Encode state |
| `encodeStatus` | Encode status |

### Composite Function Blocks (69)

#### Device Logic

| Block | Description |
|-------|-------------|
| `motor2DLogic` | Two-direction motor logic |
| `motor2SLogic` | Two-speed motor logic |
| `motorCycLogic` | Cyclic motor logic |
| `motorLogic` | Motor logic |
| `motorVsLogic` | Variable speed motor logic |
| `valve2OpLogic` | Two-output valve logic |
| `valveControlLogic` | Control valve logic |
| `valveHandLogic` | Hand valve logic |
| `valveLogic` | Valve logic |
| `valveMLogic` | Motorized valve logic |
| `valveMPosLogic` | Motorized valve with position logic |

#### Process Control

| Block | Description |
|-------|-------------|
| `leadLagCtl` | Lead/Lag control |
| `PIDCtl` | PID control |
| `PWMCtl` | PWM control |
| `rampCtl` | Ramp control |

#### Equipment Module

| Block | Description |
|-------|-------------|
| `flowCtlLogic` | Flow control logic |
| `mergeIDevice` | Merge IDevice |
| `pumpAssetSeqCtl` | Pump asset sequence control |
| `pumpSetConfigSeq` | Pump set configuration sequence |
| `pumpSetLogic` | Pump set logic |
| `pumpSetQuickStop` | Pump set quick stop |
| `pumpSetStopSeq` | Pump set stop sequence |

#### Sequence Data (for Recipe/Batch)

| Block | Description |
|-------|-------------|
| `analogInSeqData` | Analog input sequence data |
| `digitalInSeqData` | Digital input sequence data |
| `motorSeqData` | Motor sequence data |
| `valveSeqData` | Valve sequence data |
| `PIDSeqData` | PID sequence data |
| ... | (many more for each CAT type) |

### Adapters (30)

#### Condition Adapters

| Adapter | Description |
|---------|-------------|
| `IFailCondSum` | Failure condition chain |
| `IIlckCondSum` | Interlock condition chain |
| `IOpCondS` | Operation condition socket |
| `IOpFailS` | Operation failure socket |
| `IOpPermS` | Operation permissive socket |
| `IPermCondSum` | Permissive condition chain |

#### Device Adapters

| Adapter | Description |
|---------|-------------|
| `IDevice` | Device command/status interface |
| `ISeqData` | Sequence data interface |
| `IServiceExtension` | Service extension interface |
| `IEmServiceExtension` | Equipment module service extension |
| `IPIDServiceExtension` | PID service extension |

#### Equipment Adapters

| Adapter | Description |
|---------|-------------|
| `IAssetData` | Asset data interface |
| `IEm` | Equipment module interface |
| `IEmCommand` | Equipment module command |
| `IEmData` | Equipment module data |
| `IEmSeqCtl` | Equipment module sequence control |
| `IPumpAsset` | Pump asset interface |

#### Local Panel Adapters

| Adapter | Description |
|---------|-------------|
| `IDevLp` | Device local panel interface |
| `IDevPosLp` | Device position local panel |
| `IDevVsLp` | Device variable speed local panel |

#### Maintenance Adapter

| Adapter | Description |
|---------|-------------|
| `IDevMnt` | Device maintenance interface |

#### Positioner Adapters

| Adapter | Description |
|---------|-------------|
| `IPositioner` | Positioner interface |
| `IPositionerVSDDriveIn` | VSD drive input |
| `IPositionerVSDDriveOut` | VSD drive output |
| `IPosServoDriveIn` | Servo drive input |
| `IPosServoDriveOut` | Servo drive output |

#### Process Control Adapters

| Adapter | Description |
|---------|-------------|
| `ICascadeLoop` | Cascade loop interface |
| `IPIDExtPara` | PID external parameters |
| `IDintSp` | DINT setpoint interface |
