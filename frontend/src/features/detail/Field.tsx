import type { ReactNode } from "react";

import { Label } from "@/components/ui/label";

interface FieldProps {
  id: string;
  label: string;
  error?: string;
  children: (props: {
    id: string;
    "aria-invalid": boolean;
    "aria-describedby": string | undefined;
  }) => ReactNode;
}

/**
 * A labelled control with its validation message wired to it.
 *
 * The message is `role="alert"` and referenced by `aria-describedby`, so a
 * screen reader hears why the write was refused rather than only seeing the
 * form fail to submit (technical spec section 8).
 */
export function Field({ id, label, error, children }: FieldProps) {
  const errorId = `${id}-error`;
  return (
    <div>
      <Label htmlFor={id}>{label}</Label>
      <div className="mt-1">
        {children({
          id,
          "aria-invalid": Boolean(error),
          "aria-describedby": error ? errorId : undefined,
        })}
      </div>
      {error && (
        <p id={errorId} role="alert" className="mt-1 text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
