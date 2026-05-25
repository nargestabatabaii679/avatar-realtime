// ============================================================
// Core Enums
// ============================================================

export enum UserRole {
  SUPER_ADMIN = 'super_admin',
  ADMIN = 'admin',
  EDITOR = 'editor',
  VIEWER = 'viewer',
}

export enum UserStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  SUSPENDED = 'suspended',
  PENDING = 'pending',
}

export enum AvatarStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  READY = 'ready',
  FAILED = 'failed',
}

export enum AvatarType {
  PHOTO = 'photo',
  VIDEO = 'video',
  MULTI_PHOTO = 'multi_photo',
  WEBCAM = 'webcam',
}

export enum VoiceStatus {
  PENDING = 'pending',
  TRAINING = 'training',
  READY = 'ready',
  FAILED = 'failed',
}

export enum VoiceGender {
  MALE = 'male',
  FEMALE = 'female',
  NEUTRAL = 'neutral',
}

export enum VideoStatus {
  PENDING = 'pending',
  QUEUED = 'queued',
  PROCESSING = 'processing',
  RENDERING = 'rendering',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

export enum VideoResolution {
  HD_720 = '720p',
  HD_1080 = '1080p',
  UHD_4K = '4k',
}

export enum AgentStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  DRAFT = 'draft',
}

export enum LLMProvider {
  OPENAI = 'openai',
  ANTHROPIC = 'anthropic',
  GOOGLE = 'google',
  LOCAL = 'local',
  GROQ = 'groq',
}

export enum DocumentStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  INDEXED = 'indexed',
  FAILED = 'failed',
}

export enum DocumentType {
  PDF = 'pdf',
  DOCX = 'docx',
  TXT = 'txt',
  URL = 'url',
  MARKDOWN = 'markdown',
}

export enum JobStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

export enum JobType {
  AVATAR_CREATION = 'avatar_creation',
  VOICE_TRAINING = 'voice_training',
  VIDEO_GENERATION = 'video_generation',
  DOCUMENT_INDEXING = 'document_indexing',
}

export enum Language {
  EN = 'en',
  FA = 'fa',
  AR = 'ar',
  TR = 'tr',
  FR = 'fr',
  DE = 'de',
  ES = 'es',
  ZH = 'zh',
}

// ============================================================
// Auth Types
// ============================================================

export interface LoginCredentials {
  email: string
  password: string
  remember_me?: boolean
}

