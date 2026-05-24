# Monitoring Strategy — AI Digital Human Platform

## Monitoring Stack

```
Application → Prometheus (metrics scraping)
Application → Loki (log aggregation via Promtail)
Prometheus + Loki → Grafana (unified dashboards)
Prometheus → Alertmanager → PagerDuty/Slack/Email
```

## Metrics Categories

### 1. Business Metrics (Custom Prometheus Counters)

```prometheus
# Video generation
avatar_videos_generated_total{resolution, status, organization_id}
avatar_video_generation_duration_seconds{resolution} (histogram)
avatar_video_generation_queue_depth (gauge)

# Avatar processing  
avatar_uploads_total{source_type, status}
avatar_processing_duration_seconds (histogram)

# Voice cloning
avatar_voice_clones_total{language, engine, status}
avatar_tts_requests_total{language, engine}
avatar_tts_duration_seconds (histogram)

# Agent conversations
avatar_agent_conversations_total{agent_id}
avatar_agent_response_latency_seconds (histogram)
avatar_agent_satisfaction_score (gauge)

# Real-time sessions
avatar_realtime_sessions_active (gauge)
avatar_realtime_e2e_latency_seconds (histogram)
avatar_realtime_stt_latency_seconds (histogram)
avatar_realtime_llm_latency_seconds (histogram)
avatar_realtime_tts_latency_seconds (histogram)
avatar_realtime_lipsync_latency_seconds (histogram)

# Storage
avatar_storage_used_bytes{organization_id, resource_type}
avatar_storage_uploads_total{file_type}
```

### 2. Infrastructure Metrics

```prometheus
# GPU (via nvidia_gpu_exporter)
nvidia_gpu_memory_used_bytes{gpu="0"}
nvidia_gpu_memory_total_bytes{gpu="0"}
nvidia_gpu_utilization_percentage{gpu="0"}
nvidia_gpu_temperature_celsius{gpu="0"}
nvidia_gpu_power_draw_watts{gpu="0"}

# API Performance (via prometheus-fastapi-instrumentator)
http_requests_total{method, handler, status}
http_request_duration_seconds{method, handler} (histogram)
http_requests_in_progress{method, handler}

# Celery (via flower/celery_exporter)
celery_tasks_total{task_name, state}
celery_task_runtime_seconds{task_name} (histogram)
celery_workers_active
celery_queue_length{queue}

# Database (via postgres_exporter)
pg_stat_activity_count{state}
pg_stat_database_tup_fetched{datname}
pg_stat_bgwriter_checkpoint_write_time_total
pg_database_size_bytes{datname}

# Redis (via redis_exporter)
redis_memory_used_bytes
redis_connected_clients
redis_commands_total{cmd}
redis_keyspace_hits_total
redis_keyspace_misses_total
```

## Alert Rules

### Critical (Page Immediately — 24/7)

```yaml
- alert: BackendServiceDown
  expr: up{job="avatar-backend"} == 0
  for: 2m
  labels: { severity: critical }
  annotations:
    summary: "API backend is unreachable"
    runbook: "https://wiki.yourcompany.com/runbooks/backend-down"

- alert: DatabaseDown
  expr: up{job="postgres"} == 0
  for: 1m
  labels: { severity: critical }

- alert: GPUOutOfMemory
  expr: nvidia_gpu_memory_used_bytes / nvidia_gpu_memory_total_bytes > 0.95
  for: 5m
  labels: { severity: critical }
  annotations:
    summary: "GPU VRAM > 95% - new tasks may fail"

- alert: CeleryWorkerDown
  expr: celery_workers_active{queue="gpu"} == 0
  for: 5m
  labels: { severity: critical }
```

### Warning (Page During Business Hours)

```yaml
- alert: HighVideoGenerationFailureRate
  expr: rate(avatar_videos_generated_total{status="failed"}[5m]) / rate(avatar_videos_generated_total[5m]) > 0.1
  for: 10m
  labels: { severity: warning }
  annotations: { summary: "Video failure rate > 10%" }

- alert: HighAPILatency
  expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{handler="/api/v1/videos/generate"}[5m])) > 5
  for: 10m
  labels: { severity: warning }

- alert: StorageUsageHigh
  expr: avatar_storage_used_bytes / 1e12 > 1.8  # > 1.8TB of 2TB limit
  for: 1h
  labels: { severity: warning }

- alert: CeleryQueueBacklog
  expr: celery_queue_length{queue="gpu"} > 50
  for: 15m
  labels: { severity: warning }

- alert: HighRealtimeLatency
  expr: histogram_quantile(0.95, rate(avatar_realtime_e2e_latency_seconds_bucket[5m])) > 2
  for: 5m
  labels: { severity: warning }
  annotations: { summary: "Real-time avatar E2E latency P95 > 2s (target: <1.2s)" }

- alert: GPUTemperatureHigh
  expr: nvidia_gpu_temperature_celsius > 85
  for: 5m
  labels: { severity: warning }

- alert: DatabaseConnectionPoolExhausted
  expr: pg_stat_activity_count{state="active"} / pg_settings_max_connections > 0.8
  for: 5m
  labels: { severity: warning }

- alert: RedisMemoryHigh
  expr: redis_memory_used_bytes > 1.8e9  # > 1.8GB of 2GB limit
  for: 10m
  labels: { severity: warning }
```

