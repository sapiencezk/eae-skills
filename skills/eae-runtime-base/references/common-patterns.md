# Runtime.Base Common Patterns

Practical usage patterns for Runtime.Base function blocks.

---

## 1. Cyclic Execution Patterns

### Basic Cyclic Task

Execute a function block every 100ms:

```xml
<FB ID="1" Name="timer" Type="E_CYCLE" Namespace="Runtime.Base" x="500" y="350" />
<FB ID="2" Name="myTask" Type="MyTaskFB" Namespace="MyLib" x="900" y="350" />

<EventConnections>
  <Connection Source="$INIT" Destination="$1.START" />
  <Connection Source="$1.EO" Destination="$2.REQ" />
</EventConnections>

<DataConnections>
  <Connection Source="T#100ms" Destination="$1.DT" />
</DataConnections>
```

### High-Resolution Cyclic with Phase

For precise timing with phase synchronization:

```xml
<FB ID="1" Name="hrTimer" Type="E_HRCYCLE" Namespace="Runtime.Base" x="500" y="350" />

<DataConnections>
  <Connection Source="T#10ms" Destination="$1.DT" />
  <Connection Source="T#0ms" Destination="$1.PHASE" />
</DataConnections>
```

---

## 2. Event Synchronization Patterns

### Wait for Two Sources (Rendezvous)

Synchronize two independent event sources before continuing:

```xml
<FB ID="1" Name="source1" Type="DataReader" x="500" y="200" />
<FB ID="2" Name="source2" Type="ConfigLoader" x="500" y="500" />
<FB ID="3" Name="sync" Type="E_REND" Namespace="Runtime.Base" x="900" y="350" />
<FB ID="4" Name="process" Type="Processor" x="1300" y="350" />

<EventConnections>
  <Connection Source="$1.CNF" Destination="$3.EI1" />
  <Connection Source="$2.CNF" Destination="$3.EI2" />
  <Connection Source="$3.EO" Destination="$4.REQ" />
</EventConnections>
```

### Sequential Chain with E_SPLIT

Fan out one event to multiple targets:

```xml
<FB ID="1" Name="split" Type="E_SPLIT" Namespace="Runtime.Base" x="500" y="350" />

<EventConnections>
  <Connection Source="$INIT" Destination="$1.EI" />
  <Connection Source="$1.EO1" Destination="$target1.REQ" />
  <Connection Source="$1.EO2" Destination="$target2.REQ" />
</EventConnections>
```

---

## 3. Conditional Routing Patterns

### Boolean Event Switch

Route events based on a condition:

```xml
<FB ID="1" Name="switch" Type="E_SWITCH" Namespace="Runtime.Base" x="500" y="350" />

<EventConnections>
  <Connection Source="$trigger" Destination="$1.EI" />
  <Connection Source="$1.EO0" Destination="$normalPath.REQ" />  <!-- G=FALSE -->
  <Connection Source="$1.EO1" Destination="$errorPath.REQ" />   <!-- G=TRUE -->
</EventConnections>

<DataConnections>
  <Connection Source="$isError" Destination="$1.G" />
</DataConnections>
```

### Event Gating with E_PERMIT

Only allow events when enabled:

```xml
<FB ID="1" Name="gate" Type="E_PERMIT" Namespace="Runtime.Base" x="500" y="350" />

<EventConnections>
  <Connection Source="$input.CNF" Destination="$1.EI" />
  <Connection Source="$1.EO" Destination="$output.REQ" />
</EventConnections>

<DataConnections>
  <Connection Source="$enabled" Destination="$1.PERMIT" />
</DataConnections>
```

### Multi-Way Demux

Route to one of N outputs based on index:

```xml
<FB ID="1" Name="demux" Type="E_DEMUX" Namespace="Runtime.Base" x="500" y="350" />

<EventConnections>
  <Connection Source="$input.CNF" Destination="$1.EI" />
  <Connection Source="$1.EO0" Destination="$handler0.REQ" />
  <Connection Source="$1.EO1" Destination="$handler1.REQ" />
  <Connection Source="$1.EO2" Destination="$handler2.REQ" />
</EventConnections>

<DataConnections>
  <Connection Source="$routeIndex" Destination="$1.K" />
</DataConnections>
```

