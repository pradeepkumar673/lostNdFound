"""
CampusLostFound - Run Script
Usage:
  python run.py          → starts Flask dev server
  python run.py celery   → starts Celery worker
  python run.py beat     → starts Celery beat scheduler
"""
import sys

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "flask"

    if arg == "celery":
        from tasks.match_tasks import celery_app
        celery_app.worker_main(["worker", "--loglevel=info", "-c", "2"])

    elif arg == "beat":
        from tasks.match_tasks import celery_app
        celery_app.Beat(loglevel="info").run()

    else:
        from app import app, socketio
        socketio.run(app, host="0.0.0.0", port=5000, debug=True, use_reloader=True)
