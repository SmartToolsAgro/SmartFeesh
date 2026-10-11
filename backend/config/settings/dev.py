from .base import *  # noqa: F403
from .base import env

CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_EAGER", default=True)  # no worker needed in development

DEBUG = env.bool("DJANGO_DEBUG", default=True)
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-insecure-secret-key")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "backend"])
