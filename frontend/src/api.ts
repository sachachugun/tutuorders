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

export async function createSupplier(payload: { name: string; min_order_amount: number }) {
  const response = await apiFetch("/api/suppliers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось добавить поставщика");
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

export async function getDepartments() {
  const response = await apiFetch("/api/departments");
  if (!response.ok) throw new Error("Не удалось загрузить отделы");
  return response.json();
}

export async function getLocations() {
  const response = await apiFetch("/api/locations");
  if (!response.ok) throw new Error("Не удалось загрузить локации");
  return response.json();
}

export async function createLocation(payload: {
  code: string;
  name: string;
  sort_order: number;
  is_active: boolean;
}) {
  const response = await apiFetch("/api/locations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось добавить локацию");
  }
  return response.json();
}

export async function updateLocation(
  locationId: number,
  payload: { code: string; name: string; sort_order: number; is_active: boolean }
) {
  const response = await apiFetch(`/api/locations/${locationId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось сохранить локацию");
  }
  return response.json();
}

export async function deleteLocation(locationId: number) {
  const response = await apiFetch(`/api/locations/${locationId}`, { method: "DELETE" });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось удалить локацию");
  }
  return response.json();
}

export async function getProducts() {
  const response = await apiFetch("/api/products");
  if (!response.ok) throw new Error("Не удалось загрузить словарь");
  return response.json();
}

export async function createProduct(payload: {
  name: string;
  default_unit: string;
  category?: string | null;
  notes?: string | null;
  is_active: boolean;
}) {
  const response = await apiFetch("/api/products", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось добавить продукт");
  }
  return response.json();
}

export async function updateProduct(
  productId: number,
  payload: {
    name: string;
    default_unit: string;
    category?: string | null;
    notes?: string | null;
    is_active: boolean;
  }
) {
  const response = await apiFetch(`/api/products/${productId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось сохранить продукт");
  }
  return response.json();
}

export async function getProductDeleteImpact(productId: number) {
  const response = await apiFetch(`/api/products/${productId}/delete-impact`);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось проверить связи продукта");
  }
  return response.json();
}

export async function deleteProduct(productId: number) {
  const response = await apiFetch(`/api/products/${productId}`, { method: "DELETE" });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось удалить продукт");
  }
  return response.json();
}

export async function createProductSku(
  productId: number,
  payload: { supplier_id: number; name_in_price: string; is_preferred: boolean; match_source?: string }
) {
  const response = await apiFetch(`/api/products/${productId}/skus`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось привязать SKU");
  }
  return response.json();
}

export async function getProductSpecs(productId: number) {
  const response = await apiFetch(`/api/products/${productId}/specs`);
  if (!response.ok) throw new Error("Не удалось загрузить спецификации");
  return response.json();
}

export async function createProductSpec(productId: number, payload: unknown) {
  const response = await apiFetch(`/api/products/${productId}/specs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось добавить правило");
  }
  return response.json();
}

export async function updateProductSpec(productId: number, specId: number, payload: unknown) {
  const response = await apiFetch(`/api/products/${productId}/specs/${specId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось сохранить правило");
  }
  return response.json();
}

export async function deleteProductSpec(productId: number, specId: number) {
  const response = await apiFetch(`/api/products/${productId}/specs/${specId}`, { method: "DELETE" });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось удалить правило");
  }
  return response.json();
}

