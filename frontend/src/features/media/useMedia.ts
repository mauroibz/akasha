import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { queryKeys } from "@/api/keys";
import type { ItemType } from "@/api/library";
import { getMedia, type Media } from "@/api/media";
import { useItemTypes } from "@/features/library/useItemTypes";

/** The person's media, in their order (Sprint 143, DEC-193). */
export function useMedia() {
  return useQuery({
    queryKey: queryKeys.media,
    queryFn: ({ signal }) => getMedia(signal),
    staleTime: Infinity,
    retry: false,
  });
}

/**
 * The registry in the person's order, without what they turned off.
 *
 * A medium the list does not name keeps its place after those it does, as the
 * server appends it. An answer that is not a list is treated as no preference: the
 * registry as declared, because the media a person can reach must never depend on
 * this request having worked.
 */
export function inTheirOrder(
  types: ItemType[] | undefined,
  media: Media | undefined,
): ItemType[] {
  const all = Array.isArray(types) ? types : [];
  const rows = Array.isArray(media?.media) ? media.media : [];
  if (rows.length === 0) return all;
  const byId = new Map(all.map((type) => [type.id, type]));
  const named = new Set(rows.map((row) => row.item_type));
  return [
    ...rows.flatMap((row) => {
      const type = byId.get(row.item_type);
      return type && row.presence !== "off" ? [type] : [];
    }),
    ...all.filter((type) => !named.has(type.id)),
  ];
}

/**
 * The media a chooser offers: the registry, in the person's order, minus what is off.
 *
 * `useItemTypes` stays the whole registry, for labels and vocabularies: an entry of a
 * medium that is off still opens and still reads in its own words. This is only for
 * the places that ask "which medium?". Nothing is offered until both requests have
 * settled, so a chooser never shows one order and then another.
 */
export function useShownItemTypes() {
  const itemTypes = useItemTypes();
  const media = useMedia();
  const settled = !media.isPending;
  const data = useMemo(
    () =>
      itemTypes.data && settled
        ? inTheirOrder(itemTypes.data, media.data)
        : undefined,
    [itemTypes.data, media.data, settled],
  );
  return { data, isPending: itemTypes.isPending || !settled };
}