export interface RegisterData {
  email: string
  password: string
  full_name: string
  organization_name?: string
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface TokenRefreshResponse {
  access_token: string
  token_type: string
  expires_in: number
}

// ============================================================
// User & Organization
// ============================================================

export interface User {
  id: string
  email: string
  full_name: string
  avatar_url?: string
  role: UserRole
  status: UserStatus
  organization_id?: string
  organization?: Organization
  preferences: UserPreferences
  storage_used: number
  storage_limit: number
  api_calls_today: number
  api_calls_limit: number
  created_at: string
  updated_at: string
  last_login?: string
}

export interface UserPreferences {
  language: Language
  theme: 'light' | 'dark' | 'system'
  notifications_email: boolean
  notifications_push: boolean
  default_resolution: VideoResolution
  default_language: Language
}

export interface Organization {
  id: string
  name: string
  slug: string
  logo_url?: string
  plan: 'free' | 'starter' | 'pro' | 'enterprise'
  member_count: number
  storage_used: number
  storage_limit: number
  api_calls_limit: number
  created_at: string
  updated_at: string
  settings: OrganizationSettings
}

export interface OrganizationSettings {
  allow_public_agents: boolean
  default_language: Language
  branding: {
    primary_color?: string
    logo_url?: string
  }
}

// ============================================================
// Avatar
// ============================================================

export interface Avatar {
  id: string
  name: string
  description?: string
  status: AvatarStatus
  type: AvatarType
  thumbnail_url?: string
  source_url?: string
  quality_score?: number
  face_embedding?: number[]
  face_attributes?: FaceAttributes
  usage_count: number
  is_public: boolean
  user_id: string
  organization_id?: string
  created_at: string
  updated_at: string
  metadata?: AvatarMetadata
}

export interface FaceAttributes {
  age_estimate?: number
  gender_estimate?: string
  emotion?: string
  expression?: string
  head_pose?: {
    yaw: number
    pitch: number
    roll: number
  }
}

export interface AvatarMetadata {
  source_resolution?: string
  fps?: number
  duration?: number
  face_count?: number
  processing_time?: number
  quality_score?: number
  landmarks_count?: number
  face_bbox?: number[]
  age?: number
  gender?: string
}

export interface CreateAvatarRequest {
  name: string
  description?: string
  type: AvatarType
  is_public?: boolean
}

export interface UpdateAvatarRequest {
  name?: string
  description?: string
  is_public?: boolean
}

// ============================================================
// Voice Model
// ============================================================

export interface VoiceModel {
  id: string
  name: string
  description?: string
  status: VoiceStatus
  gender: VoiceGender
  language: Language
  accent?: string
  sample_url?: string
  is_public: boolean
  is_system: boolean
  quality_score?: number
  usage_count: number
  user_id?: string
  organization_id?: string
  created_at: string
  updated_at: string
  metadata?: VoiceMetadata
}

export interface VoiceMetadata {
  training_duration?: number
  sample_count?: number
  model_version?: string
  pitch_range?: [number, number]
  speaking_rate?: number
}

export interface CreateVoiceRequest {
  name: string
  description?: string
  gender: VoiceGender
  language: Language
  accent?: string
  is_public?: boolean
}

export interface VoiceSynthesisRequest {
  text: string
  voice_id: string
  speed?: number
  pitch?: number
  emotion?: string
}

export interface VoiceSynthesisResponse {
  audio_url: string
  duration: number
  word_timestamps?: WordTimestamp[]
}

export interface WordTimestamp {
  word: string
  start: number
  end: number
}

// ============================================================
// Video
// ============================================================

export interface Video {
  id: string
  title: string
  description?: string
  status: VideoStatus
  resolution: VideoResolution
  duration?: number
  script: string
  language: Language
  avatar_id: string
  avatar?: Avatar
  voice_id: string
  voice?: VoiceModel
  template_id?: string
  video_url?: string
  thumbnail_url?: string
  subtitle_url?: string
  file_size?: number
  view_count: number
  download_count: number
  is_public: boolean
  user_id: string
  organization_id?: string
  job_id?: string
  job?: VideoJob
  created_at: string
  updated_at: string
  completed_at?: string
  metadata?: VideoMetadata
}

export interface VideoMetadata {
  fps?: number
  codec?: string
  bitrate?: number
  aspect_ratio?: string
  watermarked?: boolean
}

export interface CreateVideoRequest {
  title: string
  description?: string
  script: string
  avatar_id: string
  voice_id: string
  resolution?: VideoResolution
  language?: Language
  template_id?: string
  include_subtitles?: boolean
}

export interface UpdateVideoRequest {
  title?: string
  description?: string
  is_public?: boolean
}

// ============================================================
// Video Job (Processing)
// ============================================================

export interface VideoJob {
  id: string
  type: JobType
  status: JobStatus
  progress: number
  current_step: string
  steps: JobStep[]
  video_id?: string
  avatar_id?: string
  voice_id?: string
  error_message?: string
  eta_seconds?: number
  started_at?: string
  completed_at?: string
  created_at: string
  metadata?: Record<string, unknown>
}

export interface JobStep {
  name: string
  label: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  started_at?: string
  completed_at?: string
}

// ============================================================
// Agent
// ============================================================

export interface Agent {
  id: string
  name: string
  description?: string
  status: AgentStatus
  role?: string
  avatar_id?: string
  avatar?: Avatar
  voice_id?: string
  voice?: VoiceModel
  knowledge_base_id?: string
  knowledge_base?: KnowledgeBase
  llm_config: LLMConfig
  system_prompt: string
  personality: PersonalityConfig
  embed_config: EmbedConfig
  conversation_count: number
  avg_rating?: number
  is_public: boolean
  user_id: string
  organization_id?: string
  created_at: string
  updated_at: string
}

export interface LLMConfig {
  provider: LLMProvider
  model: string
  temperature: number
  max_tokens: number
  top_p?: number
  frequency_penalty?: number
  presence_penalty?: number
}

export interface PersonalityConfig {
  formality: number // 0 = casual, 100 = formal
  verbosity: number // 0 = concise, 100 = verbose
  empathy: number
  confidence: number
  humor: number
}

export interface EmbedConfig {
  allowed_domains: string[]
  custom_css?: string
  greeting_message?: string
  placeholder_text?: string
  show_branding: boolean
  position: 'bottom-right' | 'bottom-left' | 'center'
}

export interface CreateAgentRequest {
  name: string
  description?: string
  role?: string
  avatar_id?: string
  voice_id?: string
  knowledge_base_id?: string
  llm_config: Partial<LLMConfig>
  system_prompt: string
  personality?: Partial<PersonalityConfig>
  is_public?: boolean
}

// ============================================================
// Knowledge Base
// ============================================================

export interface KnowledgeBase {
  id: string
  name: string
  description?: string
  document_count: number
  total_chunks: number
  embedding_model: string
  language: Language
  user_id: string
  organization_id?: string
  created_at: string
  updated_at: string
}

export interface Document {
  id: string
  name: string
  type: DocumentType
  status: DocumentStatus
  source_url?: string
  file_url?: string
  file_size?: number
  chunk_count?: number
  knowledge_base_id: string
  error_message?: string
  created_at: string
  updated_at: string
  indexed_at?: string
}

export interface CreateKnowledgeBaseRequest {
  name: string
  description?: string
  language?: Language
}

export interface AddDocumentRequest {
  knowledge_base_id: string
  type: DocumentType
  url?: string
  name?: string
}

export interface SearchResult {
  id: string
  content: string
  score: number
  document_id: string
  document_name: string
  metadata?: Record<string, unknown>
}

export interface KnowledgeSearchRequest {
  query: string
  knowledge_base_id: string
  limit?: number
  min_score?: number
}

// ============================================================
// Analytics
// ============================================================

export interface AnalyticsSummary {
  period: string
  videos_generated: number
  videos_change_pct: number
  total_duration_seconds: number
  duration_change_pct: number
  storage_used_bytes: number
  storage_change_pct: number
  api_calls: number
  api_calls_change_pct: number
  active_agents: number
  conversations: number
  avg_generation_time: number
}

export interface TimeSeriesDataPoint {
  date: string
  value: number
  label?: string
}

export interface AvatarUsageStat {
  avatar_id: string
  avatar_name: string
  avatar_thumbnail?: string
  usage_count: number
  video_count: number
}

export interface ResolutionBreakdown {
  resolution: VideoResolution
  count: number
  percentage: number
}

export interface StorageGrowth {
  date: string
  total_bytes: number
  videos_bytes: number
  avatars_bytes: number
  voices_bytes: number
}

export interface AgentConversationStat {
  agent_id: string
  agent_name: string
  conversation_count: number
  avg_duration_seconds: number
  avg_rating?: number
  resolution_rate?: number
}

export interface GPUStats {
  utilization_pct: number
  memory_used_gb: number
  memory_total_gb: number
  temperature_c: number
  power_watts: number
  active_jobs: number
  queue_length: number
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'down'
  database: ServiceHealth
  redis: ServiceHealth
  storage: ServiceHealth
  gpu: ServiceHealth
  api: ServiceHealth
}

export interface ServiceHealth {
  status: 'up' | 'down' | 'degraded'
  latency_ms?: number
  message?: string
  last_checked: string
}

// ============================================================
// Conversation (Real-time)
// ============================================================

export interface Conversation {
  id: string
  agent_id: string
  agent?: Agent
  session_id: string
  messages: ConversationMessage[]
  started_at: string
  ended_at?: string
  duration_seconds?: number
  user_rating?: number
  metadata?: Record<string, unknown>
}

export interface ConversationMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  audio_url?: string
  video_url?: string
  tokens?: number
  latency_ms?: number
}

