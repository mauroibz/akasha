import { type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { cn } from "@/lib/utils";

interface NavItem {
  readonly to: string;
  readonly label: string;
  readonly icon: ReactNode;
}

const navItems: readonly NavItem[] = [
  { to: "/", label: "Library", icon: <LibraryIcon /> },
  { to: "/add", label: "Add", icon: <PlusIcon /> },
  { to: "/import", label: "Import", icon: <ImportIcon /> },
  { to: "/shelves", label: "Shelves", icon: <ShelfIcon /> },
];

function LibraryIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      viewBox="0 0 24 24"
    >
      <path
        d="M3.75 5.25h16.5M3.75 9h16.5m-16.5 3.75h16.5M3.75 15.75h16.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      viewBox="0 0 24 24"
    >
      <path
        d="M12 4.5v15m7.5-7.5h-15"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ImportIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      viewBox="0 0 24 24"
    >
      <path
        d="M3 16.5v3.75A1.5 1.5 0 0 0 4.5 21h15a1.5 1.5 0 0 0 1.5-1.5V16.5M12 3v12m0 0 3.75-3.75M12 15l-3.75-3.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ShelfIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      viewBox="0 0 24 24"
    >
      <path
        d="M3.75 6.75h16.5M3.75 12h16.5M3.75 17.25h16.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation();
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <nav
        aria-label="Primary"
        className="hidden border-b border-zinc-800/80 bg-zinc-950/95 backdrop-blur sm:flex sm:items-center sm:gap-1 sm:px-6 sm:py-2"
      >
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "flex min-h-11 items-center gap-2 rounded-lg px-4 text-sm font-medium transition-colors focus-ring",
                isActive
                  ? "bg-fuchsia-500/15 text-fuchsia-300"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50",
              )
            }
          >
            {item.icon}
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
      <nav
        aria-label="Primary"
        className="fixed inset-x-0 bottom-0 z-30 flex border-t border-zinc-800 bg-zinc-950/95 backdrop-blur sm:hidden"
      >
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            aria-label={item.label}
            className={({ isActive }) =>
              cn(
                "flex h-14 flex-1 flex-col items-center justify-center gap-0.5 text-xs transition-colors focus-ring",
                isActive ? "text-fuchsia-300" : "text-zinc-500",
              )
            }
          >
            {item.icon}
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
      <div data-route-key={location.pathname}>{children}</div>
      <div className="h-16 sm:hidden" aria-hidden="true" />
    </div>
  );
}
