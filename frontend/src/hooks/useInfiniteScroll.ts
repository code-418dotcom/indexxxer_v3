import { useEffect, useRef } from "react";

/**
 * Calls `onLoadMore` when a sentinel element enters the viewport.
 *
 * Usage:
 *   const ref = useInfiniteScroll({ onLoadMore: fetchNextPage, disabled: !hasNextPage });
 *   return <div ref={ref} />;  // place at bottom of list
 */
export function useInfiniteScroll({
  onLoadMore,
  disabled = false,
  rootMargin = "200px",
}: {
  onLoadMore: () => void;
  disabled?: boolean;
  rootMargin?: string;
}) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || disabled) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          onLoadMore();
        }
      },
      { rootMargin }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [onLoadMore, disabled, rootMargin]);

  return ref;
}
