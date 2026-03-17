import client from "./client";

export interface ProwlarrResult {
  title: string;
  size: number;
  seeders: number;
  leechers: number;
  age: string;
  magnet_url: string | null;
  download_url: string | null;
  indexer: string;
  categories: string[];
  info_url: string | null;
}

export interface ProwlarrSearchResponse {
  query: string;
  results: ProwlarrResult[];
  count: number;
}

export interface TorrentDownload {
  id: string;
  torrent_hash: string;
  title: string;
  size: number | null;
  performer_id: string | null;
  performer_name: string | null;
  status: string;
  progress: number;
  source_url: string | null;
  indexer: string | null;
  destination_path: string | null;
  created_at: string;
  completed_at: string | null;
}

export async function searchProwlarr(q: string): Promise<ProwlarrSearchResponse> {
  const { data } = await client.get("/torrents/search", { params: { q } });
  return data;
}

export async function sendToTransmission(req: {
  title: string;
  magnet_url?: string | null;
  download_url?: string | null;
  performer_id: string;
  size?: number | null;
  indexer?: string | null;
}): Promise<TorrentDownload> {
  const { data } = await client.post("/torrents/download", req);
  return data;
}

export async function getActiveDownloads(): Promise<TorrentDownload[]> {
  const { data } = await client.get("/torrents/active");
  return data;
}

export async function getDownloadHistory(): Promise<TorrentDownload[]> {
  const { data } = await client.get("/torrents/history");
  return data;
}

export async function cancelDownload(id: string): Promise<void> {
  await client.delete(`/torrents/${id}`);
}
