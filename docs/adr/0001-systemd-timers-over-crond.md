# ADR 0001: Systemd Timers over Legacy crond for Enterprise Job Scheduling

## Status
Accepted

## Context
Production workloads across modern enterprise Linux environments depend on recurring automation tasks (database maintenance, telemetry rollups, health audits, batch workers). Traditionally, these tasks are scheduled via legacy `crond` (`crontab`).

However, legacy `crond` displays significant operational liabilities in high-reliability enterprise environments:
1. **Silent Failure & Execution Black Holes**: When a cron job exits with a non-zero code, standard output and errors are discarded or trapped in unmonitored local `mailx` spools, leaving failures undetected until downstream outages occur.
2. **Missing Dependency Orchestration**: Cron has no inherent understanding of network availability, filesystem mount readiness, or predecessor service health, frequently firing prematurely during reboot sequences.
3. **Thundering Herd Contention**: Coincident job schedules (`0 * * * *`) spike system CPU and I/O simultaneously due to the absence of native randomized jitter.
4. **No Native Resource Sandboxing**: Crond cannot enforce cgroup limits (CPU quotas, memory caps, IO bandwidth) on executing scripts.

## Decision
In `cron-stabilizer`, we migrate cron workflows to **native systemd timers and paired service units** (`.timer` + `.service`).

1. **Integrated `journald` Telemetry**: Every invocation stream is captured with precise timestamps, exit statuses, and standard I/O in the system journal without bespoke wrapper scripts.
2. **Deterministic Jitter via `RandomizedDelaySec`**: Systemd timers natively randomize fire intervals within defined bounds, leveling CPU/IO load across cluster fleets.
3. **Cgroup Enforcement**: Each executed job runs in an isolated transient systemd slice with bounded resource constraints (`MemoryMax=`, `CPUQuota=`).
4. **Dependency Coordination**: Timers assert preconditions (`After=network-online.target`, `RequiresMountsFor=`) before launching mission-critical payloads.

## Consequences

### Positive
- **Observability**: Immediate introspection via `systemctl list-timers` and `journalctl -u <job>.service`.
- **Fleet Stability**: Eliminates thundering herds through micro-jitter and prevents memory-leaking runaway scripts from destabilizing the host.
- **Auditable Lifecycle**: Failures can natively trigger `OnFailure=` alert units (e.g., paging, webhooks) without altering application code.

### Negative / Trade-offs
- **Unit File Overhead**: Requires two configuration units (`.service` and `.timer`) per scheduled job instead of a single one-line crontab entry.
- **Root/User Daemon Dependency**: Requires systemd user manager or root daemon access to register units.