---

## 4. Edge Detection Patterns

### Rising Edge Trigger

Detect when a boolean goes from FALSE to TRUE:

```xml
<FB ID="1" Name="risingEdge" Type="E_R_TRIG" Namespace="Runtime.Base" x="500" y="350" />

<EventConnections>
  <Connection Source="$cycle.EO" Destination="$1.EI" />
  <Connection Source="$1.EO" Destination="$action.REQ" />
</EventConnections>

<DataConnections>
  <Connection Source="$buttonPressed" Destination="$1.QI" />
</DataConnections>
```

### Falling Edge Trigger

Detect when a boolean goes from TRUE to FALSE:

```xml
<FB ID="1" Name="fallingEdge" Type="E_F_TRIG" Namespace="Runtime.Base" x="500" y="350" />

<EventConnections>
  <Connection Source="$cycle.EO" Destination="$1.EI" />
  <Connection Source="$1.EO" Destination="$releaseAction.REQ" />
</EventConnections>

<DataConnections>
  <Connection Source="$buttonPressed" Destination="$1.QI" />
</DataConnections>
```

---

## 5. Timer Patterns

### One-Shot Delay

Execute action after delay:

```xml
<FB ID="1" Name="delay" Type="E_DELAY" Namespace="Runtime.Base" x="500" y="350" />

<EventConnections>
  <Connection Source="$trigger.CNF" Destination="$1.START" />
  <Connection Source="$1.EO" Destination="$delayedAction.REQ" />
</EventConnections>

<DataConnections>
  <Connection Source="T#5s" Destination="$1.DT" />
</DataConnections>
```

### Retriggerable Timeout (Watchdog)

Reset timer on each input, fire if no input for duration:

```xml
<FB ID="1" Name="watchdog" Type="E_DELAYR" Namespace="Runtime.Base" x="500" y="350" />

<EventConnections>
  <Connection Source="$heartbeat.CNF" Destination="$1.START" />
  <Connection Source="$1.EO" Destination="$timeout.REQ" />
</EventConnections>

<DataConnections>
  <Connection Source="T#10s" Destination="$1.DT" />
</DataConnections>
```

### Event Burst (Train)

Generate N events at regular intervals:

```xml
<FB ID="1" Name="burst" Type="E_TRAIN" Namespace="Runtime.Base" x="500" y="350" />

<EventConnections>
  <Connection Source="$trigger.CNF" Destination="$1.START" />
  <Connection Source="$1.EO" Destination="$pulseAction.REQ" />
</EventConnections>

<DataConnections>
  <Connection Source="T#100ms" Destination="$1.DT" />  <!-- interval -->
  <Connection Source="5" Destination="$1.N" />          <!-- count -->
</DataConnections>
```

---

## 6. MQTT Communication Pattern

### Complete MQTT Setup

```xml
<!-- Connection block -->
<FB ID="1" Name="mqttConn" Type="MQTT_CONNECTION" Namespace="Runtime.Base" x="500" y="350" />

<!-- Publish block -->
<FB ID="2" Name="mqttPub" Type="MQTT_PUBLISH" Namespace="Runtime.Base" x="900" y="200" />

<!-- Subscribe block -->
<FB ID="3" Name="mqttSub" Type="MQTT_SUBSCRIBE" Namespace="Runtime.Base" x="900" y="500" />

<EventConnections>
  <!-- Initialize connection first -->
  <Connection Source="$INIT" Destination="$1.INIT" />
  <Connection Source="$1.INITO" Destination="$1.CONNECT" />

  <!-- Then initialize pub/sub -->
  <Connection Source="$1.CONNECTO" Destination="$2.INIT" />
  <Connection Source="$1.CONNECTO" Destination="$3.INIT" />

  <!-- Publishing -->
  <Connection Source="$dataReady.CNF" Destination="$2.PUBLISH1" />

  <!-- Receiving -->
  <Connection Source="$3.IND1" Destination="$processMsg.REQ" />
</EventConnections>

<DataConnections>
  <!-- Connection config -->
  <Connection Source="TRUE" Destination="$1.QI" />
  <Connection Source="'mqtt://broker.example.com:1883'" Destination="$1.ServerURI" />
  <Connection Source="'myClientId'" Destination="$1.ClientID" />

  <!-- Publish config -->
  <Connection Source="'mqttConn'" Destination="$2.ConnectionID" />
  <Connection Source="'sensors/'" Destination="$2.RootPath" />
  <Connection Source="'temperature'" Destination="$2.Topic1" />
  <Connection Source="$tempValue" Destination="$2.Payload1" />
  <Connection Source="1" Destination="$2.QoS1" />  <!-- at least once -->

  <!-- Subscribe config -->
  <Connection Source="'mqttConn'" Destination="$3.ConnectionID" />
  <Connection Source="'commands/#'" Destination="$3.Topic1" />
</DataConnections>
```

