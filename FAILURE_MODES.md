# System Failure Modes & Operational Safeguards

This document identifies runtime failure surfaces, timer scheduling conflicts, and mitigation patterns enforced by `cron-stabilizer`.

---

## 1. Failure Modes Matrix

| Failure Mode | Root Cause | System Behavior | Detection Metric | Automated Mitigation |
| :--- | :--- | :--- | :--- | :--- |
| **Silent Job Crash** | Executed script fails with non-zero exit status or uncaught exception. | Unit transitions to `failed` state; captured in journald. | `ActiveState=failed` or non-zero `ExecMainStatus`. | `OnFailure=alert-handler@%n.service` trigger dispatches operational notification; journald preserves stdout/stderr. |
| **Overlapping Execution / Long-Running Hang** | Job execution duration exceeds timer frequency interval. | Systemd timer default skips invocation if current unit is still active. | Unit runtime > scheduled cadence. | Enforce `TimeoutStartSec=` and `RuntimeMaxSec=` directives in generated `.service` unit to kill zombie processes. |
| **Timer Skew Across Sleep/Suspend** | Host VM enters suspend or hypervisor pause state. | Missed execution triggers. | Discrepancy between monotonic clock and wall-clock time. | Set `Persistent=true` in `[Timer]` section to trigger catch-up invocation immediately upon host resume. |
| **Host Resource Exhaustion** | Heavy scheduled batch script leaks memory or monopolizes CPU cores. | Host node out-of-memory (OOM) killer impacts sibling services. | Cgroup memory/CPU ceiling breached. | Embed `MemoryMax=` and `CPUQuota=` directives directly into service template slices. |

---

## 2. Hard Boundaries & Constraints

1. **Timer Persistence**: Periodic jobs requiring catch-up guarantee must set `Persistent=true`.
2. **Jitter Bounds**: Production workloads must specify `RandomizedDelaySec=60s` to 300s to avoid cluster-wide stampedes.
3. **Execution Timeouts**: All generated units default to strict execution ceilings (`RuntimeMaxSec=1800s`) unless explicitly overridden.