// ============================================================
// API Response Wrappers
// ============================================================

export interface ApiResponse<T> {
  data: T
  message?: string
  success: boolean
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
  has_next: boolean
  has_prev: boolean
}

export interface PaginationParams {
  page?: number
  per_page?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  search?: string
}

export interface ApiError {
  status: number
  message: string
  detail?: string | Record<string, unknown>
  code?: string
}

// ============================================================
// WebSocket Events
// ============================================================

export interface WSJobProgressEvent {
  type: 'job_progress'
  job_id: string
  status: JobStatus
  progress: number
  current_step: string
  eta_seconds?: number
  error?: string
}

export interface WSConversationEvent {
  type: 'conversation_message'
  conversation_id: string
  message: ConversationMessage
}

export interface WSSystemEvent {
  type: 'system_alert'
  severity: 'info' | 'warning' | 'error'
  message: string
  timestamp: string
}

export type WSEvent = WSJobProgressEvent | WSConversationEvent | WSSystemEvent

// ============================================================
// UI / Component Types
// ============================================================

export interface NavItem {
  id: string
  label: string
  labelFa?: string
  icon: string
  path: string
  badge?: number
  children?: NavItem[]
  requiredRole?: UserRole
}

export interface BreadcrumbItem {
  label: string
  path?: string
}

