import type { MediaItem } from "@/types/api";
import client from "./client";

export interface DuplicateGroup {
  group_id: string;
  count: number;
  items: MediaItem[];
}

export interface DuplicateGroupsResponse {
  groups: DuplicateGroup[];
  total_groups: number;
}

export async function listDuplicateGroups(): Promise<DuplicateGroupsResponse> {
  const { data } = await client.get<DuplicateGroupsResponse>("/duplicates");
  return data;
}

export async function backfillPhash(): Promise<{ task_id: string; status: string }> {
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
