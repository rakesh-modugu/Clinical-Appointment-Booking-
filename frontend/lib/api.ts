/**
 * Typed REST API client.
 * All requests go through this wrapper which injects auth headers automatically.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("access_token");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const token = getToken();
    const res = await fetch(`${BASE_URL}${path}`, {
        ...init,
        headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(init.headers ?? {}),
        },
    });
    if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
    return res.json();
}

export const api = {
    get: <T>(path: string) => request<T>(path),
    post: <T>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) }),
    put: <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
    delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
