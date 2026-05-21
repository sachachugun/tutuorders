import { useEffect, useMemo, useState } from "react";
import {
  createProductSpec,
  deleteProductSpec,
  getDepartments,
  getLocations,
  getProducts,
  getProductSpecs,
  getSuppliers,
  previewProductSpec,
  updateProductSpec,
} from "../api";

const SCOPE_OPTIONS = [
  { value: "global", label: "Глобально" },
  { value: "department", label: "Отдел" },
  { value: "location", label: "Локация" },
  { value: "location_department", label: "Локация + отдел" },
  { value: "supplier", label: "Поставщик" },
  { value: "supplier_department", label: "Поставщик + отдел" },
  { value: "supplier_location", label: "Поставщик + локация" },
];

const emptySpecForm = () => ({
  scope_type: "global",
  scope_location_id: "",
  scope_department_id: "",
  scope_supplier_id: "",
  spec_text: "",
  append_to_supplier_order: true,
  valid_from: "",
  valid_to: "",
  is_active: true,
});

function needsLocation(scope: string) {
  return ["location", "location_department", "supplier_location"].includes(scope);
}

function needsDepartment(scope: string) {
  return ["department", "location_department", "supplier_department"].includes(scope);
}

function needsSupplier(scope: string) {
  return ["supplier", "supplier_department", "supplier_location"].includes(scope);
}

