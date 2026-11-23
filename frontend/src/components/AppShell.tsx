import {
  BookOpen,
  Bookmark,
  ChartBar,
  House,
  LibraryBig,
  LogOut,
  Settings,
  UserRound,
  Search,
} from "lucide-react";
import { LazyMotion, domAnimation } from "motion/react";
import { createContext, type ReactNode, useContext, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { logout, stopActingAs, type AuthUser } from "@/api/auth";
import { ActivityIndicator } from "@/features/activity/ActivityIndicator";
import { JobEventsProvider } from "@/features/activity/JobEvents";
import { isActive, useJobEvent } from "@/features/activity/jobEvents";
import { DataCredit } from "@/components/DataCredit";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Toaster } from "@/components/ui/sonner";
import { cn } from "@/lib/utils";
import { CommandBarProvider } from "@/features/command/CommandBarProvider";
import { useCommandBar } from "@/features/command/commandBar";
import { Kbd } from "@/components/ui/kbd";
import { queryKeys } from "@/api/keys";
import { getInboxCount } from "@/api/library";
import { useQuery, useQueryClient } from "@tanstack/react-query";

interface NavItem {
  readonly to: string;
  readonly label: string;
  readonly icon: ReactNode;
  /** Kept off the phone's bottom bar, which holds five; the command bar reaches it. */
  readonly desktopOnly?: boolean;
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
  // Home leads since Sprint 130 (DEC-183); the library moved to `/library`.
  { to: "/", label: "Home", icon: <House aria-hidden="true" /> },
  {
    to: "/library",
    label: "Library",
    icon: <LibraryBig aria-hidden="true" />,
  },
  // No Add and no Import since Sprint 140 (DEC-193): the bar finds and adds, and its
  // footer holds the form and the importer. The navigation is places only.
  { to: "/shelves", label: "Shelves", icon: <Bookmark aria-hidden="true" /> },
  { to: "/insights", label: "Insights", icon: <ChartBar aria-hidden="true" /> },
  // Sprint 098: what you finished, month by month.
  {
    to: "/diary",
    label: "Diary",
    icon: <BookOpen aria-hidden="true" />,
    desktopOnly: true,
  },
];

/**
 * How many entries wait to be sorted, as a link to the Inbox (Sprint 096, §5.1; a
 * link of its own since Sprint 140, when Import left the navigation): an import's
 * results are one click from anywhere, and an empty Inbox says nothing.
 */
function useToSort(): number {
  const queryClient = useQueryClient();
  const count = useQuery({
    queryKey: queryKeys.triage.count,
    queryFn: ({ signal }) => getInboxCount(signal),
    // The count changes when an import lands, which this tab learns from its own
    // writes (they invalidate it) or from a job finishing on the events stream
    // (below). Coming back to the window still recounts once it is a minute old,
    // for the import another device ran meanwhile: one `limit=1` request.
    staleTime: 60_000,
    refetchOnWindowFocus: true,
    retry: false,
  });
  useJobEvent((event) => {
    if (!isActive(event))
      void queryClient.invalidateQueries({ queryKey: queryKeys.triage.count });
  });
  return count.data ?? 0;
}

const ToSortContext = createContext(0);

/** Counted once for the shell: the desktop bar and the phone's header both show it. */
function ToSortProvider({ children }: { children: ReactNode }) {
  return (
    <ToSortContext.Provider value={useToSort()}>
      {children}
    </ToSortContext.Provider>
  );
}

function ToSort() {
  const count = useContext(ToSortContext);
  if (!count) return null;
  return (
    <NavLink
      to="/inbox"
      className="flex h-11 shrink-0 items-center rounded-lg px-2.5 text-sm font-medium tabular-nums text-primary-text transition-colors hover:bg-accent focus-ring"
    >
      {count > 99 ? "99+" : count} to sort
    </NavLink>
  );
}

