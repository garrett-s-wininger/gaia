"""Explicit test-project adapter for the pinned reusable django-todo app."""
import os
from pathlib import Path

BASE_DIR = Path(os.environ["GAIA_APP_PATH"])
SECRET_KEY = "local-benchmark-only"
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]
INSTALLED_APPS = ["django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
                  "django.contrib.messages", "django.contrib.sessions", "django.contrib.sites",
                  "django.contrib.staticfiles", "todo", "dal", "dal_select2"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.environ["GAIA_DB_PATH"],
                          "TEST": {"NAME": os.environ["GAIA_DB_PATH"]}}}
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
SITE_ID = 1
ROOT_URLCONF = "gaia_urls"
MIDDLEWARE = ["django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware",
              "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
              "django.contrib.messages.middleware.MessageMiddleware"]
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
              "OPTIONS": {"context_processors": ["django.template.context_processors.request",
                         "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
MEDIA_ROOT = os.environ["GAIA_MEDIA_ROOT"]
MEDIA_URL = "/media/"
STATIC_URL = "/static/"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
TODO_DEFAULT_LIST_SLUG = "tickets"
TODO_DEFAULT_ASSIGNEE = None
TODO_PUBLIC_SUBMIT_REDIRECT = "/"
TODO_MAIL_USER_MAPPER = None
USE_TZ = True
if os.environ.get("GAIA_FAST_HASHER") == "1":
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
if "GAIA_STAFF_ONLY" in os.environ:
    TODO_STAFF_ONLY = os.environ["GAIA_STAFF_ONLY"] == "1"

