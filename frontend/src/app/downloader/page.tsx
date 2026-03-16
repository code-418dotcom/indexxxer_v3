"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Download,
  FolderOpen,
  ImageIcon,
  Loader2,
  Search,
} from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import {
  getDownloadHistory,
  previewGallery,
  startDownloadWithUrls,
} from "@/lib/api/downloader";
import { formatBytes } from "@/lib/utils";

export default function DownloaderPage() {
  const qc = useQueryClient();
  const [url, setUrl] = useState("");
  const [subdirectory, setSubdirectory] = useState("");
  const [imageUrls, setImageUrls] = useState<string[]>([]);

  const preview = useMutation({
    mutationFn: () => previewGallery(url),
    onSuccess: (data) => {
      if (data.images.length > 0) {
        setImageUrls(data.images);
      }
    },
  });

  const download = useMutation({
    mutationFn: () => startDownloadWithUrls(imageUrls, subdirectory),
    onSuccess: () => {
      setTimeout(() => qc.invalidateQueries({ queryKey: ["download-history"] }), 5000);
    },
  });

  const { data: history } = useQuery({
    queryKey: ["download-history"],
    queryFn: getDownloadHistory,
    refetchInterval: 10_000,
  });

  function handlePreview() {
    if (!url.trim()) return;
    if (!subdirectory) {
      const parts = url.split("/").filter(Boolean);
      const slug = parts[parts.length - 1] || parts[parts.length - 2] || "gallery";
      setSubdirectory(slug.replace(/[^a-zA-Z0-9_-]/g, "_").substring(0, 80));
    }
    preview.mutate();
  }

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Downloader">
        <div />
      </Topbar>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-3 md:px-5 py-6 space-y-6">
          {/* Input section */}
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 space-y-3">
            <h2 className="text-sm font-semibold text-[var(--color-foreground)]">
              Download Gallery
            </h2>

            <div className="space-y-2">
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Gallery URL (e.g. https://www.pornpics.com/galleries/...)"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handlePreview(); }}
                  className="flex-1 px-3 py-2 rounded-lg text-sm bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)]"
                />
                <button
                  onClick={handlePreview}
                  disabled={!url.trim() || preview.isPending}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium border border-[var(--color-border)] hover:border-[hsl(217_33%_30%)] hover:bg-[var(--color-muted)] disabled:opacity-50 transition-all shrink-0"
                >
                  {preview.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Search className="w-4 h-4" />
                  )}
                  Preview
                </button>
              </div>

              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Subdirectory name"
                  value={subdirectory}
                  onChange={(e) => setSubdirectory(e.target.value)}
                  className="flex-1 px-3 py-2 rounded-lg text-sm bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)] font-mono"
                />
                <button
                  onClick={() => download.mutate()}
                  disabled={imageUrls.length === 0 || !subdirectory.trim() || download.isPending}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-[hsl(217_91%_60%)] text-white hover:bg-[hsl(217_91%_55%)] disabled:opacity-50 transition-colors shrink-0"
                >
                  {download.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Download className="w-4 h-4" />
                  )}
                  Download {imageUrls.length > 0 ? `(${imageUrls.length})` : ""}
                </button>
              </div>
            </div>

            {preview.isPending && (
              <p className="text-xs text-[var(--color-muted-foreground)]">Scraping page...</p>
            )}
            {preview.isError && (
              <p className="text-xs text-red-400">Failed to scrape page. Try again.</p>
            )}
            {preview.isSuccess && imageUrls.length === 0 && (
              <p className="text-xs text-amber-400">No images found on this page.</p>
            )}

            {download.isSuccess && (
              <div className="flex items-center gap-2 text-xs text-emerald-400">
                <CheckCircle2 className="w-4 h-4" />
                Download started! Saving to /Downloader/{download.data.subdirectory}/
              </div>
            )}
            {download.isError && (
              <p className="text-xs text-red-400">Failed to start download</p>
            )}
          </div>

          {/* Preview grid */}
          {imageUrls.length > 0 && (
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] overflow-hidden">
              <div className="px-4 py-2.5 border-b border-[var(--color-border)]">
                <span className="text-xs font-medium text-[var(--color-foreground)]">
                  {imageUrls.length} images ready to download
                </span>
              </div>
              <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 gap-1 p-2">
                {imageUrls.slice(0, 24).map((imgUrl, i) => (
                  <div key={i} className="relative aspect-square rounded overflow-hidden bg-[var(--color-muted)]">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={imgUrl}
                      alt={`Preview ${i + 1}`}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  </div>
                ))}
                {imageUrls.length > 24 && (
                  <div className="flex items-center justify-center aspect-square rounded bg-[var(--color-muted)] text-[var(--color-muted-foreground)]">
                    <span className="text-xs">+{imageUrls.length - 24}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Download history */}
          {history && history.directories.length > 0 && (
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] overflow-hidden">
              <div className="px-4 py-2.5 border-b border-[var(--color-border)]">
                <span className="text-xs font-medium text-[var(--color-foreground)]">
                  Downloaded Galleries
                </span>
              </div>
              <div className="divide-y divide-[var(--color-border)]">
                {history.directories.map((dir) => (
                  <div key={dir.name} className="flex items-center gap-3 px-4 py-2.5">
                    <FolderOpen className="w-4 h-4 text-[var(--color-muted-foreground)] shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-[var(--color-foreground)] truncate">
                        {dir.name}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 text-[10px] text-[var(--color-muted-foreground)] shrink-0">
                      <span className="flex items-center gap-1">
                        <ImageIcon className="w-3 h-3" />
                        {dir.image_count}
                      </span>
                      <span>{formatBytes(dir.total_size)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
