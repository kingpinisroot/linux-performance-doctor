from __future__ import annotations
import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from . import __version__
from .collectors import (collect_cpu_and_processes, collect_memory,
                         collect_filesystems, collect_io, collect_sensors,
                         collect_failed_services, read_text)
from .diagnose import diagnose


def scan(interval=2.0):
    if platform.system() != "Linux":
        raise RuntimeError("Linux is required")
    proc = Path("/proc")
    before_vmstat = read_text(proc / "vmstat")
    memory = collect_memory(proc)
    # CPU and process sampling takes `interval`; I/O sampling follows it and
    # takes another `interval`, so the two counter windows are serial.
    cpu = collect_cpu_and_processes(proc, interval=interval)
    after_memory = collect_memory(proc)
    # Never surface boot-cumulative swap counters as if they were sample deltas.
    memory["swap_pages_in"] = None
    memory["swap_pages_out"] = None
    if before_vmstat is not None:
        try:
            old = {p[0]: int(p[1]) for line in before_vmstat.splitlines()
                   if len(p := line.split()) == 2 and p[0] in ("pswpin", "pswpout")}
            for key, counter in (("swap_pages_in", "pswpin"), ("swap_pages_out", "pswpout")):
                new_value = after_memory.get(key)
                if new_value is not None and counter in old:
                    memory[key] = max(0, new_value - old[counter])
        except (ValueError, KeyError):
            pass
    filesystems = collect_filesystems(proc)
    io = collect_io(proc, interval=interval)
    sensors = collect_sensors()
    services = collect_failed_services()
    memory_status = "ok" if memory["memory_used_percent"] is not None else "unavailable"
    memory_limits = [] if memory_status == "ok" else ["Memory availability could not be measured from /proc/meminfo"]
    if memory["swap_pages_in"] is None or memory["swap_pages_out"] is None:
        memory_status = "partial" if memory_status == "ok" else memory_status
        memory_limits.append("Swap activity deltas were unavailable; first-sample counters are never reported cumulatively")
    modules = {
        "cpu": {"status": "ok" if cpu["cpu_percent"] is not None else "unavailable",
                "limitations": [] if cpu["cpu_percent"] is not None else ["CPU counters were unavailable or invalid in one of the two samples"]},
        "processes": {"status": cpu["process_status"], "limitations": cpu["process_limitations"]},
        "memory_swap": {"status": memory_status, "limitations": memory_limits},
        "filesystems": {"status": filesystems["status"], "limitations": filesystems["limitations"]},
        "io": {"status": io["status"], "limitations": io["limitations"]},
        "sensors": {"status": sensors["status"], "limitations": sensors["limitations"]},
        "systemd_services": {"status": services["status"], "limitations": services["limitations"]},
    }
    data = {"schema_version": "1.1", "tool": {"name": "Linux Performance Doctor", "version": __version__},
            "generated_at": datetime.now(timezone.utc).isoformat(), "sample_interval_seconds": interval,
            "modules": modules, "cpu": cpu, "memory": memory, "filesystems": filesystems,
            "io": io, "sensors": sensors, "services": services}
    data["findings"] = diagnose(data)
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local, read-only Linux performance snapshot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan_parser = subparsers.add_parser("scan", help="collect metrics and deterministic findings")
    scan_parser.add_argument("--json", action="store_true", help="emit structured JSON")
    scan_parser.add_argument("--interval", type=float, default=2.0, help="each serial CPU and I/O sample window, seconds (default: 2)")
    args = parser.parse_args(argv)
    if not 0.1 <= args.interval <= 10:
        scan_parser.error("--interval must be between 0.1 and 10 seconds")
    try:
        data = scan(args.interval)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(f"Linux Performance Doctor {__version__} — {data['generated_at']}")
        print(f"Sample windows: CPU/process {data['cpu']['interval_seconds']} s, then I/O {data['io']['interval_seconds']} s")
        print(f"CPU: {data['cpu']['cpu_percent']}% busy")
        print("Top processes by CPU (one-core percent):")
        for p in data['cpu']['processes_by_cpu'][:5]:
            print(f"  {p['pid']:>7} {p['cpu_percent_one_core']:>6.1f}%  RSS {p['rss_bytes']} B  {p['name']}")
        print("Top processes by RSS:")
        for p in data['cpu']['processes_by_rss'][:5]:
            print(f"  {p['pid']:>7} {p['rss_bytes']:>12} B  {p['name']}")
        m = data['memory']
        print(f"Memory: {m['memory_used_percent']}% used; swap: {m['swap_used_percent']}% used; swap pages in/out: {m['swap_pages_in']}/{m['swap_pages_out']}")
        print("Filesystems:")
        for fs in data['filesystems']['filesystems']:
            print(f"  {fs['mountpoint']}: space {fs['used_percent']}%, inodes {fs['inodes_used_percent']}%")
        print(f"I/O devices: {len(data['io']['devices'] or []) if data['io']['devices'] is not None else 'unavailable'}")
        print(f"Sensors: {len(data['sensors']['sensors'])}; failed services: {len(data['services']['services']) if data['services']['services'] is not None else 'unavailable'}")
        print("Module status:")
        for name, module in data["modules"].items():
            print(f"  {name}: {module['status']}")
            for limitation in module["limitations"]:
                print(f"    limitation: {limitation}")
        print("Findings:")
        if not data["findings"]:
            print("  No configured thresholds were exceeded.")
        for finding in data["findings"]:
            print(f"  [{finding['severity'].upper()}] {finding['metric']} — evidence: {finding['evidence']}; threshold: {finding['threshold']}")
            print(f"    {finding['explanation']} Suggestion: {finding['suggestion']} Impact: {finding['impact']}")
            if finding["uncertainty"]:
                print(f"    Uncertainty: {finding['uncertainty']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
