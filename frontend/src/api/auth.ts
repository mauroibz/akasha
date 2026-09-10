export interface AuthUser {
  id: number;
  username: string;
  display_name: string | null;
  is_admin: boolean;
}

export interface AuthState {
  auth: "off" | "on";
  authenticated: boolean;
  setup_required: boolean;
  user: AuthUser | null;
  acting_as: AuthUser | null;
}

export interface ManagedUser extends AuthUser {
  entry_count: number;
  shelf_count: number;
}

export const AUTH_STATE_QUERY_KEY = ["auth", "me"] as const;

export class AuthRequestError extends Error {
  constructor(
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "AuthRequestError";
  }
}

async function authJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      error?: { code?: string; message?: string };
    } | null;
    throw new AuthRequestError(
      body?.error?.code ?? "auth_failed",
      body?.error?.message ?? "Authentication failed",
    );
  }
  return response.json() as Promise<T>;
}

export function login(username: string, password: string): Promise<AuthUser> {
  return fetch("/api/auth/login", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  }).then(authJson<AuthUser>);
}

export function setup(
  username: string,
  displayName: string,
  password: string,
): Promise<AuthUser> {
  return fetch("/api/auth/setup", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      username,
      display_name: displayName,
      password,
    }),
  }).then(authJson<AuthUser>);
}

export async function logout(): Promise<void> {
  const response = await fetch("/api/auth/session", { method: "DELETE" });
  if (!response.ok) throw new Error("Sign out failed");
}

/**
 * Probe the deployment once before mounting a private route.
 *
 * Auth routes deliberately return 404 in the default off mode, so that response
 * is the mode signal rather than an authentication failure.
 */
export async function getAuthState(): Promise<AuthState> {
  const response = await fetch("/api/auth/me", {
    headers: { Accept: "application/json" },
  });
  if (response.status === 404) {
    return {
      auth: "off",
      authenticated: false,
      setup_required: false,
      user: null,
      acting_as: null,
    };
  }
  return authJson<AuthState>(response);
}

export async function actAs(userId: number): Promise<void> {
  const response = await fetch(`/api/auth/act-as/${userId}`, {
    method: "POST",
  });
  if (!response.ok) await authJson(response);
}

export async function stopActingAs(): Promise<void> {
  const response = await fetch("/api/auth/act-as", { method: "DELETE" });
  if (!response.ok) await authJson(response);
}

export function getUsers(): Promise<ManagedUser[]> {
  return fetch("/api/users", { headers: { Accept: "application/json" } }).then(
    authJson<ManagedUser[]>,
  );
}

export function createUser(values: {
  username: string;
  display_name: string;
  password: string;
  is_admin: boolean;
}): Promise<AuthUser> {
  return fetch("/api/users", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(values),
  }).then(authJson<AuthUser>);
}

export function updateUser(
  id: number,
  values: { display_name?: string; password?: string; is_admin?: boolean },
): Promise<AuthUser> {
  return fetch(`/api/users/${id}`, {
    method: "PATCH",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(values),
  }).then(authJson<AuthUser>);
}

export async function deleteUser(
  id: number,
  decision:
    { action: "delete" } | { action: "transfer"; transfer_to_user_id: number },
): Promise<void> {
  const response = await fetch(`/api/users/${id}`, {
    method: "DELETE",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(decision),
  });
  if (!response.ok) await authJson(response);
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  const response = await fetch("/api/auth/password", {
    method: "PATCH",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
  if (!response.ok) await authJson(response);
}
