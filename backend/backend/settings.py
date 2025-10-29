from pathlib import Path
import os
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# 加载 .env 文件
env_path = BASE_DIR.parent / '.env'
load_dotenv(dotenv_path=env_path)

# ... (SECRET_KEY, DEBUG, ALLOWED_HOSTS, etc. remain the same) ...
SECRET_KEY = 'django-insecure-^j%3#x#c+q#@&z#a$a@d@a&o)v$!y!#p!j$o!c@t#y'
DEBUG = True
ALLOWED_HOSTS = ['*']  # 允许所有主机访问（包括 host.docker.internal 和容器网络）


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'backend.wsgi.application'


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_NAME', 'ocr_pipeline_db'),
        'USER': os.getenv('POSTGRES_USER', 'test'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'test1234'),
        'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
    }
}


# ... (Password validators, Internationalization, etc. remain the same) ...
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# CORS 配置 - 允许 Label Studio 跨域访问
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://host.docker.internal:8081",
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'range',
]
CORS_EXPOSE_HEADERS = [
    'content-length',
    'content-type',
    'content-disposition',
]

# --- 核心改动：从环境变量读取Redis主机 ---
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
CELERY_BROKER_URL = f'redis://{REDIS_HOST}:6379/0'
CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:6379/0'
# --- 结束改动 ---

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

DATA_ROOT_PATH = Path(os.getenv('LOCAL_DATA_PATH')) if os.getenv('LOCAL_DATA_PATH') else BASE_DIR.parent
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024

# Label Studio 配置
LABEL_STUDIO_URL = os.getenv('LABEL_STUDIO_URL', 'http://label-studio:8080')
LABEL_STUDIO_API_KEY = os.getenv('LABEL_STUDIO_API_KEY', '')  # 需要在 Label Studio 中生成
LABEL_STUDIO_PROJECT_ID = os.getenv('LABEL_STUDIO_PROJECT_ID', '1')  # 默认项目 ID

