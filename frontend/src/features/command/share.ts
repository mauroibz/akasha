/**
 * What a phone shared, as one value for the command bar (Sprint 097). Apps put the
 * link in `url`, or only in `text` among other words, so the first link wins.
 */
export function sharedValue(params: URLSearchParams): string {
  const url = params.get("url")?.trim();
  if (url) return url;
  const text = params.get("text") ?? "";
  const link = text.match(/https?:\/\/\S+/)?.[0];
  return (link ?? text ?? params.get("title") ?? "").trim();
}
