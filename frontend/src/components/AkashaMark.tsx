import type { SVGProps } from "react";

type AkashaMarkProps = SVGProps<SVGSVGElement> & {
  /** Rendered size in px. Matches the `size` prop on Lucide icons. */
  size?: number | string;
  /** Render the dot in the current text colour instead of amber. */
  mono?: boolean;
};

/**
 * The Akasha mark.
 *
 * Drawn on Lucide's 24x24 grid at stroke-width 2 so it can sit inline with
 * `library-big`, `plus`, `inbox`, `upload` and `bookmark` at 20px without
 * looking like a foreign object. The arch stroke inherits `currentColor`;
 * only the dot is amber.
 *
 * Below 20px, prefer the hand-hinted /favicon/favicon-16.svg — this component
 * antialiases when the browser scales the 24 grid down.
 */
export function AkashaMark({
  size = 24,
  mono = false,
  ...props
}: AkashaMarkProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path d="M4 21V10a8 8 0 0 1 16 0v11" />
      <circle
        cx="12"
        cy="11"
        r="2"
        fill={mono ? "currentColor" : "#fbbf24"}
        stroke="none"
      />
    </svg>
  );
}

export default AkashaMark;
