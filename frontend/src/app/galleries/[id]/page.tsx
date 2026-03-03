"use client";

import Image from "next/image";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Archive, ArrowLeft, Loader2 } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { GalleryLightbox } from "@/components/media/GalleryLightbox";
import { galleryImageUrl, getGallery } from "@/lib/api/galleries";
import type { GalleryImage } from "@/types/api";

export default function GalleryDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  // Escape with no lightbox open → back to galleries overview
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && lightboxIndex === null) {
        router.push("/galleries");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [lightboxIndex, router]);

  const { data: gallery, isLoading } = useQuery({
    queryKey: ["gallery", id],
    queryFn: () => getGallery(id),
    staleTime: 60_000,
  });

  const images: GalleryImage[] = gallery?.images ?? [];

  return (
    <div className="flex flex-col h-full">
      <Topbar
        title={
          <span className="flex items-center gap-2">
            <Link
              href="/galleries"
              className="flex items-center gap-1 text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Galleries
            </Link>
            <span className="text-[var(--color-muted-foreground)] opacity-40">/</span>
            <span>{gallery?.filename ?? "…"}</span>
          </span>
        }
      />

      {/* Stats bar */}
      <div className="flex items-center gap-3 px-5 py-2 border-b border-[var(--color-border)] text-xs text-[var(--color-muted-foreground)]">
        {isLoading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <span>{images.length.toLocaleString()} images</span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4">
        {isLoading && (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--color-muted-foreground)]">
            <Loader2 className="w-8 h-8 animate-spin" />
            <span className="text-sm">Loading…</span>
          </div>
        )}

        {!isLoading && images.length === 0 && (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--color-muted-foreground)]">
            <Archive className="w-12 h-12 opacity-30" />
            <p className="text-sm">No images in this gallery.</p>
          </div>
        )}

        {images.length > 0 && (
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8 gap-2">
            {images.map((img) => (
              <button
                key={img.id}
                onClick={() => setLightboxIndex(img.index_order)}
                className="relative aspect-square rounded overflow-hidden bg-[var(--color-muted)] hover:ring-2 hover:ring-[hsl(217_91%_60%)] transition-all group"
                title={img.filename.split("/").pop()}
              >
                <Image
                  src={galleryImageUrl(id, img.index_order)}
                  alt={`Image ${img.index_order + 1}`}
                  fill
                  className="object-cover transition-transform duration-200 group-hover:scale-105"
                  unoptimized
                />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Lightbox */}
      {lightboxIndex !== null && gallery && (
        <GalleryLightbox
          galleryId={id}
          images={images}
          index={lightboxIndex}
          onClose={() => setLightboxIndex(null)}
          onNavigate={setLightboxIndex}
        />
      )}
    </div>
  );
}
