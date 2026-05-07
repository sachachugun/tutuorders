export async function getSuppliers() {
  const response = await fetch("/api/suppliers");
  if (!response.ok) throw new Error("Не удалось загрузить поставщиков");
  return response.json();
}

export async function getPriceFormatHelp() {
  const response = await fetch("/api/prices/format-help");
  if (!response.ok) throw new Error("Не удалось загрузить подсказку по формату прайса");
  return response.json();
}

export async function uploadPrice(supplierId: number, file: File) {
  const formData = new FormData();
  formData.append("supplier_id", String(supplierId));
  formData.append("file", file);
  const response = await fetch("/api/prices/upload", {
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
  const response = await fetch(`/api/suppliers/${supplierId}`, {
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
  const response = await fetch("/api/match", {
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
  const response = await fetch("/api/order/parse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ order_text: orderText }),
  });
  if (!response.ok) throw new Error("Не удалось разобрать заказ");
  return response.json();
}

export async function exportXlsx(payload: unknown) {
  const response = await fetch("/api/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Не удалось скачать xlsx");
  return response.blob();
}
