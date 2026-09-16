from pathlib import Path
from decouple import Csv, config 
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

def env_bool(value):
    """Cast tolerante para ambientes que já definem DEBUG com outro significado."""
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


SECRET_KEY = config("SECRET_KEY")
SECRET_SALT = config("SECRET_SALT")
DEBUG = config("DEBUG", default=False, cast=env_bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in config('CSRF_TRUSTED_ORIGINS', default='').split(',')
    if origin.strip()
]

# A presença de LDAP_SERVER ativa a integração. As outras quatro variáveis
# são obrigatórias quando o servidor é informado.
LDAP_SERVER = config('LDAP_SERVER', default='').strip()
LDAP_DOMAIN = config('LDAP_DOMAIN', default='').strip()
LDAP_BASE_DN = config('LDAP_BASE_DN', default='').strip()
LDAP_BIND_USER = config('LDAP_BIND_USER', default='').strip()
LDAP_BIND_PASSWORD = config('LDAP_BIND_PASSWORD', default='')

if LDAP_SERVER and not all((LDAP_DOMAIN, LDAP_BASE_DN, LDAP_BIND_USER, LDAP_BIND_PASSWORD)):
    raise ImproperlyConfigured(
        'LDAP_DOMAIN, LDAP_BASE_DN, LDAP_BIND_USER e LDAP_BIND_PASSWORD '
        'são obrigatórias quando LDAP_SERVER está configurado.'
    )

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'pesquisas',
    'desligamentos',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'enps.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'enps.wsgi.application'
ASGI_APPLICATION = 'enps.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'CONN_MAX_AGE': config('DB_CONN_MAX_AGE', default=60, cast=int),
    }
}


AUTH_USER_MODEL = 'pesquisas.User'

AUTHENTICATION_BACKENDS = [
    'pesquisas.authentication.HybridAuthenticationBackend',
]

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
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


LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True


STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').is_dir() else []
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'auth': {
            'format': '{asctime} {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'auth_console': {
            'class': 'logging.StreamHandler',
            'formatter': 'auth',
        },
    },
    'loggers': {
        'pesquisas.auth': {
            'handlers': ['auth_console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'pesquisas:dashboard' 
LOGOUT_REDIRECT_URL = 'login'

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = min(config('SESSION_MAX_AGE', default=28800, cast=int), 8 * 60 * 60)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
X_FRAME_OPTIONS = 'DENY'
if not DEBUG:
    SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=True, cast=env_bool)
    CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=True, cast=env_bool)
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=env_bool)
    SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


