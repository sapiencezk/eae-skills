# SE Process Libraries - Common Patterns

Practical usage patterns for SE.App2Base and SE.App2CommonProcess function blocks.

---

## 1. Basic Analog Input with Alarm

Monitor an analog signal with scaling and limit alarms.

```xml
<FBNetwork>
  <!-- Analog Input CAT -->
  <FB ID="1" Name="tempInput" Type="AnalogInput" Namespace="SE.App2CommonProcess" x="500" y="350" />

  <!-- Limit Alarm for high/low detection -->
  <FB ID="2" Name="tempAlarm" Type="LimitAlarm" Namespace="SE.App2Base" x="1100" y="350" />

  <EventConnections>
    <Connection Source="$INIT" Destination="$1.INIT" />
    <Connection Source="$1.INITO" Destination="$2.INIT" />
    <Connection Source="$1.UPD" Destination="$2.UPD" />
  </EventConnections>

  <DataConnections>
    <!-- Raw input from hardware -->
    <Connection Source="$RawInput" Destination="$1.In" />

    <!-- Connect analog output to alarm -->
    <Connection Source="$1.Pv" Destination="$2.Pv" />

    <!-- Alarm limits -->
    <Connection Source="80.0" Destination="$2.HiHi" />
    <Connection Source="70.0" Destination="$2.Hi" />
    <Connection Source="30.0" Destination="$2.Lo" />
    <Connection Source="20.0" Destination="$2.LoLo" />
  </DataConnections>
</FBNetwork>
```

---

## 2. Motor with Interlocks

Control a motor with interlock conditions.

```xml
<FBNetwork>
  <!-- Interlock condition items -->
  <FB ID="1" Name="ilckOilPressure" Type="ilckCondItem" Namespace="SE.App2CommonProcess" x="300" y="200" />
  <FB ID="2" Name="ilckOverTemp" Type="ilckCondItem" Namespace="SE.App2CommonProcess" x="300" y="400" />

  <!-- Interlock summary -->
  <FB ID="3" Name="ilckSum" Type="IlckCondSum" Namespace="SE.App2CommonProcess" x="700" y="300" />

  <!-- Motor CAT -->
  <FB ID="4" Name="pump" Type="Motor" Namespace="SE.App2CommonProcess" x="1200" y="350" />

  <EventConnections>
    <Connection Source="$INIT" Destination="$1.INIT" />
    <Connection Source="$1.INITO" Destination="$2.INIT" />
    <Connection Source="$2.INITO" Destination="$3.INIT" />
    <Connection Source="$3.INITO" Destination="$4.INIT" />
  </EventConnections>

  <DataConnections>
    <!-- Interlock conditions (TRUE = OK, FALSE = interlock active) -->
    <Connection Source="$OilPressureOK" Destination="$1.CondIn" />
    <Connection Source="$TempOK" Destination="$2.CondIn" />

    <!-- Chain interlocks -->
    <!-- Use IIlckCondSum adapter connections -->
  </DataConnections>
</FBNetwork>
```

---

## 3. PID Control Loop

Standard PID controller with auto/manual modes.

```xml
<FBNetwork>
  <!-- Analog Input for PV -->
  <FB ID="1" Name="pvInput" Type="AnalogInput" Namespace="SE.App2CommonProcess" x="300" y="350" />

  <!-- PID Controller -->
  <FB ID="2" Name="tempPID" Type="PID" Namespace="SE.App2CommonProcess" x="800" y="350" />

  <!-- Analog Output for MV -->
  <FB ID="3" Name="mvOutput" Type="AnalogOutput" Namespace="SE.App2CommonProcess" x="1300" y="350" />

  <EventConnections>
    <Connection Source="$INIT" Destination="$1.INIT" />
    <Connection Source="$1.INITO" Destination="$2.INIT" />
    <Connection Source="$2.INITO" Destination="$3.INIT" />

    <!-- Cyclic update -->
    <Connection Source="$1.UPD" Destination="$2.UPD" />
    <Connection Source="$2.UPD" Destination="$3.UPD" />
  </EventConnections>

  <DataConnections>
    <!-- PV from analog input -->
    <Connection Source="$1.Pv" Destination="$2.Pv" />

    <!-- Setpoint -->
    <Connection Source="$Setpoint" Destination="$2.Sp" />

    <!-- PID tuning -->
    <Connection Source="1.5" Destination="$2.Kp" />      <!-- Proportional gain -->
    <Connection Source="T#30s" Destination="$2.Ti" />   <!-- Integral time -->
    <Connection Source="T#5s" Destination="$2.Td" />    <!-- Derivative time -->

    <!-- Output limits -->
    <Connection Source="100.0" Destination="$2.OutMax" />
    <Connection Source="0.0" Destination="$2.OutMin" />

    <!-- MV to analog output -->
    <Connection Source="$2.Out" Destination="$3.Sp" />
  </DataConnections>
</FBNetwork>
```

---

## 4. Control Valve with Permissives

Control valve with permissive conditions.

