import type { MediaItem } from "@/types/api";
import client from "./client";

export interface DuplicateGroup {
  group_id: string;
  count: number;
  total_size: number;
  items: MediaItem[];
}

export interface DuplicateGroupsResponse {
  groups: DuplicateGroup[];
  total_groups: number;
}

export interface DedupStats {
  total_items: number;
  hashed_items: number;
  pending_items: number;
  no_thumbnail: number;
  progress_pct: number;
  duplicate_items: number;
  duplicate_groups: number;
  wasted_bytes: number;
}

export interface BackfillResponse {
  task_id: string;
  status: string;
  pending: number;
}

export async function listDuplicateGroups(): Promise<DuplicateGroupsResponse> {
  const { data } = await client.get<DuplicateGroupsResponse>("/duplicates");
  return data;
}

export async function getDedupStats(): Promise<DedupStats> {
  const { data } = await client.get<DedupStats>("/duplicates/stats");
  return data;
}

export async function backfillPhash(): Promise<BackfillResponse> {
  const { data } = await client.post("/duplicates/backfill");
  return data;
}

export async function resolveDuplicates(
  groupId: string,
  keepItemId: string
): Promise<{ resolved: number; kept: string }> {
  const { data } = await client.delete(`/duplicates/${groupId}/keep/${keepItemId}`);
  return data;
}

export async function destroyDuplicates(
  groupId: string,
  keepItemId: string
): Promise<{ kept: string; deleted_files: number; deleted_bytes: number; errors: string[] }> {
  const { data } = await client.delete(`/duplicates/${groupId}/keep/${keepItemId}/destroy`);
  return data;
}
