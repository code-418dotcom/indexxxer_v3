import client from "./client";
import type { Gallery, GalleryDetail } from "@/types/api";

export interface GalleryListResponse {
  items: Gallery[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export async function listGalleries(page = 1, limit = 48): Promise<GalleryListResponse> {
  const { data } = await client.get<GalleryListResponse>("/galleries", {
    params: { page, limit },
  });
  return data;
}

export async function getGallery(id: string): Promise<GalleryDetail> {
  const { data } = await client.get<GalleryDetail>(`/galleries/${id}`);
  return data;
}

export function galleryCoverUrl(id: string): string {
  return `/api/v1/galleries/${id}/cover`;
}

export function galleryImageUrl(galleryId: string, index: number): string {
  return `/api/v1/galleries/${galleryId}/images/${index}`;
}

export async function triggerGalleryScan(): Promise<{ status: string; sources: number; task_ids: string[] }> {
  const { data } = await client.post("/galleries/scan");
  return data;
}
