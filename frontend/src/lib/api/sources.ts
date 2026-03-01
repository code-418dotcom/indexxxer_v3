import type { IndexJob, MediaSource, ScanRequest, SourceCreate, SourceUpdate } from "@/types/api";
import client from "./client";

export async function listSources() {
  const { data } = await client.get<MediaSource[]>("/sources");
  return data;
}

export async function getSource(id: string) {
  const { data } = await client.get<MediaSource>(`/sources/${id}`);
  return data;
}

export async function createSource(payload: SourceCreate) {
  const { data } = await client.post<MediaSource>("/sources", payload);
  return data;
}

export async function updateSource(id: string, payload: SourceUpdate) {
  const { data } = await client.put<MediaSource>(`/sources/${id}`, payload);
  return data;
}

export async function deleteSource(id: string) {
  await client.delete(`/sources/${id}`);
}

export async function triggerScan(id: string, payload: ScanRequest) {
  const { data } = await client.post<IndexJob>(`/sources/${id}/scan`, payload);
  return data;
}
