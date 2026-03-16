import client from "./client";

export interface DownloadPreviewResponse {
  images: string[];
  count: number;
  error?: string;
}

export interface DownloadStartResponse {
  task_id: string;
  status: string;
  subdirectory: string;
  error?: string;
}

export interface DownloadHistoryDir {
  name: string;
  image_count: number;
  total_size: number;
}

export async function previewGallery(url: string): Promise<DownloadPreviewResponse> {
  const { data } = await client.post("/downloader/preview", { url });
  return data;
}

export async function startDownload(url: string, subdirectory: string): Promise<DownloadStartResponse> {
  const { data } = await client.post("/downloader/start", { url, subdirectory });
  return data;
}

export async function startDownloadWithUrls(imageUrls: string[], subdirectory: string): Promise<DownloadStartResponse> {
  const { data } = await client.post("/downloader/start-urls", { image_urls: imageUrls, subdirectory });
  return data;
}

export async function getDownloadHistory(): Promise<{ directories: DownloadHistoryDir[] }> {
  const { data } = await client.get("/downloader/history");
  return data;
}
