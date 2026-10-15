import { useState } from "react";

/** A product's photo on the stock and sale lists; a plain mark with its first letter when there is none, or it does not load (P3-T02). */
export function ProductPhoto({ url, name }: { url: string | null; name: string }) {
  const [failed, setFailed] = useState(false);
  if (url === null || failed) {
    return (
      <span
        aria-hidden="true"
        className="flex h-12 w-12 shrink-0 items-center justify-center rounded-control bg-sea-soft text-lg font-bold text-ink-2"
      >
        {name.charAt(0).toUpperCase()}
      </span>
    );
  }
  return (
    <img
      src={url}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
      className="h-12 w-12 shrink-0 rounded-control object-cover"
    />
  );
}
