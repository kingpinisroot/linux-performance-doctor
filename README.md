# Linux Performance Doctor

Linux Performance Doctor is a local, read-only Linux diagnostic CLI written in Python. It samples system state across several subsystems and reports measurements, limitations, and conservative findings in text or JSON.

## Safety and scope

The tool is designed to observe the host without changing it. It does not require `sudo`, make network or telemetry requests, read journals, query SMART data, or inspect process command-line arguments or environment variables. It reads from `/proc`, `/sys`, mount information, and performs a bounded `systemctl` query for failed service units. It does not apply fixes or take automatic action.

Missing or inaccessible measurements are reported as partial or unavailable. They are not treated as evidence that a subsystem is healthy.

## Install

Requires Linux and Python 3.10 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

This installs the `lpdoctor` and `linux-performance-doctor` commands.

## Usage

```bash
lpdoctor scan
lpdoctor scan --json
lpdoctor scan --interval 1
```

The interval must be between `0.1` and `10` seconds and defaults to `2` seconds. CPU and process counters are measured over one interval; I/O counters are sampled in a second, serial interval. A default scan therefore takes at least about four seconds, plus short reads.

The same commands are available through `python3 -m linux_performance_doctor.cli` when the package is on `PYTHONPATH`.

## Measurements and findings

Collectors cover CPU utilization and processes, memory and swap, filesystems and inodes, block-device I/O, temperature sensors, and failed systemd service units. The text and JSON reports include per-module status and limitations. JSON output includes a schema version, timestamp, measurements, and deterministic findings with evidence, explanation, suggestion, impact, and uncertainty.

Findings use conservative thresholds: CPU at 90%, memory usage at 95%, filesystem space or inode usage at 90%, and temperature at 90°C. Swap activity and failed systemd services are also reported. A short CPU sample does not establish sustained load; any unavailable or partial module is represented as unknown in the findings.

## Limitations

Short samples can miss spikes or capture temporary fluctuations. Process visibility, sensors, systemd, and filesystem information vary by permissions, containers, namespaces, and hardware. I/O values are counter deltas, not latency measurements; device and partition counters may overlap. The tool is a snapshot diagnostic, not continuous monitoring or a full root-cause analysis.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```

The tests use deterministic fixtures and mocks so they do not depend on live host readings.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