## Grafana Dashboards

### Dashboard 1: Platform Overview
**Panels:**
- Videos Generated Today (counter + sparkline)
- Active Real-time Sessions (gauge)
- Storage Used (donut chart by type)
- API Request Rate (time series, all endpoints)
- Error Rate (time series, 4xx vs 5xx)
- Top 5 Busiest Organizations (table)

### Dashboard 2: GPU & AI Models
**Panels:**
- GPU VRAM Usage (gauge, 0-24GB)
- GPU Utilization % (time series, 24h)
- GPU Temperature (time series with threshold at 85°C)
- Current Running Tasks (table: task_name, avatar_id, started_at, eta)
- Task Queue Depth by Queue (bar chart)
- Model Load Times (histogram: LivePortrait, MuseTalk, XTTS-v2)
- Video Generation Pipeline Breakdown (stacked bar: TTS, LipSync, Render)

### Dashboard 3: API Performance
**Panels:**
- Request Rate by Endpoint (time series)
- P50/P95/P99 Latency (time series, overlay)
- Error Rate by Status Code (stacked area)
- Rate Limited Requests (counter)
- Active WebSocket Connections (gauge)
- Celery Tasks/min by Queue (time series)

### Dashboard 4: Business Analytics
**Panels:**
- Daily Active Users (time series)
- Videos Generated per Day (bar chart, 30 days)
- Voice Cloning Sessions (bar chart)
- Language Distribution of Videos (pie chart)
- Resolution Distribution (pie chart)
- Agent Conversation Volume (time series)
- User Satisfaction Scores (gauge)
- Revenue / Plan Distribution (if billing enabled)

### Dashboard 5: Infrastructure Health
**Panels:**
- Service Health Status (status table: postgres, redis, qdrant, minio)
- Database Query Performance (histogram)
- Redis Cache Hit Rate (gauge, target >90%)
- MinIO Object Count and Storage
- Container CPU/Memory Usage (multi-row panel)
- Network Throughput In/Out
- Backup Status (last successful backup timestamp)

## Log Management (Loki)

### Log Levels by Environment

| Environment | Log Level |
|-------------|-----------|
| Development | DEBUG |
| Staging | INFO |
| Production | WARNING + ERROR |

### Key Log Queries (LogQL)

```logql
# Failed video generations in last 1h
{app="avatar-backend"} |= "generate_video_task" |= "FAILED" | json

# All admin actions
{app="avatar-backend"} | json | action=~".*" | user_role="admin"

# GPU OOM errors
{app="avatar-worker-gpu"} |= "CUDA out of memory"

# Authentication failures
{app="avatar-backend"} |= "authentication failed" | json | rate()

# Slow API requests (> 5s)
{app="avatar-backend"} | json | duration_ms > 5000

# Persian language TTS errors
{app="avatar-worker-gpu"} |= "xtts" |= "error" | json | language="fa"
```

### Log Retention Policy

| Log Type | Retention |
|----------|-----------|
| Application (INFO) | 30 days |
| Error logs | 90 days |
| Audit logs | 1 year (compliance) |
| Access logs | 90 days |
| Security events | 1 year |

## SLOs (Service Level Objectives)

| Metric | SLO Target | Measurement |
|--------|-----------|-------------|
| API Availability | 99.9% | Uptime monitoring (1-min intervals) |
| API P95 Latency (read) | < 500ms | Prometheus histogram |
| API P95 Latency (video gen) | < 30s (to start) | Custom metric |
| Video Generation Success Rate | > 98% | `status=completed / total` |
| Real-time Avatar Latency P95 | < 1.5s E2E | WebRTC metrics |
| Voice Clone Success Rate | > 97% | Task success rate |
| STT Accuracy | > 95% WER | Periodic test set |
| Backup Success | 100% | Daily backup alert |

## Uptime Monitoring (External)

Use an external service (UptimeRobot, Better Uptime, Checkly) to monitor:

- `GET /health` — every 1 minute
- `GET /health/ready` — every 5 minutes
- Frontend homepage — every 5 minutes
- WebSocket endpoint — every 10 minutes

Alert channels: Email, Slack, PagerDuty (critical)

## Runbooks

### Video Generation Stuck
1. Check `GET /admin/jobs` for stuck jobs
2. Check GPU memory: `nvidia-smi`
3. Check Celery worker logs: `docker compose logs worker-gpu`
4. If OOM: restart GPU worker
5. Retry failed job via admin panel
6. If persistent: check model corruption, reload models

### GPU Worker Not Processing
1. Check worker health: `GET /health/gpu`
2. Restart GPU worker: `docker compose restart worker-gpu`
3. Check GPU driver: `nvidia-smi`
4. Check CUDA version compatibility
5. Check model file integrity

### Database Connection Issues
1. Check pool exhaustion: Grafana → DB panel
2. Kill idle connections: `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state='idle' AND query_start < NOW() - INTERVAL '10 minutes';`
3. Check for long-running transactions
4. If DB unreachable: check container health, disk space

### Storage Full
1. Check MinIO storage: dashboard
2. Delete old temp files: `scripts/cleanup/cleanup_temp.sh`
3. Delete failed video renders
4. Archive old videos to cold storage
5. Increase disk capacity or add MinIO node
