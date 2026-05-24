# API Documentation — AI Digital Human Platform

**Base URL**: `https://api.yourdomain.com/api/v1`  
**OpenAPI Spec**: `https://api.yourdomain.com/docs`  
**Authentication**: Bearer JWT Token

---

## Authentication

### Register
```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "full_name": "John Doe",
  "organization_name": "Acme Corp"
}

Response 201:
{
  "user": { "id": "uuid", "email": "...", "role": "creator" },
  "message": "Registration successful. Please verify your email."
}
```

### Login
```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}

Response 200:
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": { "id": "uuid", "email": "...", "role": "creator", "organization_id": "uuid" }
}
```

### Refresh Token
```http
POST /auth/refresh
Authorization: Bearer {refresh_token}

Response 200:
{
  "access_token": "eyJ...",
  "expires_in": 1800
}
```

---

## Avatar Management

### Create Avatar
```http
POST /avatars
Authorization: Bearer {token}
Content-Type: multipart/form-data

file: (binary) — JPEG, PNG, MP4, MOV (max 500MB)
name: "My Professional Avatar"
description: "Corporate headshot avatar"
source_type: "photo"  # or "video", "multi_photo"

Response 201:
{
  "id": "uuid",
  "name": "My Professional Avatar",
  "status": "processing",
  "job_id": "celery-task-id",
  "message": "Avatar is being processed. Poll /avatars/{id}/status for updates."
}
```

### Get Avatar Status
```http
GET /avatars/{avatar_id}/status
Authorization: Bearer {token}

Response 200:
{
  "id": "uuid",
  "status": "processing",  # processing | ready | failed
  "progress": 65,  # 0-100
  "current_step": "extracting_face_embedding",
  "thumbnail_url": null,  # populated when ready
  "error_message": null
}
```

### List Avatars
```http
GET /avatars?page=1&limit=20&status=ready&search=professional
Authorization: Bearer {token}

Response 200:
{
  "items": [
    {
      "id": "uuid",
      "name": "Professional Avatar",
      "thumbnail_url": "https://...",
      "status": "ready",
      "usage_count": 42,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 15,
  "page": 1,
  "limit": 20,
  "pages": 1
}
```

### Delete Avatar
```http
DELETE /avatars/{avatar_id}
Authorization: Bearer {token}

Response 204: (no content)
```

---

## Voice Cloning

### Clone Voice
```http
POST /voices/clone
Authorization: Bearer {token}
Content-Type: multipart/form-data

samples[]: (binary) — WAV, MP3, FLAC (multiple files, min 30s total)
name: "My Voice Clone"
language: "fa"  # fa, en, ar, tr, fr, de, es, zh
tts_engine: "xtts"  # xtts, cosyvoice, f5tts

Response 201:
{
  "id": "uuid",
  "name": "My Voice Clone",
  "status": "cloning",
  "language": "fa",
  "estimated_duration_seconds": 120
}
```

### Text-to-Speech
```http
POST /voices/tts
Authorization: Bearer {token}
Content-Type: application/json

{
  "voice_model_id": "uuid",
  "text": "سلام، من یک آواتار هوشمند هستم.",
  "language": "fa",
  "speed": 1.0,
  "emotion": "neutral"  # neutral, happy, sad, angry, excited
}

Response 200:
{
  "audio_url": "https://minio.../tts/uuid.wav",
  "duration_seconds": 4.2,
  "sample_rate": 24000
}
```

### List Supported Languages
```http
GET /voices/languages

Response 200:
{
  "languages": [
    { "code": "fa", "name": "Persian (Farsi)", "rtl": true, "engines": ["xtts", "cosyvoice"] },
    { "code": "en", "name": "English", "rtl": false, "engines": ["xtts", "cosyvoice", "f5tts"] },
    { "code": "ar", "name": "Arabic", "rtl": true, "engines": ["xtts", "cosyvoice"] },
    { "code": "tr", "name": "Turkish", "rtl": false, "engines": ["xtts"] },
    { "code": "fr", "name": "French", "rtl": false, "engines": ["xtts", "f5tts"] },
    { "code": "de", "name": "German", "rtl": false, "engines": ["xtts", "f5tts"] }
  ]
}
```

