<div dir="rtl">

# پلتفرم آواتار دیجیتال هوشمند | AI Digital Human Platform

**پلتفرم خودمیزبان، GPU-محور و open-source برای ساخت آواتارهای دیجیتال واقعی با قابلیت مکالمه بلادرنگ**

رقیب مستقیم HeyGen، Synthesia، D-ID، Tavus و Elai — کاملاً زیر کنترل شما

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react)](https://react.dev)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6?style=flat-square&logo=typescript)](https://typescriptlang.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker)](https://docker.com)
[![License](https://img.shields.io/badge/License-Commercial-red?style=flat-square)](#لایسنس)

</div>

---

<div dir="rtl">

## فهرست مطالب

- [درباره پروژه](#درباره-پروژه)
- [قابلیت‌های اصلی](#قابلیتهای-اصلی)
- [وضعیت پیاده‌سازی](#وضعیت-پیادهسازی)
- [معماری سیستم](#معماری-سیستم)
- [استک فناوری](#استک-فناوری)
- [مدل‌های هوش مصنوعی](#مدلهای-هوش-مصنوعی)
- [پیش‌نیازها](#پیشنیازها)
- [نصب سریع](#نصب-سریع)
- [نصب گام‌به‌گام](#نصب-گامبهگام)
- [متغیرهای محیطی](#متغیرهای-محیطی)
- [ساختار پروژه](#ساختار-پروژه)
- [مستندات API](#مستندات-api)
- [استقرار تولیدی](#استقرار-تولیدی)
- [امنیت](#امنیت)
- [مانیتورینگ](#مانیتورینگ)
- [پشتیبان‌گیری](#پشتیبانگیری)
- [رفع مشکلات](#رفع-مشکلات)
- [زبان‌های پشتیبانی‌شده](#زبانهای-پشتیبانیشده)
- [لایسنس](#لایسنس)

---

## درباره پروژه

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  استودیوی آواتار │ استودیوی صدا │ استودیوی ویدیو │ سازنده Agent │ آنالیتیکس  │
├─────────────────────────────────────────────────────────────────────────────┤
│       React 19 · TypeScript · TailwindCSS · Shadcn UI · پشتیبانی RTL       │
├─────────────────────────────────────────────────────────────────────────────┤
│              FastAPI · Python 3.12 · Celery · احراز هویت JWT               │
├───────────────────────────────────┬─────────────────────────────────────────┤
│  PostgreSQL 16 · Redis 7 · Qdrant │  MinIO · FFmpeg · WebRTC · WebSocket   │
├───────────────────────────────────┴─────────────────────────────────────────┤
│  LivePortrait · MuseTalk · XTTS-v2 · Whisper V3 · InsightFace · E5-large   │
└─────────────────────────────────────────────────────────────────────────────┘
```

این پلتفرم به شما امکان می‌دهد:

- 🎭 **آواتار دیجیتال** از عکس یا ویدیو بسازید با تشخیص چهره خودکار
- 🎙️ **صدای شما را کلون کنید** در ۷ زبان با کیفیت استودیویی
- 🎬 **ویدیوهای حرفه‌ای** با لیپ سینک دقیق در رزولوشن 4K تولید کنید
- 🤖 **Agent هوشمند** با پایگاه دانش RAG و شخصیت سفارشی بسازید
- 💬 **مکالمه بلادرنگ** با تأخیر کمتر از ۱.۲ ثانیه داشته باشید

> **مناسب برای:** شرکت‌های فناوری، استارتاپ‌ها، آموزش آنلاین، رسانه، بازاریابی دیجیتال، خدمات مشتری هوشمند

---

## قابلیت‌های اصلی

| ماژول | قابلیت‌ها |
|-------|-----------|
| 🎭 **استودیوی آواتار** | آپلود عکس/ویدیو/وبکم → تشخیص و آنالیز چهره با InsightFace → تولید Embedding 512 بُعدی → ثامبنیل خودکار |
| 🎙️ **استودیوی صدا** | کلون صدا با XTTS-v2 در ۷ زبان · تشخیص زبان خودکار · اعتبارسنجی کیفیت · پیش‌نمایش فوری |
| 🎬 **استودیوی ویدیو** | تولید ویدیوی گویا 720p/1080p/4K · لیپ سینک دقیق · صف پردازش GPU · دانلود MP4 |
| 🤖 **سازنده Agent** | ساخت Agent هوشمند · اتصال پایگاه دانش RAG · انتخاب LLM · شخصیت‌پردازی سفارشی |
| 📚 **پایگاه دانش** | آپلود PDF/DOCX/URL · پردازش و Chunking · جستجوی معنایی با Qdrant · پاسخ استنادی |
| ⚡ **مکالمه بلادرنگ** | تأخیر < ۱.۲ ثانیه · WebSocket + WebRTC · تشخیص فعالیت صوتی (VAD) |
| 📊 **آنالیتیکس** | متریک‌های زنده GPU · آمار مصرف · نمودارهای تعاملی · صادرات CSV |
| ⚙️ **پنل مدیریت** | مدیریت کاربران · کنترل Jobها · لاگ حسابرسی · سلامت سیستم |

---

## وضعیت پیاده‌سازی

### ✅ کامل و آماده استفاده

| بخش | وضعیت | توضیح |
|-----|--------|-------|
| Backend API | ✅ کامل | FastAPI · ۱۲ endpoint · WebSocket · Celery |
| Frontend | ✅ کامل | React 19 · ۹ صفحه · RTL · i18n چند زبانه |
| پایگاه داده | ✅ کامل | SQLAlchemy async · Migration Alembic |
| احراز هویت | ✅ کامل | JWT RS256 · Refresh Token · RBAC |
| ذخیره‌سازی | ✅ کامل | MinIO S3-compatible · آپلود چندبخشی |
| صف وظایف | ✅ کامل | Celery · Worker GPU/CPU · پیشرفت زنده |
| جستجوی معنایی | ✅ کامل | Qdrant · E5-multilingual embeddings |
| Docker | ✅ کامل | Compose · Nginx · Kubernetes manifests |
| مانیتورینگ | ✅ کامل | Prometheus · Grafana · Loki · Sentry |
| امنیت | ✅ کامل | Rate limiting · CORS · Audit log |
| طراحی UI | ✅ کامل | Glassmorphism · انیمیشن · Dark mode |

### ⚙️ نیاز به پیکربندی برای اجرا

| مورد | توضیح |
|------|-------|
| مدل‌های AI | دانلود ~14GB از HuggingFace/GitHub |
| GPU Driver | نصب NVIDIA Driver 535+ (اختیاری) |
| متغیرهای `.env` | SECRET_KEY، رمز DB، کلید MinIO |
| LLM API Key | OpenAI یا DeepSeek (حداقل یکی) |

---

## معماری سیستم

```
┌─────────────────────────────────────────────────────────────────┐
│                     کاربران / Clients                            │
│    مرورگر وب │ موبایل │ صفحه لمسی ۸۶ اینچ │ API مستقیم         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS / WSS / WebRTC
┌──────────────────────────▼──────────────────────────────────────┐
│              NGINX (Reverse Proxy + TLS + Rate Limit)            │
└──────┬───────────────────────────────────┬───────────────────────┘
       │                                   │
┌──────▼──────┐                   ┌────────▼────────┐
│  Frontend   │                   │   Backend API    │
│  React 19   │                   │  FastAPI 0.111   │
│  TypeScript │                   │  Python 3.12     │
│  Port 3000  │                   │  Port 8000       │
└─────────────┘                   └────────┬────────┘
                                           │
          ┌────────────────────────────────┼────────────────────────┐
          │                                │                         │
┌─────────▼──────┐              ┌──────────▼──────┐      ┌─────────▼──────┐
│  PostgreSQL 16 │              │    Redis 7       │      │    Qdrant       │
│  (دیتابیس اصلی)│              │  Cache + Queue   │      │  Vector DB      │
│   Port 5432    │              │   Port 6379      │      │   Port 6333     │
└────────────────┘              └─────────────────┘      └────────────────┘
                                           │
                                ┌──────────▼──────────────────────────┐
                                │         Celery Workers               │
                                │  ┌─────────────┐  ┌──────────────┐  │
                                │  │ GPU Worker  │  │  CPU Worker  │  │
                                │  │ آواتار/TTS/ │  │   اسناد/     │  │
                                │  │  ویدیو      │  │  آنالیتیکس  │  │
                                │  └──────┬──────┘  └──────────────┘  │
                                └─────────┼────────────────────────────┘
                                          │
                          ┌───────────────▼───────────────────────┐
                          │            مدل‌های AI                   │
                          │  LivePortrait │ MuseTalk               │
                          │  Wav2Lip      │ InsightFace            │
                          │  Whisper V3   │ XTTS-v2               │
                          │  CosyVoice    │ E5-Multilingual        │
                          └───────────────────────────────────────┘
                                          │
                          ┌───────────────▼───────────────────────┐
                          │       MinIO Object Storage             │
                          │  آواتار │ صدا │ ویدیو │ اسناد         │
                          └───────────────────────────────────────┘
```

### پایپ‌لاین تولید ویدیو

```
درخواست (آواتار + صدا + متن + رزولوشن)
    ↓
ساخت Job و اعتبارسنجی
    ↓
Celery Task (GPU Worker)
    ├── مرحله ۱ · TTS با XTTS-v2  ───────────→  متن → صدای WAV 24kHz
    ├── مرحله ۲ · Lip Sync          ──────────→  آواتار + صدا → فریم‌های انیمیشن
    ├── مرحله ۳ · Video Compose     ──────────→  فریم‌ها → MP4 (تا 4K)
    └── مرحله ۴ · Post-Processing   ──────────→  ثامبنیل + متادیتا + اطلاع‌رسانی
    ↓
ویدیو آماده دانلود/پخش
```

### پایپ‌لاین مکالمه بلادرنگ (< ۱.۲ ثانیه)

```
صدای کاربر (WebRTC/WebSocket)
    ↓
VAD (تشخیص فعالیت صوتی)
    ↓
Whisper Large V3 (تبدیل گفتار به متن) ─── ~300ms
    ↓
LLM Processing (GPT-4o/DeepSeek/Llama) ─── ~500ms
    ↓
XTTS-v2 (سنتز صدا) ─────────────────── ~200ms (اولین chunk)
    ↓
MuseTalk (لیپ سینک بلادرنگ) ────────── ~100ms/frame
    ↓
WebRTC Stream → کاربر
```

### پایپ‌لاین RAG (پایگاه دانش)

```
آپلود سند (PDF/DOCX/PPTX/URL)
    ↓
تجزیه متن (PyMuPDF/docx/openpyxl)
    ↓
Chunking (۵۱۲ توکن، ۵۰ توکن overlap)
    ↓
تولید Embedding (multilingual-e5-large)
    ↓
ذخیره در Qdrant (cosine similarity)
    ↓
هنگام پرسش:
پرسش کاربر → Embedding → جستجو در Qdrant (top-5)
    ↓
Chunk‌های بازیابی‌شده + پرسش → LLM
    ↓
پاسخ با استناد به منابع
```

---

## استک فناوری

### فرانت‌اند (Frontend)

| فناوری | نسخه | کاربرد |
|--------|------|--------|
| React | 19 | UI Framework |
| TypeScript | 5.7 | Type Safety |
| Vite | 6 | Build Tool |
| TailwindCSS | 4 | Styling |
| Shadcn UI / Radix | latest | کامپوننت‌های UI |
| Framer Motion | 12 | انیمیشن |
| TanStack Query | 5 | مدیریت State سرور |
| Zustand | 5 | مدیریت State کلاینت |
| React Hook Form + Zod | 7/3 | اعتبارسنجی فرم |
| Socket.IO Client | 4 | WebSocket |
| Simple Peer | 9 | WebRTC |
| Recharts | 2 | نمودارهای آنالیتیکس |
| i18next | 24 | چندزبانگی |
| WaveSurfer.js | 7 | نمایش امواج صوتی |

### بک‌اند (Backend)

| فناوری | نسخه | کاربرد |
|--------|------|--------|
| FastAPI | 0.111 | REST API + WebSocket |
| Python | 3.12 | Runtime |
| SQLAlchemy (async) | 2.0 | ORM |
| Alembic | 1.13 | Migration دیتابیس |
| Celery | 5.4 | صف وظایف |
| Pydantic v2 | 2.7 | اعتبارسنجی داده |
| python-jose | 3.3 | JWT |
| passlib + bcrypt | 1.7 | هش رمز عبور |
| Uvicorn | 0.30 | ASGI Server |
| structlog | 24 | لاگینگ ساختاریافته |

### دیتابیس و ذخیره‌سازی

| سرویس | نسخه | کاربرد |
|-------|------|--------|
| PostgreSQL | 16 | دیتابیس اصلی (Relational) |
| Redis | 7 | Cache + Celery Broker |
| Qdrant | latest | Vector DB برای RAG |
| MinIO | latest | Object Storage (سازگار با S3) |

### زیرساخت

| ابزار | کاربرد |
|-------|--------|
| Docker + Docker Compose | Containerization |
| Nginx | Reverse Proxy + TLS |
| Kubernetes (Kustomize) | سازمان‌دهی Enterprise |
| Prometheus | جمع‌آوری متریک |
| Grafana | داشبورد مانیتورینگ |
| Loki | تجمیع لاگ |
| Sentry | ردیابی خطا |

---

## مدل‌های هوش مصنوعی

| مؤلفه | مدل اصلی | مدل جایگزین | حجم تقریبی |
|-------|---------|------------|------------|
| انیمیشن آواتار | LivePortrait | Wav2Lip | ~4 GB |
| لیپ سینک بلادرنگ | MuseTalk | Wav2Lip | ~3 GB |
| کلون صدا (TTS) | XTTS-v2 | CosyVoice | ~2 GB |
| تشخیص گفتار (STT) | Whisper Large V3 | — | ~3 GB |
| تحلیل چهره | InsightFace buffalo_l | MediaPipe | ~500 MB |
| LLM | GPT-4o (OpenAI) | DeepSeek / Llama (Ollama) | — |
| Embeddings | multilingual-e5-large | text-embedding-3-small | ~600 MB |

> **مجموع حجم مدل‌ها:** ~13 تا 14 گیگابایت (بدون LLM محلی)

---

## پیش‌نیازها

### سخت‌افزار

| مؤلفه | حداقل | پیشنهادی | Enterprise |
|-------|-------|---------|------------|
| CPU | ۸ هسته | ۱۶ هسته | ۳۲+ هسته |
| RAM | ۳۲ GB | ۶۴ GB | ۱۲۸+ GB |
| GPU | RTX 3080 (10GB VRAM) | RTX 4090 (24GB VRAM) | A100 (80GB) |
| Storage | 500 GB SSD | 2 TB NVMe | 10+ TB RAID |
| Network | 100 Mbps | 1 Gbps | 10 Gbps |

> **توجه:** GPU اختیاری است ولی بدون آن تولید ویدیو و مکالمه بلادرنگ بسیار کند خواهد بود.

### نرم‌افزار

- **OS:** Ubuntu 22.04 LTS یا RHEL 9 (پیشنهادی)
- **Docker:** 26.x+
- **Docker Compose:** v2.x+
- **NVIDIA Driver:** 535+ (برای GPU)
- **NVIDIA Container Toolkit** (برای GPU)
- **Git:** 2.x+

### نصب درایور NVIDIA (Ubuntu)

```bash
# نصب درایور
sudo apt install -y nvidia-driver-535 cuda-toolkit-12-3

# نصب NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# تأیید نصب
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi
```

---

## نصب سریع

```bash
# ۱. دریافت کد
git clone https://github.com/nargestabatabaii679/avatar-realtime.git
cd avatar-realtime

# ۲. اجرای اسکریپت نصب تعاملی
chmod +x scripts/setup/install.sh
./scripts/setup/install.sh

# ۳. مرورگر را باز کنید
open http://localhost:3000
```

### آدرس‌های سرویس‌ها پس از نصب

| سرویس | آدرس |
|-------|------|
| 🖥️ رابط کاربری | http://localhost:3000 |
| ⚡ Backend API | http://localhost:8000 |
| 📖 مستندات API (Swagger) | http://localhost:8000/api/docs |
| 🗄️ MinIO Console | http://localhost:9001 |
| 🌸 Flower (Celery Monitor) | http://localhost:5555 |
| 📊 Grafana Dashboard | http://localhost:3001 |
| 📈 Prometheus | http://localhost:9090 |

---

## نصب گام‌به‌گام

### گام ۱ — آماده‌سازی سیستم

```bash
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER && newgrp docker
sudo apt install -y docker-compose-plugin
docker --version && docker compose version
```

### گام ۲ — Clone کردن پروژه

```bash
git clone https://github.com/nargestabatabaii679/avatar-realtime.git
cd avatar-realtime
```

### گام ۳ — تنظیم متغیرهای محیطی

```bash
cp .env.example .env
```

حداقل مقادیر ضروری را تنظیم کنید:

```bash
# کلید رمزنگاری (حتماً تغییر دهید)
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# رمز دیتابیس
POSTGRES_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

# رمز MinIO
MINIO_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

# کلید OpenAI (اختیاری)
OPENAI_API_KEY=sk-...
```

### گام ۴ — دانلود مدل‌های AI

```bash
mkdir -p models/{liveportrait,musetalk,wav2lip,whisper,xtts-v2,insightface}
docker compose run --rm backend python scripts/setup/download_models.py
# حجم: ~14 GB · زمان: بسته به سرعت اینترنت
```

### گام ۵ — راه‌اندازی سرویس‌ها

```bash
docker compose up -d
docker compose ps         # بررسی وضعیت
docker compose logs -f backend
```

### گام ۶ — راه‌اندازی دیتابیس

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/setup/init_db.py \
  --admin-email admin@yourcompany.com \
  --admin-password "YourSecurePassword123!" \
  --org-name "نام سازمان شما"
```

### گام ۷ — تأیید نصب

```bash
curl http://localhost:8000/health/ready
# {"status": "ready", "database": "connected", "redis": "connected", "minio": "connected"}
```

---

## متغیرهای محیطی

| متغیر | اجباری | پیش‌فرض | توضیح |
|-------|--------|---------|-------|
| `SECRET_KEY` | ✅ | — | کلید امضای JWT (حداقل ۳۲ کاراکتر) |
| `POSTGRES_PASSWORD` | ✅ | — | رمز دیتابیس PostgreSQL |
| `MINIO_SECRET_KEY` | ✅ | — | رمز ذخیره‌سازی MinIO |
| `REDIS_URL` | ✅ | `redis://redis:6379/0` | آدرس Redis |
| `QDRANT_HOST` | ✅ | `qdrant` | آدرس Qdrant |
| `CORS_ORIGINS` | ✅ | `["http://localhost:3000"]` | دامنه‌های مجاز CORS |
| `OPENAI_API_KEY` | ❌ | — | کلید OpenAI برای GPT-4 |
| `DEEPSEEK_API_KEY` | ❌ | — | کلید DeepSeek |
| `CUDA_VISIBLE_DEVICES` | ❌ | `0` | شماره GPU |
| `WHISPER_MODEL_SIZE` | ❌ | `large-v3` | سایز مدل Whisper |
| `ANIMATION_ENGINE` | ❌ | `liveportrait` | موتور انیمیشن |
| `TTS_ENGINE` | ❌ | `xtts` | موتور TTS |
| `LLM_PROVIDER` | ❌ | `openai` | ارائه‌دهنده LLM |
| `SENTRY_DSN` | ❌ | — | DSN ردیابی خطا |

---

## ساختار پروژه

```
avatar-realtime/
│
├── backend/                          # اپلیکیشن FastAPI
│   ├── app/
│   │   ├── api/v1/endpoints/         # اندپوینت‌های REST API
│   │   │   ├── auth.py               # ورود، خروج، ثبت‌نام، تجدید توکن
│   │   │   ├── avatars.py            # مدیریت آواتار
│   │   │   ├── voices.py             # مدیریت صدا و کلون
│   │   │   ├── videos.py             # تولید ویدیو
│   │   │   ├── agents.py             # Agent Builder
│   │   │   ├── knowledge.py          # پایگاه دانش RAG
│   │   │   ├── realtime.py           # WebSocket بلادرنگ
│   │   │   ├── analytics.py          # آمار و تحلیل
│   │   │   ├── admin.py              # پنل مدیریت
│   │   │   ├── users.py              # مدیریت کاربران
│   │   │   ├── organizations.py      # مدیریت سازمان (Multi-tenant)
│   │   │   └── health.py             # بررسی سلامت سیستم
│   │   │
│   │   ├── core/                     # هسته اصلی
│   │   │   ├── config.py             # تنظیمات (Pydantic Settings v2)
│   │   │   ├── database.py           # اتصال async PostgreSQL
│   │   │   ├── security.py           # JWT، bcrypt، RBAC
│   │   │   ├── redis_client.py       # کلاینت Redis
│   │   │   ├── celery_app.py         # تنظیمات Celery
│   │   │   └── logging.py            # لاگینگ ساختاریافته
│   │   │
│   │   ├── ml/                       # ماژول‌های AI
│   │   │   ├── avatar/               # LivePortrait، Wav2Lip، InsightFace
│   │   │   ├── voice/                # XTTS-v2، CosyVoice، Whisper
│   │   │   ├── lip_sync/             # MuseTalk
│   │   │   ├── llm/                  # Router برای OpenAI/DeepSeek/Ollama
│   │   │   └── rag/                  # Document Processor، Embedder، Qdrant، RAG Chain
│   │   │
│   │   ├── models/                   # مدل‌های SQLAlchemy ORM
│   │   ├── schemas/                  # اسکیماهای Pydantic
│   │   ├── services/                 # MinIO Storage، WebRTC Streaming
│   │   ├── workers/                  # Celery Tasks (GPU/CPU)
│   │   ├── utils/                    # ابزارهای کمکی (persian_utils، video_utils)
│   │   └── main.py                   # نقطه ورود FastAPI
│   │
│   ├── alembic/                      # Migration دیتابیس
│   ├── tests/                        # مجموعه تست pytest
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                         # اپلیکیشن React
│   └── src/
│       ├── pages/                    # ۹ صفحه اصلی
│       │   ├── dashboard/            # داشبورد با آمار زنده
│       │   ├── auth/                 # صفحه ورود
│       │   ├── avatar-studio/        # استودیوی آواتار
│       │   ├── voice-studio/         # استودیوی صدا
│       │   ├── video-studio/         # استودیوی ویدیو
│       │   ├── agent-builder/        # سازنده Agent
│       │   ├── knowledge-center/     # مرکز دانش
│       │   ├── realtime/             # مکالمه بلادرنگ
│       │   ├── analytics/            # آنالیتیکس
│       │   └── admin/                # پنل مدیریت
│       ├── components/layout/        # AppLayout، Sidebar، Header
│       ├── stores/                   # Zustand (auth، theme، notifications)
│       ├── services/                 # API Client (axios)، WebSocket
│       ├── hooks/                    # React Query hooks
│       ├── types/                    # TypeScript types
│       ├── utils/                    # cn، format، rtl
│       └── styles/globals.css        # سیستم طراحی کامل
│
├── infrastructure/
│   ├── nginx/                        # تنظیمات Reverse Proxy
│   ├── kubernetes/                   # K8s Manifests (base + production)
│   └── monitoring/                   # Prometheus + Grafana
│
├── scripts/
│   ├── setup/                        # install.sh، init_db.py، download_models.py
│   └── backup/                       # backup.sh
│
├── docs/                             # مستندات کامل
├── .github/workflows/                # CI/CD (ci.yml، cd.yml)
├── docker-compose.yml
└── .env.example
```

---

## مستندات API

مستندات کامل API به صورت خودکار توسط FastAPI تولید می‌شود:

- **Swagger UI:** `http://localhost:8000/api/docs`
- **ReDoc:** `http://localhost:8000/api/redoc`
- **OpenAPI JSON:** `http://localhost:8000/api/openapi.json`

### اندپوینت‌های اصلی

| روش | مسیر | توضیح |
|-----|------|-------|
| `POST` | `/api/v1/auth/login` | ورود و دریافت JWT |
| `POST` | `/api/v1/auth/refresh` | تجدید Access Token |
| `GET/POST` | `/api/v1/avatars` | لیست/ساخت آواتار |
| `GET/POST` | `/api/v1/voices` | لیست/کلون صدا |
| `GET/POST` | `/api/v1/videos` | لیست/تولید ویدیو |
| `GET/POST` | `/api/v1/agents` | مدیریت Agent |
| `GET/POST` | `/api/v1/knowledge` | پایگاه دانش RAG |
| `WS` | `/api/v1/realtime/{session_id}` | WebSocket مکالمه بلادرنگ |
| `GET` | `/api/v1/analytics/dashboard` | داشبورد آمار |
| `GET` | `/health/ready` | بررسی سلامت |

### نمونه استفاده

```bash
# دریافت توکن
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"password"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# لیست آواتارها
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/avatars

# ساخت آواتار جدید
curl -X POST http://localhost:8000/api/v1/avatars \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@photo.jpg" \
  -F "name=آواتار من" \
  -F "source_type=photo"
```

---

## استقرار تولیدی

### گزینه A — Docker Compose (سرور تکی)

```bash
docker compose -f docker-compose.yml up -d

# تنظیم SSL با Let's Encrypt
sudo certbot certonly --standalone -d avatar.yourdomain.com

# تمدید خودکار
echo "0 0 1 * * certbot renew && docker compose exec nginx nginx -s reload" | crontab -
```

### گزینه B — Kubernetes (Enterprise)

```bash
# نصب NVIDIA GPU Operator
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm install gpu-operator nvidia/gpu-operator

# استقرار
kubectl apply -k infrastructure/kubernetes/base/
kubectl apply -k infrastructure/kubernetes/overlays/production/

kubectl get pods -n avatar-platform
kubectl get ingress -n avatar-platform
```

### توپولوژی‌های پیشنهادی

| محیط | پیکربندی |
|------|----------|
| **توسعه** | ۱ سرور · docker-compose · ۳۲GB RAM · ۱x RTX 4090 · ۲TB SSD |
| **تولیدی** | Load Balancer × ۲ · API Servers × ۳ · GPU Workers × ۲-۴ · DB Primary + ۲ Replica |
| **Enterprise** | Kubernetes · CPU Nodes × ۳-۱۰ (auto-scale) · GPU Nodes × ۱-۴ |

---

## امنیت

### لایه‌های احراز هویت و مجوز

1. **JWT (RS256)** — همه اندپوینت‌ها نیاز به توکن معتبر دارند
2. **RBAC** — نقش‌ها: `super_admin` > `admin` > `manager` > `creator` > `viewer`
3. **Organization Scoping** — کاربران فقط به منابع سازمان خود دسترسی دارند
4. **Resource Ownership** — سازندگان فقط منابع خودشان را تغییر می‌دهند
5. **API Key** — برای دسترسی برنامه‌نویسی (Hash شده در DB)

### چک‌لیست امنیتی تولیدی

- [ ] `SECRET_KEY` تصادفی ۳۲+ کاراکتری تنظیم شود
- [ ] رمز قوی برای PostgreSQL و MinIO استفاده شود
- [ ] `CORS_ORIGINS` فقط به دامنه‌های واقعی محدود شود
- [ ] SSL/TLS روی Nginx فعال شود
- [ ] Firewall: فقط پورت‌های 80/443 از خارج
- [ ] پورت‌های داخلی (5432، 6379، 9000) بسته باشند
- [ ] `DEBUG=False` در محیط تولیدی
- [ ] Sentry برای ردیابی خطا فعال شود

مستندات کامل: [SECURITY_CHECKLIST.md](docs/deployment/SECURITY_CHECKLIST.md)

---

## مانیتورینگ

| داشبورد | آدرس | اعتبارنامه پیش‌فرض |
|---------|------|-------------------|
| Grafana | http://server:3001 | admin/admin |
| Prometheus | http://server:9090 | — |
| Flower (Celery) | http://server:5555 | — |
| API Docs | http://server:8000/api/docs | — |

```bash
# مانیتور GPU
watch -n 1 nvidia-smi

# مانیتور لاگ‌ها
docker compose logs -f backend
docker compose logs -f worker-gpu

# مانیتور منابع
docker stats
```

---

## پشتیبان‌گیری

```bash
# پشتیبان‌گیری دستی
./scripts/backup/backup.sh

# پشتیبان‌گیری خودکار (هر شب ساعت ۲)
echo "0 2 * * * /opt/avatar-realtime/scripts/backup/backup.sh" | crontab -

# فایل‌های پشتیبان: /opt/backups/avatar-platform/
# فرمت: avatar-platform-YYYYMMDD-HHMMSS.tar.gz.gpg
```

---

## رفع مشکلات

### GPU شناسایی نمی‌شود

```bash
docker info | grep -i runtime
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi
# در صورت خطا:
sudo systemctl restart docker
```

### حافظه GPU پر می‌شود (OOM)

```bash
# کاهش batch size در .env
AVATAR_BATCH_SIZE=1
VIDEO_BATCH_FRAMES=30

# پاک‌سازی دستی
docker compose exec worker-gpu python -c "import torch; torch.cuda.empty_cache()"
```

### مشکل اتصال دیتابیس

```bash
docker compose logs postgres
docker compose exec backend python -c "
from app.core.database import engine
import asyncio
async def test():
    async with engine.connect() as conn:
        result = await conn.execute('SELECT 1')
        print('DB OK:', result.scalar())
asyncio.run(test())
"
```

### مشکل MinIO

```bash
curl http://localhost:9000/minio/health/live
docker compose exec minio mc ls local/
```

---

## زبان‌های پشتیبانی‌شده

| زبان | RTL | TTS (صدا) | STT (تشخیص گفتار) |
|------|-----|-----------|-------------------|
| 🇮🇷 فارسی (Persian) | ✅ | ✅ | ✅ |
| 🇸🇦 عربی (Arabic) | ✅ | ✅ | ✅ |
| 🇺🇸 انگلیسی (English) | — | ✅ | ✅ |
| 🇹🇷 ترکی (Turkish) | — | ✅ | ✅ |
| 🇫🇷 فرانسوی (Français) | — | ✅ | ✅ |
| 🇩🇪 آلمانی (Deutsch) | — | ✅ | ✅ |
| 🇪🇸 اسپانیایی (Español) | — | ✅ | ✅ |

پشتیبانی کامل RTL (راست‌به‌چپ) برای فارسی و عربی در رابط کاربری، فونت و چیدمان.

---

## مستندات بیشتر

- 📥 [راهنمای نصب کامل](docs/deployment/INSTALLATION.md)
- 🏗️ [معماری سیستم](docs/architecture/ARCHITECTURE.md)
- 📡 [مستندات API](docs/api/API_DOCUMENTATION.md)
- 🔒 [چک‌لیست امنیتی](docs/deployment/SECURITY_CHECKLIST.md)
- 📊 [راهنمای مانیتورینگ](docs/deployment/MONITORING.md)

---

## لایسنس

لایسنس تجاری — برای قیمت‌گذاری Enterprise با ما تماس بگیرید:

📧 support@avatarplatform.com

---

<div align="center">

ساخته شده با ❤️ برای ارتباطات هوشمند چندزبانه

**[نصب سریع](#نصب-سریع)** · **[مستندات API](#مستندات-api)** · **[معماری](#معماری-سیستم)**

</div>
</div>
