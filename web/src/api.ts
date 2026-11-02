import type { Answer } from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function ask(question: string, token: string): Promise<Answer> {
  const response = await fetch("/api/ask", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ question }),
  });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    throw new ApiError(response.status, detail(body) ?? `Request failed (${response.status})`);
  }
  return (await response.json()) as Answer;
}

function detail(body: unknown): string | null {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const value = (body as { detail: unknown }).detail;
    if (typeof value === "string") return value;
  }
  return null;
}
