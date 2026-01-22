#!/usr/bin/env python3
"""
Generate HMI stub files for a forked EAE block.

This script creates the basic C# stub files needed for HMI implementation
with correct namespace patterns.

Usage:
    python generate_hmi_stubs.py <block_name> <target_namespace> [--project-path PATH]

Example:
    python generate_hmi_stubs.py AnalogInput SE.ScadapackWWW
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional


def find_project_path() -> Optional[Path]:
    """Find EAE project path from current directory."""
    cwd = Path.cwd()

    for parent in [cwd] + list(cwd.parents):
        if (parent / "IEC61499").exists():
            return parent
        eaproj = list(parent.glob("*.eaproj"))
        if eaproj:
            return parent

    return None


def generate_def_cs(block_name: str, namespace: str) -> str:
    """Generate the .def.cs file content."""
    return f'''// Auto-generated HMI definition file for {block_name}
// Namespace: {namespace}

namespace {namespace}.Faceplates.{block_name}
{{
    /// <summary>
    /// Default faceplate for {block_name}
    /// </summary>
    partial class fpDefault
    {{
        // Faceplate implementation
    }}

    /// <summary>
    /// Parameter faceplate for {block_name}
    /// </summary>
    partial class fpParameter
    {{
        // Parameter faceplate implementation
    }}
}}

namespace {namespace}.Symbols.{block_name}
{{
    /// <summary>
    /// Default symbol for {block_name}
    /// </summary>
    partial class sDefault
    {{
        // Symbol implementation
    }}

    /// <summary>
    /// Vertical symbol for {block_name}
    /// </summary>
    partial class sVertical
    {{
        // Symbol implementation
    }}

    /// <summary>
    /// Display PV symbol for {block_name}
    /// </summary>
    partial class sDisplayPv
    {{
        // Symbol implementation
    }}

    /// <summary>
    /// Instance name symbol for {block_name}
    /// </summary>
    partial class sInstanceName
    {{
        // Symbol implementation
    }}
}}
'''


def generate_event_cs(block_name: str, namespace: str) -> str:
    """Generate the .event.cs file content."""
    return f'''// Auto-generated HMI event file for {block_name}
// Namespace: {namespace}

namespace {namespace}.Symbols.{block_name}
{{
    partial class sDefault
    {{
        /// <summary>
        /// Handle symbol click event
        /// </summary>
        partial void OnSymbolClick()
        {{
            // Navigate to faceplate or handle click
        }}
    }}
}}

namespace {namespace}.Faceplates.{block_name}
{{
    partial class fpDefault
    {{
        /// <summary>
        /// Initialize faceplate
        /// </summary>
        partial void OnInitialize()
        {{
            // Initialization logic
        }}
    }}
}}
'''


def generate_symbol_cnv_cs(block_name: str, namespace: str, symbol_name: str) -> str:
    """Generate a symbol .cnv.cs file content."""
    class_name = f"s{symbol_name}"
    return f'''// Auto-generated symbol implementation for {block_name}
// Symbol: {class_name}
// Namespace: {namespace}

using System;
using System.Windows.Forms;

namespace {namespace}.Symbols.{block_name}
{{
    /// <summary>
    /// {symbol_name} symbol implementation for {block_name}
    /// </summary>
    public partial class {class_name} : UserControl
    {{
        public {class_name}()
        {{
            InitializeComponent();
        }}

        /// <summary>
        /// Update symbol display based on current values
        /// </summary>
        public void UpdateDisplay()
        {{
            // Symbol update logic
        }}

        /// <summary>
        /// Handle symbol interaction
        /// </summary>
        protected virtual void OnInteraction()
        {{
            // Open faceplate or handle interaction
        }}
    }}
}}
'''


def generate_symbol_designer_cs(block_name: str, namespace: str, symbol_name: str) -> str:
    """Generate a symbol .cnv.Designer.cs file content."""
    class_name = f"s{symbol_name}"
    return f'''// Auto-generated designer file for {block_name} symbol
// Symbol: {class_name}

namespace {namespace}.Symbols.{block_name}
{{
    partial class {class_name}
    {{
        private System.ComponentModel.IContainer components = null;

        protected override void Dispose(bool disposing)
        {{
            if (disposing && (components != null))
            {{
                components.Dispose();
            }}
            base.Dispose(disposing);
        }}

        private void InitializeComponent()
        {{
            this.SuspendLayout();
            //
            // {class_name}
            //
            this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 13F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.Name = "{class_name}";
            this.Size = new System.Drawing.Size(100, 50);
            this.ResumeLayout(false);
        }}
    }}
}}
'''


def generate_symbol_resx(block_name: str, namespace: str, symbol_name: str) -> str:
    """Generate a symbol .cnv.resx file content."""
    return '''<?xml version="1.0" encoding="utf-8"?>
<root>
  <xsd:schema id="root" xmlns="" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:msdata="urn:schemas-microsoft-com:xml-msdata">
    <xsd:element name="root" msdata:IsDataSet="true">
      <xsd:complexType>
        <xsd:choice maxOccurs="unbounded">
          <xsd:element name="metadata">
            <xsd:complexType>
              <xsd:sequence>
                <xsd:element name="value" type="xsd:string" minOccurs="0" />
              </xsd:sequence>
              <xsd:attribute name="name" use="required" type="xsd:string" />
              <xsd:attribute name="type" type="xsd:string" />
              <xsd:attribute name="mimetype" type="xsd:string" />
            </xsd:complexType>
          </xsd:element>
          <xsd:element name="data">
            <xsd:complexType>
              <xsd:sequence>
                <xsd:element name="value" type="xsd:string" minOccurs="0" msdata:Ordinal="1" />
                <xsd:element name="comment" type="xsd:string" minOccurs="0" msdata:Ordinal="2" />
              </xsd:sequence>
              <xsd:attribute name="name" type="xsd:string" use="required" />
              <xsd:attribute name="type" type="xsd:string" />
              <xsd:attribute name="mimetype" type="xsd:string" />
            </xsd:complexType>
          </xsd:element>
        </xsd:choice>
      </xsd:complexType>
    </xsd:element>
  </xsd:schema>
  <resheader name="resmimetype">
    <value>text/microsoft-resx</value>
  </resheader>
  <resheader name="version">
    <value>2.0</value>
  </resheader>
  <resheader name="reader">
    <value>System.Resources.ResXResourceReader, System.Windows.Forms</value>
  </resheader>
  <resheader name="writer">
    <value>System.Resources.ResXResourceWriter, System.Windows.Forms</value>
  </resheader>
</root>
'''


def generate_hmi_stubs(project_path: Path, block_name: str, namespace: str,
                       symbols: Optional[List[str]] = None, dry_run: bool = False) -> List[str]:
    """Generate HMI stub files for a forked block."""

    if symbols is None:
        symbols = ["Default", "Vertical", "DisplayPv", "InstanceName"]

    hmi_path = project_path / namespace / "HMI" / block_name
    files_created = []

    if not dry_run:
        hmi_path.mkdir(parents=True, exist_ok=True)

    # Generate .def.cs
    def_file = hmi_path / f"{block_name}.def.cs"
    if not dry_run:
        def_file.write_text(generate_def_cs(block_name, namespace), encoding="utf-8")
    files_created.append(str(def_file))

    # Generate .event.cs
    event_file = hmi_path / f"{block_name}.event.cs"
    if not dry_run:
        event_file.write_text(generate_event_cs(block_name, namespace), encoding="utf-8")
    files_created.append(str(event_file))

    # Generate symbol files
    for symbol in symbols:
        # .cnv.cs
        cnv_file = hmi_path / f"{block_name}_s{symbol}.cnv.cs"
        if not dry_run:
            cnv_file.write_text(generate_symbol_cnv_cs(block_name, namespace, symbol), encoding="utf-8")
        files_created.append(str(cnv_file))

        # .cnv.Designer.cs
        designer_file = hmi_path / f"{block_name}_s{symbol}.cnv.Designer.cs"
        if not dry_run:
            designer_file.write_text(generate_symbol_designer_cs(block_name, namespace, symbol), encoding="utf-8")
        files_created.append(str(designer_file))

        # .cnv.resx
        resx_file = hmi_path / f"{block_name}_s{symbol}.cnv.resx"
        if not dry_run:
            resx_file.write_text(generate_symbol_resx(block_name, namespace, symbol), encoding="utf-8")
        files_created.append(str(resx_file))

    return files_created


def main():
    parser = argparse.ArgumentParser(
        description="Generate HMI stub files for a forked EAE block"
    )
    parser.add_argument("block_name", help="Block name (e.g., AnalogInput)")
    parser.add_argument("target_namespace", help="Target namespace (e.g., SE.ScadapackWWW)")
    parser.add_argument("--project-path", "-p", help="Project path (auto-detected if not specified)")
    parser.add_argument("--symbols", "-s", nargs="+",
                        help="Symbol names to generate (default: Default, Vertical, DisplayPv, InstanceName)")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Show what would be created without making changes")

    args = parser.parse_args()

    # Find project path
    if args.project_path:
        project_path = Path(args.project_path)
    else:
        project_path = find_project_path()
        if not project_path:
            print("Error: Could not find EAE project. Specify --project-path", file=sys.stderr)
            sys.exit(1)

    if args.dry_run:
        print("\n[DRY RUN - No files will be created]\n")

    print(f"Project: {project_path}")
    print(f"Block: {args.block_name}")
    print(f"Namespace: {args.target_namespace}")
    print()

    files = generate_hmi_stubs(
        project_path=project_path,
        block_name=args.block_name,
        namespace=args.target_namespace,
        symbols=args.symbols,
        dry_run=args.dry_run
    )

    print(f"HMI stub files {'would be' if args.dry_run else ''} created ({len(files)} files):")
    for f in files:
        print(f"  {f}")


if __name__ == "__main__":
    main()
