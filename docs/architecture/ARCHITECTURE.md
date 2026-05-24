# AI Digital Human Platform — Architecture Guide

## System Overview

A self-hosted, GPU-accelerated AI Digital Human Platform enabling creation, training, management, and deployment of realistic talking avatars with real-time conversational capabilities.

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENTS                                   │
│  Web Browser │ Mobile │ 86" Touchscreen │ API Consumers          │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS / WSS / WebRTC
┌──────────────────────────▼──────────────────────────────────────┐
│                      NGINX (Reverse Proxy)                       │
│           TLS Termination │ Rate Limiting │ Load Balance         │
└──────┬───────────────────────────────────┬───────────────────────┘
       │                                   │
┌──────▼──────┐                   ┌────────▼────────┐
│  Frontend   │                   │    Backend API   │
│ React 19    │                   │   FastAPI 0.115  │
│ TypeScript  │                   │   Python 3.12    │
│ Tailwind    │                   │   Uvicorn        │
│ Vite        │                   │   Port 8000      │
└─────────────┘                   └────────┬────────┘
                                           │
              ┌────────────────────────────┼──────────────────────┐
              │                            │                       │
   ┌──────────▼──────┐          ┌──────────▼──────┐    ┌─────────▼──────┐
   │   PostgreSQL    │          │     Redis        │    │    Qdrant      │
   │   (Primary DB)  │          │  Cache + Queue   │    │  Vector DB     │
   │   Port 5432     │          │  Port 6379       │    │  Port 6333     │
   └─────────────────┘          └─────────────────┘    └────────────────┘
                                           │
                                ┌──────────▼──────────────────────────┐
                                │         Celery Workers               │
                                │                                      │
                                │  ┌─────────────┐  ┌──────────────┐  │
                                │  │ GPU Worker  │  │  CPU Worker  │  │
                                │  │ (Avatar/    │  │  (Documents/ │  │
                                │  │  Video/TTS) │  │   Analytics) │  │
                                │  └──────┬──────┘  └──────────────┘  │
                                └─────────┼────────────────────────────┘
                                          │ GPU Tasks
                          ┌───────────────▼───────────────────────┐
                          │            AI/ML Models                │
                          │                                        │
                          │  LivePortrait  │  MuseTalk             │
                          │  Wav2Lip       │  InsightFace          │
                          │  Whisper V3    │  XTTS-v2             │
                          │  CosyVoice     │  F5-TTS              │
                          │  Llama/Qwen    │  E5-Multilingual     │
                          └───────────────────────────────────────┘
                                          │
                          ┌───────────────▼───────────────────────┐
                          │            MinIO Storage               │
                          │  Avatars │ Voices │ Videos │ Documents │
                          └───────────────────────────────────────┘
```

## Module Architecture

### Module 1: Avatar Studio
```
Upload (Photo/Video/Webcam)
    ↓
File Validation & Storage (MinIO)
    ↓
Celery Task: process_avatar_upload
    ↓
InsightFace Detection & Analysis
    ├── Face Embedding (512-dim ArcFace)
    ├── Landmark Extraction (468 points)
    ├── Quality Scoring (blur, lighting, angle)
    └── Thumbnail Generation (256x256)
    ↓
Metadata Storage (PostgreSQL)
    ↓
Avatar Ready for Use
```

### Module 2: Voice Clone Studio
```
Upload Audio Samples (WAV/MP3/FLAC)
    ↓
Audio Preprocessing (denoise, normalize)
    ↓
Celery Task: clone_voice_task
    ↓
XTTS-v2 / CosyVoice Voice Cloning
    ├── Voice Fingerprint Extraction
    ├── Language Detection & Tagging
    └── Quality Validation
    ↓
Voice Model Saved (MinIO + PostgreSQL)
    ↓
Voice Ready for Synthesis
```

### Module 3: Video Generation Pipeline
```
Request (avatar_id + voice_id + script + resolution)
    ↓
Validation & Job Creation
    ↓
Celery Pipeline Task
    │
    ├── Step 1: TTS Synthesis (XTTS-v2)
    │   └── Text → Audio (24kHz WAV)
    │
    ├── Step 2: Lip Sync (LivePortrait/Wav2Lip)
    │   └── Avatar + Audio → Animated Frames
    │
    ├── Step 3: Video Compositing (FFmpeg)
    │   └── Frames → MP4 (720p/1080p/4K)
    │
    └── Step 4: Post-Processing
        ├── Thumbnail extraction
        ├── Metadata update
        └── Notification dispatch
    ↓
