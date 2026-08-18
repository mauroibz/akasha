import { useQuery } from "@tanstack/react-query";

import { getItemTypes } from "@/api/library";

/**
 * The domain registry, fetched once for the whole session.
 *
 * It changes with a deployment, never with a library edit, so every screen that needs
 * a field spec or a status label shares one cached request rather than adding one of
 * its own. A failure renders the shared vocabulary: the registry must never be the
 * reason a page is blank.
 */
export function useItemTypes() {
  return useQuery({
    queryKey: ["item-types"],
    queryFn: getItemTypes,
    staleTime: Infinity,
    retry: false,
  });
}
