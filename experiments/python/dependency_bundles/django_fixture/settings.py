import os

SECRET_KEY = 'fixed-benchmark-key-not-a-deployment'
DEBUG = False
ALLOWED_HOSTS = ['testserver']
ROOT_URLCONF = 'django_fixture.urls'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
USE_TZ = True
USE_I18N = False
TIME_ZONE = 'UTC'
LANGUAGE_CODE = 'en'
STATIC_URL = '/static/'
FORM_RENDERER = 'django.forms.renderers.TemplatesSetting'
BENCH_USE_REST = os.environ['GAIA_DJANGO_SCENARIO'] == 'rest'
INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'django.forms', 'django_fixture.apps.FixtureConfig',
] + (['rest_framework', 'django_filters'] if BENCH_USE_REST else [])
MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]
loaders = (['django.template.loaders.filesystem.Loader', 'django.template.loaders.app_directories.Loader']
           if os.environ['GAIA_DJANGO_TEMPLATES'] == 'filesystem'
           else ['django_fixture.template_loader.PackageLoader'])
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [], 'APP_DIRS': False,
    'OPTIONS': {
        'loaders': [('django.template.loaders.cached.Loader', loaders)],
        'context_processors': ['django.template.context_processors.request',
                               'django.contrib.auth.context_processors.auth',
                               'django.contrib.messages.context_processors.messages'],
    },
}]
REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES': [], 'DEFAULT_PERMISSION_CLASSES': [],
                  'UNAUTHENTICATED_USER': None}