---

## Video Generation

### Generate Video
```http
POST /videos/generate
Authorization: Bearer {token}
Content-Type: application/json

{
  "avatar_id": "uuid",
  "voice_model_id": "uuid",
  "script": "سلام. امروز میخوام درباره هوش مصنوعی صحبت کنم...",
  "language": "fa",
  "resolution": "1080p",  # 720p, 1080p, 4k
  "template_id": "corporate",  # optional
  "title": "AI Introduction Video",
  "add_captions": true,
  "background_music": false
}

Response 202:
{
  "video_id": "uuid",
  "job_id": "celery-task-id",
  "status": "queued",
  "estimated_duration_seconds": 180,
  "message": "Video generation started. Poll /videos/{id}/status for updates."
}
```

### Poll Video Status
```http
GET /videos/{video_id}/status
Authorization: Bearer {token}

Response 200:
{
  "video_id": "uuid",
  "status": "rendering",  # queued | processing | rendering | completed | failed
  "progress": 72,
  "current_step": "lip_sync",  # tts | lip_sync | rendering | uploading
  "steps": {
    "tts": { "status": "completed", "duration_ms": 8432 },
    "lip_sync": { "status": "running", "progress": 45 },
    "rendering": { "status": "pending" },
    "uploading": { "status": "pending" }
  },
  "error_message": null,
  "estimated_remaining_seconds": 52
}
```

### Download Video
```http
GET /videos/{video_id}/download?quality=1080p
Authorization: Bearer {token}

Response 200:
{
  "download_url": "https://minio.../videos/uuid_1080p.mp4?X-Amz-Expires=3600&...",
  "expires_at": "2024-01-15T12:30:00Z",
  "file_size_bytes": 52428800,
  "duration_seconds": 45.3,
  "resolution": "1080p"
}
```

### Batch Video Generation
```http
POST /videos/batch
Authorization: Bearer {token}
Content-Type: application/json

{
  "avatar_id": "uuid",
  "voice_model_id": "uuid",
  "resolution": "720p",
  "videos": [
    { "script": "Video 1 script...", "title": "Chapter 1", "language": "fa" },
    { "script": "Video 2 script...", "title": "Chapter 2", "language": "fa" }
  ]
}

Response 202:
{
  "batch_id": "uuid",
  "video_ids": ["uuid1", "uuid2"],
  "total_videos": 2,
  "message": "Batch generation started"
}
```

---

## AI Agent Management

### Create Agent
```http
POST /agents
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Sales Assistant Leila",
  "description": "AI sales consultant for tech products",
  "role": "sales_consultant",
  "avatar_id": "uuid",
  "voice_model_id": "uuid",
  "knowledge_base_id": "uuid",
  "llm_provider": "openai",
  "llm_model": "gpt-4o",
  "system_prompt": "You are Leila, a friendly sales consultant...",
  "personality": {
    "formality": 0.7,  # 0=casual, 1=formal
    "verbosity": 0.5,  # 0=concise, 1=verbose
    "empathy": 0.9
  },
  "capabilities": ["product_recommendations", "price_inquiry", "appointment_booking"],
  "language": "fa"
}

Response 201:
{
  "id": "uuid",
  "name": "Sales Assistant Leila",
  "status": "active",
  "embed_code": "<script src='...'></script>",
  "api_endpoint": "/api/v1/agents/uuid/chat"
}
```

### Chat with Agent
```http
POST /agents/{agent_id}/chat
Authorization: Bearer {token}  # or API key
Content-Type: application/json
Accept: text/event-stream  # for streaming

{
  "message": "سلام، می‌خوام یه لپتاپ بخرم برای برنامه‌نویسی",
  "session_id": "uuid",  # optional, for conversation continuity
  "include_sources": true  # return RAG source citations
}

Response (SSE streaming):
data: {"type": "thinking", "content": ""}
data: {"type": "text", "content": "سلام! خوش اومدید. "}
data: {"type": "text", "content": "برای برنامه‌نویسی، "}
data: {"type": "text", "content": "پیشنهاد می‌کنم..."}
data: {"type": "sources", "citations": [{"doc": "laptop-catalog.pdf", "page": 12}]}
data: {"type": "done", "session_id": "uuid", "tokens_used": 142}
```

