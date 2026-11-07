<div align="center">

# 🛡️ Cron-Stabilizer
### Enterprise Autonomous Fleet SRE & Zero-Downtime Cron Modernization Engine

[![CI](https://github.com/Amz34/cron-stabilizer/actions/workflows/ci.yml/badge.svg)](https://github.com/Amz34/cron-stabilizer/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-brightgreen.svg)](https://www.python.org/)
[![Architecture: Enterprise SRE](https://img.shields.io/badge/Architecture-CA%20%26%20EGM%20Compliant-orange.svg)](#architecture)

*Turn brittle, silent-failing legacy crontabs into hardened, crashproof systemd timers with automated watchdog restarts, unbuffered telemetry, and zero-loss execution.*

</div>

---

## ⚡ The Enterprise Dilemma

Production Linux VMs run dozens of critical crons across multiple users. Over time, cron systems silently degrade due to:
* **Silent Stderr Dropping**: Crons swallow execution failures when not explicitly piped.
* **Environment Drift**: Subshells inherit restricted `$PATH` and non-interactive environments, breaking virtualenvs and CLI connectors.
* **Zombie / Overlap Accumulation**: Long-running jobs spawn uncoordinated concurrent instances, causing memory leaks and lock contention.
* **Zero Watchdog Telemetry**: When a background cron crashes, no recovery or backoff logic is applied.

**`cron-stabilizer`** delivers automated, forensic Reverse Engineering Analysis (REA) to audit, parse, validate, and migrate raw crontab configurations into enterprise-grade systemd `.service` and `.timer` pairs with zero production downtime.

---

## 🚀 Key Architectural Capabilities

* **Deep Forensic Extraction**: Auto-discovers crontabs across `/var/spool/cron/crontabs`, `/etc/cron.*`, and active system timers.
* **Static Binary & Path Verification**: Validates whether target binaries, Python runtimes, virtual environments, or scripts exist and are executable before execution.
* **Zero-Downtime Systemd Migration**: Compiles raw cron expressions into resilient systemd timers with:
  * `Restart=on-failure` & exponential backoff
  * `StandardOutput=journal` unbuffered structured telemetry
  * Dead-man's alerting triggers
  * Jitter injection (`RandomizedDelaySec`) to prevent CPU/IO thundering herds
* **ACID Inventory Matrix**: Emits a structured JSON audit bill-of-materials for formal SRE sign-off.

---

## 📦 Installation & Quickstart

```bash
# Clone the repository
git clone https://github.com/Amz34/cron-stabilizer.git
cd cron-stabilizer

# Run non-destructive forensic audit
PYTHONPATH=. python3 -m src.cron_stabilizer --audit

# Emit migration artifacts to target directory
PYTHONPATH=. python3 -m src.cron_stabilizer --export-dir ./stabilized_units
```

---

## 🛠️ Generated Systemd Unit Architecture

For each legacy crontab job, `cron-stabilizer` compiles a hardened unit pair:

```ini
# /etc/systemd/system/fleet-ubuntu-task.service
[Unit]
Description=Automated Fleet Task - fleet-ubuntu-task
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=ubuntu
Environment=PYTHONUNBUFFERED=1
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/bin/bash -lc '/usr/bin/python3 /home/ubuntu/ops/scripts/task.py'
StandardOutput=journal
StandardError=journal
Restart=on-failure
RestartSec=30s
TimeoutStartSec=1800s

[Install]
WantedBy=multi-user.target
```

---

## 🧪 Test Verification

```bash
PYTHONPATH=. python3 -m pytest tests/ -v
```

---

## 📜 License
Released under the [MIT License](LICENSE).
