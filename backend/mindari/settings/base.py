"""
Base Django settings for Mindari / Deal Analysis.
Override in production.py.
"""
import os
from pathlib import Path
from datetime import timedelta
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1']),
)
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-me-in-production-please')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]
THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
]
LOCAL_APPS = [
    'apps.users',
    'apps.deals',
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'mindari.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'mindari.wsgi.application'

# Railway: reference the Postgres add-on (DATABASE_URL=${{Postgres.DATABASE_URL}}).
# Without it the app falls back to SQLite inside the container, which is wiped on every deploy.
DATABASE_URL_SET = bool(os.environ.get('DATABASE_URL'))
DATABASES = {
    'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}')
}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'users.User'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

# Every data endpoint requires a signed-in user.
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'mindari.pagination.Pagination',
    'PAGE_SIZE': 100,
    'DEFAULT_RENDERER_CLASSES': ('rest_framework.renderers.JSONRenderer',),
    'DEFAULT_THROTTLE_CLASSES': ('rest_framework.throttling.ScopedRateThrottle',),
    'DEFAULT_THROTTLE_RATES': {'login': '10/min', 'import': '20/hour'},
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=['http://localhost:5173', 'http://localhost:3000'])
CORS_ALLOW_CREDENTIALS = True

# ── Deal analysis: Claude API + web search ────────────────────────────────────
# strip spaces, quotes and a pasted "ANTHROPIC_API_KEY=" prefix — common copy/paste slips
ANTHROPIC_API_KEY = env('ANTHROPIC_API_KEY', default='').strip().strip('"\'').removeprefix('ANTHROPIC_API_KEY=').strip()
# Main model (research, scoring, memo) and the cheaper model that digests each uploaded file.
ANALYSIS_MODEL = env('ANALYSIS_MODEL', default='claude-sonnet-5-5')
DIGEST_MODEL = env('DIGEST_MODEL', default='claude-haiku-5-5')
# USD per million tokens: (input, output, input above 100K-token prompts, output above).
ANALYSIS_MODELS = {
    'claude-haiku-5-5': {'label': 'Haiku 5.5 · economy', 'price': (0.10, 0.50, 0.50, 2.50)},
    'claude-sonnet-5-5': {'label': 'Sonnet 5.5 · balanced', 'price': (2.0, 10.0, 2.0, 10.0)},
    'claude-opus-5-5': {'label': 'Opus 5.5 · deepest', 'price': (4.0, 20.0, 4.0, 20.0)},
}
SEARCH_PRICE = 0.01  # $10 per 1,000 web searches
ANALYSIS_MAX_SEARCHES = env.int('ANALYSIS_MAX_SEARCHES', default=25)
ANALYSIS_CONCURRENCY = env.int('ANALYSIS_CONCURRENCY', default=2)  # deals analysed in parallel
DIGEST_CONCURRENCY = env.int('DIGEST_CONCURRENCY', default=4)      # files digested in parallel per deal

# ── Uploaded deal files ──────────────────────────────────────────────────────
# Files are uploaded one per request (so 15-20 files never hit a single-request limit) and
# streamed to disk by Django. Store them on a Railway Volume mounted at /data (MEDIA_ROOT), or
# in an S3-compatible bucket (Railway Bucket, Cloudflare R2, AWS S3) when S3_BUCKET is set.
MEDIA_ROOT = env('MEDIA_ROOT', default=str(BASE_DIR / 'media'))
MEDIA_URL = '/media/'
MAX_UPLOAD_MB = env.int('MAX_UPLOAD_MB', default=200)        # per file
MAX_FILES_PER_DEAL = env.int('MAX_FILES_PER_DEAL', default=60)
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024               # larger uploads stream to a temp file
DATA_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024
S3_BUCKET = env('S3_BUCKET', default='')
# Uploaded files survive redeploys only on a bucket or a mounted Railway Volume (/data); container disk is wiped.
ON_RAILWAY = bool(os.environ.get('RAILWAY_SERVICE_ID') or os.environ.get('RAILWAY_ENVIRONMENT'))
STORAGE_PERSISTENT = bool(S3_BUCKET) or str(MEDIA_ROOT).startswith('/data') or not ON_RAILWAY

# Built React app (copied in by the root Dockerfile); served at / by WhiteNoise + spa_index
FRONTEND_DIST = BASE_DIR / 'frontend_dist'
WHITENOISE_ROOT = FRONTEND_DIST if FRONTEND_DIST.exists() else None

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': ({'BACKEND': 'storages.backends.s3.S3Storage', 'OPTIONS': {
        'bucket_name': S3_BUCKET,
        'endpoint_url': env('S3_ENDPOINT_URL', default='') or None,
        'access_key': env('S3_ACCESS_KEY_ID', default=''),
        'secret_key': env('S3_SECRET_ACCESS_KEY', default=''),
        'region_name': env('S3_REGION', default='') or None,
        'default_acl': None, 'file_overwrite': False, 'querystring_auth': True,
    }} if S3_BUCKET else {'BACKEND': 'django.core.files.storage.FileSystemStorage'}),
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dubai'
USE_I18N = True
USE_TZ = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'verbose': {'format': '[{asctime}] {levelname} {name}: {message}', 'style': '{'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'apps': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}
