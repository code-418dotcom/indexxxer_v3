"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useCurrentUser } from "@/hooks/useCurrentUser";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { data: user, isLoading, isError } = useCurrentUser();

  useEffect(() => {
    if (!isLoading && (isError || (user && user.role !== "admin"))) {
      router.push("/library");
    }
  }, [user, isLoading, isError, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen text-neutral-400">
        Loading…
      </div>
    );
  }

  if (!user || user.role !== "admin") return null;

  return <>{children}</>;
}
