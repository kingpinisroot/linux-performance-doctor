# Contributing to Linux Performance Doctor

Thank you for your interest in contributing to **Linux Performance Doctor**.

This repository currently holds the foundational project skeleton ahead of importing and reviewing the existing CLI codebase. All contributions must preserve the project's core diagnostic principles.

## Core Design Rules

Linux Performance Doctor is strictly a **read-only Linux diagnostic tool**, not an optimizer, cleaner, or tuning script. Every change must adhere to these boundaries:

1. **Strict Read-Only Behavior:** Never modify system configuration, start/stop services, kill or alter processes, or write/delete user or system files outside explicitly requested diagnostic output.
2. **No Privileged Mutations:** Diagnostics must not assume root-level interventions or make invasive system changes.
3. **Transparent Partial Results:** When metrics, sensors, or subsystems are unavailable or lack permissions on a host, collectors must degrade gracefully and surface the limitation clearly rather than failing silently or fabricating values.
4. **Modular Collector Separation:** Keep subsystem logic (CPU, RAM, Swap, Filesystems, I/O, Sensors, `systemd`, Processes) cleanly separated into independent collectors with structured output, including machine-readable JSON.
5. **Verified Documentation:** Document only implemented commands, flags, collectors, and test results. Distinguish clearly between implemented capabilities and future roadmap items.

## Local Development Setup

```bash
git clone https://github.com/kingpinisroot/linux-performance-doctor.git
cd linux-performance-doctor
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the test suite:

```bash
pytest -v
```

## Submitting Changes

1. Create a focused feature or fix branch from `main`.
2. Add or update unit tests covering your changes (using mocked/deterministic system fixtures where Linux host state varies).
3. Ensure `pytest -v` passes locally and CI passes on your pull request.
4. Open a pull request describing what changed, why, and any limitations or platform assumptions.
