"""
Django settings for websistemasinfo project.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# La clave se lee de una variable de entorno en Azure; en tu PC usa la de respaldo.
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-ay!i+=eon&ltq_ozz7l@!d9x5d(_a&ilb+ua+!jh-8@zm_8%di'
)

# ── Detección de entorno ─────────────────────────────────────────────────────
# Azure App Service crea automáticamente la variable WEBSITE_HOSTNAME.
# Si existe, estamos en la nube; si no, estamos en tu PC.
EN_AZURE = 'WEBSITE_HOSTNAME' in os.environ
DEBUG = not EN_AZURE

if EN_AZURE:
    HOSTNAME = os.environ['WEBSITE_HOSTNAME']
    ALLOWED_HOSTS = [HOSTNAME]
    CSRF_TRUSTED_ORIGINS = [f'https://{HOSTNAME}']
    # Azure entrega el sitio por HTTPS detrás de un proxy.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
else:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']
    CSRF_TRUSTED_ORIGINS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'LibreriaChichi',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'websistemasinfo.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'websistemasinfo.wsgi.application'

# ── Base de datos ────────────────────────────────────────────────────────────
# En Azure se leen las variables de entorno; en tu PC usa PostgreSQL local.
if EN_AZURE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ['DBNAME'],
            'USER': os.environ['DBUSER'],
            'PASSWORD': os.environ['DBPASS'],
            'HOST': os.environ['DBHOST'],
            'PORT': '5432',
            'OPTIONS': {'sslmode': 'require'},
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'bdd_sisinfo',
            'USER': 'postgres',
            'PASSWORD': '+Ben-2004',
            'HOST': 'localhost',
            'PORT': '5432',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Idioma y zona horaria ──
LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True

# ── Archivos estáticos ──
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
# Carpeta donde se juntan los estáticos para producción (collectstatic).
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}

# ── Archivos media ──
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Email ──────────────────────────────────────────────────────────────────
# La configuración se lee de variables de entorno.
#   • En tu PC (sin variables): usa la consola → el correo aparece en la terminal.
#   • En Azure: define EMAIL_BACKEND y las credenciales en
#     App Service → Configuración → Configuración de la aplicación.
#
# Para enviar de verdad, define en Azure (como mínimo):
#   EMAIL_BACKEND     = django.core.mail.backends.smtp.EmailBackend
#   EMAIL_HOST_USER   = tucorreo@gmail.com
#   EMAIL_HOST_PASSWORD = <contraseña de aplicación de 16 caracteres>
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend'  # respaldo: solo consola
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

# Remitente que ve el cliente. OJO con Gmail: reescribe el "From" a la cuenta
# autenticada, así que si usas Gmail conviene que sea tu propio correo.
DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL',
    EMAIL_HOST_USER or 'Librería Chichi <noreply@libreriachichi.cl>'
)

# Correo donde llegan los mensajes del formulario de Soporte/Contacto.
# Por defecto, el mismo buzón que envía (tu correo configurado arriba).
SOPORTE_EMAIL = os.environ.get('SOPORTE_EMAIL', '') or EMAIL_HOST_USER or DEFAULT_FROM_EMAIL

# Correo donde llega el reporte semanal de ventas (por defecto, tu buzón).
REPORTE_EMAIL = os.environ.get('REPORTE_EMAIL', '') or SOPORTE_EMAIL

# Token secreto para que un programador externo (ej. cron-job.org) dispare el
# envío automático del reporte llamando a:
#   /gestion/reporte/enviar/?token=<REPORTE_TOKEN>
# Si queda vacío, esa vía queda desactivada (solo se envía estando logueado).
REPORTE_TOKEN = os.environ.get('REPORTE_TOKEN', '')

# ── Login / Logout ──
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# ── CSRF y sesiones ──
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_AGE = 31449600
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 1209600
SESSION_SAVE_EVERY_REQUEST = True
