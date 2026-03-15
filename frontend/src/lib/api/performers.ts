import client from "./client";
import type { Gallery, PaginatedResponse, Performer, PerformerCreate, PerformerUpdate, MediaItem } from "@/types/api";

export async function listPerformers(params?: {
  page?: number;
  limit?: number;
  q?: string;
  sort?: string;
  order?: string;
}): Promise<PaginatedResponse<Performer>> {
  const { data } = await client.get("/performers", { params });
  return data;
}

export async function getPerformer(id: string): Promise<Performer> {
  const { data } = await client.get(`/performers/${id}`);
  return data;
}

export async function createPerformer(body: PerformerCreate): Promise<Performer> {
  const { data } = await client.post("/performers", body);
  return data;
}

export async function updatePerformer(id: string, body: PerformerUpdate): Promise<Performer> {
  const { data } = await client.put(`/performers/${id}`, body);
  return data;
}

export async function deletePerformer(id: string): Promise<void> {
  await client.delete(`/performers/${id}`);
}

export async function getPerformerMedia(id: string, params?: {
  page?: number;
  limit?: number;
  type?: string;
}): Promise<PaginatedResponse<MediaItem>> {
  const { data } = await client.get(`/performers/${id}/media`, { params });
  return data;
}

export async function getPerformerGalleries(id: string, params?: {
  page?: number;
  limit?: number;
}): Promise<PaginatedResponse<Gallery>> {
  const { data } = await client.get(`/performers/${id}/galleries`, { params });
  return data;
}

export async function scrapePerformer(id: string): Promise<{ status: string }> {
  const { data } = await client.post(`/performers/${id}/scrape`);
  return data;
}

export async function scrapeNewPerformer(body: {
  name?: string;
  freeones_url?: string;
}): Promise<Performer> {
  const { data } = await client.post("/performers/scrape-new", body);
  return data;
}

export async function matchPerformer(id: string): Promise<{ status: string }> {
  const { data } = await client.post(`/performers/${id}/match`);
  return data;
}

export async function matchAllPerformers(): Promise<{ status: string }> {
  const { data } = await client.post("/performers/match-all");
  return data;
}

export async function uploadPerformerImage(id: string, file: File): Promise<Performer> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await client.put(`/performers/${id}/image`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function scrapeAllPerformers(): Promise<{ status: string; task_id: string }> {
  const { data } = await client.post("/performers/scrape-all");
  return data;
}

export function performerImageUrl(id: string): string {
  return `/api/v1/performers/${id}/image`;
}
