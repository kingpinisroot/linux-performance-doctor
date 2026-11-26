"""Read-only Linux metric collectors. All paths are injectable for fixtures."""
from __future__ import annotations
import os
import re
import selectors
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return None


def cpu_counters(proc: Path) -> tuple[int, int] | None:
    raw = read_text(proc / "stat")
    if raw is None:
        return None
    line = next((x for x in raw.splitlines() if x.startswith("cpu ")), None)
    if not line:
        return None
    try:
        v = list(map(int, line.split()[1:]))
        idle = v[3] + (v[4] if len(v) > 4 else 0)
        return sum(v[:8]), idle
    except (ValueError, IndexError):
        return None


def _process_snapshot(proc: Path) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    try:
        entries = list(proc.iterdir())
    except OSError:
        return result, {"status": "unavailable", "visible": 0, "unreadable": 0, "limitations": ["/proc could not be enumerated"]}
    pids = [entry for entry in entries if entry.name.isdigit()]
    unreadable = 0
    for entry in pids:
        raw = read_text(entry / "stat")
        if raw is None:
            unreadable += 1
            continue
        # comm is parenthesized and can itself contain spaces or ')'. The final
        # ')' separates it from fields beginning with state (field 3).
        end = raw.rfind(")")
        try:
            pid = int(raw[:raw.find(" ")])
            comm = raw[raw.find("(") + 1:end]
            fields = raw[end + 1:].split()
            # fields starts at field 3 (state): utime=14, stime=15,
            # starttime=22 and rss=24 (pages).
            ticks = int(fields[11]) + int(fields[12])
            starttime = int(fields[19])
            rss_pages = max(0, int(fields[21]))
            result[pid] = {"pid": pid, "name": comm, "ticks": ticks,
                           "starttime": starttime, "rss_bytes": rss_pages * os.sysconf("SC_PAGE_SIZE")}
        except (ValueError, IndexError):
            unreadable += 1
    if not result:
        status = "unavailable"
        limitations = ["No process stat records were readable"]
    elif unreadable:
        status = "partial"
        limitations = [f"{unreadable} of {len(pids)} visible /proc process records disappeared or were unreadable"]
    else:
        status = "ok"
        limitations = []
    return result, {"status": status, "visible": len(pids), "readable": len(result),
                    "unreadable": unreadable, "limitations": limitations}


def process_counters(proc: Path) -> dict[int, dict[str, Any]]:
    """Compatibility helper used by tests and callers that need one snapshot."""
    return _process_snapshot(proc)[0]


def collect_cpu_and_processes(proc: Path = Path("/proc"), interval: float = 2.0, clock_ticks: int | None = None) -> dict[str, Any]:
    before_cpu = cpu_counters(proc)
    before_proc, before_status = _process_snapshot(proc)
    start = time.monotonic()
    time.sleep(max(0, interval))
    elapsed = max(time.monotonic() - start, 0.001)
    after_cpu = cpu_counters(proc)
    after_proc, after_status = _process_snapshot(proc)
    ticks_per_second = clock_ticks or int(os.sysconf("SC_CLK_TCK"))
    cpu = None
    if before_cpu is not None and after_cpu is not None:
        total = after_cpu[0] - before_cpu[0]
        idle = after_cpu[1] - before_cpu[1]
        if total > 0 and 0 <= idle <= total:
            cpu = round(100 * (total - idle) / total, 1)
    paired = []
    for pid, newer in after_proc.items():
        older = before_proc.get(pid)
        # starttime is kernel ticks since boot and protects against PID reuse.
        if older is None or newer["starttime"] != older["starttime"] or newer["ticks"] < older["ticks"]:
            continue
        paired.append({"pid": pid, "name": newer["name"],
                       "cpu_percent_one_core": round((newer["ticks"] - older["ticks"]) / ticks_per_second / elapsed * 100, 1),
                       "rss_bytes": newer["rss_bytes"]})
    top_cpu = sorted(paired, key=lambda p: (-p["cpu_percent_one_core"], p["pid"]))[:10]
    top_rss = sorted(after_proc.values(), key=lambda p: (-p["rss_bytes"], p["pid"]))[:10]
    top_rss = [{"pid": p["pid"], "name": p["name"], "rss_bytes": p["rss_bytes"]} for p in top_rss]
    proc_status = after_status["status"]
    limitations = list(after_status["limitations"])
    if before_status["status"] == "unavailable":
        proc_status = "unavailable"
        limitations.append("Initial process snapshot was unavailable; CPU deltas could not be paired")
    elif before_status["status"] == "partial" and proc_status == "ok":
        proc_status = "partial"
        limitations.append("Some initial process entries could not be read")
    if not after_proc:
        proc_status = "unavailable"
    return {"cpu_percent": cpu, "interval_seconds": round(elapsed, 2),
            "processes_by_cpu": top_cpu, "processes_by_rss": top_rss,
            "process_count_sampled": after_status["readable"],
            "process_status": proc_status, "process_limitations": limitations}


