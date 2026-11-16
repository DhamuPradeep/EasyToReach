---
name: rea
description: Reverse engineer, decompile, and analyze web bundles, native binaries, and application packages using the REA (Reverse Engineer Anything) toolkit and MCP server. Triggers when analyzing compiled binaries, Electron/ASAR packages, WebAssembly, source maps, or client-side assets for debugging, architecture research, and security audits.
---

# REA (Reverse Engineer Anything) Analysis Workflow

The REA toolkit enables inspection and reverse engineering of compiled software, web applications, and native packages.

## Capabilities

- **Web / Frontend Apps**: Analyzes JavaScript bundles, routes, DOM components, source maps, network traces (HAR), and WebSocket/IPC channels.
- **Desktop & Native Binaries**: Inspects `.exe`, `.dll`, `.so`, Mach-O, and Electron ASAR packages.
- **Mobile & Managed Runtimes**: Decompiles Android APKs (via JADX), .NET assemblies, WebAssembly (WASM), and Flutter assets.
- **Local MCP Integration**: Leverages the local REA MCP server (`rea-agents`) to execute decompilation and query symbols, routes, and call trees.

## Standard Workflow

### 1. Identify Target Format
Determine target type and asset structure:
- **Web Applications**: Look for production JS bundles, bundle manifests, source maps (`.map`), and API endpoints.
- **Electron Apps**: Extract and analyze `app.asar` files.
- **Native Binaries**: Identify architecture, symbols, and dependencies using local disassembly tools (Ghidra, Hopper, or IDA via REA).
- **APKs / Bytecode**: Decompile bytecode and manifests to extract package structure and logic.

### 2. Analysis & Extraction
Use REA MCP tools or CLI commands to inspect components:
- Extract and format bundled scripts or decompile classes.
- Map out internal data contracts, schemas, and state management logic.
- Trace network calls, payload structures, and communication protocols.

### 3. Architecture & Reconstruction
When reconstructing or interoperating with analyzed software:
- Document component hierarchies, interface definitions, and state flow.
- Implement clean-room, standards-compliant equivalents for required features and interfaces.
- Validate functionality against original protocol specifications and data contracts.

## Verification
- Verify that analyzed assets produce readable pseudocode/source representations.
- Test newly implemented clean-room components against mock data or target interfaces.

