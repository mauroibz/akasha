/** The one signal from API refusal to the router (Sprint 078). */
export const AUTH_REQUIRED_EVENT = "akasha:auth-required";

export class Unauthenticated extends Error {
  constructor() {
    super("Authentication is required");
    this.name = "Unauthenticated";
  }
}

export class SetupRequired extends Error {
  constructor() {
    super("Initial setup is required");
    this.name = "SetupRequired";
  }
}

type AuthRequiredDetail = { kind: "login" | "setup" };

function announce(kind: AuthRequiredDetail["kind"]) {
  window.dispatchEvent(
    new CustomEvent<AuthRequiredDetail>(AUTH_REQUIRED_EVENT, {
      detail: { kind },
    }),
  );
}

/**
 * A deliberately thin fetch wrapper: it recognizes only the two application-wide
 * authentication refusals and otherwise leaves the Response untouched.
 */
export async function request(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const response = await fetch(input, init);
  if (response.status === 401) {
    announce("login");
    throw new Unauthenticated();
  }
  if (response.status === 409) {
    const body = (await response
      .clone()
      .json()
      .catch(() => null)) as { error?: { code?: string } } | null;
    if (body?.error?.code === "setup_required") {
      announce("setup");
      throw new SetupRequired();
    }
  }
  return response;
}

/**
 * Every refusal the API sends, as one type (Sprint 088). The server answers every
 * error with `{"error": {code, message, details}}` (Sprint 087), so there is one
 * shape to read; a body that is not the envelope (a proxy's HTML page, a dropped
 * connection) falls back on what the caller says went wrong.
 */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  /** The connector's next step, when it supplied one (DEC-080). */
  readonly action: string | null;
  readonly details: Record<string, unknown>;
  /** `X-Request-Id`, to find this refusal in the server's log. */
  readonly requestId: string | null;

  constructor(
    message: string,
    code: string,
    fields: {
      status?: number;
      action?: string | null;
      details?: Record<string, unknown>;
      requestId?: string | null;
    } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = fields.status ?? 0;
    this.action = fields.action ?? null;
    this.details = fields.details ?? {};
    this.requestId = fields.requestId ?? null;
  }
}

type Envelope = {
  error?: {
    code?: string;
    message?: string;
    user_message?: string;
    action?: string;
    details?: Record<string, unknown>;
  };
};

/** The fields of a failed response, read once for every error class. */
export async function readErrorFields(
  response: Response,
  fallback: string,
  fallbackCode = "request_failed",
) {
  const body = (await response.json().catch(() => null)) as Envelope | null;
  const error = body?.error;
  return {
    // `user_message` is written for a person and `message` for a log.
    message: error?.user_message ?? error?.message ?? fallback,
    code: error?.code ?? fallbackCode,
    status: response.status,
    action: error?.action ?? null,
    details: error?.details ?? {},
    requestId: response.headers.get("X-Request-Id"),
  };
}

export async function readApiError(
  response: Response,
  fallback: string,
  fallbackCode = "request_failed",
): Promise<ApiError> {
  const fields = await readErrorFields(response, fallback, fallbackCode);
  return new ApiError(fields.message, fields.code, fields);
}

/** The JSON body of a successful response, or the response's `ApiError`. */
export async function jsonOrApiError<T>(
  response: Response,
  fallback: string,
  fallbackCode?: string,
): Promise<T> {
  if (!response.ok) throw await readApiError(response, fallback, fallbackCode);
  return response.json() as Promise<T>;
}

/**
 * An `ApiError` that keeps the caller's own sentence. For the calls whose screens
 * have always said one fixed thing, so the copy does not change while the error
 * still carries the server's code and request id.
 */
export async function apiFailure(
  response: Response,
  message: string,
): Promise<ApiError> {
  const fields = await readErrorFields(response, message);
  return new ApiError(message, fields.code, fields);
}
