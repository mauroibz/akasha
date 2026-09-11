import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import {
  actAs,
  createUser,
  deleteUser,
  getUsers,
  updateUser,
  type AuthUser,
  type ManagedUser,
} from "@/api/auth";
import { AccountSection } from "@/components/AccountSection";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function PersonRow({
  person,
  currentUser,
  actingAs,
  onActAs,
}: {
  person: ManagedUser;
  currentUser: AuthUser;
  actingAs: AuthUser | null;
  onActAs: (user: AuthUser | null) => void;
}) {
  const cache = useQueryClient();
  const navigate = useNavigate();
  const [name, setName] = useState(person.display_name ?? "");
  const [isAdmin, setIsAdmin] = useState(person.is_admin);
  const [password, setPassword] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [decision, setDecision] = useState<"delete" | "transfer" | null>(null);
  const [target, setTarget] = useState("");
  const users = cache.getQueryData<ManagedUser[]>(["users"]) ?? [];
  const save = useMutation({
    mutationFn: () =>
      updateUser(person.id, {
        display_name: name,
        is_admin: isAdmin,
        ...(password ? { password } : {}),
      }),
    onSuccess: () => {
      if (
        actingAs?.id === person.id &&
        (Boolean(password) || (person.is_admin && !isAdmin))
      ) {
        onActAs(null);
      }
      setPassword("");
      toast.success(`${person.username} updated`);
      void cache.invalidateQueries({ queryKey: ["users"] });
    },
  });
  const remove = useMutation({
    mutationFn: () =>
      decision === "transfer"
        ? deleteUser(person.id, {
            action: "transfer",
            transfer_to_user_id: Number(target),
          })
        : deleteUser(person.id, { action: "delete" }),
    onSuccess: () => {
      setDeleting(false);
      toast.success(`${person.username} deleted`);
      if (actingAs?.id === person.id) {
        onActAs(null);
        void navigate("/", { replace: true });
      }
      void cache.invalidateQueries({ queryKey: ["users"] });
    },
  });
  const view = useMutation({
    mutationFn: () => actAs(person.id),
    onSuccess: () => {
      onActAs(person);
      void navigate("/", { replace: true });
    },
  });
  return (
    <Panel className="space-y-4 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">
            {person.display_name || person.username}
          </h3>
          <p className="text-sm text-muted-foreground">
            @{person.username} · {person.entry_count} entries ·{" "}
            {person.shelf_count} shelves
          </p>
        </div>
        {person.is_admin ? (
          <span className="rounded-full bg-primary/15 px-3 py-1 text-xs font-medium text-primary">
            Admin
          </span>
        ) : null}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Label className="space-y-2">
          <span>Display name</span>
          <Input
            className="h-11"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </Label>
        <Label className="space-y-2">
          <span>Reset password</span>
          <Input
            className="h-11"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </Label>
      </div>
      <Label className="flex min-h-11 items-center gap-3 sm:w-fit">
        <Checkbox
          checked={isAdmin}
          onCheckedChange={(value) => setIsAdmin(value === true)}
        />
        Administrator
      </Label>
      <div className="flex flex-col gap-2 sm:flex-row">
        {person.id !== currentUser.id ? (
          <Button
            variant="outline"
            className="h-11"
            disabled={view.isPending}
            onClick={() => view.mutate()}
          >
            View {(person.display_name || person.username) + "'s"} library
          </Button>
        ) : null}
        <Button
          className="h-11"
          onClick={() => save.mutate()}
          disabled={save.isPending}
        >
          Save changes
        </Button>
        {person.id !== currentUser.id ? (
          <Button
            variant="outline"
            className="h-11 text-destructive hover:text-destructive"
            onClick={() => setDeleting(true)}
          >
            Delete {person.username}
          </Button>
        ) : null}
      </div>
      <AlertDialog open={deleting} onOpenChange={setDeleting}>
        <AlertDialogContent className="max-h-[90vh] max-w-[calc(100%-2rem)] overflow-y-auto rounded-xl">
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {person.display_name || person.username}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              They own {person.entry_count} entries and {person.shelf_count}{" "}
              shelves. Choose what happens to that library. Shared metadata,
              covers and attachments stay in Akasha.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <fieldset className="space-y-3">
            <legend className="sr-only">Library decision</legend>
            <label className="flex min-h-11 items-center gap-3 rounded-lg border p-3">
              <input
                type="radio"
                name={`delete-${person.id}`}
                onChange={() => setDecision("transfer")}
              />
              Transfer the library
            </label>
            {decision === "transfer" ? (
              <Label className="space-y-2">
                <span>Transfer to</span>
                <select
                  className="h-11 w-full rounded-md border border-input bg-background px-3"
                  value={target}
                  onChange={(event) => setTarget(event.target.value)}
                >
                  <option value="">Choose a person</option>
                  {users
                    .filter((row) => row.id !== person.id)
                    .map((row) => (
                      <option key={row.id} value={row.id}>
                        {row.display_name || row.username}
                      </option>
                    ))}
                </select>
              </Label>
            ) : null}
            <label className="flex min-h-11 items-center gap-3 rounded-lg border border-destructive/40 p-3">
              <input
                type="radio"
                name={`delete-${person.id}`}
                onChange={() => setDecision("delete")}
              />
              Delete their entries, shelves and import history
            </label>
          </fieldset>
          {remove.isError ? (
            <p role="alert" className="text-sm text-destructive">
              {remove.error.message}
            </p>
          ) : null}
          <AlertDialogFooter>
            <AlertDialogCancel className="h-11">Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="h-11 bg-destructive text-destructive-foreground"
              disabled={
                !decision ||
                (decision === "transfer" && !target) ||
                remove.isPending
              }
              onClick={(event) => {
                event.preventDefault();
                remove.mutate();
              }}
            >
              Confirm deletion
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Panel>
  );
}

