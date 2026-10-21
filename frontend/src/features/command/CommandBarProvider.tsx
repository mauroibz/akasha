import { useCallback, useEffect, useState, type ReactNode } from "react";

import { looksResolvable } from "@/api/add";
import { isEditableTarget } from "@/features/library/library";

import { CommandBar } from "./CommandBar";
import { GlobalDrop } from "./GlobalDrop";
import { CommandBarContext } from "./commandBar";

/**
 * Owns the command bar for the whole shell (Sprint 094): ⌘K or Ctrl+K opens it
 * from anywhere, including from inside a text field, because the shortcut cannot
 * be typed as text; a screen opens it with `useCommandBar().open(query)`.
 */
export function CommandBarProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [initialQuery, setInitialQuery] = useState("");
  // Mounted on first use, then kept so closing still animates: nothing the bar
  // queries is worth fetching for a page nobody opened it on.
  const [used, setUsed] = useState(false);
  useEffect(() => {
    if (open) setUsed(true);
  }, [open]);

  const openBar = useCallback((query = "") => {
    setInitialQuery(query);
    setOpen(true);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((current) => {
          if (!current) setInitialQuery("");
          return !current;
        });
      }
    };
    // A link or ISBN pasted outside a field opens the bar already resolving it
    // (Sprint 095): copy a link in another tab, come back, paste, Enter.
    const onPaste = (event: ClipboardEvent) => {
      if (isEditableTarget(event.target)) return;
      const text = event.clipboardData?.getData("text")?.trim() ?? "";
      if (!text || !looksResolvable(text)) return;
      event.preventDefault();
      openBar(text);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("paste", onPaste);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("paste", onPaste);
    };
  }, [openBar]);

  return (
    <CommandBarContext.Provider value={{ open: openBar }}>
      {children}
      <GlobalDrop />
      {used || open ? (
        <CommandBar
          open={open}
          onOpenChange={setOpen}
          initialQuery={initialQuery}
        />
      ) : null}
    </CommandBarContext.Provider>
  );
}
