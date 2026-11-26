# Linux Performance Doctor

**Linux Performance Doctor** is a standalone, read-only Linux system diagnostic tool written in Python.

It is designed to inspect a Linux host systematically, correlate signals across multiple operating system subsystems, highlight potential performance issues and resource bottlenecks, and present findings in a clear, structured form—including machine-readable JSON output.

> **Repository Status:** This repository currently contains the clean **project skeleton** (`src/` layout, packaging metadata, CI workflow, documentation structure, and license) prepared as the publishing foundation for our existing Linux Performance Doctor CLI. The existing CLI source code has not yet been imported here; verified CLI commands, flags, and real JSON output examples will be added directly from the reviewed source code once it is brought in.

---

## Why Linux Performance Doctor Exists

Conventional system monitors typically show isolated, momentary snapshots—CPU percentages in one place, disk space in another, service health somewhere else. Diagnosing why a Linux system feels slow or constrained usually requires mentally piecing together signals across multiple commands and subsystems.

Linux Performance Doctor exists to bridge that gap:

- **Holistic System View:** Brings together multiple Linux diagnostic areas into a single structured assessment rather than dumping disconnected raw metrics.
- **Strict Separation of Diagnosis and Intervention:** Built to observe and explain what is happening on a host—never to alter it.
- **Automation-Ready Output:** Designed for both interactive inspection by administrators and structured consumption via JSON.

### What It Is Not

Linux Performance Doctor is **not** an automatic system optimizer, cleaner, or tuning script. It diagnoses and informs; it never decides on its own to change your system.

---

## Design & Safety Principles

Linux Performance Doctor is built around a strict **read-only architecture**:

- **No configuration changes** — never writes to or alters system configuration files.
- **No service control** — never starts, stops, or restarts system services.
- **No destructive actions** — never modifies or deletes files or processes.
- **No privileged interventions required** — designed to gather useful diagnostics without invasive operations.
- **Transparent handling of missing metrics** — missing or inaccessible readings are reported openly rather than hidden or guessed.
- **Explicit partial results** — limitations and incomplete checks are surfaced clearly so results remain trustworthy.

---

## Architecture & Diagnostic Scope

### Modular Diagnostic Collectors

Instead of a monolithic script, Linux Performance Doctor follows a modular collector architecture with separated collectors for distinct Linux subsystems:

| Subsystem | Diagnostic Scope |
| --- | --- |
| **CPU** | Utilization and processor information |
| **RAM** | Memory consumption and available capacity |
| **Swap** | Swap allocation and usage |
| **Filesystems** | Storage capacity and filesystem details |
| **I/O** | Block device and input/output activity |
| **Sensors** | Available temperature and hardware sensor readings |
| **systemd** | State of system services |
| **Processes** | Running processes and notable resource consumers |

### Structured & JSON Output

Diagnostic collectors feed into a unified, structured result model designed for:

- Clear, understandable summaries for Linux users, administrators, and technical operators.
- Machine-readable **JSON output** for automation, scripting, and repeatable checks.
- Explicit per-collector status reporting when a subsystem cannot be queried completely.

See [docs/architecture.md](docs/architecture.md) for the architectural overview.

---

## Implemented vs. Planned Status

To keep this repository transparent and accurate:

### Currently Implemented in This Repository (Skeleton Phase)

- Standard Python `src/` package layout (`src/linux_performance_doctor/`)
- Packaging configuration (`pyproject.toml`) targeting Linux and Python 3.10+
- Automated GitHub Actions test workflow (`.github/workflows/ci.yml`) across Python 3.10–3.13
- Minimal package import smoke test (`tests/test_package.py`)
- Architecture overview (`docs/architecture.md`), contribution guide (`CONTRIBUTING.md`), `.gitignore`, and MIT `LICENSE`

### Next Milestones (Pending Source Import & Review)

- Review and import the existing Linux Performance Doctor CLI modules and modular collectors into `src/linux_performance_doctor/`
- Wire the verified CLI entry point in `pyproject.toml` (`[project.scripts]`)
- Document exact CLI commands, flags, options, and real JSON output examples directly from the imported code
- Import and expand the full collector, CLI, and JSON serialization test suite in `tests/`

### Long-Term Project Vision

- Reliable, low-overhead diagnostic data collection across Linux environments
- Meaningful performance indicators that correlate subsystem bottlenecks
- Clean modular extensibility for additional diagnostic collectors
- Transparent partial-status and error reporting across restricted environments
- Smooth automation via stable CLI behavior and JSON output

---

## Requirements & Setup (Current Skeleton)

- **Operating System:** Linux
- **Python:** 3.10 or newer

Clone the repository and install the current skeleton in editable mode with development dependencies:

```bash
git clone https://github.com/kingpinisroot/linux-performance-doctor.git
cd linux-performance-doctor
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the current skeleton smoke test:

```bash
pytest -v
```

### CLI Usage & Examples

> **Pending source import:** The existing Linux Performance Doctor CLI code has not yet been imported into this repository skeleton. Exact CLI invocations, available flags, collector options, and verified JSON output examples will be added here once the existing codebase is reviewed and committed.

---

## Project Structure

```text
linux-performance-doctor/
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   └── architecture.md
├── src/
│   └── linux_performance_doctor/
│       └── __init__.py
├── tests/
│   └── test_package.py
├── .gitignore
├── CONTRIBUTING.md
├── LICENSE
├── pyproject.toml
└── README.md
```

---

## Contributing

Contributions are welcome once source integration is underway. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.
