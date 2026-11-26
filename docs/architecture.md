# Architecture Overview

> **Repository Status:** This document captures the verified architectural foundation of **Linux Performance Doctor** prior to importing and reviewing the existing CLI implementation. Module-level APIs, exact CLI options, and JSON schemas will be documented here once the existing codebase is added.

## Core Design Boundary: Diagnosis Only

Linux Performance Doctor is strictly a **read-only diagnostic tool**. It observes and correlates system state without modifying the host:

- Does **not** alter system configuration.
- Does **not** start, stop, or restart services.
- Does **not** modify or delete files or processes.
- Does **not** require privileged system modifications.
- Treats missing or inaccessible telemetry transparently.
- Reports partial results and collection limitations explicitly.

## Modular Collector Model

Rather than bundling all system checks into a monolithic script, diagnostics are organized into separate collectors per Linux subsystem:

- **CPU** — processor information and utilization
- **RAM** — memory usage and available capacity
- **Swap** — swap allocation and usage
- **Filesystems** — disk capacity and filesystem information
- **I/O** — block device and input/output activity
- **Sensors** — available temperature and hardware sensor readings
- **systemd** — state of system services
- **Processes** — running processes and notable resource consumers

## Structured Output

Collected telemetry is aggregated into structured diagnostic results, including machine-readable **JSON output** suitable for automation, scripting, and downstream analysis, alongside clear human-readable summaries.
