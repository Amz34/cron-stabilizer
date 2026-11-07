"""Unit tests for cron_stabilizer."""
import pytest
from src.cron_stabilizer import CronFleetStabilizer, JobAuditRecord
from pathlib import Path

def test_parse_valid_crontab(tmp_path):
    stabilizer = CronFleetStabilizer(output_dir=tmp_path)
    sample_cron = """
    # Sample comment
    */5 * * * * /usr/bin/python3 /tmp/test.py >> /tmp/test.log 2>&1
    0 12 * * * /bin/bash /tmp/backup.sh
    """
    records = stabilizer.parse_crontab_content(sample_cron, user="testuser")
    assert len(records) == 2
    assert records[0].schedule == "*/5 * * * *"
    assert records[0].user == "testuser"
    assert records[1].schedule == "0 12 * * *"

def test_parse_invalid_crontab_line(tmp_path):
    stabilizer = CronFleetStabilizer(output_dir=tmp_path)
    sample_cron = "invalid_token_line"
    records = stabilizer.parse_crontab_content(sample_cron, user="testuser")
    assert len(records) == 1
    assert records[0].status == "SYNTAX_ERROR"

def test_systemd_artifact_generation(tmp_path):
    stabilizer = CronFleetStabilizer(output_dir=tmp_path)
    record = JobAuditRecord(
        raw_line="*/10 * * * * /usr/bin/python3 script.py",
        user="ubuntu",
        schedule="*/10 * * * *",
        command="/usr/bin/python3 script.py",
        executable="/usr/bin/python3",
        status="OK",
        target_unit_name="fleet-ubuntu-python3"
    )
    svc, tmr = stabilizer.generate_systemd_artifacts(record)
    assert "[Unit]" in svc
    assert "Restart=on-failure" in svc
    assert "OnCalendar=" in tmr
