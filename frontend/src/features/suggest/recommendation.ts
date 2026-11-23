import type {
  ItemType,
  RecommendationInfo,
  RecommendationSourceInfo,
} from "@/api/library";

/**
 * What a library says about *More like this* (Sprint 134), read from the server's
 * item types: `null` where nothing suggests its things, so no button is drawn.
 */
export function recommendationFor(
  type: string,
  types: ItemType[] | undefined,
): RecommendationInfo | null {
  const info = types?.find(
    (candidate) => candidate.id === type,
  )?.recommendation;
  return info && info.sources.length ? info : null;
}

/** The first source that can answer, else the first declared (which explains why not). */
export function firstSource(info: RecommendationInfo) {
  return info.sources.find((source) => source.configured) ?? info.sources[0];
}

/**
 * Every source any library declares, once each, in the order first met: what
 * Settings lists (Sprint 135).
 */
export function allSources(
  types: ItemType[] | undefined,
): RecommendationSourceInfo[] {
  const seen = new Map<string, RecommendationSourceInfo>();
  for (const type of types ?? []) {
    for (const source of type.recommendation?.sources ?? []) {
      if (!seen.has(source.name)) seen.set(source.name, source);
    }
  }
  return [...seen.values()];
}

/** Each distinct attribution line the given sources' terms ask for. */
export function attributionsFor(
  sources: Iterable<string>,
  types: ItemType[] | undefined,
): string[] {
  const lines = new Set<string>();
  const wanted = new Set(sources);
  for (const type of types ?? []) {
    for (const [name, line] of Object.entries(
      type.recommendation?.attribution ?? {},
    )) {
      if (wanted.has(name)) lines.add(line);
    }
  }
  return [...lines];
}