export function SpecsPage() {
  const [products, setProducts] = useState<any[]>([]);
  const [locations, setLocations] = useState<any[]>([]);
  const [departments, setDepartments] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [specs, setSpecs] = useState<any[]>([]);
  const [message, setMessage] = useState("");
  const [newSpec, setNewSpec] = useState(emptySpecForm());
  const [editingSpecId, setEditingSpecId] = useState<number | null>(null);
  const [editSpec, setEditSpec] = useState(emptySpecForm());
  const [previewCtx, setPreviewCtx] = useState({ supplier_id: "", location_id: "", department_id: "" });
  const [previewResult, setPreviewResult] = useState<any | null>(null);

  const selectedProduct = useMemo(
    () => products.find((p) => p.id === selectedProductId) || null,
    [products, selectedProductId]
  );

  const loadRefs = () => {
    Promise.all([getProducts(), getLocations(), getDepartments(), getSuppliers()])
      .then(([productsData, locationsData, departmentsData, suppliersData]) => {
        const items = productsData.items || [];
        setProducts(items);
        setLocations(locationsData.items || []);
        setDepartments(departmentsData.items || []);
        setSuppliers(suppliersData.items || []);
        setSelectedProductId((prev) => {
          if (!items.length) return null;
          if (prev && items.some((row: any) => row.id === prev)) return prev;
          return items[0].id;
        });
      })
      .catch(() => {
        setProducts([]);
        setLocations([]);
        setDepartments([]);
        setSuppliers([]);
      });
  };

  const loadSpecs = (productId: number) => {
    getProductSpecs(productId)
      .then((data) => setSpecs(data.items || []))
      .catch(() => setSpecs([]));
  };

  useEffect(() => {
    loadRefs();
  }, []);

  useEffect(() => {
    if (!selectedProductId) {
      setSpecs([]);
      return;
    }
    loadSpecs(selectedProductId);
    setEditingSpecId(null);
    setPreviewResult(null);
  }, [selectedProductId]);

  const toPayload = (form: ReturnType<typeof emptySpecForm>) => ({
    scope_type: form.scope_type,
    scope_location_id: form.scope_location_id ? Number(form.scope_location_id) : null,
    scope_department_id: form.scope_department_id ? Number(form.scope_department_id) : null,
    scope_supplier_id: form.scope_supplier_id ? Number(form.scope_supplier_id) : null,
    spec_text: form.spec_text.trim(),
    append_to_supplier_order: form.append_to_supplier_order,
    valid_from: form.valid_from.trim() || null,
    valid_to: form.valid_to.trim() || null,
    is_active: form.is_active,
  });

  const onCreateSpec = async () => {
    if (!selectedProductId) return;
    if (!newSpec.spec_text.trim()) {
      setMessage("Укажите текст спецификации");
      return;
    }
    setMessage("");
    try {
      await createProductSpec(selectedProductId, toPayload(newSpec));
      setNewSpec(emptySpecForm());
      setMessage("Правило добавлено");
      loadSpecs(selectedProductId);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось добавить правило");
    }
  };

  const onStartEdit = (row: any) => {
    setEditingSpecId(row.id);
    setEditSpec({
      scope_type: row.scope_type,
      scope_location_id: row.scope_location_id ? String(row.scope_location_id) : "",
      scope_department_id: row.scope_department_id ? String(row.scope_department_id) : "",
      scope_supplier_id: row.scope_supplier_id ? String(row.scope_supplier_id) : "",
      spec_text: row.spec_text,
      append_to_supplier_order: row.append_to_supplier_order,
      valid_from: row.valid_from || "",
      valid_to: row.valid_to || "",
      is_active: row.is_active,
    });
  };

  const onSaveEdit = async () => {
    if (!selectedProductId || !editingSpecId) return;
    setMessage("");
    try {
      await updateProductSpec(selectedProductId, editingSpecId, toPayload(editSpec));
      setEditingSpecId(null);
      setMessage("Правило сохранено");
      loadSpecs(selectedProductId);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось сохранить правило");
    }
  };

  const onDeleteSpec = async (specId: number) => {
    if (!selectedProductId) return;
    if (!window.confirm("Удалить правило спецификации?")) return;
    setMessage("");
    try {
      await deleteProductSpec(selectedProductId, specId);
      setMessage("Правило удалено");
      loadSpecs(selectedProductId);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось удалить правило");
    }
  };

  const onPreview = async () => {
    if (!selectedProductId) return;
    setMessage("");
    try {
      const result = await previewProductSpec(selectedProductId, {
        supplier_id: previewCtx.supplier_id ? Number(previewCtx.supplier_id) : null,
        location_id: previewCtx.location_id ? Number(previewCtx.location_id) : null,
        department_id: previewCtx.department_id ? Number(previewCtx.department_id) : null,
      });
      setPreviewResult(result);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось построить превью");
    }
  };

  const renderScopeFields = (
    form: ReturnType<typeof emptySpecForm>,
    setForm: (updater: (prev: ReturnType<typeof emptySpecForm>) => ReturnType<typeof emptySpecForm>) => void
  ) => (
    <div className="spec-scope-fields">
      <label className="field">
        <span>Область</span>
        <select value={form.scope_type} onChange={(e) => setForm((p) => ({ ...p, scope_type: e.target.value }))}>
          {SCOPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>
      {needsLocation(form.scope_type) && (
        <label className="field">
          <span>Локация</span>
          <select
            value={form.scope_location_id}
            onChange={(e) => setForm((p) => ({ ...p, scope_location_id: e.target.value }))}
          >
            <option value="">Выберите...</option>
            {locations.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {needsDepartment(form.scope_type) && (
        <label className="field">
          <span>Отдел</span>
          <select
            value={form.scope_department_id}
            onChange={(e) => setForm((p) => ({ ...p, scope_department_id: e.target.value }))}
          >
            <option value="">Выберите...</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {needsSupplier(form.scope_type) && (
        <label className="field">
          <span>Поставщик</span>
          <select
            value={form.scope_supplier_id}
            onChange={(e) => setForm((p) => ({ ...p, scope_supplier_id: e.target.value }))}
          >
            <option value="">Выберите...</option>
            {suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );

  return (
    <section className="page-stack">
      <h2 className="section-title">Спецификации</h2>
      {message && <p className="status-message">{message}</p>}

      <article className="card product-toolbar">
        <label className="field">
          <span>Продукт</span>
          <select
            value={selectedProductId ?? ""}
            onChange={(e) => setSelectedProductId(e.target.value ? Number(e.target.value) : null)}
          >
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      </article>

      {selectedProduct && (
        <>
          <article className="card">
            <h3 className="card-title">Правила для «{selectedProduct.name}»</h3>
            <div className="table-wrap registry-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Область</th>
                    <th>Условие</th>
                    <th>Текст</th>
                    <th>v</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {specs.map((row) => (
                    <tr key={row.id}>
                      <td>{row.scope_label}</td>
                      <td>{row.scope_summary}</td>
                      <td className="spec-text-cell">{row.spec_text}</td>
                      <td>{row.version}</td>
                      <td>
                        <div className="actions-row compact-actions">
                          <button className="btn btn-secondary btn-compact" onClick={() => onStartEdit(row)}>
                            Изменить
                          </button>
                          <button className="btn btn-secondary btn-compact" onClick={() => void onDeleteSpec(row.id)}>
                            Удалить
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!specs.length && <p className="muted">Пока нет правил для этого продукта.</p>}
          </article>

          <article className="card">
            <h3 className="card-title">{editingSpecId ? "Редактировать правило" : "Добавить правило"}</h3>
            {editingSpecId ? (
              <>
                {renderScopeFields(editSpec, (fn) => setEditSpec(fn(editSpec)))}
                <label className="field">
                  <span>Текст для поставщика</span>
                  <textarea
                    rows={3}
                    value={editSpec.spec_text}
                    onChange={(e) => setEditSpec((p) => ({ ...p, spec_text: e.target.value }))}
                  />
                </label>
                <div className="spec-meta-row">
                  <label className="field">
                    <span>Действует с</span>
                    <input type="date" value={editSpec.valid_from} onChange={(e) => setEditSpec((p) => ({ ...p, valid_from: e.target.value }))} />
                  </label>
                  <label className="field">
                    <span>Действует до</span>
                    <input type="date" value={editSpec.valid_to} onChange={(e) => setEditSpec((p) => ({ ...p, valid_to: e.target.value }))} />
                  </label>
                  <label className="checkbox-inline">
                    <input
                      type="checkbox"
                      checked={editSpec.append_to_supplier_order}
                      onChange={(e) => setEditSpec((p) => ({ ...p, append_to_supplier_order: e.target.checked }))}
                    />
                    <span>Добавлять в заказ поставщику</span>
                  </label>
                </div>
                <div className="actions-row">
                  <button className="btn btn-primary" onClick={() => void onSaveEdit()}>
                    Сохранить
                  </button>
                  <button className="btn btn-secondary" onClick={() => setEditingSpecId(null)}>
                    Отмена
                  </button>
                </div>
              </>
            ) : (
              <>
                {renderScopeFields(newSpec, (fn) => setNewSpec(fn(newSpec)))}
                <label className="field">
                  <span>Текст для поставщика</span>
                  <textarea
                    rows={3}
                    value={newSpec.spec_text}
                    onChange={(e) => setNewSpec((p) => ({ ...p, spec_text: e.target.value }))}
                    placeholder="калибр 25-30, только фиолетовый"
                  />
                </label>
                <div className="spec-meta-row">
                  <label className="field">
                    <span>Действует с</span>
                    <input type="date" value={newSpec.valid_from} onChange={(e) => setNewSpec((p) => ({ ...p, valid_from: e.target.value }))} />
                  </label>
                  <label className="field">
                    <span>Действует до</span>
                    <input type="date" value={newSpec.valid_to} onChange={(e) => setNewSpec((p) => ({ ...p, valid_to: e.target.value }))} />
                  </label>
                </div>
                <button className="btn btn-primary" onClick={() => void onCreateSpec()}>
                  Добавить правило
                </button>
              </>
            )}
          </article>

          <article className="card">
            <h3 className="card-title">Превью для поставщика</h3>
            <div className="spec-preview-row">
              <select
                value={previewCtx.supplier_id}
                onChange={(e) => setPreviewCtx((p) => ({ ...p, supplier_id: e.target.value }))}
              >
                <option value="">Поставщик (опц.)</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
              <select
                value={previewCtx.location_id}
                onChange={(e) => setPreviewCtx((p) => ({ ...p, location_id: e.target.value }))}
              >
                <option value="">Локация (опц.)</option>
                {locations.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </select>
              <select
                value={previewCtx.department_id}
                onChange={(e) => setPreviewCtx((p) => ({ ...p, department_id: e.target.value }))}
              >
                <option value="">Отдел (опц.)</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
              <button className="btn btn-primary" onClick={() => void onPreview()}>
                Показать превью
              </button>
            </div>
            {previewResult && (
              <div className="spec-preview-box">
                <p className="muted">
                  Сработало правило: {previewResult.matched_scope_label || "нет"}
                  {previewResult.matched_spec_id ? ` (#${previewResult.matched_spec_id})` : ""}
                </p>
                <p>{previewResult.spec_text || "— комментарий не добавится —"}</p>
              </div>
            )}
          </article>
        </>
      )}
    </section>
  );
}
