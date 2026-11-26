# Architecture Overview

Linux Performance Doctor is a read-only Linux diagnostic CLI. The implementation separates system collection from deterministic diagnosis and presentation.

## Components

- `src/linux_performance_doctor/collectors.py` reads CPU and process counters, memory and swap data, filesystem capacity and inode usage, block-device counters, thermal sensors, and failed systemd service units. Collectors report `ok`, `partial`, or `unavailable` status with limitations when data is incomplete.
- `src/linux_performance_doctor/cli.py` validates the `scan` command and interval, coordinates serial CPU/process and I/O sampling windows, assembles the report, and renders text or JSON.
- `src/linux_performance_doctor/diagnose.py` applies deterministic thresholds to the collected values. Findings carry evidence, explanation, suggestion, impact, and uncertainty. Any non-`ok` module produces an `unknown` finding rather than a healthy result.

## Data sources and safety boundary

The CLI reads `/proc`, `/sys`, and mount information. It invokes `systemctl` with a fixed environment and bounded output to query failed service units. It does not read journals, process command-line arguments, or environment variables; it does not write system state, control services, make network requests, or apply remediation.

## Output and sampling

Reports include schema version `1.1`, generation time, module statuses and limitations, measurements, and findings. `--json` emits the structured report. CPU/process counters are sampled over the selected interval, followed by a separate I/O sampling interval. The two windows are serial rather than concurrent.

## Known limitations

Readings depend on host permissions and available kernel, hardware, mount, and systemd interfaces. Missing data remains explicit. Short samples can miss transient behavior; device counters are not latency measurements, and process visibility can be restricted by containers or namespaces. The tool is a snapshot aid, not continuous monitoring or a complete root-cause analysis.
