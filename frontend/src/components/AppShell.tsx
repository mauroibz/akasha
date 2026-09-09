import {
  Bookmark,
  ChartBar,
  LibraryBig,
  LogOut,
  Plus,
  Settings,
  Upload,
  UserRound,
} from "lucide-react";
import { LazyMotion, domAnimation } from "motion/react";
import { type ReactNode, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { logout, type AuthUser } from "@/api/auth";
import { AkashaMark } from "@/components/AkashaMark";
import { DataCredit } from "@/components/DataCredit";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Toaster } from "@/components/ui/sonner";
import { cn } from "@/lib/utils";

interface NavItem {
  readonly to: string;
  readonly label: string;
  readonly icon: ReactNode;
}

// Triage is not here on purpose: it is the tail of the import flow, not a
// destination of its own, and as a top-level item it was a dead page unless an
// import had just run (DEC-079). It is a tab on `/import`.
//
// The item reads "Data" rather than "Import" as of Sprint 069: `/import` grew a
// third tab that takes a library out rather than bringing one in, and "Import"
// on its own reads as one direction only (docs/export-proposal.md §3). "Data"
// is this sprint's recommendation over the proposal's other option, "Import &
// export" — shorter, and it still names what the destination is for rather than
// what you do there. One label, easy to change if the owner prefers the longer
// one; nothing downstream depends on the exact word.
const navItems: readonly NavItem[] = [
  { to: "/", label: "Library", icon: <LibraryBig aria-hidden="true" /> },
  { to: "/add", label: "Add", icon: <Plus aria-hidden="true" /> },
  { to: "/import", label: "Data", icon: <Upload aria-hidden="true" /> },
  { to: "/shelves", label: "Shelves", icon: <Bookmark aria-hidden="true" /> },
  { to: "/insights", label: "Insights", icon: <ChartBar aria-hidden="true" /> },
];

function AccountControl({
  user,
  onSignedOut,
}: {
  user: AuthUser;
  onSignedOut: () => void;
}) {
  const navigate = useNavigate();
  const [signingOut, setSigningOut] = useState(false);
  const name = user.display_name?.trim() || user.username;

  async function signOut() {
    setSigningOut(true);
    try {
      await logout();
      onSignedOut();
      void navigate("/login", {
        replace: true,
        state: { returnTo: "/" },
      });
    } catch {
      setSigningOut(false);
      toast.error("You could not be signed out. Try again.");
    }
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          className="min-h-11 max-w-48 gap-2 px-3 text-muted-foreground"
          aria-label={name}
        >
          <UserRound className="h-5 w-5 shrink-0" aria-hidden="true" />
          <span className="truncate">{name}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-44 p-2">
        <Button
          variant="ghost"
          className="min-h-11 w-full justify-start gap-2"
          onClick={() => void navigate("/people")}
        >
          <Settings className="h-4 w-4" aria-hidden="true" />
          {user.is_admin ? "People" : "Settings"}
        </Button>
        <Button
          variant="ghost"
          className="min-h-11 w-full justify-start gap-2"
          disabled={signingOut}
          onClick={() => void signOut()}
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
          {signingOut ? "Signing out…" : "Sign out"}
        </Button>
      </PopoverContent>
    </Popover>
  );
}

export function AppShell({
  children,
  user,
  onSignedOut,
}: {
  children: ReactNode;
  user?: AuthUser | null;
  onSignedOut?: () => void;
}) {
  const location = useLocation();
  return (
    // `domAnimation` deliberately omits Motion's projection features, so
    // `layout` and `layoutId` do nothing anywhere in the application. That is
    // the acceptance criterion "no row-level layout animation in a virtualized
    // list" made structural rather than remembered: it cannot be violated by a
    // later edit without also changing this line. `strict` turns an accidental
    // eager `motion.*` component into a loud error instead of a silent bundle.
    <LazyMotion features={domAnimation} strict>
      <div className="min-h-screen bg-background text-foreground">
        <nav
          aria-label="Primary"
          className="hidden border-b border-border/80 bg-background/95 backdrop-blur sm:flex sm:items-center sm:gap-1 sm:px-6 sm:py-2"
        >
          {/* Decorative, not a second home link: "Library" below already goes to
            "/", and duplicating it would make a screen reader announce the same
            destination twice. Sized to 20px so it reads as a sibling of the
            Lucide icons beside it rather than as a foreign object
            (docs/brand/BRAND.md). */}
          <AkashaMark
            size={20}
            className="mx-3 shrink-0 text-foreground"
            aria-hidden="true"
          />
          <span
            className="mr-2 h-5 w-px shrink-0 bg-border"
            aria-hidden="true"
          />
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex min-h-11 items-center gap-2 rounded-lg px-4 text-sm font-medium transition-colors focus-ring",
                  isActive
                    ? "bg-primary/15 text-primary"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
                )
              }
            >
              <span className="[&_svg]:h-5 [&_svg]:w-5">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
          {user && onSignedOut ? (
            <div className="ml-auto">
              <AccountControl user={user} onSignedOut={onSignedOut} />
            </div>
          ) : null}
        </nav>
        {user && onSignedOut ? (
          <header className="flex min-h-14 items-center justify-end border-b border-border/80 px-4 sm:hidden">
            <AccountControl user={user} onSignedOut={onSignedOut} />
          </header>
        ) : null}
        <nav
          aria-label="Primary"
          className="fixed inset-x-0 bottom-0 z-30 flex border-t border-border bg-background/95 backdrop-blur sm:hidden"
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
                  isActive ? "text-primary" : "text-muted-foreground",
                )
              }
            >
              <span className="[&_svg]:h-5 [&_svg]:w-5">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div data-route-key={location.pathname}>{children}</div>
        {/* The CC BY-SA credit (DEC-105): findable from every screen, below the
            content so it never competes with a control. The mobile bottom padding
            clears the fixed bottom navigation. */}
        <footer className="pb-20 sm:pb-0">
          <DataCredit />
        </footer>
        <div className="h-16 sm:hidden" aria-hidden="true" />
        {/* The application's one visible feedback surface. Mounted at the shell so
          a confirmation survives the navigation that follows the action.
          Bottom-right, not top-centre: every screen puts its primary controls in
          the header, and a toast there covers the control the reader just used.
          The mobile offset clears the fixed bottom navigation. */}
        <Toaster
          position="bottom-right"
          closeButton
          mobileOffset={{ bottom: "80px", left: "16px", right: "16px" }}
        />
      </div>
    </LazyMotion>
  );
}
