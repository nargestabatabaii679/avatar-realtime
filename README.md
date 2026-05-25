# AI Digital Human Platform

<div align="center">

**پلتفرم خودمیزبان آواتار دیجیتال هوشمند با قابلیت مکالمه بلادرنگ**

یک پلتفرم کامل، GPU-محور و self-hosted برای ساخت، آموزش و استقرار آواتارهای واقعی گویا — رقیب مستقیم HeyGen، Synthesia، D-ID، Tavus و Elai

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react)](https://react.dev)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6?style=flat-square&logo=typescript)](https://typescriptlang.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker)](https://docker.com)
[![License](https://img.shields.io/badge/License-Commercial-red?style=flat-square)](mailto:support@avatarplatform.com)

</div>

---

## فهرست مطالب

- [معرفی پلتفرم](#معرفی-پلتفرم)
- [قابلیت‌های اصلی](#قابلیتهای-اصلی)
- [معماری سیستم](#معماری-سیستم)
- [استک فناوری](#استک-فناوری)
- [مدل‌های هوش مصنوعی](#مدلهای-هوش-مصنوعی)
- [پیش‌نیازها](#پیشنیازها)
- [نصب سریع](#نصب-سریع)
- [نصب مرحله به مرحله](#نصب-مرحله-به-مرحله)
- [متغیرهای محیطی](#متغیرهای-محیطی)
- [ساختار پروژه](#ساختار-پروژه)
- [API Documentation](#api-documentation)
- [استقرار تولیدی](#استقرار-تولیدی)
- [مانیتورینگ](#مانیتورینگ)
- [پشتیبان‌گیری](#پشتیبانگیری)
- [رفع مشکلات](#رفع-مشکلات)
- [زبان‌های پشتیبانی شده](#زبانهای-پشتیبانی-شده)
- [مشارکت](#مشارکت)
- [لایسنس](#لایسنس)

---

## معرفی پلتفرم

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Avatar Studio │ Voice Studio │ Video Studio │ Agent Builder │  Analytics   │
├─────────────────────────────────────────────────────────────────────────────┤
│        React 19 · TypeScript · TailwindCSS · Shadcn UI · RTL (fa/ar)        │
├─────────────────────────────────────────────────────────────────────────────┤
│              FastAPI · Python 3.12 · Celery · JWT Auth (RS256)               │
├───────────────────────────────────┬─────────────────────────────────────────┤
│  PostgreSQL 16 · Redis 7 · Qdrant │   MinIO · FFmpeg · WebRTC · WebSocket   │
├───────────────────────────────────┴─────────────────────────────────────────┤
│  LivePortrait · MuseTalk · XTTS-v2 · Whisper v3 · InsightFace · E5-large    │
└─────────────────────────────────────────────────────────────────────────────┘
```

این پلتفرم به شما اجازه می‌دهد آواتارهای دیجیتال واقع‌گرایانه بسازید که می‌توانند:
- با صدای کلون‌شده صحبت کنند
- به صورت بلادرنگ با کاربران مکالمه کنند
- از پایگاه دانش سفارشی پاسخ دهند
- ویدیوهای حرفه‌ای با لیپ سینک دقیق تولید کنند

---

## قابلیت‌های اصلی

| ماژول | قابلیت‌ها |
|-------|-----------|
| **Avatar Studio** | آپلود عکس/ویدیو/وبکم → تشخیص چهره → Embedding → ثامبنیل خودکار |
| **Voice Studio** | کلون صدا در ۷ زبان با XTTS-v2 · کیفیت استودیویی · تشخیص زبان خودکار |
| **Video Studio** | تولید ویدیوی گویا (720p/1080p/4K) · لیپ سینک دقیق · خروجی MP4 |
| **Agent Builder** | ساخت AI Agent سفارشی · پایگاه دانش RAG · شخصیت‌پردازی · انتخاب LLM |
| **Knowledge Base** | RAG با PDF/DOCX/URL · جستجوی معنایی · پایگاه Qdrant |
| **Real-Time** | تأخیر < 1.2 ثانیه · WebSocket + WebRTC · VAD هوشمند |
| **Analytics** | متریک‌های GPU · آمار مصرف · صادرات CSV · داشبورد زنده |
| **Admin Portal** | مدیریت کاربران · کنترل jobها · لاگ audit · سلامت سیستم |

---

## معماری سیستم

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLIENTS                                  │
│     Web Browser │ Mobile │ 86" Touchscreen │ API Consumers        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS / WSS / WebRTC
┌──────────────────────────▼──────────────────────────────────────┐
│                    NGINX (Reverse Proxy)                          │
│          TLS Termination │ Rate Limiting │ Load Balance           │
└──────┬───────────────────────────────────┬───────────────────────┘
       │                                   │
┌──────▼──────┐                   ┌────────▼────────┐
│  Frontend   │                   │   Backend API    │
│  React 19   │                   │  FastAPI 0.111   │
│  TypeScript │                   │  Python 3.12     │
│  Vite 6     │                   │  Uvicorn         │
│  Port 3000  │                   │  Port 8000       │
└─────────────┘                   └────────┬────────┘
                                           │
          ┌────────────────────────────────┼────────────────────────┐
          │                                │                         │
┌─────────▼──────┐              ┌──────────▼──────┐      ┌─────────▼──────┐
│  PostgreSQL 16 │              │    Redis 7       │      │    Qdrant       │
│  (Primary DB)  │              │  Cache + Queue   │      │  Vector DB      │
│   Port 5432    │              │   Port 6379      │      │   Port 6333     │
└────────────────┘              └─────────────────┘      └────────────────┘
                                           │
                                ┌──────────▼──────────────────────────┐
                                │         Celery Workers               │
                                │  ┌─────────────┐  ┌──────────────┐  │
                                │  │ GPU Worker  │  │  CPU Worker  │  │
                                │  │ Avatar/TTS/ │  │  Documents/  │  │
                                │  │ Video tasks │  │  Analytics   │  │
                                │  └──────┬──────┘  └──────────────┘  │
                                └─────────┼────────────────────────────┘
                                          │
                          ┌───────────────▼───────────────────────┐
                          │            AI/ML Models                │
                          │  LivePortrait │ MuseTalk               │
                          │  Wav2Lip      │ InsightFace            │
                          │  Whisper V3   │ XTTS-v2               │
                          │  CosyVoice    │ E5-Multilingual        │
                          │  GPT-4o       │ DeepSeek / Llama       │
                          └───────────────────────────────────────┘
                                          │
                          ┌───────────────▼───────────────────────┐
                          │            MinIO Storage               │
                          │  Avatars │ Voices │ Videos │ Documents │
                          └───────────────────────────────────────┘
```

### پایپ‌لاین تولید ویدیو

```
درخواست (avatar_id + voice_id + متن + رزولوشن)
    ↓
ساخت Job و اعتبارسنجی
    ↓
Celery Pipeline Task
    ├── مرحله ۱: سنتز TTS (XTTS-v2)  → متن به صدا (WAV 24kHz)
    ├── مرحله ۲: لیپ سینک (LivePortrait/Wav2Lip)  → آواتار + صدا → فریم‌های انیمیشن
    ├── مرحله ۳: ترکیب ویدیو (FFmpeg)  → فریم‌ها → MP4
    └── مرحله ۴: پس‌پردازش  → ثامبنیل + متادیتا + نوتیفیکیشن
    ↓
ویدیو آماده دانلود/استریم
```

### پایپ‌لاین مکالمه بلادرنگ

```
استریم صدای کاربر (WebRTC/WebSocket)
    ↓
VAD (Voice Activity Detection)
    ↓
Whisper Large V3 (STT) — ~300ms
    ↓
LLM Processing (GPT-4o/DeepSeek/Llama) — ~500ms
    ↓
XTTS-v2 Synthesis — ~200ms (اولین chunk)
    ↓
MuseTalk Lip Sync (streaming) — ~100ms/frame
    ↓
WebRTC Video Stream → کاربر
هدف تأخیر کل: < 1200ms
```

---

## استک فناوری

### Frontend

| فناوری | نسخه | کاربرد |
|--------|------|--------|
| React | 19 | UI Framework |
| TypeScript | 5.7 | Type Safety |
| Vite | 6 | Build Tool |
| TailwindCSS | 4 | Styling |
| Shadcn UI / Radix | latest | Component Library |
| Framer Motion | 12 | Animations |
| TanStack Query | 5 | Server State Management |
| Zustand | 5 | Client State Management |
| React Hook Form + Zod | 7/3 | Form Validation |
| Socket.IO Client | 4 | WebSocket |
| Simple Peer | 9 | WebRTC |
| Recharts | 2 | Charts & Analytics |
| i18next | 24 | Internationalization |
| WaveSurfer.js | 7 | Audio Visualization |

### Backend

| فناوری | نسخه | کاربرد |
|--------|------|--------|
| FastAPI | 0.111 | REST API + WebSocket |
| Python | 3.12 | Runtime |
| SQLAlchemy (async) | 2.0 | ORM |
| Alembic | 1.13 | Database Migrations |
| Celery | 5.4 | Task Queue |
| Pydantic v2 | 2.7 | Data Validation |
| python-jose | 3.3 | JWT Authentication |
| passlib + bcrypt | 1.7 | Password Hashing |
| Uvicorn | 0.30 | ASGI Server |
| structlog | 24 | Structured Logging |

### Databases & Storage

| سرویس | نسخه | کاربرد |
|-------|------|--------|
| PostgreSQL | 16 | Primary Database |
| Redis | 7 | Cache + Celery Broker |
| Qdrant | latest | Vector Database (RAG) |
| MinIO | latest | Object Storage (S3-compatible) |

### Infrastructure

| ابزار | کاربرد |
|-------|--------|
| Docker + Docker Compose | Containerization |
| Nginx | Reverse Proxy + TLS |
| Kubernetes | Enterprise Orchestration |
| Prometheus | Metrics Collection |
| Grafana | Visualization Dashboards |
| Loki | Log Aggregation |
| Sentry | Error Tracking |

---

## مدل‌های هوش مصنوعی

| مؤلفه | مدل اصلی | مدل جایگزین | حجم تقریبی |
|-------|---------|------------|------------|
| انیمیشن آواتار | LivePortrait | Wav2Lip | ~4 GB |
| لیپ سینک بلادرنگ | MuseTalk | Wav2Lip | ~3 GB |
| کلون صدا (TTS) | XTTS-v2 | CosyVoice | ~2 GB |
| تشخیص گفتار (STT) | Whisper Large V3 | — | ~3 GB |
| تحلیل چهره | InsightFace buffalo_l | MediaPipe | ~500 MB |
| LLM | OpenAI GPT-4o | DeepSeek / Ollama (Llama) | — |
| Embeddings | multilingual-e5-large | OpenAI text-embedding-3-small | ~600 MB |

> مجموع حجم مدل‌ها: **~13-14 GB** (بدون LLM محلی)

---

## پیش‌نیازها

### سخت‌افزار

| مؤلفه | حداقل | پیشنهادی | Enterprise |
|-------|-------|---------|------------|
| CPU | 8 هسته | 16 هسته | 32+ هسته |
| RAM | 32 GB | 64 GB | 128+ GB |
| GPU | RTX 3080 (10GB VRAM) | RTX 4090 (24GB VRAM) | A100 (80GB) |
| Storage | 500 GB SSD | 2 TB NVMe | 10+ TB RAID |
| Network | 100 Mbps | 1 Gbps | 10 Gbps |

> **توجه**: GPU اختیاری است اما بدون آن سرعت تولید ویدیو و مکالمه بلادرنگ به شدت کاهش می‌یابد.

### نرم‌افزار

- **OS**: Ubuntu 22.04 LTS یا RHEL 9 (پیشنهادی)
- **Docker**: 26.x+
- **Docker Compose**: v2.x+
- **NVIDIA Driver**: 535+ (برای GPU)
- **NVIDIA Container Toolkit** (برای GPU)
- **Git**: 2.x+

### نصب درایور NVIDIA (Ubuntu)

```bash
# اضافه کردن repository NVIDIA
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update

# نصب درایور
sudo apt install -y nvidia-driver-535
sudo apt install -y cuda-toolkit-12-3

# نصب NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
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
# ۱. Clone کردن مخزن
git clone https://github.com/nargestabatabaii679/avatar-realtime.git
cd avatar-realtime

# ۲. اجرای اسکریپت نصب
chmod +x scripts/setup/install.sh
./scripts/setup/install.sh

# ۳. باز کردن مرورگر
open http://localhost:3000
```

پس از نصب، سرویس‌های زیر در دسترس خواهند بود:

| سرویس | آدرس |
|-------|------|
| Frontend (رابط کاربری) | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| MinIO Console | http://localhost:9001 |
| Flower (Celery Monitor) | http://localhost:5555 |
| Grafana Dashboard | http://localhost:3001 |
| Prometheus | http://localhost:9090 |

---

## نصب مرحله به مرحله

### مرحله ۱: آماده‌سازی سیستم

```bash
# بروزرسانی سیستم
sudo apt update && sudo apt upgrade -y

# نصب Docker
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER
newgrp docker

# نصب Docker Compose
sudo apt install -y docker-compose-plugin

# تأیید نصب
docker --version
docker compose version
```

### مرحله ۲: Clone کردن پروژه

```bash
git clone https://github.com/nargestabatabaii679/avatar-realtime.git
cd avatar-realtime
```

### مرحله ۳: تنظیم متغیرهای محیطی

```bash
cp .env.example .env
nano .env
```

مقادیر ضروری:
```bash
# کلید رمزنگاری JWT (حتماً تغییر دهید)
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# رمز دیتابیس
POSTGRES_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

# رمز MinIO
MINIO_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

# کلید OpenAI (اختیاری - برای GPT-4)
OPENAI_API_KEY=sk-...

# DSN خطایابی Sentry (اختیاری)
SENTRY_DSN=https://...@sentry.io/...
```

### مرحله ۴: دانلود مدل‌های هوش مصنوعی

```bash
# ساخت دایرکتوری مدل‌ها
mkdir -p models/{liveportrait,musetalk,wav2lip,whisper,xtts-v2,insightface}

# دانلود مدل‌ها (~14 GB)
docker compose run --rm backend python scripts/setup/download_models.py
```

### مرحله ۵: راه‌اندازی سرویس‌ها

```bash
# اجرای همه سرویس‌ها
docker compose up -d

# بررسی وضعیت
docker compose ps

# مشاهده لاگ‌ها
docker compose logs -f backend
docker compose logs -f worker-gpu
```

### مرحله ۶: راه‌اندازی دیتابیس

```bash
# اجرای migrations
docker compose exec backend alembic upgrade head

# ساخت ادمین اولیه
docker compose exec backend python scripts/setup/init_db.py \
  --admin-email admin@yourcompany.com \
  --admin-password "YourSecurePassword123!" \
  --org-name "نام سازمان شما"
```

### مرحله ۷: تأیید نصب

```bash
# بررسی سلامت API
curl http://localhost:8000/health/ready
# خروجی مورد انتظار: {"status": "ready", "database": "connected", "redis": "connected", "minio": "connected"}

# بررسی GPU
curl http://localhost:8000/health/gpu

# بررسی Frontend
curl -I http://localhost:3000
```

---

## متغیرهای محیطی

| متغیر | اجباری | مقدار پیش‌فرض | توضیح |
|-------|--------|--------------|-------|
| `SECRET_KEY` | بله | — | کلید امضای JWT (حداقل ۳۲ کاراکتر) |
| `POSTGRES_HOST` | بله | `postgres` | آدرس PostgreSQL |
| `POSTGRES_PASSWORD` | بله | — | رمز دیتابیس |
| `REDIS_URL` | بله | `redis://redis:6379/0` | آدرس Redis |
| `MINIO_ENDPOINT` | بله | `minio:9000` | آدرس MinIO |
| `MINIO_ACCESS_KEY` | بله | — | کلید دسترسی MinIO |
| `MINIO_SECRET_KEY` | بله | — | رمز MinIO |
| `QDRANT_HOST` | بله | `qdrant` | آدرس Qdrant |
| `OPENAI_API_KEY` | خیر | — | کلید OpenAI برای GPT-4 |
| `DEEPSEEK_API_KEY` | خیر | — | کلید DeepSeek |
| `CORS_ORIGINS` | بله | `["http://localhost:3000"]` | دامنه‌های مجاز CORS |
| `CUDA_VISIBLE_DEVICES` | خیر | `0` | شماره GPU |
| `WHISPER_MODEL_SIZE` | خیر | `large-v3` | سایز مدل Whisper |
| `ANIMATION_ENGINE` | خیر | `liveportrait` | موتور انیمیشن (`liveportrait` یا `wav2lip`) |
| `TTS_ENGINE` | خیر | `xtts` | موتور TTS (`xtts` یا `cosyvoice`) |
| `LLM_PROVIDER` | خیر | `openai` | ارائه‌دهنده LLM (`openai`, `deepseek`, `ollama`) |
| `SENTRY_DSN` | خیر | — | DSN خطایابی Sentry |

---

## ساختار پروژه

```
avatar-realtime/
│
├── backend/                          # اپلیکیشن FastAPI
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── endpoints/        # اندپوینت‌های REST API
│   │   │       │   ├── auth.py       # ورود/خروج/ثبت‌نام
│   │   │       │   ├── avatars.py    # مدیریت آواتار
│   │   │       │   ├── voices.py     # مدیریت صدا
│   │   │       │   ├── videos.py     # تولید ویدیو
│   │   │       │   ├── agents.py     # Agent Builder
│   │   │       │   ├── knowledge.py  # پایگاه دانش RAG
│   │   │       │   ├── realtime.py   # WebSocket بلادرنگ
│   │   │       │   ├── analytics.py  # آمار و تحلیل
│   │   │       │   ├── admin.py      # پنل ادمین
│   │   │       │   ├── users.py      # مدیریت کاربران
│   │   │       │   ├── organizations.py # مدیریت سازمان
│   │   │       │   └── health.py     # بررسی سلامت سیستم
│   │   │       └── router.py
│   │   │
│   │   ├── core/                     # هسته اصلی
│   │   │   ├── config.py             # تنظیمات کلی (Pydantic Settings)
│   │   │   ├── database.py           # اتصال async به PostgreSQL
│   │   │   ├── security.py           # JWT، bcrypt، RBAC
│   │   │   ├── redis_client.py       # کلاینت Redis
│   │   │   ├── celery_app.py         # تنظیمات Celery
│   │   │   └── logging.py            # لاگینگ ساختاریافته
│   │   │
│   │   ├── ml/                       # ماژول‌های هوش مصنوعی
│   │   │   ├── avatar/
│   │   │   │   ├── face_analyzer.py  # InsightFace
│   │   │   │   ├── live_portrait.py  # LivePortrait Animation
│   │   │   │   └── wav2lip.py        # Wav2Lip Fallback
│   │   │   ├── voice/
│   │   │   │   ├── xtts_engine.py    # XTTS-v2 TTS
│   │   │   │   ├── cosyvoice_engine.py # CosyVoice TTS
│   │   │   │   └── whisper_stt.py    # Whisper STT
│   │   │   ├── lip_sync/
│   │   │   │   └── muse_talk.py      # MuseTalk Real-time Lip Sync
│   │   │   ├── llm/
│   │   │   │   └── llm_router.py     # Router برای OpenAI/DeepSeek/Ollama
│   │   │   └── rag/
│   │   │       ├── document_processor.py # پردازش PDF/DOCX/URL
│   │   │       ├── embedder.py       # تولید embedding
│   │   │       ├── qdrant_store.py   # ذخیره‌سازی وکتور
│   │   │       └── rag_chain.py      # زنجیره RAG با LangChain
│   │   │
│   │   ├── models/                   # مدل‌های SQLAlchemy ORM
│   │   │   ├── user.py               # کاربران
│   │   │   ├── organization.py       # سازمان‌ها (Multi-tenant)
│   │   │   ├── avatar.py             # آواتارها
│   │   │   ├── voice_model.py        # مدل‌های صدا
│   │   │   ├── video.py              # ویدیوها
│   │   │   ├── video_job.py          # Job‌های ویدیو
│   │   │   ├── agent.py              # Agentها
│   │   │   ├── knowledge_base.py     # پایگاه دانش
│   │   │   ├── document.py           # اسناد
│   │   │   ├── conversation.py       # مکالمات
│   │   │   ├── analytics.py          # آمار
│   │   │   ├── audit_log.py          # لاگ حسابرسی
│   │   │   ├── subscription.py       # اشتراک‌ها
│   │   │   └── base.py               # مدل پایه
│   │   │
│   │   ├── schemas/                  # اسکیماهای Pydantic
│   │   │   ├── user.py
│   │   │   ├── avatar.py
│   │   │   ├── voice.py
│   │   │   ├── video.py
│   │   │   ├── agent.py
│   │   │   ├── knowledge.py
│   │   │   └── analytics.py
│   │   │
│   │   ├── services/
│   │   │   └── storage/
│   │   │       └── minio_service.py  # سرویس Object Storage
│   │   │
│   │   ├── workers/                  # Celery Tasks
│   │   │   ├── avatar_tasks.py       # پردازش آواتار (GPU)
│   │   │   ├── voice_tasks.py        # کلون صدا (GPU)
│   │   │   ├── video_tasks.py        # تولید ویدیو (GPU)
│   │   │   └── knowledge_tasks.py    # پردازش اسناد (CPU)
│   │   │
│   │   ├── utils/
│   │   │   ├── persian_utils.py      # ابزارهای متن فارسی
│   │   │   └── video_utils.py        # ابزارهای FFmpeg
│   │   │
│   │   └── main.py                   # نقطه ورود FastAPI
│   │
│   ├── alembic/                      # Migration دیتابیس
│   │   ├── versions/
│   │   │   └── 001_initial_schema.py
│   │   └── env.py
│   │
│   ├── tests/
│   │   └── unit/
│   │       ├── test_security.py
│   │       ├── test_schemas.py
│   │       └── test_persian_utils.py
│   │
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── Dockerfile
│
├── frontend/                         # اپلیکیشن React
│   └── src/
│       ├── pages/
│       │   ├── dashboard/            # داشبورد اصلی
│       │   ├── auth/                 # ورود/خروج
│       │   ├── avatar-studio/        # استودیوی آواتار
│       │   ├── voice-studio/         # استودیوی صدا
│       │   ├── video-studio/         # استودیوی ویدیو
│       │   ├── agent-builder/        # ساخت Agent
│       │   ├── knowledge-center/     # مرکز دانش RAG
│       │   ├── realtime/             # مکالمه بلادرنگ
│       │   ├── analytics/            # آمار و تحلیل
│       │   └── admin/                # پنل ادمین
│       ├── components/
│       │   └── layout/               # AppLayout، Header، Sidebar
│       ├── stores/                   # Zustand (auth، theme، notifications)
│       ├── services/                 # API Client، WebSocket
│       ├── hooks/                    # React Query hooks
│       ├── types/                    # TypeScript types
│       ├── utils/                    # cn، format، rtl
│       ├── styles/                   # globals.css
│       └── i18n.ts                   # تنظیمات چندزبانه
│
├── infrastructure/
│   ├── nginx/                        # تنظیمات Reverse Proxy
│   │   ├── nginx.conf
│   │   └── ssl.conf
│   └── monitoring/                   # Prometheus + Grafana
│
├── scripts/
│   ├── setup/
│   │   ├── install.sh                # اسکریپت نصب تعاملی
│   │   ├── init_db.py                # راه‌اندازی دیتابیس
│   │   └── download_models.py        # دانلود مدل‌های AI
│   └── backup/
│       └── backup.sh                 # پشتیبان‌گیری خودکار
│
├── docs/
│   ├── architecture/ARCHITECTURE.md  # معماری سیستم
│   ├── api/API_DOCUMENTATION.md      # مستندات API
│   └── deployment/
│       ├── INSTALLATION.md           # راهنمای نصب کامل
│       ├── MONITORING.md             # راهنمای مانیتورینگ
│       └── SECURITY_CHECKLIST.md     # چک‌لیست امنیتی
│
├── .github/
│   └── workflows/
│       ├── ci.yml                    # CI: تست + lint
│       └── cd.yml                    # CD: build + deploy
│
├── docker-compose.yml                # توسعه محلی
├── docker-compose.override.yml       # override توسعه
├── .env.example                      # نمونه متغیرهای محیطی
└── README.md
```

---

## API Documentation

مستندات کامل API به صورت خودکار توسط FastAPI تولید می‌شود:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

### اندپوینت‌های اصلی

| روش | مسیر | توضیح |
|-----|------|-------|
| `POST` | `/api/v1/auth/login` | ورود با JWT |
| `POST` | `/api/v1/auth/refresh` | تجدید Access Token |
| `GET/POST` | `/api/v1/avatars` | لیست/ساخت آواتار |
| `GET/POST` | `/api/v1/voices` | لیست/کلون صدا |
| `GET/POST` | `/api/v1/videos` | لیست/تولید ویدیو |
| `GET/POST` | `/api/v1/agents` | مدیریت Agent |
| `GET/POST` | `/api/v1/knowledge` | پایگاه دانش RAG |
| `WS` | `/api/v1/realtime/{session_id}` | WebSocket مکالمه |
| `GET` | `/api/v1/analytics/dashboard` | داشبورد آمار |
| `GET` | `/health/ready` | بررسی سلامت |

### احراز هویت

```bash
# ورود و دریافت توکن
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"password"}' \
  | jq -r '.access_token')

# استفاده از توکن
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/avatars
```

---

## استقرار تولیدی

### گزینه A: Docker Compose (سرور تکی)

```bash
# استفاده از فایل production
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# تنظیم SSL با Let's Encrypt
sudo apt install -y certbot
sudo certbot certonly --standalone -d avatarplatform.yourdomain.com

# تمدید خودکار گواهینامه
echo "0 0 1 * * certbot renew && docker compose exec nginx nginx -s reload" | crontab -
```

### گزینه B: Kubernetes (Enterprise)

```bash
# نصب NVIDIA GPU Operator
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm install gpu-operator nvidia/gpu-operator

# اعمال manifests پایه
kubectl apply -k infrastructure/kubernetes/base/

# اعمال overlay تولیدی
kubectl apply -k infrastructure/kubernetes/overlays/production/

# بررسی وضعیت
kubectl get pods -n avatar-platform
kubectl get ingress -n avatar-platform
```

### توپولوژی‌های استقرار

#### سرور تکی (توسعه/کوچک)
```
۱ سرور: همه سرویس‌ها با docker-compose
پیشنهادی: 32GB RAM، 8 هسته CPU، 1x RTX 4090 (24GB VRAM)، 2TB SSD
```

#### چندسروره (تولیدی)
```
Load Balancer (2x برای HA)
API Servers (3x، هر کدام 16GB RAM)
GPU Workers (2-4x، هر کدام با GPU اختصاصی)
Database (Primary + 2 Read Replica)
Redis Cluster (3 گره)
MinIO Cluster (4 گره، distributed)
Qdrant Cluster (3 گره)
```

---

## امنیت

### لایه‌های احراز هویت و مجوز

1. **JWT (RS256)** — همه اندپوینت‌ها نیاز به توکن معتبر دارند
2. **RBAC** — نقش‌ها: `super_admin` > `admin` > `manager` > `creator` > `viewer`
3. **Organization Scoping** — کاربران فقط به منابع سازمان خودشان دسترسی دارند
4. **Resource Ownership** — سازندگان فقط منابع خودشان را تغییر می‌دهند
5. **API Key Auth** — برای دسترسی برنامه‌نویسی (Hash شده در DB)

### چک‌لیست امنیتی تولیدی

- [ ] `SECRET_KEY` را به یک مقدار تصادفی ۳۲+ کاراکتری تغییر دهید
- [ ] `POSTGRES_PASSWORD` قوی تنظیم کنید
- [ ] `MINIO_SECRET_KEY` قوی تنظیم کنید
- [ ] `CORS_ORIGINS` را به دامنه‌های واقعی محدود کنید
- [ ] SSL/TLS را روی Nginx فعال کنید
- [ ] Firewall را پیکربندی کنید (فقط پورت‌های 80/443 باز باشد)
- [ ] پورت‌های داخلی (5432، 6379، 9000) را از دسترسی خارجی ببندید
- [ ] `DEBUG=False` در محیط تولیدی
- [ ] Sentry را برای خطایابی فعال کنید

مستندات کامل: [SECURITY_CHECKLIST.md](docs/deployment/SECURITY_CHECKLIST.md)

---

## مانیتورینگ

| داشبورد | آدرس | اعتبارنامه پیش‌فرض |
|---------|------|-------------------|
| Grafana | http://server:3001 | admin/admin |
| Prometheus | http://server:9090 | — |
| Flower (Celery) | http://server:5555 | — |
| API Docs | http://server:8000/docs | — |

```bash
# بررسی لاگ‌های سرویس‌ها
docker compose logs -f backend
docker compose logs -f worker-gpu
docker compose logs -f nginx

# مانیتور GPU
watch -n 1 nvidia-smi

# مانیتور CPU/RAM
docker stats
```

مستندات کامل: [MONITORING.md](docs/deployment/MONITORING.md)

---

## پشتیبان‌گیری

```bash
# پشتیبان‌گیری دستی
./scripts/backup/backup.sh

# پشتیبان‌گیری خودکار (هر شب ساعت ۲)
echo "0 2 * * * /opt/avatar-realtime/scripts/backup/backup.sh >> /var/log/avatar-backup.log 2>&1" | crontab -

# فایل‌های پشتیبان: /opt/backups/avatar-platform/
# فرمت: avatar-platform-YYYYMMDD-HHMMSS.tar.gz.gpg
```

---

## رفع مشکلات

### GPU شناسایی نمی‌شود

```bash
docker info | grep -i runtime
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi
# اگر خطا داشت:
sudo systemctl restart docker
```

### حافظه GPU پر می‌شود (OOM)

```bash
# کاهش batch size در .env
AVATAR_BATCH_SIZE=1
VIDEO_BATCH_FRAMES=30

# پاک‌سازی دستی حافظه GPU
docker compose exec worker-gpu python -c "import torch; torch.cuda.empty_cache()"
```

### مشکل اتصال به دیتابیس

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

## زبان‌های پشتیبانی شده

| زبان | RTL | TTS | STT |
|------|-----|-----|-----|
| فارسی (Persian) | ✅ | ✅ | ✅ |
| عربی (Arabic) | ✅ | ✅ | ✅ |
| English | — | ✅ | ✅ |
| Turkish | — | ✅ | ✅ |
| Français | — | ✅ | ✅ |
| Deutsch | — | ✅ | ✅ |
| Español | — | ✅ | ✅ |

پشتیبانی کامل RTL برای فارسی و عربی در رابط کاربری.

---

## مستندات

- [راهنمای نصب کامل](docs/deployment/INSTALLATION.md)
- [معماری سیستم](docs/architecture/ARCHITECTURE.md)
- [مستندات API](docs/api/API_DOCUMENTATION.md)
- [چک‌لیست امنیتی](docs/deployment/SECURITY_CHECKLIST.md)
- [راهنمای مانیتورینگ](docs/deployment/MONITORING.md)

---

## مشارکت

برای مشارکت در توسعه این پروژه:

1. یک Fork بسازید
2. یک branch جدید بسازید (`git checkout -b feature/amazing-feature`)
3. تغییرات خود را commit کنید (`git commit -m 'feat: add amazing feature'`)
4. به branch خود push کنید (`git push origin feature/amazing-feature`)
5. یک Pull Request باز کنید

---

## لایسنس

لایسنس تجاری — برای قیمت‌گذاری Enterprise با ما تماس بگیرید:

📧 support@avatarplatform.com

---

<div align="center">

ساخته شده با ❤️ برای ارتباطات هوشمند چندزبانه

**[نصب](docs/deployment/INSTALLATION.md)** · **[مستندات API](docs/api/API_DOCUMENTATION.md)** · **[معماری](docs/architecture/ARCHITECTURE.md)**

</div>
