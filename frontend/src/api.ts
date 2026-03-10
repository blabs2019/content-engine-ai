import type {
  Vertical,
  VerticalCreate,
  VerticalUpdate,
  VerticalCollectedData,
} from "./types";

const BASE = "http://localhost:8000/api/v1";

async function request<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// --- Verticals ---

export const getVerticals = () => request<Vertical[]>("/verticals");

export const getVertical = (id: number) => request<Vertical>(`/verticals/${id}`);

export const createVertical = (data: VerticalCreate) =>
  request<Vertical>("/verticals", { method: "POST", body: JSON.stringify(data) });

export const updateVertical = (id: number, data: VerticalUpdate) =>
  request<Vertical>(`/verticals/${id}`, { method: "PUT", body: JSON.stringify(data) });

export const deleteVertical = (id: number) =>
  request<void>(`/verticals/${id}`, { method: "DELETE" });

// --- Collected Data ---

export const getVerticalData = (verticalId: number) =>
  request<VerticalCollectedData>(`/collected-data/vertical/${verticalId}`);
