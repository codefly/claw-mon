export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });

  const raw = await response.text();
  const contentType = response.headers.get("content-type") ?? "";
  const body = parseBody(raw, contentType);

  if (!response.ok) {
    const message = response.statusText || "Request failed";
    throw new ApiError(message, response.status, body);
  }

  if (typeof body === "string" && body.length > 0) {
    throw new ApiError(
      "Expected JSON response but received non-JSON payload. Check backend URL/proxy.",
      response.status,
      body.slice(0, 500)
    );
  }

  return body as T;
}

function parseBody(raw: string, contentType: string): unknown {
  if (raw.length === 0) {
    return null;
  }

  const shouldParseJson =
    contentType.includes("application/json") ||
    raw.trimStart().startsWith("{") ||
    raw.trimStart().startsWith("[");

  if (!shouldParseJson) {
    return raw;
  }

  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}
