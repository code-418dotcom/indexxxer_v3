"use client";

import Image from "next/image";
import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Camera,
  ExternalLink,
  RefreshCw,
  Trash2,
  UserCircle,
} from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { ImageOverlay } from "@/components/media/ImageOverlay";
import { VideoOverlay } from "@/components/media/VideoOverlay";
import {
  deletePerformer,
  getPerformer,
  getPerformerMedia,
  matchPerformer,
  performerImageUrl,
  scrapePerformer,
  uploadPerformerImage,
} from "@/lib/api/performers";
import { thumbnailUrl } from "@/lib/api/media";
import type { MediaItem } from "@/types/api";

// ── Info row ─────────────────────────────────────────────────────────────────

function InfoRow({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="flex justify-between py-1.5 border-b border-[var(--color-border)] last:border-0">
      <span className="text-xs text-[var(--color-muted-foreground)]">{label}</span>
      <span className="text-xs text-[var(--color-foreground)] text-right max-w-[60%]">{value}</span>
    </div>
  );
}

// ── Media card ───────────────────────────────────────────────────────────────

function MediaCard({ item, onClick }: { item: MediaItem; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      className="group relative rounded-lg overflow-hidden border border-[var(--color-border)] bg-[var(--color-card)] hover:border-[hsl(217_33%_30%)] hover:shadow-lg transition-all cursor-pointer"
    >
      <div className="relative w-full aspect-video bg-[var(--color-muted)]">
        {item.thumbnail_url ? (
          <Image
            src={item.thumbnail_url}
            alt={item.filename}
            fill
            className="object-cover transition-transform duration-300 group-hover:scale-105"
            unoptimized
          />
        ) : (
          <div className="flex items-center justify-center h-full text-[var(--color-muted-foreground)] text-xs">
            No thumb
          </div>
        )}
        {item.duration_seconds != null && item.duration_seconds > 0 && (
          <span className="absolute bottom-1 right-1 text-[10px] font-mono bg-black/70 text-white px-1 py-0.5 rounded">
            {Math.floor(item.duration_seconds / 60)}:{String(Math.floor(item.duration_seconds % 60)).padStart(2, "0")}
          </span>
        )}
      </div>
      <div className="px-2 py-1.5">
        <p className="text-[11px] text-[var(--color-foreground)] truncate">{item.filename}</p>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PerformerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [mediaPage, setMediaPage] = useState(1);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [selected, setSelected] = useState<MediaItem | null>(null);

  const { data: performer, isLoading } = useQuery({
    queryKey: ["performer", id],
    queryFn: () => getPerformer(id),
    staleTime: 30_000,
  });

  const { data: mediaData, isLoading: mediaLoading } = useQuery({
    queryKey: ["performer-media", id, mediaPage],
    queryFn: () => getPerformerMedia(id, { page: mediaPage, limit: 36 }),
    staleTime: 30_000,
  });

  const scrape = useMutation({
    mutationFn: () => scrapePerformer(id),
    onSuccess: () => {
      // Refetch after a delay to allow scraping to complete
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["performer", id] }), 5000);
    },
  });

  const match = useMutation({
    mutationFn: () => matchPerformer(id),
    onSuccess: () => {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["performer", id] });
        queryClient.invalidateQueries({ queryKey: ["performer-media", id] });
      }, 3000);
    },
  });

  const uploadImage = useMutation({
    mutationFn: (file: File) => uploadPerformerImage(id, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["performer", id] });
    },
  });

  const doDelete = useMutation({
    mutationFn: () => deletePerformer(id),
    onSuccess: () => {
      router.push("/performers");
    },
  });

  const media = mediaData?.items ?? [];
  const mediaPages = mediaData?.pages ?? 1;
  const mediaTotal = mediaData?.total ?? 0;

  if (isLoading) {
    return (
      <div className="flex flex-col h-full">
        <Topbar title="Performer" />
        <div className="flex items-center justify-center h-64 text-[var(--color-muted-foreground)]">Loading...</div>
      </div>
    );
  }

  if (!performer) {
    return (
      <div className="flex flex-col h-full">
        <Topbar title="Performer" />
        <div className="flex items-center justify-center h-64 text-[var(--color-muted-foreground)]">Not found</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <Topbar title={performer.name}>
        <div className="flex items-center gap-2">
          <button
            onClick={() => router.push("/performers")}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] hover:bg-[var(--color-muted)] transition-colors"
          >
            <ArrowLeft className="w-3 h-3" /> Back
          </button>
        </div>
      </Topbar>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto p-4">
          <div className="flex flex-col md:flex-row gap-6">
            {/* Left: Profile image + actions */}
            <div className="md:w-64 shrink-0 space-y-3">
              {/* Profile image — click to replace */}
              <div
                className="relative w-full aspect-[3/4] rounded-xl overflow-hidden border border-[var(--color-border)] bg-[var(--color-muted)] cursor-pointer group"
                onClick={() => fileInputRef.current?.click()}
              >
                {performer.profile_image_url ? (
                  <Image
                    src={performerImageUrl(performer.id)}
                    alt={performer.name}
                    fill
                    className="object-cover"
                    unoptimized
                  />
                ) : (
                  <div className="flex items-center justify-center h-full">
                    <UserCircle className="w-20 h-20 text-[var(--color-muted-foreground)] opacity-30" />
                  </div>
                )}
                <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                  <Camera className="w-8 h-8 text-white" />
                </div>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) uploadImage.mutate(file);
                  e.target.value = "";
                }}
              />

              {/* Action buttons */}
              <div className="space-y-1.5">
                <button
                  onClick={() => scrape.mutate()}
                  disabled={scrape.isPending}
                  className="flex items-center gap-1.5 w-full px-3 py-1.5 rounded-lg text-xs font-medium border border-[var(--color-border)] hover:border-[hsl(217_33%_30%)] hover:bg-[var(--color-muted)] disabled:opacity-50 transition-all"
                >
                  <RefreshCw className={`w-3 h-3 ${scrape.isPending ? "animate-spin" : ""}`} />
                  {scrape.isPending ? "Scraping..." : "Scrape Freeones"}
                </button>
                <button
                  onClick={() => match.mutate()}
                  disabled={match.isPending}
                  className="flex items-center gap-1.5 w-full px-3 py-1.5 rounded-lg text-xs font-medium border border-[var(--color-border)] hover:border-[hsl(217_33%_30%)] hover:bg-[var(--color-muted)] disabled:opacity-50 transition-all"
                >
                  <RefreshCw className={`w-3 h-3 ${match.isPending ? "animate-spin" : ""}`} />
                  {match.isPending ? "Matching..." : "Re-match Files"}
                </button>
                {performer.freeones_url && (
                  <a
                    href={performer.freeones_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 w-full px-3 py-1.5 rounded-lg text-xs font-medium border border-[var(--color-border)] hover:border-[hsl(217_33%_30%)] hover:bg-[var(--color-muted)] transition-all text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
                  >
                    <ExternalLink className="w-3 h-3" />
                    View on Freeones
                  </a>
                )}
                {confirmDelete ? (
                  <button
                    onClick={() => doDelete.mutate()}
                    disabled={doDelete.isPending}
                    className="flex items-center gap-1.5 w-full px-3 py-1.5 rounded-lg text-xs font-medium border border-red-500/60 text-red-400 hover:bg-red-500/10 disabled:opacity-50 transition-all"
                  >
                    <Trash2 className="w-3 h-3" />
                    Confirm Delete
                  </button>
                ) : (
                  <button
                    onClick={() => setConfirmDelete(true)}
                    className="flex items-center gap-1.5 w-full px-3 py-1.5 rounded-lg text-xs font-medium border border-[var(--color-border)] text-[var(--color-muted-foreground)] hover:border-red-500/50 hover:text-red-400 transition-all"
                  >
                    <Trash2 className="w-3 h-3" />
                    Delete Performer
                  </button>
                )}
              </div>
            </div>

            {/* Right: Info + Media */}
            <div className="flex-1 min-w-0 space-y-6">
              {/* Bio info */}
              <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] overflow-hidden">
                <div className="px-4 py-3 border-b border-[var(--color-border)]">
                  <h2 className="text-sm font-semibold text-[var(--color-foreground)]">Profile</h2>
                </div>
                <div className="px-4 py-2">
                  {performer.bio && (
                    <p className="text-xs text-[var(--color-muted-foreground)] mb-3 leading-relaxed">
                      {performer.bio}
                    </p>
                  )}
                  <InfoRow label="Birthdate" value={performer.birthdate} />
                  <InfoRow label="Birthplace" value={performer.birthplace} />
                  <InfoRow label="Nationality" value={performer.nationality} />
                  <InfoRow label="Ethnicity" value={performer.ethnicity} />
                  <InfoRow label="Hair Color" value={performer.hair_color} />
                  <InfoRow label="Eye Color" value={performer.eye_color} />
                  <InfoRow label="Height" value={performer.height} />
                  <InfoRow label="Weight" value={performer.weight} />
                  <InfoRow label="Measurements" value={performer.measurements} />
                  <InfoRow label="Years Active" value={performer.years_active} />
                  {performer.aliases && performer.aliases.length > 0 && (
                    <InfoRow label="Aliases" value={performer.aliases.join(", ")} />
                  )}
                  {performer.scraped_at && (
                    <InfoRow
                      label="Last Scraped"
                      value={new Date(performer.scraped_at).toLocaleDateString()}
                    />
                  )}
                  {!performer.bio &&
                    !performer.birthdate &&
                    !performer.nationality && (
                      <p className="text-xs text-[var(--color-muted-foreground)] opacity-50 py-2">
                        No profile data yet. Click &quot;Scrape Freeones&quot; to fetch bio data.
                      </p>
                    )}
                </div>
              </div>

              {/* Media grid */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-semibold text-[var(--color-foreground)]">
                    Media ({mediaTotal})
                  </h2>
                </div>

                {mediaLoading && (
                  <div className="text-xs text-[var(--color-muted-foreground)]">Loading media...</div>
                )}

                {!mediaLoading && media.length === 0 && (
                  <p className="text-xs text-[var(--color-muted-foreground)] opacity-50">
                    No media linked yet. Try &quot;Re-match Files&quot; or add this performer&apos;s name to your filenames/directories.
                  </p>
                )}

                {media.length > 0 && (
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
                    {media.map((item) => (
                      <MediaCard key={item.id} item={item} onClick={() => setSelected(item)} />
                    ))}
                  </div>
                )}

                {mediaPages > 1 && (
                  <div className="flex items-center justify-center gap-2 mt-4">
                    <button
                      onClick={() => setMediaPage((p) => Math.max(1, p - 1))}
                      disabled={mediaPage <= 1}
                      className="px-3 py-1 rounded text-xs border border-[var(--color-border)] hover:bg-[var(--color-muted)] disabled:opacity-30 transition-colors"
                    >
                      Prev
                    </button>
                    <span className="text-xs text-[var(--color-muted-foreground)]">
                      {mediaPage} / {mediaPages}
                    </span>
                    <button
                      onClick={() => setMediaPage((p) => Math.min(mediaPages, p + 1))}
                      disabled={mediaPage >= mediaPages}
                      className="px-3 py-1 rounded text-xs border border-[var(--color-border)] hover:bg-[var(--color-muted)] disabled:opacity-30 transition-colors"
                    >
                      Next
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Overlays */}
      {selected && selected.media_type === "image" && (
        <ImageOverlay item={selected} onClose={() => setSelected(null)} />
      )}
      {selected && selected.media_type === "video" && (
        <VideoOverlay item={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
