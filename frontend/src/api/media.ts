import type { components } from "./schema";
import { jsonOrApiError, request } from "./request";

type Schemas = components["schemas"];

/** One medium as the person keeps it (Sprint 143, DEC-193). */
export type Medium = Schemas["MediumResponse"];
export type Presence = Medium["presence"];
export type MediumChoice = Schemas["MediumChoice"];
export type Media = Schemas["MediaResponse"];

export function getMedia(signal?: AbortSignal) {
  return request("/api/media", { signal }).then((r) =>
    jsonOrApiError<Media>(r, "Your media could not be loaded"),
  );
}

export function putMedia(media: MediumChoice[]) {
  return request("/api/media", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ media }),
  }).then((r) => jsonOrApiError<Media>(r, "Your media could not be saved"));
}
