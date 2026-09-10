import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import {
  changePassword,
  getSessions,
  logoutEverywhere,
  revokeSession,
  type AuthSession,
} from "@/api/auth";
import { Panel } from "@/components/Panel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const SESSION_QUERY_KEY = ["auth", "sessions"] as const;
const dateTime = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

function sessionName(session: AuthSession): string {
  return session.user_agent?.trim() || "Unknown browser";
}

function ChangePassword({ onChanged }: { onChanged: () => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const mutation = useMutation({
    mutationFn: () => changePassword(current, next),
    onSuccess: () => {
      setCurrent("");
      setNext("");
      toast.success("Password changed. Your other sessions were signed out.");
      onChanged();
    },
  });
  return (
    <Panel className="space-y-4 p-5">
      <div>
        <h2 className="text-lg font-semibold">Change password</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          This device stays signed in; your other sessions are closed.
        </p>
      </div>
      <form
        className="grid gap-4 sm:max-w-md"
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <Label className="space-y-2">
          <span>Current password</span>
          <Input
            className="h-11"
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
          />
        </Label>
        <Label className="space-y-2">
          <span>New password</span>
          <Input
            className="h-11"
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(event) => setNext(event.target.value)}
          />
        </Label>
        {mutation.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {mutation.error.message}
          </p>
        ) : null}
        <Button
          className="min-h-11 sm:w-fit"
          disabled={!current || !next || mutation.isPending}
        >
          Change password
        </Button>
      </form>
    </Panel>
  );
}

export function AccountSection({
  onPasswordChanged,
  onSignedOut,
}: {
  onPasswordChanged: () => void;
  onSignedOut: () => void;
}) {
  const cache = useQueryClient();
  const sessions = useQuery({
    queryKey: SESSION_QUERY_KEY,
    queryFn: getSessions,
  });
  const revoke = useMutation({
    mutationFn: revokeSession,
    onSuccess: (_result, id) => {
      const revoked = sessions.data?.find((session) => session.id === id);
      if (revoked?.current) {
        onSignedOut();
        return;
      }
      cache.setQueryData<AuthSession[]>(SESSION_QUERY_KEY, (current) =>
        current?.filter((session) => session.id !== id),
      );
      toast.success("Session signed out");
    },
  });
  const revokeAll = useMutation({
    mutationFn: logoutEverywhere,
    onSuccess: onSignedOut,
  });

  return (
    <section className="space-y-6" aria-label="Account">
      <ChangePassword onChanged={onPasswordChanged} />
      <Panel className="space-y-4 p-5">
        <div>
          <h2 className="text-lg font-semibold">Your sessions</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Sign out a phone or browser you no longer have.
          </p>
        </div>
        {sessions.isPending ? (
          <p role="status" className="text-sm text-muted-foreground">
            Loading sessions…
          </p>
        ) : sessions.isError ? (
          <p role="alert" className="text-sm text-destructive">
            Your sessions could not be loaded.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {sessions.data.map((session) => {
              const name = sessionName(session);
              return (
                <li
                  key={session.id}
                  className="flex flex-col gap-3 py-4 first:pt-0 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <p className="break-words font-medium">{name}</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Created {dateTime.format(new Date(session.created_at))}
                      <br />
                      Last used{" "}
                      {dateTime.format(new Date(session.last_seen_at))}
                    </p>
                    {session.current ? (
                      <span className="mt-2 inline-block rounded-full bg-primary/15 px-3 py-1 text-xs font-medium text-primary">
                        Current session
                      </span>
                    ) : null}
                  </div>
                  <Button
                    variant="outline"
                    className="min-h-11 shrink-0"
                    disabled={revoke.isPending}
                    onClick={() => revoke.mutate(session.id)}
                  >
                    {session.current
                      ? "Sign out this session"
                      : `Sign out ${name}`}
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
        <Button
          variant="outline"
          className="min-h-11 w-full text-destructive hover:text-destructive sm:w-fit"
          disabled={revokeAll.isPending}
          onClick={() => revokeAll.mutate()}
        >
          Sign out everywhere
        </Button>
      </Panel>
    </section>
  );
}
