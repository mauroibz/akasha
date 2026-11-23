import { afterEach, describe, expect, it, vi } from "vitest";

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import {
  applyTheme,
  followDeviceTheme,
  readThemeChoice,
  saveThemeChoice,
  THEMES,
} from "./theme";

function fakeDevice(light: boolean) {
  const listeners = new Set<() => void>();
  const query = {
    matches: light,
    addEventListener: (_: string, listener: () => void) =>
      listeners.add(listener),
    removeEventListener: (_: string, listener: () => void) =>
      listeners.delete(listener),
  };
  vi.stubGlobal("matchMedia", () => query);
  return {
    flip(next: boolean) {
      query.matches = next;
      listeners.forEach((listener) => listener());
    },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("theme", () => {
  it("follows the device until a theme is chosen, and live while it follows", () => {
    const device = fakeDevice(true);
    applyTheme(readThemeChoice());
    expect(document.documentElement.dataset.theme).toBe("paper");
    const stop = followDeviceTheme();
    device.flip(false);
    expect(document.documentElement.dataset.theme).toBe("ink");
    stop();
  });

  it("keeps a chosen theme across reloads and ignores the device then", () => {
    const device = fakeDevice(false);
    saveThemeChoice("paper");
    expect(readThemeChoice()).toBe("paper");
    expect(document.documentElement.dataset.theme).toBe("paper");
    const stop = followDeviceTheme();
    device.flip(false);
    expect(document.documentElement.dataset.theme).toBe("paper");
    saveThemeChoice("system");
    expect(readThemeChoice()).toBe("system");
    expect(document.documentElement.dataset.theme).toBe("ink");
    stop();
  });

  it("keeps a preset, whatever the device prefers, and tells the browser its colour", () => {
    fakeDevice(true);
    const meta = document.createElement("meta");
    meta.name = "theme-color";
    document.head.append(meta);
    saveThemeChoice("dusk");
    expect(readThemeChoice()).toBe("dusk");
    expect(document.documentElement.dataset.theme).toBe("dusk");
    expect(meta.content).toBe("#0d0f18");
    meta.remove();
  });

  it("falls back to the device for a stored name that is not a theme", () => {
    fakeDevice(false);
    localStorage.setItem("akasha:theme", "neon");
    expect(readThemeChoice()).toBe("system");
    applyTheme(readThemeChoice());
    expect(document.documentElement.dataset.theme).toBe("ink");
  });

  it("names the same themes before first paint, in the stylesheet and here", () => {
    const init = readFileSync(
      resolve(__dirname, "../../public/theme-init.js"),
      "utf8",
    );
    const css = readFileSync(resolve(__dirname, "../index.css"), "utf8");
    const listed = /var themes = \[([^\]]+)\]/.exec(init)?.[1] ?? "";
    expect(
      listed.split(",").map((name) => name.trim().replace(/"/g, "")),
    ).toEqual(THEMES.map((theme) => theme.id));
    for (const theme of THEMES)
      expect(css).toContain(`[data-theme="${theme.id}"]`);
  });
});
