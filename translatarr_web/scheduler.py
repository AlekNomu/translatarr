"""
translatarr_web.scheduler
~~~~~~~~~~~~~~~~~~~~~
APScheduler wrapper for periodic library scans.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

from translatarr_web.task_manager import TaskManager

logger = logging.getLogger("translatarr")

_JOB_ID = "library_scan"


def init_scheduler(
    app: Flask, task_manager: TaskManager, interval_minutes: int, scan_on_startup: bool
) -> BackgroundScheduler:
    """Create and start the background scheduler."""
    scheduler = BackgroundScheduler(daemon=True)

    def _trigger_scan() -> None:
        logger.info("Scheduled scan triggered")
        task_manager.submit_scan()

    if interval_minutes > 0:
        scheduler.add_job(
            _trigger_scan, "interval", minutes=interval_minutes, id=_JOB_ID,
        )

    if scan_on_startup:
        scheduler.add_job(
            _trigger_scan, "date", id="startup_scan",
        )

    scheduler.start()
    return scheduler