```xml
<FBNetwork>
  <!-- Permissive condition items -->
  <FB ID="1" Name="permSystem" Type="permCondItem" Namespace="SE.App2CommonProcess" x="300" y="200" />
  <FB ID="2" Name="permPressure" Type="permCondItem" Namespace="SE.App2CommonProcess" x="300" y="400" />

  <!-- Permissive summary -->
  <FB ID="3" Name="permSum" Type="PermCondSum" Namespace="SE.App2CommonProcess" x="700" y="300" />

  <!-- Control Valve -->
  <FB ID="4" Name="controlValve" Type="ValveControl" Namespace="SE.App2CommonProcess" x="1200" y="350" />

  <EventConnections>
    <Connection Source="$INIT" Destination="$1.INIT" />
    <Connection Source="$1.INITO" Destination="$2.INIT" />
    <Connection Source="$2.INITO" Destination="$3.INIT" />
    <Connection Source="$3.INITO" Destination="$4.INIT" />
  </EventConnections>

  <DataConnections>
    <!-- Permissive conditions -->
    <Connection Source="$SystemReady" Destination="$1.CondIn" />
    <Connection Source="$PressureOK" Destination="$2.CondIn" />

    <!-- Valve position setpoint (from PID output) -->
    <Connection Source="$PositionSp" Destination="$4.Sp" />

    <!-- Feedback from valve -->
    <Connection Source="$ActualPosition" Destination="$4.Fb" />
  </DataConnections>
</FBNetwork>
```

---

## 5. Pump Set with Duty/Standby

Equipment module for pump management.

```xml
<FBNetwork>
  <!-- Pump Set (manages multiple pumps) -->
  <FB ID="1" Name="pumpSet" Type="PumpSet" Namespace="SE.App2CommonProcess" x="500" y="350" />

  <!-- Individual pump assets -->
  <FB ID="2" Name="pump1" Type="PumpAssets" Namespace="SE.App2CommonProcess" x="1000" y="200" />
  <FB ID="3" Name="pump2" Type="PumpAssets" Namespace="SE.App2CommonProcess" x="1000" y="500" />

  <!-- Actual motor CATs (connected to PumpAssets) -->
  <FB ID="4" Name="motor1" Type="Motor" Namespace="SE.App2CommonProcess" x="1500" y="200" />
  <FB ID="5" Name="motor2" Type="Motor" Namespace="SE.App2CommonProcess" x="1500" y="500" />

  <EventConnections>
    <Connection Source="$INIT" Destination="$1.INIT" />
    <Connection Source="$1.INITO" Destination="$2.INIT" />
    <Connection Source="$2.INITO" Destination="$3.INIT" />
    <!-- ... continue chain -->
  </EventConnections>

  <DataConnections>
    <!-- PumpSet configuration -->
    <Connection Source="2" Destination="$1.NrOfPumps" />

    <!-- Connect pump assets via IDevice adapter -->
    <!-- Use IPumpAsset adapter for asset connections -->
  </DataConnections>
</FBNetwork>
```

---

## 6. Digital I/O with Signal Delay

Digital input with on/off delay filtering.

```xml
<FBNetwork>
  <!-- Digital Input -->
  <FB ID="1" Name="limitSwitch" Type="DigitalInput" Namespace="SE.App2CommonProcess" x="500" y="350" />

  <!-- Signal Delay for debounce -->
  <FB ID="2" Name="delay" Type="SignalDelay" Namespace="SE.App2Base" x="1100" y="350" />

  <EventConnections>
    <Connection Source="$INIT" Destination="$1.INIT" />
    <Connection Source="$1.INITO" Destination="$2.INIT" />
    <Connection Source="$1.UPD" Destination="$2.UPD" />
  </EventConnections>

  <DataConnections>
    <!-- Raw input -->
    <Connection Source="$RawDigitalIn" Destination="$1.In" />

    <!-- Connect to delay -->
    <Connection Source="$1.Out" Destination="$2.In" />

    <!-- Delay times -->
    <Connection Source="T#500ms" Destination="$2.OnDelay" />
    <Connection Source="T#200ms" Destination="$2.OffDelay" />
  </DataConnections>
</FBNetwork>
```

---

## 7. Display Variables for HMI

Display real-time values on HMI.

```xml
<FBNetwork>
  <!-- Display Real Value -->
  <FB ID="1" Name="dispTemp" Type="DisplayReal" Namespace="SE.App2Base" x="500" y="200" />

  <!-- Display Integer -->
  <FB ID="2" Name="dispCount" Type="DisplayInt" Namespace="SE.App2Base" x="500" y="400" />

  <!-- Display Boolean -->
  <FB ID="3" Name="dispRunning" Type="DisplayBool" Namespace="SE.App2Base" x="500" y="600" />

  <EventConnections>
    <Connection Source="$INIT" Destination="$1.INIT" />
    <Connection Source="$1.INITO" Destination="$2.INIT" />
    <Connection Source="$2.INITO" Destination="$3.INIT" />

    <!-- Update all displays -->
    <Connection Source="$cycleTimer.EO" Destination="$1.UPD" />
    <Connection Source="$1.UPD" Destination="$2.UPD" />
    <Connection Source="$2.UPD" Destination="$3.UPD" />
  </EventConnections>

  <DataConnections>
    <Connection Source="$Temperature" Destination="$1.Value" />
    <Connection Source="$ProductCount" Destination="$2.Value" />
    <Connection Source="$MotorRunning" Destination="$3.Value" />
  </DataConnections>
</FBNetwork>
```