---

## Knowledge Base (RAG)

### Create Knowledge Base
```http
POST /knowledge
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Product Knowledge Base",
  "description": "All product documentation and FAQs",
  "embedding_model": "multilingual-e5-large"
}
```

### Upload Document
```http
POST /knowledge/{kb_id}/upload
Authorization: Bearer {token}
Content-Type: multipart/form-data

file: (binary) — PDF, DOCX, PPTX, XLSX, TXT (max 100MB)
language: "fa"  # auto-detected if omitted

Response 202:
{
  "document_id": "uuid",
  "filename": "product-catalog.pdf",
  "status": "processing",
  "estimated_chunks": 145
}
```

### Add URL
```http
POST /knowledge/{kb_id}/add-url
Authorization: Bearer {token}
Content-Type: application/json

{
  "url": "https://yoursite.com/documentation",
  "depth": 2,  # crawl depth
  "include_patterns": ["/docs/*"],
  "exclude_patterns": ["/blog/*"]
}
```

### Semantic Search
```http
POST /knowledge/{kb_id}/search
Authorization: Bearer {token}
Content-Type: application/json

{
  "query": "چطور محصول را نصب کنم؟",
  "top_k": 5,
  "score_threshold": 0.7,
  "filters": { "doc_type": "pdf" }
}

Response 200:
{
  "results": [
    {
      "chunk_id": "uuid",
      "text": "برای نصب محصول، ابتدا...",
      "score": 0.92,
      "metadata": { "document": "installation-guide.pdf", "page": 5 }
    }
  ],
  "total": 3
}
```

---

## Real-Time Avatar (WebSocket)

### Connect to Real-Time Session

```
WebSocket: wss://api.yourdomain.com/api/v1/realtime/connect?token={jwt}&agent_id={uuid}
```

**Client → Server messages:**
```json
{ "type": "audio_chunk", "data": "base64-encoded-pcm-16k" }
{ "type": "text", "content": "Hello, how are you?" }
{ "type": "end_turn" }
{ "type": "ping" }
```

**Server → Client messages:**
```json
{ "type": "transcription", "text": "Hello, how are you?", "is_final": true }
{ "type": "llm_thinking" }
{ "type": "llm_chunk", "text": "I'm doing great, thanks!" }
{ "type": "video_frame", "data": "base64-jpeg", "timestamp_ms": 1234 }
{ "type": "audio_chunk", "data": "base64-pcm", "sample_rate": 24000 }
{ "type": "turn_complete", "latency_ms": 850 }
{ "type": "error", "code": "STT_FAILED", "message": "..." }
```

---

## Analytics

### Dashboard Stats
```http
GET /analytics/dashboard?period=30d
Authorization: Bearer {token}

Response 200:
{
  "period": "30d",
  "videos": {
    "total": 1247,
    "trend": +12.5,  # % change vs previous period
    "total_duration_hours": 89.3,
    "by_resolution": { "720p": 743, "1080p": 456, "4k": 48 }
  },
  "avatars": { "total": 34, "active": 28 },
  "voices": { "total": 12, "languages": { "fa": 7, "en": 4, "ar": 1 } },
  "agents": { "total": 8, "conversations": 5621, "avg_satisfaction": 4.3 },
  "storage": {
    "used_gb": 847,
    "limit_gb": 2000,
    "breakdown": { "videos": 720, "avatars": 45, "voices": 12, "documents": 70 }
  },
  "gpu": { "avg_utilization_percent": 67, "total_gpu_hours": 142 }
}
```

---

## Admin

