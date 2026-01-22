# EAE Library Structure Reference

## Standard Library Organization

```
{LibraryName}/
├── General/                    # Library metadata
│   ├── ProjectInfo.xml         # Library name, version, namespace
│   └── Folders.xml             # Block categorization for toolbox
│
├── IEC61499/                   # Function block definitions
│   ├── {BlockName}/            # One folder per block
│   │   ├── {BlockName}.fbt     # Main function block
│   │   ├── {BlockName}_HMI.fbt # HMI service interface
│   │   ├── {BlockName}.cfg     # CAT configuration
│   │   ├── {BlockName}.doc.xml # Documentation
│   │   ├── {BlockName}_CAT.offline.xml
│   │   ├── {BlockName}_CAT.opcua.xml
│   │   ├── {BlockName}_HMI.offline.xml
│   │   ├── {BlockName}_HMI.opcua.xml
│   │   └── {BlockName}.meta.xml
│   └── Images/                 # Documentation images
│       └── {BlockName}/
│
├── HMI/                        # HMI implementations
│   └── {BlockName}/
│       ├── {BlockName}.def.cs
│       ├── {BlockName}.event.cs
│       ├── {BlockName}.Design.resx
│       ├── {BlockName}_sDefault.cnv.cs
│       ├── {BlockName}_sDefault.cnv.Designer.cs
│       ├── {BlockName}_sDefault.cnv.resx
│       └── {BlockName}_sDefault.cnv.xml
│
├── Languages/                  # Localization resources
│   └── {Language}.resx
│
├── AssetLinkData/              # Asset manifests (optional)
└── HwConfiguration/            # Hardware config (optional)
```

## Application Project Structure

```
{ProjectName}/
├── General/
│   ├── ProjectInfo.xml
│   └── Folders.xml
│
├── IEC61499/
│   ├── System/                 # System topology
│   │   ├── {SystemGUID}.system
│   │   ├── {SystemGUID}.cfg
│   │   └── {SystemGUID}/
│   │       ├── {AppGUID}.sysapp
│   │       ├── {DevGUID}.sysdev
│   │       └── {DevGUID}/
│   │           ├── {ResGUID}.sysres
│   │           └── {ResGUID}/
│   │               ├── offline.xml
│   │               └── opcua.xml
│   │
│   └── {ApplicationFBs}/       # Application-level FBs
│
├── HMI/                        # Application HMI
├── Topology/                   # Topology visualization
└── HwConfiguration/            # Hardware configuration
```

## Folders.xml Structure

```xml
<?xml version="1.0" encoding="utf-8"?>
<Folders xmlns="http://www.nxtcontrol.com/IEC61499.xsd">
  <FolderItem Type="Folder" Name="SignalProcessing">
    <FolderItem Type="Folder" Name="AnalogInput">
      <FolderItem Type="Link" Name="AnalogInput"
                  Target="IEC61499/AnalogInput/AnalogInput.cfg" />
      <FolderItem Type="Link" Name="AnalogInputBase"
                  Target="IEC61499/AnalogInputBase/AnalogInputBase.cfg" />
    </FolderItem>
  </FolderItem>
  <FolderItem Type="Folder" Name="Control">
    <FolderItem Type="Link" Name="Motor"
                Target="IEC61499/Motor/Motor.cfg" />
  </FolderItem>
</Folders>
```

## ProjectInfo.xml Structure

```xml
<?xml version="1.0" encoding="utf-8"?>
<Project xmlns="http://www.nxtcontrol.com/IEC61499.xsd">
  <Name>SE.ScadapackWWW</Name>
  <Version>1.0.0</Version>
  <Namespace>SE.ScadapackWWW</Namespace>
  <Type>Library</Type>
  <References>
    <Reference Name="SE.App2Base" Version="26.0" />
    <Reference Name="SE.App2CommonProcess" Version="26.0" />
  </References>
</Project>
```

## Block Hierarchy Pattern

Common pattern for process blocks:

```
BlockBase (SE.App2CommonProcess)
    ↓ (fork/extend)
BlockBaseExt (SE.ScadapackWWW)
    ↓ (compose)
Block (SE.ScadapackWWW)
```

Example:
- `AnalogInputBase` → `AnalogInputBaseExt` → `AnalogInput`
- `MotorBase` → `MotorBaseExt` → `Motor`
