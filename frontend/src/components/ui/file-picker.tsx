import { Upload } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

type FilePickerProps = Omit<
  React.InputHTMLAttributes<HTMLInputElement>,
  "type"
> & {
  /** What the button says before anything is chosen. */
  buttonLabel?: string;
  /** The folder variant: Chromium's `webkitdirectory`, for whole-folder imports. */
  directory?: boolean;
  /** Off when the caller already says what was chosen, so it is not said twice. */
  showChosen?: boolean;
};

/**
 * A file input that looks like the rest of the application (Sprint 091, D8).
 *
 * The native input stays: it is still the focusable control a keyboard reaches, it
 * still opens the platform picker on Space or Enter, and every caller's label, id,
 * accept and onChange go to it unchanged. It is visually hidden, and a drawn button
 * beside it opens it on click and shows the focus ring when it has focus. The chosen
 * file's name replaces "No file chosen".
 */
export const FilePicker = React.forwardRef<HTMLInputElement, FilePickerProps>(
  (
    {
      className,
      buttonLabel = "Choose a file",
      directory,
      showChosen = true,
      onChange,
      multiple,
      ...props
    },
    forwarded,
  ) => {
    const local = React.useRef<HTMLInputElement | null>(null);
    const [chosen, setChosen] = React.useState<string | null>(null);
    const setRefs = (node: HTMLInputElement | null) => {
      local.current = node;
      if (typeof forwarded === "function") forwarded(node);
      else if (forwarded) forwarded.current = node;
    };
    const directoryProps = directory
      ? ({ webkitdirectory: "", directory: "" } as Record<string, string>)
      : {};
    return (
      <span className={cn("flex min-w-0 items-center gap-3", className)}>
        <input
          ref={setRefs}
          type="file"
          multiple={multiple}
          className="peer sr-only"
          onChange={(event) => {
            const files = event.currentTarget.files;
            setChosen(
              !files || files.length === 0
                ? null
                : files.length === 1
                  ? files[0].name
                  : `${files.length} files`,
            );
            onChange?.(event);
          }}
          {...directoryProps}
          {...props}
        />
        <span
          aria-hidden="true"
          onClick={() => local.current?.click()}
          className="inline-flex h-11 shrink-0 cursor-pointer items-center gap-2 rounded-lg border border-input bg-surface-raised px-4 text-sm font-medium transition-colors hover:bg-accent peer-focus-visible:ring-2 peer-focus-visible:ring-primary peer-disabled:cursor-not-allowed peer-disabled:opacity-50"
        >
          <Upload className="h-4 w-4" aria-hidden="true" />
          {buttonLabel}
        </span>
        {/* Not a live region: a modal opened elsewhere on the page hides
          everything outside it from assistive technology except `aria-live`
          elements and their ancestors, so a live region here would keep the
          whole page readable behind a dialog. The input announces its own value. */}
        {showChosen ? (
          <span className="min-w-0 truncate text-sm text-muted-foreground">
            {chosen ??
              (multiple || directory
                ? "Nothing chosen yet"
                : "No file chosen yet")}
          </span>
        ) : null}
      </span>
    );
  },
);
FilePicker.displayName = "FilePicker";