export function PeoplePage({
  user,
  actingAs,
  onActAs,
  onSignedOut,
}: {
  user: AuthUser;
  actingAs: AuthUser | null;
  onActAs: (user: AuthUser | null) => void;
  onSignedOut: () => void;
}) {
  const cache = useQueryClient();
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [admin, setAdmin] = useState(false);
  const users = useQuery({
    queryKey: ["users"],
    queryFn: getUsers,
    enabled: user.is_admin,
  });
  const create = useMutation({
    mutationFn: () =>
      createUser({
        username,
        display_name: displayName,
        password,
        is_admin: admin,
      }),
    onSuccess: () => {
      setUsername("");
      setDisplayName("");
      setPassword("");
      setAdmin(false);
      toast.success("Person created");
      void cache.invalidateQueries({ queryKey: ["users"] });
    },
  });
  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 py-8">
      <PageHeader
        back
        title={user.is_admin ? "People" : "Settings"}
        lede="Manage your account and the people who use this Akasha install."
      />
      <div className="mt-6 space-y-6">
        <AccountSection
          onPasswordChanged={() => {
            if (actingAs) onActAs(null);
          }}
          onSignedOut={onSignedOut}
        />
        {user.is_admin ? (
          <section className="space-y-4" aria-labelledby="people-heading">
            <div>
              <h2 id="people-heading" className="text-xl font-semibold">
                People
              </h2>
              <p className="text-sm text-muted-foreground">
                Each person has a separate library.
              </p>
            </div>
            <Panel className="p-5">
              <form
                className="grid gap-4 sm:grid-cols-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  create.mutate();
                }}
              >
                <h3 className="text-lg font-semibold sm:col-span-2">
                  Add a person
                </h3>
                <Label className="space-y-2">
                  <span>Username</span>
                  <Input
                    className="h-11"
                    autoComplete="off"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                  />
                </Label>
                <Label className="space-y-2">
                  <span>Display name</span>
                  <Input
                    className="h-11"
                    value={displayName}
                    onChange={(event) => setDisplayName(event.target.value)}
                  />
                </Label>
                <Label className="space-y-2">
                  <span>Initial password</span>
                  <Input
                    className="h-11"
                    type="password"
                    autoComplete="new-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                </Label>
                <Label className="flex min-h-11 items-center gap-3 self-end">
                  <Checkbox
                    checked={admin}
                    onCheckedChange={(value) => setAdmin(value === true)}
                  />
                  Administrator
                </Label>
                {create.isError ? (
                  <p
                    role="alert"
                    className="text-sm text-destructive sm:col-span-2"
                  >
                    {create.error.message}
                  </p>
                ) : null}
                <Button
                  className="h-11 sm:w-fit"
                  disabled={!username.trim() || !password || create.isPending}
                >
                  Create person
                </Button>
              </form>
            </Panel>
            {users.isPending ? <p role="status">Loading people…</p> : null}
            {users.isError ? (
              <p role="alert" className="text-destructive">
                People could not be loaded.
              </p>
            ) : null}
            <div className="grid gap-4">
              {users.data?.map((person) => (
                <PersonRow
                  key={person.id}
                  person={person}
                  currentUser={user}
                  actingAs={actingAs}
                  onActAs={onActAs}
                />
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </main>
  );
}