def collect_memory(proc: Path = Path("/proc")) -> dict[str, Any]:
    raw = read_text(proc / "meminfo")
    stats = {}
    if raw:
        for line in raw.splitlines():
            m = re.match(r"(\w+):\s+(\d+)", line)
            if m:
                stats[m.group(1)] = int(m.group(2)) * 1024
    total, available = stats.get("MemTotal"), stats.get("MemAvailable")
    swap_total, swap_free = stats.get("SwapTotal"), stats.get("SwapFree")
    vm = read_text(proc / "vmstat")
    vmstats = {}
    if vm:
        for line in vm.splitlines():
            p = line.split()
            if len(p) == 2 and p[0] in ("pswpin", "pswpout"):
                try:
                    vmstats[p[0]] = int(p[1])
                except ValueError:
                    pass
    return {"memory_total_bytes": total, "memory_available_bytes": available,
            "memory_used_percent": round(100 * (total - available) / total, 1) if total and available is not None and total >= available else None,
            "swap_total_bytes": swap_total, "swap_free_bytes": swap_free,
            "swap_used_percent": round(100 * (swap_total - swap_free) / swap_total, 1) if swap_total and swap_free is not None and swap_total >= swap_free else None,
            "swap_pages_in": vmstats.get("pswpin"), "swap_pages_out": vmstats.get("pswpout")}


def collect_filesystems(proc: Path = Path("/proc")) -> dict[str, Any]:
    rows = []
    raw_mounts = read_text(proc / "self" / "mounts")
    if raw_mounts is None:
        return {"status": "unavailable", "filesystems": [], "limitations": ["/proc/self/mounts could not be read"]}
    mounts = raw_mounts.splitlines()
    if not mounts:
        return {"status": "unavailable", "filesystems": [], "limitations": ["Mount table was empty"]}
    seen = set()
    failures = 0
    unmeasurable = 0
    for line in mounts:
        p = line.split()
        if len(p) < 3:
            failures += 1
            continue
        device, mountpoint, fs = p[:3]
        mountpoint = mountpoint.replace("\\040", " ").replace("\\011", "\t")
        if mountpoint in seen or fs.startswith("fuse.") or fs in {"proc", "sysfs", "devtmpfs", "devpts", "tmpfs", "cgroup", "cgroup2", "overlay", "squashfs", "tracefs", "securityfs", "pstore", "debugfs", "mqueue", "hugetlbfs", "fusectl", "configfs", "ramfs", "efivarfs", "bpf", "autofs", "nsfs", "binfmt_misc"}:
            continue
        seen.add(mountpoint)
        try:
            s = os.statvfs(mountpoint)
            blocks = s.f_blocks * s.f_frsize
            avail = s.f_bavail * s.f_frsize
            inodes, iavail = s.f_files, s.f_favail
            used_percent = round(100 * (blocks - avail) / blocks, 1) if blocks else None
            inodes_used_percent = round(100 * (inodes - iavail) / inodes, 1) if inodes else None
            if used_percent is None or inodes_used_percent is None:
                unmeasurable += 1
            rows.append({"mountpoint": mountpoint, "filesystem": fs, "device": device,
                         "used_percent": used_percent, "inodes_used_percent": inodes_used_percent,
                         "available_bytes": avail, "inodes_available": iavail})
        except OSError:
            failures += 1
            rows.append({"mountpoint": mountpoint, "filesystem": fs, "device": device, "used_percent": None, "inodes_used_percent": None, "available_bytes": None, "inodes_available": None})
    if not rows:
        return {"status": "unavailable", "filesystems": [], "limitations": ["No measurable local filesystems remained after excluding virtual mounts"]}
    limitations = []
    if failures:
        limitations.append(f"{failures} mount entries were malformed or statvfs failed")
    if unmeasurable:
        limitations.append(f"{unmeasurable} filesystems returned zero capacity or unavailable space/inode counters")
    if limitations:
        return {"status": "partial", "filesystems": rows, "limitations": limitations}
    return {"status": "ok", "filesystems": rows, "limitations": []}


def diskstats(proc: Path) -> dict[str, tuple[int, int]] | None:
    raw = read_text(proc / "diskstats")
    if raw is None:
        return None
    result = {}
    for line in raw.splitlines():
        p = line.split()
        if len(p) < 14:
            continue
        try:
            # sectors read/written, Linux block counters use 512-byte sectors.
            result[p[2]] = (int(p[5]), int(p[9]))
        except ValueError:
            continue
    return result


