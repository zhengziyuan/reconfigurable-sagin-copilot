const configuredBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${configuredBase}${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail ?? body.error;
    const message = typeof detail === "string" ? detail : Array.isArray(detail)
      ? detail.map((item: { msg?: string }) => item.msg).join("; ") : `请求失败 (${response.status})`;
    throw new ApiError(message, response.status);
  }
  return response;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function downloadText(filename: string, text: string, type = "application/json") {
  const url = URL.createObjectURL(new Blob([text], { type: `${type};charset=utf-8` }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