---

## 7. Latch/Memory Patterns

### Set-Reset Latch (Set Dominant)

```xml
<FB ID="1" Name="latch" Type="E_SR" Namespace="Runtime.Base" x="500" y="350" />

<EventConnections>
  <Connection Source="$setTrigger.CNF" Destination="$1.S" />
  <Connection Source="$resetTrigger.CNF" Destination="$1.R" />
  <Connection Source="$1.EO" Destination="$updateDisplay.REQ" />
</EventConnections>

<!-- Q output holds the latch state -->
```

### Up Counter with Preset

```xml
<FB ID="1" Name="counter" Type="E_CTU" Namespace="Runtime.Base" x="500" y="350" />

<EventConnections>
  <Connection Source="$pulse.EO" Destination="$1.CU" />
  <Connection Source="$reset.CNF" Destination="$1.R" />
  <Connection Source="$1.CUO" Destination="$checkLimit.REQ" />
</EventConnections>

<DataConnections>
  <Connection Source="100" Destination="$1.PV" />  <!-- preset value -->
  <!-- CV = current count, Q = TRUE when CV >= PV -->
</DataConnections>
```

---

## 8. Data Handling Patterns

### Type Conversion

Convert any type to another:

```xml
<FB ID="1" Name="convert" Type="ANY2ANY" Namespace="Runtime.Base" x="500" y="350" />

<DataConnections>
  <Connection Source="$intValue" Destination="$1.IN" />
  <!-- OUT contains converted value -->
</DataConnections>
```

### Value Formatting

Format numeric value to string:

```xml
<FB ID="1" Name="format" Type="VALFORMAT" Namespace="Runtime.Base" x="500" y="350" />

<DataConnections>
  <Connection Source="$temperature" Destination="$1.VALUE" />
  <Connection Source="'%.2f'" Destination="$1.FORMAT" />
  <!-- OUT = formatted string like "23.45" -->
</DataConnections>
```

---

## 9. Initialization Pattern

Standard initialization sequence:

```xml
<!-- Input receives INIT from composite interface -->
<Input Name="INIT" x="100" y="200" Type="Event" />

<!-- Chain initialization through blocks -->
<EventConnections>
  <Connection Source="$INIT" Destination="$config.INIT" />
  <Connection Source="$config.INITO" Destination="$comms.INIT" />
  <Connection Source="$comms.INITO" Destination="$timer.START" />
  <Connection Source="$timer.EO" Destination="$mainLoop.REQ" />
</EventConnections>

<!-- Output INITO when ready -->
<Output Name="INITO" x="1700" y="200" Type="Event" />
<EventConnections>
  <Connection Source="$comms.INITO" Destination="$INITO" />
</EventConnections>
```

---

## 10. Error Handling Pattern

Route errors to handler:

```xml
<FB ID="1" Name="errorSwitch" Type="E_SWITCH" Namespace="Runtime.Base" x="900" y="350" />

<EventConnections>
  <Connection Source="$operation.CNF" Destination="$1.EI" />
  <Connection Source="$1.EO0" Destination="$success.REQ" />
  <Connection Source="$1.EO1" Destination="$errorHandler.REQ" />
</EventConnections>

<DataConnections>
  <!-- Route to EO1 if error flag is set -->
  <Connection Source="$operation.Error" Destination="$1.G" />
</DataConnections>
```
