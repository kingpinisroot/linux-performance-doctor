"""Conservative, deterministic rules over collected metrics."""


def _finding(metric, severity, threshold, value, explanation, suggestion, impact, uncertainty=""):
    return {"metric": metric, "severity": severity, "threshold": threshold, "evidence": value,
            "explanation": explanation, "suggestion": suggestion, "impact": impact,
            "uncertainty": uncertainty}


def diagnose(data):
    findings = []
    for module, detail in data.get("modules", {}).items():
        if detail.get("status") != "ok":
            limitations = detail.get("limitations") or ["The module did not provide a complete measurement"]
            findings.append(_finding(module, "unknown", "module status is ok", detail.get("status"),
                                     "This module's data is incomplete or unavailable; no healthy result can be inferred.",
                                     "Review the listed limitation and retry if the data matters.",
                                     "This scan cannot assess this area reliably.", "; ".join(limitations)))
    cpu = data.get("cpu", {}).get("cpu_percent")
    if cpu is not None and cpu >= 90:
        findings.append(_finding("CPU", "warning", ">= 90%", cpu, "Most CPU time was busy during the sample.", "Inspect the listed processes and repeat the scan during the slowdown.", "High CPU can make interactive work and applications slower.", "This is a short sample and does not establish a persistent problem."))
    mem = data.get("memory", {})
    used = mem.get("memory_used_percent")
    if used is not None and used >= 95:
        findings.append(_finding("memory", "warning", ">= 95% used", used, "Very little memory is available.", "Review top processes and workload memory demand.", "Memory pressure can cause reclaim, swapping, or application allocation failures.", "Linux uses spare RAM for cache; MemAvailable is an estimate."))
    swapin, swapout = mem.get("swap_pages_in"), mem.get("swap_pages_out")
    if swapin is not None and swapout is not None and (swapin > 0 or swapout > 0):
        findings.append(_finding("swap activity", "warning", "> 0 pages in or out", {"pages_in": swapin, "pages_out": swapout}, "Pages moved between RAM and swap during the sample.", "Check whether this coincides with slowdowns and review memory demand.", "Swap I/O can increase latency.", "Some swap activity can be normal and is not by itself proof of a problem."))
    for fs in data.get("filesystems", {}).get("filesystems", []):
        for key, label in (("used_percent", "space"), ("inodes_used_percent", "inodes")):
            val = fs.get(key)
            if val is None:
                continue
            if val >= 90:
                findings.append(_finding(f"filesystem {label} {fs.get('mountpoint', '?')}", "warning", ">= 90% used", val, f"Filesystem {label} usage is high on {fs.get('mountpoint')}.", "Review large files or inode-heavy directories before cleanup.", "Applications may fail to write files when space or inodes run out.", "Available bytes account for space available to unprivileged users."))
    for sensor in data.get("sensors", {}).get("sensors", []):
        t = sensor.get("temperature_c")
        if t is not None and t >= 90:
            findings.append(_finding(f"temperature {sensor.get('name')}", "warning", ">= 90°C", t, "A readable temperature sensor reports a high value.", "Check cooling and the device vendor's documented operating limits.", "Thermal limits can cause throttling or hardware protection.", "Sensor labels and safe limits vary by hardware."))
    services = data.get("services", {})
    if services.get("services"):
        names = [s.get("unit") for s in services["services"]]
        findings.append(_finding("systemd failed services", "warning", ">= 1 failed service", names, "systemd reports failed service units.", "Review unit status and logs with an administrator if relevant.", "A failed unit may disable its associated service.", "This scan does not read logs or determine whether the unit is needed."))
    return findings
