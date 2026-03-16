"""
backend/run.py
Application entry point.

Usage:
    python run.py              → Flask dev server (default)
    python run.py celery       → Celery worker (2 concurrent tasks)
    python run.py beat         → Celery beat scheduler
    python run.py flower       → Flower monitoring UI at :5555
    python run.py all          → All four in parallel (dev convenience only)
"""

from __future__ import annotations

import sys
import os
import subprocess
import logging

logger = logging.getLogger(__name__)


def run_flask() -> None:
    from app import app, socketio
    from config.settings import Config

    port  = int(os.getenv("PORT", 5000))
    debug = Config.DEBUG
    logger.info("Starting Flask on port %s (debug=%s)", port, debug)
    socketio.run(app, host="0.0.0.0", port=port, debug=debug, use_reloader=debug)


def run_celery() -> None:
    from tasks.match_tasks import celery_app
    logger.info("Starting Celery worker…")
    celery_app.worker_main([
        "worker",
        "--loglevel=info",
        "--concurrency=2",
        "--queues=celery",
    ])


def run_beat() -> None:
    from tasks.match_tasks import celery_app
    logger.info("Starting Celery beat scheduler…")
    celery_app.Beat(loglevel="info").run()


def run_flower() -> None:
    """Start Flower monitoring UI."""
    from config.settings import Config
    cmd = [
        sys.executable, "-m", "celery",
        "-A", "tasks.match_tasks.celery_app",
        "flower",
        f"--broker={Config.CELERY_BROKER_URL}",
        "--port=5555",
        "--loglevel=warning",
    ]
    logger.info("Starting Flower at http://localhost:5555")
    subprocess.run(cmd)


def run_all() -> None:
    """Dev-only: start all processes via subprocess."""
    import multiprocessing
    procs = [
        multiprocessing.Process(target=run_flask,  name="flask"),
        multiprocessing.Process(target=run_celery, name="celery"),
        multiprocessing.Process(target=run_beat,   name="beat"),
    ]
    for p in procs:
        p.daemon = True
        p.start()
        logger.info("Started process: %s (pid=%s)", p.name, p.pid)
    try:
        for p in procs:
            p.join()
    except KeyboardInterrupt:
        logger.info("Shutting down all processes…")
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    # ── Logging ───────────────────────────────────────────────────────────────
    from config.logging_config import configure_logging
    configure_logging()

    arg = sys.argv[1] if len(sys.argv) > 1 else "flask"

    dispatch = {
        "flask":  run_flask,
        "celery": run_celery,
        "beat":   run_beat,
        "flower": run_flower,
        "all":    run_all,
    }

    fn = dispatch.get(arg)
    if fn is None:
        print(f"Unknown command '{arg}'. Valid: {', '.join(dispatch)}")
        sys.exit(1)

    fn()