def collect_io(proc: Path = Path("/proc"), interval: float = 2.0) -> dict[str, Any]:
    before = diskstats(proc)
    start = time.monotonic()
    time.sleep(max(0, interval))
    elapsed = max(time.monotonic() - start, 0.001)
    after = diskstats(proc)
    if before is None or after is None:
        return {"status": "unavailable", "interval_seconds": round(elapsed, 2), "devices": None,
                "limitations": ["/proc/diskstats was unavailable in one or both samples"]}
    rows = []
    for dev, (r, w) in after.items():
        if dev not in before:
            continue
        br, bw = before[dev]
        rows.append({"device": dev, "read_bytes_per_second": round(max(0, r-br) * 512 / elapsed, 0), "write_bytes_per_second": round(max(0, w-bw) * 512 / elapsed, 0)})
    if not rows:
        return {"status": "unavailable", "interval_seconds": round(elapsed, 2), "devices": [],
                "limitations": ["No block device had comparable counters in both samples"]}
    return {"status": "ok", "interval_seconds": round(elapsed, 2), "devices": rows, "limitations": []}


def collect_sensors(sysroot: Path = Path("/sys")) -> dict[str, Any]:
    sensors = []
    unreadable = 0
    base = sysroot / "class" / "thermal"
    paths = sorted(base.glob("thermal_zone*/temp"))
    for p in paths:
        raw = read_text(p)
        try:
            value = int(raw.strip()) / 1000
            if -50 <= value <= 200:
                label = read_text(p.parent / "type")
                sensors.append({"name": label.strip() if label else p.parent.name, "temperature_c": round(value, 1)})
            else:
                unreadable += 1
        except (ValueError, AttributeError):
            unreadable += 1
    hwmon = sysroot / "class" / "hwmon"
    paths = sorted(hwmon.glob("hwmon*/temp*_input"))
    for p in paths:
        raw = read_text(p)
        try:
            value = int(raw.strip()) / 1000
            if -50 <= value <= 200:
                label = read_text(p.with_name(p.name.replace("_input", "_label")))
                sensors.append({"name": label.strip() if label else p.parent.name + "/" + p.name, "temperature_c": round(value, 1)})
            else:
                unreadable += 1
        except (ValueError, AttributeError):
            unreadable += 1
    if not sensors:
        return {"status": "unavailable", "sensors": [], "limitations": ["No readable thermal-zone or hwmon sensors were found"]}
    if unreadable:
        return {"status": "partial", "sensors": sensors, "limitations": [f"{unreadable} sensor inputs were unreadable or outside supported bounds"]}
    return {"status": "ok", "sensors": sensors, "limitations": []}


def collect_failed_services(timeout: float = 3.0, max_output_bytes: int = 65536, max_services: int = 100) -> dict[str, Any]:
    executable = shutil.which("systemctl", path="/usr/sbin:/usr/bin:/sbin:/bin")
    if executable is None:
        return {"status": "unavailable", "services": None, "limitations": ["systemctl not found"]}
    args = [executable, "--failed", "--type=service", "--no-legend", "--plain", "--no-pager", "--no-ask-password"]
    env = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C", "SYSTEMD_COLORS": "0", "SYSTEMD_PAGER": "cat"}
    try:
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=False, env=env, close_fds=True)
        output = bytearray()
        oversized = False
        if process.stdout is None:
            process.kill()
            process.wait()
            return {"status": "unavailable", "services": None, "limitations": ["systemctl output pipe unavailable"]}
        with process.stdout, selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    process.kill()
                    process.wait()
                    return {"status": "unavailable", "services": None, "limitations": ["systemctl query timed out"]}
                ready = selector.select(remaining)
                if not ready:
                    process.kill()
                    process.wait()
                    return {"status": "unavailable", "services": None, "limitations": ["systemctl query timed out"]}
                chunk = os.read(process.stdout.fileno(), min(8192, max_output_bytes + 1 - len(output)))
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > max_output_bytes:
                    oversized = True
                    process.kill()
                    break
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            return {"status": "unavailable", "services": None, "limitations": ["systemctl query timed out"]}
    except OSError as exc:
        return {"status": "unavailable", "services": None, "limitations": [f"systemctl could not run: {type(exc).__name__}"]}
    if returncode != 0 and not oversized:
        return {"status": "unavailable", "services": None, "limitations": ["systemctl query failed"]}
    lines = bytes(output[:max_output_bytes]).decode(errors="replace").splitlines()
    services = []
    for line in lines:
        parts = line.split()
        if parts:
            services.append({"unit": parts[0], "load": parts[1] if len(parts)>1 else None, "active": parts[2] if len(parts)>2 else None, "sub": parts[3] if len(parts)>3 else None, "description": " ".join(parts[4:]) if len(parts)>4 else ""})
        if len(services) >= max_services:
            break
    limitations = []
    status = "ok"
    if oversized or len(services) >= max_services:
        status = "partial"
        limitations.append("systemctl output was truncated at the configured output or service limit")
    return {"status": status, "services": services, "limitations": limitations}
