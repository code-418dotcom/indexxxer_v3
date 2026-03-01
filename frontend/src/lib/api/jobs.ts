import type { IndexJob, PaginatedResponse } from "@/types/api";
import client from "./client";

export async function listJobs(params?: {
  source_id?: string;
  status?: string;
  page?: number;
  limit?: number;
}) {
  const { data } = await client.get<PaginatedResponse<IndexJob>>("/jobs", { params });
  return data;
}

export async function getJob(id: string) {
  const { data } = await client.get<IndexJob>(`/jobs/${id}`);
  return data;
}

export async function cancelJob(id: string) {
  await client.delete(`/jobs/${id}`);
}
