import { afterEach, describe, expect, it, vi } from "vitest";

import {
  applyTheme,
  followDeviceTheme,
  readThemeChoice,
  saveThemeChoice,
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
});
