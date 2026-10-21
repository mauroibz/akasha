import { describe, expect, it } from "vitest";

import { sharedValue } from "@/features/command/share";

describe("sharedValue", () => {
  it("takes the shared url, else the first link in the text, else the text", () => {
    expect(
      sharedValue(new URLSearchParams("url=https://letterboxd.com/film/up/")),
    ).toBe("https://letterboxd.com/film/up/");
    expect(
      sharedValue(
        new URLSearchParams({
          text: "Kind of Blue by Miles Davis https://open.spotify.com/album/1weenld61qoidwYuZ1GESA?si=x",
        }),
      ),
    ).toBe("https://open.spotify.com/album/1weenld61qoidwYuZ1GESA?si=x");
    expect(sharedValue(new URLSearchParams({ text: "Rayuela" }))).toBe(
      "Rayuela",
    );
  });
});
