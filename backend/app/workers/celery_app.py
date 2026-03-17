"""
Celery application factory.

Queue routing:
  indexing   — filesystem scanning, metadata extraction, search index sync
  thumbnails — thumbnail generation (CPU, resumable — checks for existing file first)
  hashing    — async SHA-256 computation (I/O-bound, runs after initial indexing)
  ai         — CPU/HTTP tasks: NSFW tagging
"""

from celery import Celery

from app.config import settings

celery_app = Celery("indexxxer")

celery_app.config_from_object(
    {
        "broker_url": settings.celery_broker_url,
        "result_backend": settings.celery_result_backend,
        # Serialisation
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        # Timezone
        "timezone": "UTC",
        "enable_utc": True,
        # Reliability
        "task_acks_late": True,          # ack only after task completes (safe restart)
        "task_reject_on_worker_lost": True,
        "worker_prefetch_multiplier": 1, # one task per worker slot (fair for long jobs)
        "task_track_started": True,      # emit STARTED state so callers can distinguish queued vs running
        # Queue routing
        "task_routes": {
            "app.workers.tasks.scan.*": {"queue": "indexing"},
            "app.workers.tasks.gallery.*": {"queue": "indexing"},
            "app.workers.tasks.pdf.*": {"queue": "indexing"},
            "app.workers.tasks.thumbnail.*": {"queue": "thumbnails"},
            "app.workers.tasks.hashing.*": {"queue": "hashing"},
            "app.workers.tasks.watcher.*": {"queue": "indexing"},
            "app.workers.tasks.webhook.*": {"queue": "webhooks"},
            "app.workers.tasks.performer.*": {"queue": "indexing"},
            "app.workers.tasks.downloader.*": {"queue": "indexing"},
            "app.workers.tasks.nsfw_tag.*": {"queue": "ai"},
            "app.workers.tasks.phash.*": {"queue": "hashing"},
        },
        "task_default_queue": "indexing",
        # Time limits — thumbnail tasks enforce their own via decorator args
        "task_soft_time_limit": settings.hash_time_limit,
        "task_time_limit": settings.hash_time_limit + 30,
        # Beat schedule
        "beat_schedule": {
            # Every 10 minutes: mark jobs where all files are done as completed
            # (safety net in case the last process_file_task missed the counter check)
            "reap-stalled-jobs": {
                "task": "app.workers.tasks.scan.reap_stalled_jobs_task",
                "schedule": 600,  # every 10 minutes
            },
            # Every 60 seconds: write a heartbeat key so the status endpoint
            # can verify beat is alive
            "beat-heartbeat": {
                "task": "app.workers.tasks.heartbeat.beat_heartbeat_task",
                "schedule": 60,
            },
        },
    }
)

# Autodiscover tasks — imports all task modules so Celery registers them
celery_app.autodiscover_tasks(
    [
        "app.workers.tasks.scan",
        "app.workers.tasks.gallery",
        "app.workers.tasks.pdf",
        "app.workers.tasks.thumbnail",
        "app.workers.tasks.hashing",
        "app.workers.tasks.watcher",
        "app.workers.tasks.webhook",
        "app.workers.tasks.analytics",
        "app.workers.tasks.performer",
        "app.workers.tasks.nsfw_tag",
        "app.workers.tasks.phash",
        "app.workers.tasks.downloader",
        "app.workers.tasks.heartbeat",
    ],
    force=True,
)