export interface NotificationItem {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message: string
  timestamp: string
  read: boolean
  action_url?: string
}

export interface SelectOption<T = string> {
  value: T
  label: string
  description?: string
  disabled?: boolean
  icon?: string
}

export interface TableColumn<T> {
  key: keyof T | string
  header: string
  sortable?: boolean
  width?: string
  render?: (value: unknown, row: T) => React.ReactNode
}

export interface FileUploadResult {
  file_id: string
  url: string
  filename: string
  size: number
  content_type: string
}

export interface DateRange {
  from: Date
  to: Date
}

export interface ChartData {
  name: string
  value: number
  [key: string]: string | number
}

// ============================================================
// Theme & i18n
// ============================================================

export type ThemeMode = 'light' | 'dark' | 'system'

export type LanguageCode = 'en' | 'fa' | 'ar' | 'tr' | 'fr' | 'de'

export interface LanguageConfig {
  code: LanguageCode
  name: string
  nativeName: string
  dir: 'ltr' | 'rtl'
  flag: string
}

export const SUPPORTED_LANGUAGES: LanguageConfig[] = [
  { code: 'en', name: 'English', nativeName: 'English', dir: 'ltr', flag: '🇺🇸' },
  { code: 'fa', name: 'Persian', nativeName: 'فارسی', dir: 'rtl', flag: '🇮🇷' },
  { code: 'ar', name: 'Arabic', nativeName: 'العربية', dir: 'rtl', flag: '🇸🇦' },
  { code: 'tr', name: 'Turkish', nativeName: 'Türkçe', dir: 'ltr', flag: '🇹🇷' },
  { code: 'fr', name: 'French', nativeName: 'Français', dir: 'ltr', flag: '🇫🇷' },
  { code: 'de', name: 'German', nativeName: 'Deutsch', dir: 'ltr', flag: '🇩🇪' },
]

export const RTL_LANGUAGES: LanguageCode[] = ['fa', 'ar']

// ============================================================
// Admin Types
// ============================================================

export interface AuditLog {
  id: string
  user_id: string
  user_email?: string
  action: string
  resource_type: string
  resource_id?: string
  changes?: Record<string, unknown>
  ip_address?: string
  user_agent?: string
  created_at: string
}

export interface SystemModel {
  id: string
  name: string
  type: 'tts' | 'lip_sync' | 'face_detection' | 'llm'
  version: string
  status: 'loaded' | 'unloaded' | 'loading' | 'error'
  size_bytes: number
  loaded_at?: string
  performance_ms?: number
}
