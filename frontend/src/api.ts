const AUTH_TOKEN_KEY = "tutuorders_auth_token";

function getAuthToken() {
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

function setAuthToken(token: string) {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearAuthToken() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
}

async function apiFetch(path: string, init: RequestInit = {}, useAuth = true) {
  const headers = new Headers(init.headers || {});
  if (useAuth) {
    const token = getAuthToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(path, { ...init, headers });
  if (response.status === 401) {
    throw new Error("Требуется вход");
  }
  return response;
}

export async function login(username: string, password: string) {
  const response = await apiFetch(
    "/api/auth/login",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    },
    false
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось выполнить вход");
  }
  const data = await response.json();
  if (!data?.access_token) throw new Error("Не удалось получить токен");
  setAuthToken(data.access_token);
  return data;
}

export async function authMe() {
  const response = await apiFetch("/api/auth/me");
  if (!response.ok) throw new Error("Требуется вход");
  return response.json();
}

export async function getSuppliers() {
  const response = await apiFetch("/api/suppliers");
  if (!response.ok) throw new Error("Не удалось загрузить поставщиков");
  return response.json();
}

export async function getPriceFormatHelp() {
  const response = await apiFetch("/api/prices/format-help");
  if (!response.ok) throw new Error("Не удалось загрузить подсказку по формату прайса");
  return response.json();
}

export async function uploadPrice(supplierId: number, file: File) {
  const formData = new FormData();
  formData.append("supplier_id", String(supplierId));
  formData.append("file", file);
  const response = await apiFetch("/api/prices/upload", {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось загрузить прайс");
  }
  return response.json();
}

export async function updateSupplier(supplierId: number, payload: { name: string; min_order_amount: number }) {
  const response = await apiFetch(`/api/suppliers/${supplierId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось сохранить поставщика");
  }
  return response.json();
}

export async function matchOrder(orderText: string) {
  const MATCH_TIMEOUT_MS = 300000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), MATCH_TIMEOUT_MS);
  const response = await apiFetch("/api/match", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ order_text: orderText }),
    signal: controller.signal,
  }).finally(() => clearTimeout(timer));
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось выполнить сопоставление");
  }
  return response.json();
}

export async function parseOrder(orderText: string) {
  const response = await apiFetch("/api/order/parse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ order_text: orderText }),
  });
  if (!response.ok) throw new Error("Не удалось разобрать заказ");
  return response.json();
}

export async function exportXlsx(payload: unknown) {
  const response = await apiFetch("/api/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Не удалось скачать xlsx");
  return response.blob();
}
