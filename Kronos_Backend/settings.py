from datetime import timedelta
from pathlib import Path
import os
import django


BASE_DIR = Path(__file__).resolve().parent.parent
from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-123456")

DEBUG = True

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third party apps
    "corsheaders",
    "graphene_django",
    "graphql_auth",
    # local apps
    "apis",

    # 'channels',
    "django_celery_beat",
    "django_celery_results",
    "sslserver",
]

AUTH_USER_MODEL = "apis.User"


ALLOWED_HOSTS = [
    "app.algorobos.com",
    "algorobos.com",

    "localhost",
    "127.0.0.1",
    "13.205.120.68",
]

# Trust the X-Forwarded-Proto header set by nginx (which sits behind Cloudflare)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = False  # nginx already redirects 80 -> 443

CORS_ORIGIN_WHITELIST = [
    "https://app.algorobos.com",
    "https://algorobos.com",

    "http://localhost:3000",
    "http://13.205.120.68",
    "http://127.0.0.1:3000",
]

CSRF_TRUSTED_ORIGINS = [
    "https://app.algorobos.com",
    "https://algorobos.com",

    "http://13.205.120.68",
    "http://127.0.0.1:3000",
]



# CORS RefererPolicyMiddleware
CORS_REFERRER_POLICY = "no-referrer"
# Set Referer header
# CORS_ORIGIN_ALLOW_REFERER = True
#
CORS_ORIGIN_ALLOW_ALL = False

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_AGE = 1209600
SESSION_COOKIE_NAME = 'session'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer'
    }

}

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "Kronos_Backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

ASGI_APPLICATION = 'Kronos_Backend.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.getenv('NAME', 'Kronos'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('PASSWORD', 'kronos123'),
        'HOST': os.getenv('HOST', '127.0.0.1'),
        'PORT': os.getenv('PORT', '5432'),
    }
}

# TimescaleDB tick store (ltp hypertable). Parsed from TIGERDATA_URL.
# Example: postgres://user:pass@host:port/db?sslmode=require
_tigerdata_url = os.getenv('TIGERDATA_URL', '').strip()
if _tigerdata_url:
    try:
        from urllib.parse import urlparse, parse_qs
        _u = urlparse(_tigerdata_url)
        _qs = parse_qs(_u.query)
        DATABASES['tsdb'] = {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': (_u.path or '/').lstrip('/') or 'tsdb',
            'USER': _u.username or '',
            'PASSWORD': _u.password or '',
            'HOST': _u.hostname or '',
            'PORT': str(_u.port or 5432),
            'OPTIONS': {'sslmode': _qs.get('sslmode', ['require'])[0]},
        }
    except Exception:
        pass





AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTHENTICATION_BACKENDS = [
    "graphql_auth.backends.GraphQLAuthBackend",
    "graphql_jwt.backends.JSONWebTokenBackend",
    "django.contrib.auth.backends.ModelBackend",
]

GRAPHQL_JWT = {
    "JWT_ALLOW_ANY_CLASSES": [
        "graphql_auth.mutations.VerifyAccount",
        "graphql_auth.mutations.ResendActivationEmail",
        "graphql_auth.mutations.SendPasswordResetEmail",
        "graphql_auth.mutations.PasswordReset",
        "graphql_auth.mutations.ObtainJSONWebToken",
        "graphql_auth.mutations.VerifyToken",
        "graphql_auth.mutations.RefreshToken",
        "graphql_auth.mutations.RevokeToken",
        "graphql_auth.mutations.VerifySecondaryEmail",
    ],
    "JWT_VERIFY_EXPIRATION": True,
    # "JWT_LONG_RUNNING_REFRESH_TOKEN": True,
    "JWT_REUSE_REFRESH_TOKENS": False,
    "JWT_EXPIRATION_DELTA": timedelta(hours=6),

}

GRAPHENE = {
    "SCHEMA": "apis.schema.schema",
    "MIDDLEWARE": [
        "graphql_jwt.middleware.JSONWebTokenMiddleware",
    ],
}

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_DIRS = [os.path.join(BASE_DIR, 'staticfiles')],
STATIC_URL = '/staticfiles/'
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_L10N = False
USE_TZ = False

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

