"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ViewMode = "grid" | "list";
export type ThumbnailSize = "sm" | "md" | "lg";

interface UIState {
  viewMode: ViewMode;
  thumbnailSize: ThumbnailSize;
  sidebarCollapsed: boolean;
  mobileMenuOpen: boolean;
  setViewMode: (m: ViewMode) => void;
  toggleView: () => void;
  setThumbnailSize: (s: ThumbnailSize) => void;
  setSidebarCollapsed: (c: boolean) => void;
  toggleSidebar: () => void;
  setMobileMenuOpen: (open: boolean) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      viewMode: "grid",
      thumbnailSize: "md",
      sidebarCollapsed: false,
      mobileMenuOpen: false,

      setViewMode: (viewMode) => set({ viewMode }),
      toggleView: () =>
        set((s) => ({ viewMode: s.viewMode === "grid" ? "list" : "grid" })),
      setThumbnailSize: (thumbnailSize) => set({ thumbnailSize }),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
      toggleSidebar: () =>
        set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setMobileMenuOpen: (mobileMenuOpen) => set({ mobileMenuOpen }),
    }),
    {
      name: "indexxxer-ui",
      partialize: (state: UIState) => ({
        viewMode: state.viewMode,
        thumbnailSize: state.thumbnailSize,
        sidebarCollapsed: state.sidebarCollapsed,
      }),
    }
  )
);