/**
 * The bar as a field (Sprint 140, DEC-193): on every screen it reads as the place to
 * type, and opening it puts the cursor in the bar. ⌘K is the other way in. The
 * Library has its own field, which filters the grid as it is typed into, so this
 * one is not drawn there.
 */
function SearchField() {
  const { open } = useCommandBar();
  return (
    <button
      type="button"
      onClick={() => open()}
      aria-keyshortcuts="Meta+K Control+K"
      className="mx-auto flex h-11 min-w-0 max-w-xl flex-1 items-center gap-2.5 rounded-full border border-border bg-surface px-4 text-left text-sm text-muted-foreground transition-colors hover:border-ring/50 hover:text-foreground focus-ring [&_svg]:h-[18px] [&_svg]:w-[18px] [&_svg]:shrink-0"
    >
      <Search aria-hidden="true" />
      <span className="truncate">Search your library, or add something</span>
      <Kbd className="ml-auto hidden lg:inline-flex">⌘K</Kbd>
    </button>
  );
}

/** The bar's door where there is no room for a field: the phone. */
function SearchButton({ className }: { className?: string }) {
  const { open } = useCommandBar();
  return (
    <button
      type="button"
      onClick={() => open()}
      aria-label="Search or add"
      className={cn(
        "flex items-center justify-center text-muted-foreground transition-colors hover:text-foreground focus-ring [&_svg]:h-5 [&_svg]:w-5",
        className,
      )}
    >
      <Search aria-hidden="true" />
    </button>
  );
}

function SettingsLink() {
  return (
    <NavLink
      to="/settings"
      aria-label="Settings"
      className={({ isActive }) =>
        cn(
          "flex h-11 w-11 items-center justify-center rounded-lg transition-colors focus-ring [&_svg]:h-5 [&_svg]:w-5",
          isActive
            ? "bg-primary/15 text-primary"
            : "text-muted-foreground hover:bg-accent hover:text-foreground",
        )
      }
    >
      <Settings aria-hidden="true" />
    </NavLink>
  );
}

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
          <UserRound className="h-4 w-4" aria-hidden="true" />
          {user.is_admin ? "People" : "Account"}
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

function ActingAsBanner({
  user,
  onActingAsChanged,
}: {
  user: AuthUser;
  onActingAsChanged: (user: AuthUser | null) => void;
}) {
  const navigate = useNavigate();
  const [leaving, setLeaving] = useState(false);
  const name = user.display_name?.trim() || user.username;

  async function leave() {
    setLeaving(true);
    try {
      await stopActingAs();
      onActingAsChanged(null);
      // "Return to your library": the library, not Home (Sprint 130).
      void navigate("/library", { replace: true });
    } catch {
      setLeaving(false);
      toast.error("You could not return to your library. Try again.");
    }
  }

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={`Viewing ${name}'s library`}
      className="fixed inset-x-0 top-0 z-[60] flex min-h-14 items-center justify-between gap-3 border-b border-amber-500/50 bg-amber-100 px-4 text-amber-950 shadow-sm dark:bg-amber-950 dark:text-amber-50"
    >
      <p className="text-sm font-semibold">Viewing {name}&apos;s library</p>
      <Button
        variant="outline"
        className="min-h-11 shrink-0 border-amber-700/40 bg-transparent"
        disabled={leaving}
        onClick={() => void leave()}
      >
        {leaving ? "Returning…" : "Return to your library"}
      </Button>
    </div>
  );
}

