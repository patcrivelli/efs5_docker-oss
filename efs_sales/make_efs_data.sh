set -euo pipefail

ROOT="/Users/patrickcrivelligmail.com/Desktop/efs4_docker"
cd "$ROOT"

# Create project if it doesn't exist
[ -d efs_data ] || django-admin startproject efs_data

cd efs_data

# Create apps (ignore if they already exist)
python manage.py startapp aggregate        || true
python manage.py startapp bank_statements || true
python manage.py startapp bureau          || true
python manage.py startapp financial       || true

# Reuse the shared UI package (ok if already installed)
pip install -e ../efs_shared_ui >/dev/null

# Folders and templates
mkdir -p templates \
         aggregate/templates/aggregate \
         bank_statements/templates/bank_statements \
         bureau/templates/bureau \
         financial/templates/financial

# Project home template
cat > templates/data_home.html <<'HTML'
{% extends "efs_shared_ui/base.html" %}
{% block title %}EFS Data{% endblock %}
{% block content %}
  <h1>EFS Data</h1>
  <p>Welcome to the data service.</p>
{% block title %}Financial{% endblock %}
{% endblock %}
HTML

# App templates
cat > aggregate/templates/aggregate/home.html <<'HTML'
{% extends "efs_shared_ui/base.html" %}
{% block title %}Aggregate{% endblock %}
{% block content %}<h2>Aggregate</h2>{% endblock %}
HTML

cat > bank_statements/templates/bank_statements/home.html <<'HTML'
{% extends "efs_shared_ui/base.html" %}
{% block title %}Bank Statements{% endblock %}
{% block content %}<h2>Bank Statements</h2>{% endblock %}
HTML

cat > bureau/templates/bureau/home.html <<'HTML'
{% extends "efs_shared_ui/base.html" %}
{% block title %}Bureau{% endblock %}
{% block content %}<h2>Bureau</h2>{% endblock %}
HTML

cat > financial/templates/financial/home.html <<'HTML'
{% extends "efs_shared_ui/base.html" %}
{% block content %}<h2>Financial</h2>{% endblock %}
HTML

# settings.py (Postgres + shared UI + templates)
cat > efs_data/settings.py <<'PY'
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "dev-only-change-me"
    "financial",
TEMPLATES = [{
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # shared UI across services
    "efs_shared_ui",

    # service apps
    "aggregate",
    "bank_statements",
    "bureau",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "efs_data.urls"
WSGI_APPLICATION = "efs_data.wsgi.application"

    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
}
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
            "efs_shared_ui.context_processors.efs_nav_context",
        ],
    },
}]

# Postgres (efs_data)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "efs_data"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
PY

# urls.py + home view
cat > efs_data/urls.py <<'PY'
from django.contrib import admin
from django.urls import path, include
app_name = "aggregate"
PY
PY
from . import views

urlpatterns = [
    path("", views.home, name="data_home"),
    path("admin/", admin.site.urls),

    path("aggregate/", include("aggregate.urls")),
    path("bank-statements/", include("bank_statements.urls")),
    path("bureau/", include("bureau.urls")),
    path("financial/", include("financial.urls")),
]
PY

cat > efs_data/views.py <<'PY'
from django.shortcuts import render
def home(request):
    return render(request, "data_home.html")
PY

# App URLConfs + views
cat > aggregate/urls.py <<'PY'
from django.urls import path
from . import views
urlpatterns = [ path("", views.home, name="home"), ]
PY
cat > aggregate/views.py <<'PY'
from django.shortcuts import render
def home(request): return render(request, "aggregate/home.html")

cat > bank_statements/urls.py <<'PY'
from django.urls import path
from . import views
app_name = "bank_statements"
urlpatterns = [ path("", views.home, name="home"), ]
cat > bank_statements/views.py <<'PY'
cat > financial/views.py <<'PY'
from django.shortcuts import render
def home(request): return render(request, "bank_statements/home.html")
PY

cat > bureau/urls.py <<'PY'
from django.urls import path
from . import views
app_name = "bureau"
urlpatterns = [ path("", views.home, name="home"), ]
PY
cat > bureau/views.py <<'PY'
from django.shortcuts import render
def home(request): return render(request, "bureau/home.html")
PY

cat > financial/urls.py <<'PY'
from django.urls import path
from . import views
app_name = "financial"
urlpatterns = [ path("", views.home, name="home"), ]
PY
from django.shortcuts import render
def home(request): return render(request, "financial/home.html")
PY

echo "Bootstrap complete."
echo "Next steps:"
echo "  1) Make sure PostgreSQL is running:  brew services start postgresql@14"
echo "  2) Create DB (first time):          createdb efs_data || true"
echo "  3) Migrate:                         python manage.py migrate"
echo "  4) Run the server:                  python manage.py runserver 0.0.0.0:8002"