---

## 8. Setpoint Entry from HMI

Allow operator to enter setpoints.

```xml
<FBNetwork>
  <!-- Setpoint entry CATs -->
  <FB ID="1" Name="setTemp" Type="SetReal" Namespace="SE.App2Base" x="500" y="200" />
  <FB ID="2" Name="setSpeed" Type="SetInt" Namespace="SE.App2Base" x="500" y="400" />
  <FB ID="3" Name="setEnable" Type="SetBool" Namespace="SE.App2Base" x="500" y="600" />

  <EventConnections>
    <Connection Source="$INIT" Destination="$1.INIT" />
    <Connection Source="$1.INITO" Destination="$2.INIT" />
    <Connection Source="$2.INITO" Destination="$3.INIT" />
  </EventConnections>

  <DataConnections>
    <!-- Min/Max limits -->
    <Connection Source="0.0" Destination="$1.Min" />
    <Connection Source="100.0" Destination="$1.Max" />

    <Connection Source="0" Destination="$2.Min" />
    <Connection Source="1500" Destination="$2.Max" />

    <!-- Output values go to control logic -->
  </DataConnections>
</FBNetwork>
```

---

## 9. Mode Control

Mode selection (Auto/Manual/Program).

```xml
<FBNetwork>
  <!-- Mode CAT -->
  <FB ID="1" Name="modeCtl" Type="Mode" Namespace="SE.App2Base" x="500" y="350" />

  <!-- Owner CAT (for source selection) -->
  <FB ID="2" Name="ownerCtl" Type="Owner" Namespace="SE.App2Base" x="1100" y="350" />

  <EventConnections>
    <Connection Source="$INIT" Destination="$1.INIT" />
    <Connection Source="$1.INITO" Destination="$2.INIT" />
  </EventConnections>

  <DataConnections>
    <!-- Mode configuration -->
    <Connection Source="TRUE" Destination="$1.EnAuto" />
    <Connection Source="TRUE" Destination="$1.EnManual" />
    <Connection Source="TRUE" Destination="$1.EnProgram" />

    <!-- Owner configuration -->
    <Connection Source="$1.CurrentMode" Destination="$2.Mode" />
  </DataConnections>
</FBNetwork>
```

---

## 10. Failure Handling

Detect and summarize equipment failures.

```xml
<FBNetwork>
  <!-- Failure condition items -->
  <FB ID="1" Name="failOverload" Type="failCondItem" Namespace="SE.App2CommonProcess" x="300" y="200" />
  <FB ID="2" Name="failComm" Type="failCondItem" Namespace="SE.App2CommonProcess" x="300" y="400" />
  <FB ID="3" Name="failSensor" Type="failCondItem" Namespace="SE.App2CommonProcess" x="300" y="600" />

  <!-- Failure summary -->
  <FB ID="4" Name="failSum" Type="FailCondSum" Namespace="SE.App2CommonProcess" x="800" y="400" />

  <EventConnections>
    <Connection Source="$INIT" Destination="$1.INIT" />
    <Connection Source="$1.INITO" Destination="$2.INIT" />
    <Connection Source="$2.INITO" Destination="$3.INIT" />
    <Connection Source="$3.INITO" Destination="$4.INIT" />
  </EventConnections>

  <DataConnections>
    <!-- Failure conditions (TRUE = failure detected) -->
    <Connection Source="$OverloadTrip" Destination="$1.CondIn" />
    <Connection Source="$CommFail" Destination="$2.CondIn" />
    <Connection Source="$SensorFail" Destination="$3.CondIn" />

    <!-- Failure priority -->
    <Connection Source="1" Destination="$1.Priority" />
    <Connection Source="2" Destination="$2.Priority" />
    <Connection Source="3" Destination="$3.Priority" />

    <!-- Connect to FailCondSum via IFailCondSum adapter -->
  </DataConnections>
</FBNetwork>
```

---

## Key Integration Notes

### Adapter Connections

The SE libraries use adapters extensively for standardized connections:

```xml
<!-- Adapter socket (consumer) -->
<AdapterConnection Adapter="IDevice" SourceFB="$motorCtl" DestFB="$motor" />

<!-- Adapter plug (provider) -->
<AdapterConnection Adapter="IAnalog" SourceFB="$analogInput" DestFB="$pidController" />
```

### Status Propagation

All CATs provide `Status` output for signal quality:

```xml
<!-- Check status before using value -->
<Connection Source="$analogInput.Status" Destination="$qualityCheck.Status" />
```

### Owner/Mode Integration

Most device CATs support Owner/Mode control:

```xml
<!-- Connect Mode CAT to device -->
<Connection Source="$modeCtl.CurrentMode" Destination="$motor.Mode" />
<Connection Source="$ownerCtl.CurrentOwner" Destination="$motor.Owner" />
```