### System Health
```http
GET /admin/system
Authorization: Bearer {token}  # requires admin role

Response 200:
{
  "status": "healthy",
  "services": {
    "database": { "status": "connected", "latency_ms": 2, "connections": 15 },
    "redis": { "status": "connected", "latency_ms": 0.5, "memory_mb": 256 },
    "minio": { "status": "connected", "storage_free_gb": 1153 },
    "qdrant": { "status": "connected", "collections": 8 },
    "gpu": { 
      "available": true,
      "name": "NVIDIA RTX 4090",
      "vram_total_gb": 24,
      "vram_used_gb": 8.3,
      "utilization_percent": 45,
      "temperature_c": 72
    }
  },
  "workers": {
    "gpu_worker": { "status": "online", "active_tasks": 1 },
    "cpu_worker": { "status": "online", "active_tasks": 3, "queue_depth": 7 }
  },
  "version": "1.0.0",
  "uptime_seconds": 86400
}
```

---

## Error Codes

| HTTP Code | Error Code | Description |
|-----------|-----------|-------------|
| 400 | `VALIDATION_ERROR` | Invalid input data |
| 401 | `UNAUTHORIZED` | Missing or invalid token |
| 401 | `TOKEN_EXPIRED` | Access token expired |
| 403 | `FORBIDDEN` | Insufficient permissions |
| 404 | `NOT_FOUND` | Resource not found |
| 409 | `CONFLICT` | Resource already exists |
| 413 | `FILE_TOO_LARGE` | Upload exceeds size limit |
| 422 | `UNPROCESSABLE` | Semantic validation error |
| 429 | `RATE_LIMITED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Server error |
| 503 | `GPU_UNAVAILABLE` | GPU worker unavailable |
| 503 | `MODEL_NOT_LOADED` | AI model not loaded |

---

## Rate Limits

| Endpoint Category | Limit |
|------------------|-------|
| Auth endpoints | 10 req/min |
| File uploads | 20 req/hour |
| Video generation | 100 req/day (plan-dependent) |
| Agent chat | 200 req/hour |
| Analytics | 60 req/min |
| Admin endpoints | 30 req/min |

Rate limit headers returned with every response:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1705305600
```

---

## SDK Examples

### Python
```python
import httpx

class AvatarPlatformClient:
    def __init__(self, api_key: str, base_url: str = "https://api.yourplatform.com/api/v1"):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_key}"}
    
    async def generate_video(self, avatar_id: str, voice_id: str, script: str, resolution: str = "1080p"):
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/videos/generate",
                json={"avatar_id": avatar_id, "voice_model_id": voice_id, "script": script, "resolution": resolution},
                headers=self.headers)
            resp.raise_for_status()
            return resp.json()
    
    async def wait_for_video(self, video_id: str) -> dict:
        import asyncio
        while True:
            resp = await self.get_video_status(video_id)
            if resp["status"] == "completed":
                return await self.get_download_url(video_id)
            elif resp["status"] == "failed":
                raise Exception(f"Video generation failed: {resp['error_message']}")
            await asyncio.sleep(5)

# Usage
client = AvatarPlatformClient(api_key="your-api-key")
job = await client.generate_video(
    avatar_id="uuid",
    voice_id="uuid",
    script="سلام! این یک ویدیوی آزمایشی است.",
    resolution="1080p"
)
download = await client.wait_for_video(job["video_id"])
print(f"Download URL: {download['download_url']}")
```

### JavaScript
```javascript
class AvatarPlatformClient {
  constructor(apiKey, baseUrl = 'https://api.yourplatform.com/api/v1') {
    this.baseUrl = baseUrl;
    this.headers = { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' };
  }

  async generateVideo({ avatarId, voiceId, script, resolution = '1080p', language = 'fa' }) {
    const res = await fetch(`${this.baseUrl}/videos/generate`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({ avatar_id: avatarId, voice_model_id: voiceId, script, resolution, language })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  // Stream agent chat response
  async *chatWithAgent(agentId, message, sessionId) {
    const res = await fetch(`${this.baseUrl}/agents/${agentId}/chat`, {
      method: 'POST',
      headers: { ...this.headers, 'Accept': 'text/event-stream' },
      body: JSON.stringify({ message, session_id: sessionId })
    });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    for await (const chunk of reader) {
      const text = decoder.decode(chunk);
      for (const line of text.split('\n')) {
        if (line.startsWith('data: ')) {
          yield JSON.parse(line.slice(6));
        }
      }
    }
  }
}
```