export function AppShell({
  children,
  user,
  actingAs,
  onActingAsChanged,
  onSignedOut,
}: {
  children: ReactNode;
  user?: AuthUser | null;
  actingAs?: AuthUser | null;
  onActingAsChanged?: (user: AuthUser | null) => void;
  onSignedOut?: () => void;
}) {
  const location = useLocation();
  const onLibrary = location.pathname === "/library";
  const phoneItems = navItems.filter((item) => !item.desktopOnly);
  const phoneLink = (item: NavItem) => (
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
  );
  return (
    // `domAnimation` deliberately omits Motion's projection features, so
    // `layout` and `layoutId` do nothing anywhere in the application. That is
    // the acceptance criterion "no row-level layout animation in a virtualized
    // list" made structural rather than remembered: it cannot be violated by a
    // later edit without also changing this line. `strict` turns an accidental
    // eager `motion.*` component into a loud error instead of a silent bundle.
    <JobEventsProvider>
      <ToSortProvider>
        <CommandBarProvider>
          <LazyMotion features={domAnimation} strict>
            <div className="min-h-screen bg-background text-foreground">
              {actingAs && onActingAsChanged ? (
                <>
                  <div className="h-14" aria-hidden="true" />
                  <ActingAsBanner
                    user={actingAs}
                    onActingAsChanged={onActingAsChanged}
                  />
                </>
              ) : null}
              <nav
                aria-label="Primary"
                className="hidden border-b border-border/80 bg-background/95 backdrop-blur sm:flex sm:items-center sm:gap-1 sm:px-6 sm:py-2"
              >
                {/* Not a second home link: "Home" below already goes to "/". Since
            Sprint 089 the mark is the background-work control: its dot breathes
            while a job runs, and it opens the recent jobs. Sized to 20px so it
            reads as a sibling of the Lucide icons beside it (docs/brand/BRAND.md). */}
                <ActivityIndicator className="mx-1" />
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
                        // Tighter below 1024px: with the Inbox badge the nav must still
                        // fit a tablet (the library spec's no-overflow rule).
                        "flex min-h-11 items-center gap-2 rounded-lg px-3 text-sm font-medium transition-colors focus-ring lg:px-4",
                        isActive
                          ? "bg-primary/15 text-primary"
                          : "text-muted-foreground hover:bg-accent hover:text-foreground",
                      )
                    }
                  >
                    <span className="[&_svg]:h-5 [&_svg]:w-5">{item.icon}</span>
                    {/* Icons alone below 1024px, where six labels do not fit a tablet;
                      the label stays the link's name for a screen reader. */}
                    <span className="sr-only lg:not-sr-only">{item.label}</span>
                  </NavLink>
                ))}
                {onLibrary ? <span className="flex-1" /> : <SearchField />}
                <div className="flex items-center gap-1">
                  <ToSort />
                  <SettingsLink />
                  {user && onSignedOut ? (
                    <AccountControl user={user} onSignedOut={onSignedOut} />
                  ) : null}
                </div>
              </nav>
              {/* The phone's top bar (Sprint 093): the mark, which is the
            background-work control as on desktop, and Settings; the account
            control when signed in. Short, because on a phone every pixel above
            the first cover counts (the library spec holds it under 300px). */}
              <header className="flex h-12 items-center justify-between gap-1 border-b border-border/80 px-2 sm:hidden">
                <ActivityIndicator />
                <div className="flex items-center gap-1">
                  <ToSort />
                  <SettingsLink />
                  {user && onSignedOut ? (
                    <AccountControl user={user} onSignedOut={onSignedOut} />
                  ) : null}
                </div>
              </header>
              <nav
                aria-label="Primary"
                className="fixed inset-x-0 bottom-0 z-30 flex border-t border-border bg-background/95 backdrop-blur sm:hidden"
              >
                {phoneItems.slice(0, 2).map(phoneLink)}
                {/* The bar between the places (Sprint 140): on a phone it is the
                  thing done most, so it sits under the thumb. */}
                <span className="flex h-14 flex-1 items-center justify-center">
                  <SearchButton className="h-11 w-11 rounded-full bg-primary text-primary-foreground hover:text-primary-foreground" />
                </span>
                {phoneItems.slice(2).map(phoneLink)}
              </nav>
              <div
                key={location.pathname}
                data-route-key={location.pathname}
                className="animate-route-enter"
              >
                {children}
              </div>
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
        </CommandBarProvider>
      </ToSortProvider>
    </JobEventsProvider>
  );
}
