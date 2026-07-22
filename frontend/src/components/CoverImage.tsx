import { useState } from "react";

import { cn } from "@/lib/utils";

interface CoverImageProps {
  src: string | null | undefined;
  alt: string;
  className?: string;
  placeholderClassName?: string;
}

export function CoverImage({
  src,
  alt,
  className,
  placeholderClassName,
}: CoverImageProps) {
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded bg-zinc-800",
          placeholderClassName ?? className,
        )}
        aria-label={!src ? "No cover" : "Cover failed to load"}
      >
        <svg
          aria-hidden="true"
          className="h-8 w-8 text-zinc-600"
          fill="none"
          stroke="currentColor"
          strokeWidth={1}
          viewBox="0 0 24 24"
        >
          <path
            d="M12 6.253v13m0-13C10.832 5.477 9.247 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.753 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.753 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.747 0-3.332.477-4.5 1.253"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    );
  }

  return (
    <div className={cn("relative", className)}>
      {!loaded && (
        <div
          className={cn(
            "absolute inset-0 animate-pulse rounded bg-zinc-800",
            className,
          )}
          aria-hidden="true"
        />
      )}
      <img
        className={cn(
          "rounded object-cover transition-opacity duration-200",
          className,
          loaded ? "opacity-100" : "opacity-0",
        )}
        src={src}
        alt={alt}
        onLoad={() => setLoaded(true)}
        onError={() => setFailed(true)}
      />
    </div>
  );
}
