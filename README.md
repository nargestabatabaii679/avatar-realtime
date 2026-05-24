# AI Digital Human Platform

A self-hosted, GPU-accelerated platform for creating, training, and deploying realistic talking avatars — rivaling HeyGen, Synthesia, D-ID, Tavus, and Elai.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Avatar Studio │ Voice Studio │ Video Studio │ Agent Builder │ Analytics  │
├─────────────────────────────────────────────────────────────────────────┤
│       React 19 · TypeScript · TailwindCSS · Shadcn UI · RTL (fa/ar)     │
├─────────────────────────────────────────────────────────────────────────┤
│            FastAPI · Python 3.12 · Celery · JWT Auth                     │
├───────────────────────────────────┬─────────────────────────────────────┤
│  PostgreSQL · Redis · Qdrant       │  MinIO · FFmpeg · WebRTC            │
├───────────────────────────────────┴─────────────────────────────────────┤
│  LivePortrait · MuseTalk · XTTS-v2 · Whisper v3 · InsightFace · E5-large │
└─────────────────────────────────────────────────────────────────────────┘
```

## Features

| Module | Capabilities |
|--------|-------------|
| **Avatar Studio** | Upload photo/video/webcam → Face detection → Embedding → Thumbnail |
| **Voice Studio** | Clone voice in 6 languages (fa/en/ar/tr/fr/de) with XTTS-v2 |
| **Video Studio** | Generate talking avatar videos (720p/1080p/4K) with lip sync |
| **Agent Builder** | Create AI agents with custom knowledge, personality, LLM |
| **Knowledge Base** | RAG with PDF/DOCX/URL ingestion + semantic search (Qdrant) |
| **Real-Time** | <1.2s latency conversational avatar via WebSocket + WebRTC |
| **Analytics** | GPU metrics, usage stats, export CSV |
| **Admin Portal** | Users, jobs, audit logs, system health, model management |

## Quick Start

```bash
# 1. Clone
git clone https://github.com/your-org/avatar-realtime.git
cd avatar-realtime

# 2. Install (interactive)
chmod +x scripts/setup/install.sh
./scripts/setup/install.sh

# 3. Open browser
open http://localhost:3000
```

## Requirements

- **OS**: Ubuntu 22.04 LTS (recommended)
- **Docker**: 26.x+
- **GPU**: NVIDIA RTX 3080+ (10GB+ VRAM) — optional but recommended
- **RAM**: 32GB minimum, 64GB recommended
- **Storage**: 500GB SSD minimum

## AI Stack

| Component | Primary | Fallback |
|-----------|---------|---------|
| Avatar Animation | LivePortrait | Wav2Lip |
| Real-Time Lip Sync | MuseTalk | Wav2Lip |
| Voice Cloning | XTTS-v2 | CosyVoice |
| STT | Whisper Large V3 | — |
| LLM | OpenAI GPT-4o | DeepSeek / Ollama |
| Embeddings | multilingual-e5-large | OpenAI text-embedding-3-small |
| Face Analysis | InsightFace buffalo_l | MediaPipe |

## Tech Stack

**Frontend**: React 19 · TypeScript · Vite · TailwindCSS · Shadcn UI · Framer Motion · TanStack Query · Zustand

**Backend**: FastAPI · Python 3.12 · SQLAlchemy (async) · Alembic · Celery · Pydantic v2

**Database**: PostgreSQL 16 · Redis 7 · Qdrant · MinIO

**Infrastructure**: Docker Compose · Kubernetes · Nginx · Prometheus · Grafana · Loki

## Supported Languages

Persian (فارسی) · English · Arabic (العربية) · Turkish · French · German · Spanish

Full RTL support for Persian and Arabic.

## Documentation

- [Installation Guide](docs/deployment/INSTALLATION.md)
- [Architecture Overview](docs/architecture/ARCHITECTURE.md)
- [API Documentation](docs/api/API_DOCUMENTATION.md)
- [Security Checklist](docs/deployment/SECURITY_CHECKLIST.md)
- [Monitoring Strategy](docs/deployment/MONITORING.md)

## Project Structure

```
avatar-realtime/
├── backend/                    # FastAPI application
│   ├── app/
│   │   ├── api/v1/endpoints/   # REST API endpoints
│   │   ├── core/               # Config, DB, Security, Redis, Celery
│   │   ├── ml/                 # AI/ML modules
│   │   │   ├── avatar/         # LivePortrait, Wav2Lip, Face Analysis
│   │   │   ├── voice/          # XTTS-v2, CosyVoice, Whisper STT
│   │   │   ├── lip_sync/       # MuseTalk real-time
│   │   │   ├── llm/            # LLM router (OpenAI/DeepSeek/Ollama)
│   │   │   └── rag/            # Document processor, Embedder, Qdrant, RAG
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/           # MinIO storage, WebRTC streaming
│   │   └── workers/            # Celery tasks (avatar, voice, video, knowledge)
│   ├── alembic/                # Database migrations
│   └── tests/                  # pytest test suite
│
├── frontend/                   # React application
│   └── src/
│       ├── pages/              # Dashboard, Avatar, Voice, Video, Agent, Knowledge, Analytics, Admin, Realtime
│       ├── components/layout/  # AppLayout, Sidebar, Header
│       ├── stores/             # Zustand (auth, theme, notifications)
│       ├── services/           # API client, WebSocket service
│       └── hooks/              # React Query hooks
│
├── infrastructure/
│   ├── docker/                 # Docker configurations
│   ├── kubernetes/             # K8s manifests (base + production overlay)
│   ├── nginx/                  # Reverse proxy config
│   └── monitoring/             # Prometheus alerts, Grafana dashboards
│
├── scripts/
│   ├── setup/                  # install.sh, init_db.py, download_models.py
│   └── backup/                 # backup.sh
│
└── docs/
    ├── architecture/           # System architecture
    ├── api/                    # API documentation
    └── deployment/             # Installation, security, monitoring
```

## License

Commercial license — contact support@avatarplatform.com for enterprise pricing.

---

Built with ❤️ for multilingual AI-powered communication.
