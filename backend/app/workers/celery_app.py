"""
Celery application factory.

Queue routing:
  indexing   — filesystem scanning, metadata extraction, search index sync
  thumbnails — thumbnail generation (CPU, resumable — checks for existing file first)
  hashing    — async SHA-256 computation (I/O-bound, runs after initial indexing)
  ml         — GPU tasks: CLIP, BLIP-2 captioning, Whisper, InsightFace (concurrency=1)
  ai         — CPU/HTTP tasks: Ollama summaries, face clustering, backfill
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
            "app.workers.tasks.clip.*": {"queue": "ml"},
            "app.workers.tasks.ai.compute_caption_task": {"queue": "ml"},
            "app.workers.tasks.ai.compute_transcript_task": {"queue": "ml"},
            "app.workers.tasks.ai.detect_faces_task": {"queue": "ml"},
            "app.workers.tasks.ai.compute_summary_task": {"queue": "ai"},
            "app.workers.tasks.ai.cluster_faces_task": {"queue": "ai"},
            "app.workers.tasks.ai.backfill_ai_task": {"queue": "ai"},
            "app.workers.tasks.webhook.*": {"queue": "webhooks"},
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
            # Every 30 minutes: cluster unclustered face embeddings
            "cluster-faces": {
                "task": "app.workers.tasks.ai.cluster_faces_task",
                "schedule": 1800,
            },
            # Every hour: dispatch AI tasks for items still in pending state
            "backfill-ai": {
                "task": "app.workers.tasks.ai.backfill_ai_task",
                "schedule": 3600,
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
        "app.workers.tasks.clip",
        "app.workers.tasks.ai",
        "app.workers.tasks.webhook",
        "app.workers.tasks.analytics",
    ],
    force=True,
)
