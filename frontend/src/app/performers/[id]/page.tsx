"use client";

import Image from "next/image";
import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Camera,
  ExternalLink,
  Film,
  ImageIcon,
  RefreshCw,
  Trash2,
  UserCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Topbar } from "@/components/layout/Topbar";
import { ImageOverlay } from "@/components/media/ImageOverlay";
import { VideoOverlay } from "@/components/media/VideoOverlay";
import {
  deletePerformer,
  getPerformer,
  getPerformerGalleries,
  getPerformerMedia,
  matchPerformer,
  performerImageUrl,
  scrapePerformer,
  setImageFromGallery,
  setImageFromThumbnail,
  setImageFromUrl,
  uploadPerformerImage,
} from "@/lib/api/performers";
import { galleryCoverUrl, galleryImageUrl, getGallery } from "@/lib/api/galleries";
import { thumbnailUrl } from "@/lib/api/media";
import { formatBytes } from "@/lib/utils";
import type { Gallery, GalleryDetail, MediaItem } from "@/types/api";

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

function MediaCard({ item, onClick, onSetProfile }: { item: MediaItem; onClick: () => void; onSetProfile?: () => void }) {
  return (
    <div className="group relative rounded-lg overflow-hidden border border-[var(--color-border)] bg-[var(--color-card)] hover:border-[hsl(217_33%_30%)] hover:shadow-lg transition-all">
      <div
        onClick={onClick}
        className="relative w-full aspect-video bg-[var(--color-muted)] cursor-pointer"
      >
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
      <div className="px-2 py-1.5 flex items-center justify-between gap-1">
        <p className="text-[11px] text-[var(--color-foreground)] truncate min-w-0">{item.filename}</p>
        {onSetProfile && item.thumbnail_url && (
          <button
            onClick={(e) => { e.stopPropagation(); onSetProfile(); }}
            className="shrink-0 p-1 rounded hover:bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:text-[hsl(217_91%_65%)] transition-colors"
            title="Set as performer profile image"
          >
            <Camera className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}

// ── Gallery card ────────────────────────────────────────────────────────────

function GalleryCard({ gallery, onPickImage }: { gallery: Gallery; onPickImage: (galleryId: string) => void }) {
  const cover = gallery.cover_url ? galleryCoverUrl(gallery.id) : null;

  return (
    <div className="group relative rounded-lg overflow-hidden border border-[var(--color-border)] bg-[var(--color-card)] hover:border-[hsl(217_33%_30%)] hover:shadow-lg transition-all">
      <a href={`/galleries/${gallery.id}`} className="cursor-pointer">
        <div className="relative w-full aspect-square bg-[var(--color-muted)]">
          {cover ? (
            <Image
              src={cover}
              alt={gallery.filename}
              fill
              className="object-cover transition-transform duration-300 group-hover:scale-105"
              unoptimized
            />
          ) : (
            <div className="flex items-center justify-center h-full">
              <ImageIcon className="w-10 h-10 text-[var(--color-muted-foreground)] opacity-30" />
            </div>
          )}
          <span className="absolute bottom-1.5 right-1.5 text-[10px] font-semibold bg-black/70 text-white px-1.5 py-0.5 rounded">
            {gallery.image_count} images
          </span>
        </div>
      </a>
      <div className="px-2 py-1.5 flex items-center justify-between gap-1">
        <div className="min-w-0">
          <p className="text-[11px] text-[var(--color-foreground)] truncate" title={gallery.filename}>
            {gallery.filename}
          </p>
          {gallery.file_size && (
            <p className="text-[10px] text-[var(--color-muted-foreground)] mt-0.5">
              {formatBytes(gallery.file_size)}
            </p>
          )}
        </div>
        <button
          onClick={(e) => { e.preventDefault(); onPickImage(gallery.id); }}
          className="shrink-0 p-1 rounded hover:bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:text-[hsl(217_91%_65%)] transition-colors"
          title="Pick profile image from this gallery"
        >
          <Camera className="w-3.5 h-3.5" />
        </button>
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
  const [galleryPage, setGalleryPage] = useState(1);
  const [activeTab, setActiveTab] = useState<"video" | "gallery">("video");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [selected, setSelected] = useState<MediaItem | null>(null);
  const [pickingGallery, setPickingGallery] = useState<string | null>(null);
  const [imgVersion, setImgVersion] = useState(0);
  const [imageUrl, setImageUrl] = useState("");

  const { data: performer, isLoading } = useQuery({
    queryKey: ["performer", id],
    queryFn: () => getPerformer(id),
    staleTime: 30_000,
  });

  const { data: mediaData, isLoading: mediaLoading } = useQuery({
    queryKey: ["performer-media", id, mediaPage],
    queryFn: () => getPerformerMedia(id, { page: mediaPage, limit: 36, type: "video" }),
    staleTime: 30_000,
    enabled: activeTab === "video",
  });

  const { data: galleriesData, isLoading: galleriesLoading } = useQuery({
    queryKey: ["performer-galleries", id, galleryPage],
    queryFn: () => getPerformerGalleries(id, { page: galleryPage, limit: 36 }),
    staleTime: 30_000,
    enabled: activeTab === "gallery",
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
      setImgVersion((v) => v + 1);
      queryClient.invalidateQueries({ queryKey: ["performer", id] });
    },
  });

  const doDelete = useMutation({
    mutationFn: () => deletePerformer(id),
    onSuccess: () => {
      router.push("/performers");
    },
  });

  const { data: pickerGallery } = useQuery({
    queryKey: ["gallery-detail", pickingGallery],
    queryFn: () => getGallery(pickingGallery!),
    enabled: !!pickingGallery,
  });

  const setFromUrl = useMutation({
    mutationFn: (url: string) => setImageFromUrl(id, url),
    onSuccess: () => {
      setImgVersion((v) => v + 1);
      setImageUrl("");
      queryClient.invalidateQueries({ queryKey: ["performer", id] });
    },
  });

  const setFromThumbnail = useMutation({
    mutationFn: (mediaId: string) => setImageFromThumbnail(id, mediaId),
    onSuccess: () => {
      setImgVersion((v) => v + 1);
      queryClient.invalidateQueries({ queryKey: ["performer", id] });
    },
  });

  const setFromGallery = useMutation({
    mutationFn: ({ galleryId, imageIndex }: { galleryId: string; imageIndex: number }) =>
      setImageFromGallery(id, galleryId, imageIndex),
    onSuccess: () => {
      setImgVersion((v) => v + 1);
      queryClient.invalidateQueries({ queryKey: ["performer", id] });
      setPickingGallery(null);
    },
  });

  const media = mediaData?.items ?? [];
  const mediaPages = mediaData?.pages ?? 1;
  const mediaTotal = mediaData?.total ?? 0;

  const galleries = (galleriesData?.items ?? []) as Gallery[];
  const galleryPages = galleriesData?.pages ?? 1;
  const galleryTotal = galleriesData?.total ?? 0;

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
                    src={`${performerImageUrl(performer.id)}?v=${imgVersion}`}
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
                <div className="flex gap-1">
                  <input
                    type="text"
                    placeholder="Image URL"
                    value={imageUrl}
                    onChange={(e) => setImageUrl(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && imageUrl.trim()) setFromUrl.mutate(imageUrl.trim());
                    }}
                    className="flex-1 min-w-0 px-2 py-1.5 rounded-lg text-xs bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)]"
                  />
                  <button
                    onClick={() => { if (imageUrl.trim()) setFromUrl.mutate(imageUrl.trim()); }}
                    disabled={!imageUrl.trim() || setFromUrl.isPending}
                    className="shrink-0 px-2 py-1.5 rounded-lg text-xs font-medium border border-[var(--color-border)] hover:border-[hsl(217_33%_30%)] hover:bg-[var(--color-muted)] disabled:opacity-50 transition-all"
                  >
                    {setFromUrl.isPending ? "..." : "Set"}
                  </button>
                </div>
                {setFromUrl.isError && (
                  <p className="text-[10px] text-red-400">
                    {(setFromUrl.error as Error)?.message || "Failed to download image"}
                  </p>
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

              {/* Media / Galleries */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-1 rounded-lg bg-[var(--color-muted)] p-0.5">
                    <button
                      onClick={() => { setActiveTab("video"); setMediaPage(1); }}
                      className={cn(
                        "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                        activeTab === "video"
                          ? "bg-[var(--color-card)] text-[var(--color-foreground)] shadow-sm"
                          : "text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
                      )}
                    >
                      <Film className="w-3 h-3" />
                      Videos
                    </button>
                    <button
                      onClick={() => { setActiveTab("gallery"); setGalleryPage(1); }}
                      className={cn(
                        "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                        activeTab === "gallery"
                          ? "bg-[var(--color-card)] text-[var(--color-foreground)] shadow-sm"
                          : "text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
                      )}
                    >
                      <ImageIcon className="w-3 h-3" />
                      Galleries
                    </button>
                  </div>
                  <span className="text-xs text-[var(--color-muted-foreground)]">
                    {activeTab === "video"
                      ? `${mediaTotal} video${mediaTotal !== 1 ? "s" : ""}`
                      : `${galleryTotal} galler${galleryTotal !== 1 ? "ies" : "y"}`}
                  </span>
                </div>

                {/* Videos tab */}
                {activeTab === "video" && (
                  <>
                    {mediaLoading && (
                      <div className="text-xs text-[var(--color-muted-foreground)]">Loading videos...</div>
                    )}

                    {!mediaLoading && media.length === 0 && (
                      <p className="text-xs text-[var(--color-muted-foreground)] opacity-50">
                        No videos linked yet. Try &quot;Re-match Files&quot; or add this performer&apos;s name to your filenames/directories.
                      </p>
                    )}

                    {media.length > 0 && (
                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
                        {media.map((item) => (
                          <MediaCard
                            key={item.id}
                            item={item}
                            onClick={() => setSelected(item)}
                            onSetProfile={() => setFromThumbnail.mutate(item.id)}
                          />
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
                  </>
                )}

                {/* Galleries tab */}
                {activeTab === "gallery" && (
                  <>
                    {galleriesLoading && (
                      <div className="text-xs text-[var(--color-muted-foreground)]">Loading galleries...</div>
                    )}

                    {!galleriesLoading && galleries.length === 0 && (
                      <p className="text-xs text-[var(--color-muted-foreground)] opacity-50">
                        No galleries found. Make sure gallery folders contain this performer&apos;s name in the path.
                      </p>
                    )}

                    {galleries.length > 0 && (
                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
                        {galleries.map((g) => (
                          <GalleryCard key={g.id} gallery={g} onPickImage={setPickingGallery} />
                        ))}
                      </div>
                    )}

                    {galleryPages > 1 && (
                      <div className="flex items-center justify-center gap-2 mt-4">
                        <button
                          onClick={() => setGalleryPage((p) => Math.max(1, p - 1))}
                          disabled={galleryPage <= 1}
                          className="px-3 py-1 rounded text-xs border border-[var(--color-border)] hover:bg-[var(--color-muted)] disabled:opacity-30 transition-colors"
                        >
                          Prev
                        </button>
                        <span className="text-xs text-[var(--color-muted-foreground)]">
                          {galleryPage} / {galleryPages}
                        </span>
                        <button
                          onClick={() => setGalleryPage((p) => Math.min(galleryPages, p + 1))}
                          disabled={galleryPage >= galleryPages}
                          className="px-3 py-1 rounded text-xs border border-[var(--color-border)] hover:bg-[var(--color-muted)] disabled:opacity-30 transition-colors"
                        >
                          Next
                        </button>
                      </div>
                    )}
                  </>
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

      {/* Gallery image picker overlay */}
      {pickingGallery && (
        <div
          className="fixed inset-0 z-50 bg-black/80 overflow-y-auto"
          onClick={() => setPickingGallery(null)}
        >
          <div
            className="relative w-full max-w-4xl mx-auto px-4 pt-6 pb-12"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-white">
                Select profile image
              </h2>
              <button
                onClick={() => setPickingGallery(null)}
                className="p-2 rounded-lg text-white/50 hover:text-white transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
            </div>

            {!pickerGallery ? (
              <div className="flex items-center justify-center h-32 text-white/50 text-sm">
                Loading gallery...
              </div>
            ) : (
              <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-2">
                {pickerGallery.images.map((img) => (
                  <button
                    key={img.id}
                    onClick={() =>
                      setFromGallery.mutate({
                        galleryId: pickingGallery,
                        imageIndex: img.index_order,
                      })
                    }
                    disabled={setFromGallery.isPending}
                    className="relative aspect-square rounded-lg overflow-hidden border border-white/10 hover:border-[hsl(217_91%_60%)] hover:ring-2 hover:ring-[hsl(217_91%_60%/0.3)] transition-all group"
                  >
                    <Image
                      src={galleryImageUrl(pickingGallery, img.index_order)}
                      alt={img.filename}
                      fill
                      className="object-cover transition-transform duration-200 group-hover:scale-105"
                      unoptimized
                    />
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-center justify-center">
                      <Camera className="w-6 h-6 text-white opacity-0 group-hover:opacity-100 transition-opacity drop-shadow" />
                    </div>
                  </button>
                ))}
              </div>
            )}

            {setFromGallery.isPending && (
              <div className="mt-4 text-center text-sm text-white/50">
                Setting profile image...
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
