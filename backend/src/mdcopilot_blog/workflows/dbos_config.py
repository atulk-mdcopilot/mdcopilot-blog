"""DBOS configuration for the worker process (the only process that calls DBOS.launch())."""

from dbos import DBOSConfig

from mdcopilot_blog.settings import Settings

DBOS_APP_NAME = "mdcopilot-blog"
DBOS_SYSTEM_SCHEMA = "blog_dbos"  # blog_ namespace in the shared mdcopilot-backend database


def build_dbos_config(settings: Settings) -> DBOSConfig:
    # Recovery only picks up PENDING workflows whose executor_id AND application_version match,
    # so both are explicit and stable across restarts (never the DBOS defaults).
    return {
        "name": DBOS_APP_NAME,
        "system_database_url": settings.dbos_system_database_url,
        "application_version": settings.app_version,
        "executor_id": settings.worker_executor_id,
        "dbos_system_schema": DBOS_SYSTEM_SCHEMA,
        "log_level": settings.log_level,
    }