Video Available for Download/Stream
```

### Module 4: Real-Time Conversational Avatar
```
Client Audio Stream (WebRTC/WebSocket)
    ↓
Voice Activity Detection (VAD)
    ↓
Whisper Large V3 (STT) — ~300ms
    ↓
LLM Processing (GPT-4/DeepSeek/Llama) — ~500ms
    ↓
XTTS-v2 Synthesis — ~200ms (first chunk)
    ↓
MuseTalk Lip Sync (streaming) — ~100ms/frame
    ↓
WebRTC Video Stream → Client
Target Total Latency: < 1200ms
```

### Module 5: RAG Knowledge Brain
```
Document Upload (PDF/DOCX/PPTX/XLSX/URL)
    ↓
Document Parsing (PyMuPDF/docx/pptx/openpyxl)
    ↓
Text Chunking (512 tokens, 50 overlap)
    ↓
Embedding Generation (multilingual-e5-large)
    ↓
Qdrant Storage (cosine similarity index)
    ↓
At Query Time:
User Question → Embed → Qdrant Search (top-5)
    ↓
Retrieved Chunks + Question → LLM
    ↓
Cited Response
```

## Data Flow Architecture

### Multi-Tenant Isolation
- Every resource (avatar, voice, video, agent) belongs to a User AND Organization
- Row-level security via `organization_id` filtering on all queries
- Separate MinIO "folders" per organization: `/{org_id}/{resource_type}/`
- Separate Qdrant collections per knowledge base: `kb_{knowledge_base_id}`

### Event System
```
Action → Celery Task → Progress Updates → Redis Pub/Sub → WebSocket → Client
                    → Analytics Event → PostgreSQL analytics table
                    → Audit Log → PostgreSQL audit_logs table
```

## Security Architecture

### Authentication Flow
```
Login → bcrypt verify → JWT (RS256) Access Token (30min) + Refresh Token (30d)
    → Refresh: POST /auth/refresh with refresh token → new access token
    → Logout: invalidate refresh token in Redis blacklist
```

### Authorization Layers
1. **JWT Authentication** — all endpoints require valid token
2. **RBAC** — roles: super_admin > admin > manager > creator > viewer
3. **Organization Scoping** — users can only access their org's resources
4. **Resource Ownership** — creators can only modify their own resources
5. **API Key Auth** — for programmatic access (hashed in DB, rate-limited)

### Network Security
- Nginx handles TLS termination (Let's Encrypt or enterprise cert)
- Backend never exposed directly
- Rate limiting at Nginx and FastAPI levels
- CORS whitelist
- Helmet-equivalent security headers

## GPU Resource Management

### Task Queue Strategy
```
gpu_tasks queue → GPU Worker (1 GPU, sequential processing):
  - process_avatar_upload
  - clone_voice_task  
  - generate_video_task
  - realtime_inference

cpu_tasks queue → CPU Workers (4 parallel):
  - process_document_task
  - analytics_aggregation
  - notification_dispatch
  - backup_tasks
```

### Memory Management
- Model loading: lazy singleton pattern (load once, reuse)
- GPU memory: explicit cleanup after each task (`torch.cuda.empty_cache()`)
- Model hot-swapping: configurable (keep in memory vs load/unload)
- OOM protection: monitor VRAM before task, queue if insufficient

## Scalability Considerations

### Horizontal Scaling
- Backend: stateless → scale horizontally behind load balancer
- Workers: add more CPU workers for document processing
- GPU Workers: one per GPU (multi-GPU support via task routing)
- Database: read replicas for analytics queries

### Storage Scaling
- MinIO distributed mode (multi-node, multi-drive) for production
- CDN integration for video delivery (CloudFront/Cloudflare)
- Tiered storage: hot (SSD MinIO) → warm (object storage) → cold (glacier)

## Deployment Topologies

### Single Server (Development/Small)
```
1 server: All services via docker-compose
Recommended: 32GB RAM, 8-core CPU, 1x RTX 4090 (24GB VRAM), 2TB SSD
```

### Multi-Server (Production)
```
Load Balancer (2x for HA)
API Servers (3x, 16GB RAM each)
GPU Workers (2-4x, each with dedicated GPU)
Database (Primary + 2 Read Replicas)
Redis Cluster (3 nodes)
MinIO Cluster (4 nodes, distributed)
Qdrant Cluster (3 nodes)
```

### Kubernetes (Enterprise)
```
Control Plane (3 nodes for HA)
Worker Nodes — CPU (3-10, auto-scale)
Worker Nodes — GPU (1-4, manual scale based on demand)
Persistent Volumes — CSI drivers for storage
Ingress — NGINX Ingress Controller
```
