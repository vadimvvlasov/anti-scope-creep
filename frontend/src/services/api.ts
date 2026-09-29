// The ONLY module the app imports to talk to the backend.
// No fetch / axios / URL building anywhere outside src/services/.

import { ApiError, isApiError } from "./errors";
import { MockApiClient } from "./mock/mockClient";
import type {
  ApiClient,
  AuthResponse,
  ContractDetail,
  ContractPage,
  CreateContractInput,
  HistoryQueryResult,
  ListContractsParams,
  User,
} from "./types";

export * from "./types";
export { ApiError, isApiError };

/* ------------------------- token storage ------------------------- */

export const TOKEN_KEY = "asc_access_token";

export const getToken = (): string | null => {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
};

export const setToken = (token: string | null): void => {
  if (typeof window === "undefined") return;
  try {
    if (token === null) window.localStorage.removeItem(TOKEN_KEY);
    else window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* storage unavailable */
  }
};

/* ---------------------- global 401 interceptor -------------------- */

export const SESSION_EXPIRED_MESSAGE = "Your session has expired. Please log in again.";

type UnauthorizedHandler = () => void;
let unauthorizedHandler: UnauthorizedHandler | null = null;

/** Registered once by the app shell: shows the message and redirects to Login. */
export const setUnauthorizedHandler = (handler: UnauthorizedHandler | null) => {
  unauthorizedHandler = handler;
};

const handleUnauthorized = (error: ApiError) => {
  // Failed logins are shown inline by the Login form, never by the interceptor.
  if (error.code === "INVALID_CREDENTIALS") return;
  setToken(null);
  unauthorizedHandler?.();
};

/* ------------------------- HTTP implementation -------------------- */

const API_URL: string =
  (typeof import.meta !== "undefined" && import.meta.env?.["VITE_API_URL"]) ||
  "http://localhost:8000";

class HttpApiClient implements ApiClient {
  constructor(private baseUrl: string) {}

  private async request<T>(
    path: string,
    init: RequestInit & { auth?: boolean; expectEmpty?: boolean } = {},
  ): Promise<T> {
    const { auth = true, expectEmpty = false, ...rest } = init;
    const headers = new Headers(rest.headers);
    if (auth) {
      const token = getToken();
      if (token) headers.set("Authorization", `Bearer ${token}`);
    }

    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, { ...rest, headers });
    } catch {
      throw new ApiError(0, "NETWORK_ERROR", "Could not reach the server. Please try again.");
    }

    if (!response.ok) {
      let code = "INTERNAL_ERROR";
      let message = "Something went wrong. Please try again.";
      try {
        const body = (await response.json()) as { error?: { code?: string; message?: string } };
        if (body?.error?.code) code = body.error.code;
        if (body?.error?.message) message = body.error.message;
      } catch {
        /* non-JSON error body */
      }
      const error = new ApiError(response.status, code, message);
      if (response.status === 401) handleUnauthorized(error);
      throw error;
    }

    if (expectEmpty || response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  private json<T>(path: string, method: string, body: unknown, auth = true) {
    return this.request<T>(path, {
      method,
      auth,
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  register(email: string, password: string) {
    return this.json<AuthResponse>("/auth/register", "POST", { email, password }, false).then(
      (res) => {
        setToken(res.access_token);
        return res;
      },
    );
  }

  login(email: string, password: string) {
    return this.json<AuthResponse>("/auth/login", "POST", { email, password }, false).then(
      (res) => {
        setToken(res.access_token);
        return res;
      },
    );
  }

  getMe() {
    return this.request<User>("/auth/me");
  }

  logout() {
    setToken(null);
  }

  createContract(input: CreateContractInput) {
    const form = new FormData();
    if (input.file) form.append("file", input.file);
    if (input.text) form.append("text", input.text);
    if (input.title) form.append("title", input.title);
    return this.request<ContractDetail>("/contracts", { method: "POST", body: form });
  }

  listContracts(params: ListContractsParams = {}) {
    const search = new URLSearchParams({
      page: String(params.page ?? 1),
      page_size: String(params.page_size ?? 20),
    });
    return this.request<ContractPage>(`/contracts?${search.toString()}`);
  }

  getContract(id: string) {
    return this.request<ContractDetail>(`/contracts/${encodeURIComponent(id)}`);
  }

  renameContract(id: string, title: string) {
    return this.json<ContractDetail>(`/contracts/${encodeURIComponent(id)}`, "PATCH", { title });
  }

  retryAnalysis(id: string) {
    return this.request<ContractDetail>(`/contracts/${encodeURIComponent(id)}/retry`, {
      method: "POST",
    });
  }

  deleteContract(id: string) {
    return this.request<void>(`/contracts/${encodeURIComponent(id)}`, {
      method: "DELETE",
      expectEmpty: true,
    });
  }

  queryHistory(question: string) {
    return this.json<HistoryQueryResult>("/query", "POST", { question });
  }
}

/* ----------------- mock wrapper with the 401 handler --------------- */

const wrapUnauthorized = <T extends ApiClient>(client: T): T => {
  const handler: ProxyHandler<T> = {
    get(target, prop, receiver) {
      const value = Reflect.get(target, prop, receiver);
      if (typeof value !== "function") return value;
      return (...args: unknown[]) => {
        try {
          const result = (value as (...a: unknown[]) => unknown).apply(target, args);
          if (result instanceof Promise) {
            return result.catch((error: unknown) => {
              if (isApiError(error) && error.status === 401) handleUnauthorized(error);
              throw error;
            });
          }
          return result;
        } catch (error) {
          if (isApiError(error) && error.status === 401) handleUnauthorized(error);
          throw error;
        }
      };
    },
  };
  return new Proxy(client, handler);
};

export const createMockApi = (): ApiClient =>
  wrapUnauthorized(new MockApiClient({ getToken, setToken }));

export const createHttpApi = (baseUrl: string = API_URL): ApiClient => new HttpApiClient(baseUrl);

const USE_MOCK =
  (typeof import.meta !== "undefined" && import.meta.env?.["VITE_USE_MOCK"]) !== "false";

export const api: ApiClient = USE_MOCK ? createMockApi() : createHttpApi();
