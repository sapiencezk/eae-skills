# EAE Common Rules Reference

Rules that apply to ALL block types in EAE.

## ID Generation

### FBType/AdapterType GUID

Every FBType (Basic, Composite, CAT, Service) and AdapterType needs a GUID:

```powershell
[guid]::NewGuid()
# → 5c6df59a-e6a9-4737-9939-6d0abd951850
```

**Exception:** DataType does NOT have a GUID attribute.

### Event/VarDeclaration Hex IDs

Events and VarDeclarations require 16-character uppercase hex IDs:

```powershell
[guid]::NewGuid().ToString("N").Substring(0,16).ToUpper()
# → A33F1B2C3D4E5F60
```

Example:
```xml
<Event ID="2688631B7786B1C6" Name="INIT" Comment="..." >
<VarDeclaration ID="ACEA15B429BDF455" Name="QI" Type="BOOL" />
```

---

## DOCTYPE and DTD References

| Block Type | DOCTYPE |
|------------|---------|
| Basic FB | `<!DOCTYPE FBType SYSTEM "../LibraryElement.dtd">` |
| Composite FB | `<!DOCTYPE FBType SYSTEM "../LibraryElement.dtd">` |
| CAT FB | `<!DOCTYPE FBType SYSTEM "../LibraryElement.dtd">` |
| Service FB (_HMI) | `<!DOCTYPE FBType SYSTEM "../LibraryElement.dtd">` |
| Adapter | `<!DOCTYPE AdapterType SYSTEM "../LibraryElement.dtd">` |
| **DataType** | `<!DOCTYPE DataType SYSTEM "../DataType.dtd">` |

**Important:** DataType uses `DataType.dtd`, all others use `LibraryElement.dtd`.

---

## Identification Standards

| Block Type | Standard | Element |
|------------|----------|---------|
| Basic/Composite/CAT/Service FB | IEC 61499-2 | `<Identification Standard="61499-2" />` |
| **Adapter** | IEC 61499-1 | `<Identification Standard="61499-1" />` |
| **DataType** | IEC 61131-3 | `<Identification Standard="1131-3" />` |

---

## Format Attribute

| Block Type | Has `Format="2.0"`? |
|------------|---------------------|
| Composite FB | **Yes** |
| CAT FB | **Yes** |
| Basic FB | No |
| Adapter | No |
| Service (_HMI) | No |
| DataType | No |

---

## Critical Errors to Avoid

### NO xmlns on root element

```xml
<!-- WRONG - causes load error -->
<FBType xmlns="http://..." Name="MyBlock">

<!-- CORRECT -->
<FBType Name="MyBlock" GUID="..." ...>
```

Error message: `<FBType xmlns=...> was not expected`

### File extensions and locations

| Type | Extension | Location |
|------|-----------|----------|
| Basic/Composite FB | `.fbt` | `IEC61499/` |
| Adapter | `.adp` | `IEC61499/` |
| DataType | `.dt` | `IEC61499/DataType/` |
| CAT | `.cfg` + `.fbt` | `IEC61499/{Name}/` |

---

## dfbproj Registration

Every block must be registered in the library's `.dfbproj` file.

### Basic FB

```xml
<ItemGroup>
  <None Include="BlockName.doc.xml">
    <DependentUpon>BlockName.fbt</DependentUpon>
  </None>
  <None Include="BlockName.meta.xml">
    <DependentUpon>BlockName.fbt</DependentUpon>
  </None>
</ItemGroup>
<ItemGroup>
  <Compile Include="BlockName.fbt">
    <IEC61499Type>Basic</IEC61499Type>
  </Compile>
</ItemGroup>
```

### Composite FB

```xml
<ItemGroup>
  <None Include="BlockName.doc.xml">
    <DependentUpon>BlockName.fbt</DependentUpon>
  </None>
  <None Include="BlockName.meta.xml">
    <DependentUpon>BlockName.fbt</DependentUpon>
  </None>
  <None Include="BlockName.composite.offline.xml">
    <DependentUpon>BlockName.fbt</DependentUpon>
  </None>
</ItemGroup>
<ItemGroup>
  <Compile Include="BlockName.fbt">
    <IEC61499Type>Composite</IEC61499Type>
  </Compile>
</ItemGroup>
```

### Adapter

```xml
<ItemGroup>
  <None Include="AdapterName.doc.xml">
    <DependentUpon>AdapterName.adp</DependentUpon>
  </None>
</ItemGroup>
<ItemGroup>
  <Compile Include="AdapterName.adp">
    <IEC61499Type>Adapter</IEC61499Type>
  </Compile>
</ItemGroup>
```

### DataType

```xml
<ItemGroup>
  <None Include="DataType\TypeName.doc.xml">
    <DependentUpon>TypeName.dt</DependentUpon>
  </None>
</ItemGroup>
<ItemGroup>
  <Compile Include="DataType\TypeName.dt">
    <IEC61499Type>DataType</IEC61499Type>
  </Compile>
</ItemGroup>
```

### CAT Block

See [eae-cat SKILL.md](../../eae-cat/SKILL.md) for full registration pattern.

---

## IEC61499Type Values

| Block Type | IEC61499Type |
|------------|--------------|
| Basic FB | `Basic` |
| Composite FB | `Composite` |
| Adapter | `Adapter` |
| DataType | `DataType` |
| CAT | `CAT` |
| CAT HMI | `CAT` with `<Usage>Private</Usage>` |

---

## Files Generated Per Block Type

| Type | Files |
|------|-------|
| Basic FB | `.fbt`, `.doc.xml`, `.meta.xml` |
| Composite FB | `.fbt`, `.doc.xml`, `.meta.xml`, `.composite.offline.xml` |
| Adapter | `.adp`, `.doc.xml` |
| DataType | `.dt`, `.doc.xml` |
| CAT | Many files - see eae-cat skill |

---

## Documentation File Template (.doc.xml)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<section xmlns="http://docbook.org/ns/docbook"
         xmlns:xi="http://www.w3.org/2001/XInclude"
         xmlns:xlink="http://www.w3.org/1999/xlink">
  <info>
    <author>
      <personname>
        <firstname>{FirstName}</firstname>
        <surname>{LastName}</surname>
      </personname>
      <email>{email}</email>
    </author>
    <abstract>
      <para>{Summary}</para>
    </abstract>
  </info>
  <para></para>
</section>
```

---

## Metadata File Template (.meta.xml)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<MetaData xmlns="http://www.2ingis.com/Schema/61499/IEC61499Meta">
</MetaData>
```
