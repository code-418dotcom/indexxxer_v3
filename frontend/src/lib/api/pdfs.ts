import client from "./client";
import type { PDFDocument, PaginatedResponse } from "@/types/api";

export async function listPDFs(params?: {
  source_id?: string;
  page?: number;
  limit?: number;
}): Promise<PaginatedResponse<PDFDocument>> {
  const { data } = await client.get("/pdfs", { params });
  return data;
}

export async function getPDF(id: string): Promise<PDFDocument> {
  const { data } = await client.get(`/pdfs/${id}`);
  return data;
}

export function pdfCoverUrl(id: string): string {
  return `/api/v1/pdfs/${id}/cover`;
}

export function pdfPageUrl(id: string, page: number): string {
  return `/api/v1/pdfs/${id}/pages/${page}`;
}

export async function triggerPDFScan(sourceId: string): Promise<{ status: string; count: number }> {
  const { data } = await client.post("/pdfs/scan", { source_id: sourceId });
  return data;
}
