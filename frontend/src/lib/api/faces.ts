import client from "./client";
import type { Face, FaceCluster } from "@/types/api";

export interface FaceStats {
  total_faces: number;
  unclustered: number;
  cluster_count: number;
}

export async function getFaceStats(): Promise<FaceStats> {
  const { data } = await client.get<FaceStats>("/faces/stats");
  return data;
}

export async function triggerClustering(): Promise<{ status: string; task_id: string; unclustered_before: number }> {
  const { data } = await client.post("/faces/cluster");
  return data;
}

export async function triggerBackfill(): Promise<{ status: string; task_id: string }> {
  const { data } = await client.post("/faces/backfill");
  return data;
}

export interface TaskStatus {
  task_id: string;
  /** PENDING | STARTED | SUCCESS | FAILURE | RETRY */
  state: string;
  result: Record<string, number> | null;
  error: string | null;
}

export async function getFaceTaskStatus(taskId: string): Promise<TaskStatus> {
  const { data } = await client.get<TaskStatus>(`/faces/task/${taskId}`);
  return data;
}

export async function cancelFaceTask(taskId: string): Promise<void> {
  await client.delete(`/faces/task/${taskId}`);
}

export async function listClusters(): Promise<FaceCluster[]> {
  const { data } = await client.get<FaceCluster[]>("/faces/clusters");
  return data;
}

export interface FaceClusterMediaResponse {
  cluster_id: number;
  media_ids: string[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export async function getCluster(
  clusterId: number,
  page = 1,
  limit = 50
): Promise<FaceClusterMediaResponse> {
  const { data } = await client.get<FaceClusterMediaResponse>(`/faces/clusters/${clusterId}`, {
    params: { page, limit },
  });
  return data;
}

export async function getMediaFaces(mediaId: string): Promise<Face[]> {
  const { data } = await client.get<Face[]>(`/media/${mediaId}/faces`);
  return data;
}
