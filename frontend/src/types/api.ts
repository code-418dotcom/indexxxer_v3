// ─── Shared ────────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

// ─── Tags ──────────────────────────────────────────────────────────────────

export interface TagRef {
  id: string;
  name: string;
  slug: string;
  category?: string;
  color?: string;
  confidence: number;
  source: "manual" | "ai" | "filename";
}

export interface Tag {
  id: string;
  name: string;
  slug: string;
  category?: string;
  color?: string;
  created_at: string;
}

export interface TagCreate {
  name: string;
  category?: string;
  color?: string;
}

export interface TagUpdate {
  name?: string;
  category?: string;
  color?: string;
}

// ─── Media ─────────────────────────────────────────────────────────────────

export type MediaType = "image" | "video";
export type IndexStatus =
  | "pending"
  | "extracting"
  | "thumbnailing"
  | "indexed"
  | "error";

export type ClipStatus = "pending" | "computing" | "done" | "error";
export type AiStatus = "pending" | "computing" | "transcribing" | "summarising" | "done" | "error" | "skipped";

export interface MediaItem {
  id: string;
  source_id: string;
  filename: string;
  file_path: string;
  file_size: number;
  file_hash?: string;
  file_mtime?: string;
  media_type: MediaType;
  mime_type: string;
  width?: number;
  height?: number;
  duration_seconds?: number;
  bitrate?: number;
  codec?: string;
  frame_rate?: number;
  thumbnail_url?: string;
  index_status: IndexStatus;
  index_error?: string;
  indexed_at: string;
  updated_at: string;
  tags: TagRef[];
  is_favourite: boolean;
  clip_status: ClipStatus;
  // M3 AI fields
  caption?: string;
  caption_status: AiStatus;
  transcript?: string;
  transcript_status: AiStatus;
  summary?: string;
  summary_status: AiStatus;
  face_count: number;
}

// ─── Faces ──────────────────────────────────────────────────────────────────

export interface Face {
  id: string;
  media_id: string;
  cluster_id?: number;
  bbox_x: number;
  bbox_y: number;
  bbox_w: number;
  bbox_h: number;
  confidence: number;
  created_at: string;
}

export interface FaceCluster {
  cluster_id: number;
  member_count: number;
  representative_media_id?: string;
  representative_face_id?: string;
  face_crop_url?: string;
  representative_thumbnail_url?: string;
}

export interface MediaItemPatch {
  filename?: string;
  tags?: { id: string; op: "add" | "remove" }[];
  is_favourite?: boolean;
}

export interface BulkActionRequest {
  ids: string[];
  action: "add_tags" | "remove_tags" | "delete";
  payload?: { tag_ids: string[] };
}

// ─── Sources ───────────────────────────────────────────────────────────────

export interface MediaSource {
  id: string;
  name: string;
  path: string;
  source_type: string;
  enabled: boolean;
  scan_config?: Record<string, unknown>;
  last_scan_at?: string;
  created_at: string;
  updated_at: string;
}

export interface SourceCreate {
  name: string;
  path: string;
  source_type?: string;
  scan_config?: Record<string, unknown>;
}

export interface SourceUpdate {
  name?: string;
  path?: string;
  enabled?: boolean;
  scan_config?: Record<string, unknown>;
}

// ─── Jobs ──────────────────────────────────────────────────────────────────

export type JobStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface IndexJob {
  id: string;
  source_id: string;
  job_type: "full" | "incremental" | "rehash";
  status: JobStatus;
  total_files?: number;
  processed_files: number;
  failed_files: number;
  skipped_files: number;
  celery_task_id?: string;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export interface ScanRequest {
  job_type: "full" | "incremental";
}

// ─── Saved Filters ─────────────────────────────────────────────────────────

export interface SavedFilter {
  id: string;
  name: string;
  filters: Record<string, unknown>;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface FilterCreate {
  name: string;
  filters: Record<string, unknown>;
  is_default?: boolean;
}

// ─── Search ────────────────────────────────────────────────────────────────

export type SearchMode = "auto" | "text" | "semantic" | "hybrid";

export interface SearchParams {
  q?: string;
  mode?: SearchMode;
  type?: MediaType;
  tag_ids?: string[];
  source_id?: string;
  date_from?: string;
  date_to?: string;
  favourite?: boolean;
  sort?: "relevance" | "date" | "size" | "name";
  order?: "asc" | "desc";
  page?: number;
  limit?: number;
}

// ─── SSE Events ────────────────────────────────────────────────────────────

export type JobEventType =
  | "stream.connected"
  | "stream.end"
  | "scan.start"
  | "scan.discovered"
  | "scan.dispatched"
  | "scan.complete"
  | "file.extracted"
  | "file.error"
  | "job.failed"
  | "job.cancelled";

export interface JobEvent {
  type: JobEventType;
  job_id: string;
  [key: string]: unknown;
}

// ─── Health ────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  version: string;
}

// ─── M4 Auth ───────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  username: string;
  role: "admin" | "user";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserCreate {
  email: string;
  username: string;
  password: string;
  role?: string;
}

export interface UserUpdate {
  email?: string;
  username?: string;
  password?: string;
  role?: string;
  enabled?: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// ─── M4 Webhooks ───────────────────────────────────────────────────────────

export interface Webhook {
  id: string;
  user_id?: string;
  name: string;
  url: string;
  events: string[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface WebhookCreate {
  name: string;
  url: string;
  events: string[];
  secret?: string;
  enabled?: boolean;
}

export interface WebhookDelivery {
  id: string;
  webhook_id: string;
  event_type?: string;
  status: string;
  http_status?: number;
  error?: string;
  attempts: number;
  created_at: string;
  delivered_at?: string;
}

// ─── M4 Analytics ──────────────────────────────────────────────────────────

export interface AnalyticsOverview {
  total_media: number;
  indexed: number;
  pending: number;
  error: number;
  storage_bytes: number;
  face_count: number;
  cluster_count: number;
  source_count: number;
}

export interface QueryStats {
  daily: { date: string; count: number }[];
  top_queries: { query: string; count: number }[];
  mode_breakdown: Record<string, number>;
  total_searches: number;
}

export interface IndexingStats {
  daily_indexed: { date: string; count: number }[];
  avg_search_latency_ms: number;
  error_count: number;
}

// ─── PDFs ──────────────────────────────────────────────────────────────────

export interface PDFDocument {
  id: string;
  source_id?: string;
  filename: string;
  file_path: string;
  title?: string;
  page_count: number;
  file_size?: number;
  file_mtime?: string;
  cover_url?: string;
  created_at: string;
  updated_at: string;
}

// ─── Galleries ─────────────────────────────────────────────────────────────

export interface GalleryImage {
  id: string;
  gallery_id: string;
  filename: string;
  index_order: number;
  width?: number;
  height?: number;
}

export interface Gallery {
  id: string;
  source_id?: string;
  filename: string;
  file_path: string;
  image_count: number;
  file_size?: number;
  file_mtime?: string;
  cover_url?: string;
  created_at: string;
  updated_at: string;
}

export interface GalleryDetail extends Gallery {
  images: GalleryImage[];
}

// ─── M4 Credentials ────────────────────────────────────────────────────────

export interface SourceCredential {
  id: string;
  source_id: string;
  host: string;
  port?: number;
  username?: string;
  domain?: string;
  share?: string;
  created_at: string;
}

export interface CredentialCreate {
  host: string;
  port?: number;
  username?: string;
  password?: string;
  domain?: string;
  share?: string;
}