export async function previewProductSpec(
  productId: number,
  payload: { supplier_id: number | null; location_id: number | null; department_id: number | null }
) {
  const response = await apiFetch(`/api/products/${productId}/specs/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось построить превью");
  }
  return response.json();
}

export async function deleteProductSku(productId: number, skuId: number) {
  const response = await apiFetch(`/api/products/${productId}/skus/${skuId}`, { method: "DELETE" });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось удалить SKU");
  }
  return response.json();
}

export async function createProcurementBatch(payload: { plan_label: string; responsible?: string | null }) {
  const response = await apiFetch("/api/procurement/batches", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось создать план закупки");
  }
  return response.json();
}

export async function getProcurementBatches() {
  const response = await apiFetch("/api/procurement/batches");
  if (!response.ok) throw new Error("Не удалось загрузить планы закупки");
  return response.json();
}

export async function getProcurementBatch(batchId: number) {
  const response = await apiFetch(`/api/procurement/batches/${batchId}`);
  if (!response.ok) throw new Error("Не удалось загрузить план");
  return response.json();
}

export async function listBatchDemand(batchId: number) {
  const response = await apiFetch(`/api/procurement/batches/${batchId}/demand`);
  if (!response.ok) throw new Error("Не удалось загрузить спрос");
  return response.json();
}

export async function saveBatchDemand(
  batchId: number,
  payload: { location_id: number; department_id: number; order_text: string }
) {
  const response = await apiFetch(`/api/procurement/batches/${batchId}/demand`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось сохранить спрос");
  }
  return response.json();
}

export async function parseProcurementBatch(batchId: number) {
  const response = await apiFetch(`/api/procurement/batches/${batchId}/parse`, { method: "POST" });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось разобрать план");
  }
  return response.json();
}

export async function getProcurementMatch(batchId: number) {
  const response = await apiFetch(`/api/procurement/batches/${batchId}/match`);
  if (!response.ok) throw new Error("Не удалось загрузить проверку");
  return response.json();
}

export async function runProcurementMatch(batchId: number) {
  const response = await apiFetch(`/api/procurement/batches/${batchId}/match`, { method: "POST" });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось выполнить проверку");
  }
  return response.json();
}

export async function assignDemandLineProduct(
  batchId: number,
  lineId: number,
  payload: { canonical_product_id: number }
) {
  const response = await apiFetch(`/api/procurement/batches/${batchId}/demand/${lineId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось назначить продукт");
  }
  return response.json();
}

export async function getProcurementAllocations(batchId: number) {
  const response = await apiFetch(`/api/procurement/batches/${batchId}/allocations`);
  if (!response.ok) throw new Error("Не удалось загрузить распределение");
  return response.json();
}

export async function optimizeProcurementBatch(batchId: number) {
  const response = await apiFetch(`/api/procurement/batches/${batchId}/optimize`, { method: "POST" });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось пересчитать распределение");
  }
  return response.json();
}

export async function overrideProductSupplier(
  batchId: number,
  canonicalProductId: number,
  payload: { supplier_id: number }
) {
  const response = await apiFetch(
    `/api/procurement/batches/${batchId}/products/${canonicalProductId}/supplier`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось сменить поставщика");
  }
  return response.json();
}

export async function buildProcurementOrders(batchId: number) {
  const response = await apiFetch(`/api/procurement/batches/${batchId}/build-orders`, { method: "POST" });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось собрать заказы");
  }
  return response.json();
}

export async function getProcurementOrders(batchId: number) {
  const response = await apiFetch(`/api/procurement/batches/${batchId}/orders`);
  if (!response.ok) throw new Error("Не удалось загрузить заказы поставщикам");
  return response.json();
}

export async function updateSupplierOrderComment(
  batchId: number,
  lineId: number,
  payload: { line_comment: string }
) {
  const response = await apiFetch(`/api/procurement/batches/${batchId}/orders/${lineId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось сохранить комментарий");
  }
  return response.json();
}

export async function getProcurementSummary(
  batchId: number,
  params?: { location_id?: number | null; department_id?: number | null }
) {
  const qs = new URLSearchParams();
  if (params?.location_id) qs.set("location_id", String(params.location_id));
  if (params?.department_id) qs.set("department_id", String(params.department_id));
  const query = qs.toString();
  const response = await apiFetch(
    `/api/procurement/batches/${batchId}/summary${query ? `?${query}` : ""}`
  );
  if (!response.ok) throw new Error("Не удалось загрузить сводку");
  return response.json();
}

export async function downloadProcurementSummaryExport(
  batchId: number,
  params?: { location_id?: number | null; department_id?: number | null }
) {
  const qs = new URLSearchParams();
  if (params?.location_id) qs.set("location_id", String(params.location_id));
  if (params?.department_id) qs.set("department_id", String(params.department_id));
  const query = qs.toString();
  const response = await apiFetch(
    `/api/procurement/batches/${batchId}/summary/export${query ? `?${query}` : ""}`
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось скачать сводку");
  }
  return response.blob();
}

export async function downloadProcurementExport(batchId: number) {
  const response = await apiFetch(`/api/procurement/batches/${batchId}/export`);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось скачать xlsx");
  }
  return response.blob();
}

export async function suggestProductSkus(name: string, unit?: string) {
  const response = await apiFetch("/api/products/suggest-skus", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, unit }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось подобрать SKU");
  }
  return response.json();
}

export async function addProductFromDemandGap(
  batchId: number,
  payload: {
    demand_name: string;
    default_unit?: string;
    sku_links?: { supplier_id: number; name_in_price: string }[];
  }
) {
  const response = await apiFetch(`/api/procurement/batches/${batchId}/dictionary/add`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось добавить продукт в словарь");
  }
  return response.json();
}

export async function suggestDemandLineProducts(batchId: number, lineId: number) {
  const response = await apiFetch(`/api/procurement/batches/${batchId}/demand/${lineId}/suggest`, {
    method: "POST",
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Не удалось получить подсказки");
  }
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
