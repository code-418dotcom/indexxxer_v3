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

// ─── Media ─────────────────────────────────────────────────────────────────

export type MediaType = "image" | "video";
export type IndexStatus =
  | "pending"
  | "extracting"
  | "thumbnailing"
  | "indexed"
  | "error";

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
  thumbnail_path?: string;
  thumbnail_url?: string;
  index_status: IndexStatus;
  index_error?: string;
  indexed_at: string;
  updated_at: string;
  tags: TagRef[];
}

export interface MediaItemPatch {
  filename?: string;
  tags?: { id: string; op: "add" | "remove" }[];
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

// ─── Search ────────────────────────────────────────────────────────────────

export interface SearchParams {
  q?: string;
  type?: MediaType;
  tag_ids?: string[];
  source_id?: string;
  date_from?: string;
  date_to?: string;
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
