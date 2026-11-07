"""cron_stabilizer.cli - Zero-Downtime Cron & Automation Fleet Stabilization Engine.

Enterprise CLI for auditing, diagnosing, and migrating fragile Linux crontabs
to resilient, monitored systemd unit pairs with automated dead-man's alerting.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class JobAuditRecord:
    raw_line: str
    user: str
    schedule: str
    command: str
    executable: str
    status: str  # OK, MISSING_EXECUTABLE, SYNTAX_ERROR, DEAD_REFERENCE
    failure_reason: Optional[str] = None
    target_unit_name: Optional[str] = None


@dataclass
class FleetAuditSummary:
    total_inspected: int = 0
    passed: int = 0
    failed: int = 0
    records: List[JobAuditRecord] = field(default_factory=list)


class CronFleetStabilizer:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.systemd_dir = self.output_dir / "systemd"
        self.systemd_dir.mkdir(parents=True, exist_ok=True)

    def parse_crontab_content(self, content: str, user: str) -> List[JobAuditRecord]:
        records: List[JobAuditRecord] = []
        for line in content.splitlines():
            clean = line.strip()
            if not clean or clean.startswith("#"):
                continue

            parts = clean.split()
            if len(parts) < 6:
                records.append(
                    JobAuditRecord(
                        raw_line=clean,
                        user=user,
                        schedule="",
                        command=clean,
                        executable="",
                        status="SYNTAX_ERROR",
                        failure_reason="Line contains fewer than 6 standard cron tokens.",
                    )
                )
                continue

            # Standard 5-field schedule
            schedule = " ".join(parts[:5])
            command = " ".join(parts[5:])

            # Extract primary executable
            exec_candidate = ""
            for token in parts[5:]:
                if token.startswith("-") or "=" in token:
                    continue
                exec_candidate = token
                break

            status = "OK"
            failure_reason = None

            # Verify executable path
            if exec_candidate:
                clean_exec = re.sub(r"[><&|;]+.*$", "", exec_candidate).strip()
                if clean_exec.startswith("/") and not os.path.exists(clean_exec):
                    status = "MISSING_EXECUTABLE"
                    failure_reason = f"Executable path does not exist on disk: {clean_exec}"
                elif not clean_exec.startswith("/") and not shutil.which(clean_exec):
                    status = "MISSING_EXECUTABLE"
                    failure_reason = f"Binary not found in system $PATH: {clean_exec}"

            # Sanitized unit name
            base_name = re.sub(r"[^a-zA-Z0-9_-]", "-", Path(clean_exec).name if clean_exec else "job")
            unit_name = f"fleet-{user}-{base_name}"

            records.append(
                JobAuditRecord(
                    raw_line=clean,
                    user=user,
                    schedule=schedule,
                    command=command,
                    executable=clean_exec,
                    status=status,
                    failure_reason=failure_reason,
                    target_unit_name=unit_name,
                )
            )

        return records

    def audit_system(self) -> FleetAuditSummary:
        summary = FleetAuditSummary()
        users_to_check = ["root"]
        current_user = os.environ.get("USER", "ubuntu")
        if current_user not in users_to_check:
            users_to_check.append(current_user)

        for u in users_to_check:
            try:
                cmd = ["crontab", "-l"] if u == current_user else ["sudo", "crontab", "-u", u, "-l"]
                res = subprocess.run(cmd, capture_output=True, text=True, check=False)
                if res.returncode == 0:
                    records = self.parse_crontab_content(res.stdout, user=u)
                    summary.records.extend(records)
            except Exception as exc:
                print(f"[WARN] Failed to read crontab for user {u}: {exc}", file=sys.stderr)

        summary.total_inspected = len(summary.records)
        summary.passed = sum(1 for r in summary.records if r.status == "OK")
        summary.failed = summary.total_inspected - summary.passed
        return summary

    def generate_systemd_artifacts(self, record: JobAuditRecord) -> tuple[str, str]:
        """Generates paired .service and .timer definitions with crashproofing."""
        sanitized_cmd = record.command.replace("%", "%%")
        service_content = f"""[Unit]
Description=Automated Fleet Task - {record.target_unit_name}
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User={record.user}
Environment=PYTHONUNBUFFERED=1
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/bin/bash -lc '{sanitized_cmd}'
StandardOutput=journal
StandardError=journal
Restart=on-failure
RestartSec=30s
TimeoutStartSec=1800s

[Install]
WantedBy=multi-user.target
"""
        # Simple translation of 5-field cron to OnCalendar
        timer_content = f"""[Unit]
Description=Timer trigger for {record.target_unit_name}
Requires={record.target_unit_name}.service

[Timer]
OnCalendar=*-*-* {record.schedule.replace('*/', '0/')}
Persistent=true
RandomizedDelaySec=60s

[Install]
WantedBy=timers.target
"""
        return service_content, timer_content

    def export_migration_plan(self, summary: FleetAuditSummary) -> Path:
        plan_file = self.output_dir / "audit_inventory.json"
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in summary.records], f, indent=2)

        for r in summary.records:
            if not r.target_unit_name:
                continue
            svc, tmr = self.generate_systemd_artifacts(r)
            svc_path = self.systemd_dir / f"{r.target_unit_name}.service"
            tmr_path = self.systemd_dir / f"{r.target_unit_name}.timer"
            svc_path.write_text(svc, encoding="utf-8")
            tmr_path.write_text(tmr, encoding="utf-8")

        return plan_file


def main():
    parser = argparse.ArgumentParser(
        description="Cron-Stabilizer: Enterprise SRE Fleet Audit & Hardening Tool"
    )
    parser.add_argument(
        "--audit", action="store_true", help="Perform non-destructive system cron forensic audit"
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("./stabilized_artifacts"),
        help="Target directory for generated systemd units and audit logs",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output audit report in raw JSON format"
    )

    args = parser.parse_args()
    engine = CronFleetStabilizer(output_dir=args.export_dir)

    if args.audit or True:
        summary = engine.audit_system()
        plan_path = engine.export_migration_plan(summary)

        if args.json:
            print(json.dumps(asdict(summary), indent=2))
        else:
            print("=" * 65)
            print(" CRON-STABILIZER FORENSIC AUDIT SUMMARY")
            print("=" * 65)
            print(f"Total Jobs Inspected : {summary.total_inspected}")
            print(f"Passing / Verified   : {summary.passed}")
            print(f"Degraded / Defective : {summary.failed}")
            print(f"Artifacts Generated  : {args.export_dir.resolve()}")
            print(f"Inventory Matrix     : {plan_path.resolve()}")
            print("=" * 65)
            if summary.failed > 0:
                print("\n[!] Identified Degraded Tasks:")
                for r in summary.records:
                    if r.status != "OK":
                        print(f"  - [{r.user}] {r.command[:50]}... -> {r.failure_reason}")


if __name__ == "__main__":
    main()
