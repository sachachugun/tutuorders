import { useEffect, useState } from "react";
import { createSupplier, getPriceFormatHelp, getSuppliers, updateSupplier, uploadPrice } from "../api";

type BrokenSkuItem = {
  product_id: number;
  product_name: string;
  name_in_price: string;
};

function formatUploadDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString("ru-RU");
}

export function PricesPage() {
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [drafts, setDrafts] = useState<Record<number, { name: string; min_order_amount: string }>>({});
  const [message, setMessage] = useState("");
  const [formatHelp, setFormatHelp] = useState<any>(null);
  const [lastUploadResult, setLastUploadResult] = useState<
    Record<
      number,
      {
        at: number;
        fileName: string;
        savedRows: number;
        newPriceItems: number;
        brokenSkuLinks: number;
        affectedProducts: number;
        relinked?: number;
        brokenItems?: BrokenSkuItem[];
        error?: string;
      }
    >
  >({});
  const [newSupplierName, setNewSupplierName] = useState("");
  const [newSupplierMin, setNewSupplierMin] = useState("0");
  const [isCreating, setIsCreating] = useState(false);

  const loadSuppliers = () => {
    getSuppliers()
      .then((data) => {
        const items = data.items || [];
        setSuppliers(items);
        const nextDrafts: Record<number, { name: string; min_order_amount: string }> = {};
        for (const s of items) {
          nextDrafts[s.id] = { name: s.name, min_order_amount: String(s.min_order_amount) };
        }
        setDrafts(nextDrafts);
      })
      .catch(() => setSuppliers([]));
  };

  useEffect(() => {
    loadSuppliers();
    getPriceFormatHelp().then(setFormatHelp).catch(() => setFormatHelp(null));
  }, []);

  const onUpload = async (supplierId: number, file: File | null) => {
    if (!file) return;
    try {
      const result = await uploadPrice(supplierId, file);
      setLastUploadResult((prev) => ({
        ...prev,
        [supplierId]: {
          at: Date.now(),
          fileName: file.name,
          savedRows: result.saved_rows,
          newPriceItems: result.new_price_items_count ?? 0,
          brokenSkuLinks: result.broken_sku_links_count ?? 0,
          affectedProducts: result.affected_products_count ?? 0,
          relinked: result.relinked_count ?? 0,
          brokenItems: result.broken_items ?? [],
        },
      }));
      loadSuppliers();
    } catch (e) {
      const err = e instanceof Error ? e.message : "Не удалось загрузить прайс";
      setLastUploadResult((prev) => ({
        ...prev,
        [supplierId]: {
          at: Date.now(),
          fileName: file.name,
          savedRows: 0,
          newPriceItems: 0,
          brokenSkuLinks: 0,
          affectedProducts: 0,
          error: err,
        },
      }));
    }
  };

  const onCreateSupplier = async () => {
    const name = newSupplierName.trim();
    if (!name) {
      setMessage("Укажите имя нового поставщика");
      return;
    }
    setMessage("");
    setIsCreating(true);
    try {
      await createSupplier({ name, min_order_amount: Number(newSupplierMin) || 0 });
      setNewSupplierName("");
      setNewSupplierMin("0");
      setMessage(`Поставщик «${name}» добавлен`);
      loadSuppliers();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось добавить поставщика");
    } finally {
      setIsCreating(false);
    }
  };

  const onSave = async (supplierId: number) => {
    const draft = drafts[supplierId];
    if (!draft) return;
    setMessage("");
    try {
      await updateSupplier(supplierId, {
        name: draft.name.trim(),
        min_order_amount: Number(draft.min_order_amount),
      });
      setMessage("Карточка поставщика сохранена");
      loadSuppliers();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось сохранить поставщика");
    }
  };

  return (
    <section className="page-stack">
      <h2 className="section-title">Прайсы поставщиков</h2>
      <p className="muted">
        Загрузка заменяет прайс поставщика. Словарь и спецификации не трогаются — старые привязки SKU сохраняются;
        если позиции нет в новом файле, в словаре будет «нет в прайсе».
      </p>
      {message && <p className="status-message">{message}</p>}
      <article className="card add-supplier-card">
        <h3 className="card-title">Новый поставщик</h3>
        <div className="add-supplier-row">
          <label className="field">
            <span>Имя</span>
            <input
              value={newSupplierName}
              onChange={(e) => setNewSupplierName(e.target.value)}
              placeholder="Название поставщика"
              disabled={isCreating}
            />
          </label>
          <label className="field">
            <span>Минимальный заказ, RUB</span>
            <input
              type="number"
              step="0.01"
              value={newSupplierMin}
              onChange={(e) => setNewSupplierMin(e.target.value)}
              disabled={isCreating}
            />
          </label>
          <button type="button" className="btn btn-primary" onClick={() => void onCreateSupplier()} disabled={isCreating}>
            {isCreating ? "Добавление..." : "Добавить поставщика"}
          </button>
        </div>
        <p className="muted">После добавления загрузите прайс — в результате и Excel появятся колонки для этого поставщика.</p>
      </article>
      <div className="cards">
        {suppliers.map((s) => (
          <article className="card" key={s.id}>
            <h3 className="card-title">Поставщик #{s.id}</h3>
            <label className="field">
              <span>Имя</span>
              <input
                value={drafts[s.id]?.name ?? s.name}
                onChange={(e) =>
                  setDrafts((prev) => ({
                    ...prev,
                    [s.id]: { ...(prev[s.id] || { name: s.name, min_order_amount: String(s.min_order_amount) }), name: e.target.value },
                  }))
                }
              />
            </label>
            <label className="field">
              <span>Минимальный заказ, RUB</span>
              <input
                type="number"
                step="0.01"
                value={drafts[s.id]?.min_order_amount ?? String(s.min_order_amount)}
                onChange={(e) =>
                  setDrafts((prev) => ({
                    ...prev,
                    [s.id]: { ...(prev[s.id] || { name: s.name, min_order_amount: String(s.min_order_amount) }), min_order_amount: e.target.value },
                  }))
                }
              />
            </label>
            <p className="muted">Сначала сохраните изменения карточки поставщика</p>
            <div className="actions-row">
              <button className="btn btn-primary" onClick={() => onSave(s.id)}>Сохранить</button>
            </div>
            <p className="muted">
              В прайсе: {s.price_items_count} поз.
              {formatUploadDate(s.last_price_upload_at) ? (
                <> · загрузка {formatUploadDate(s.last_price_upload_at)}</>
              ) : null}
              {s.unmatched_price_items_count > 0 ? (
                <> · без привязки к словарю: {s.unmatched_price_items_count}</>
              ) : null}
            </p>
            <div className="price-upload-block">
              <label className="field price-upload-field">
                <span>Загрузить прайс (.xls, .xlsx)</span>
                <input
                  className="file-input"
                  type="file"
                  accept=".xls,.xlsx"
                  onChange={(e) => {
                    const file = e.target.files?.[0] || null;
                    void onUpload(s.id, file);
                    e.target.value = "";
                  }}
                />
              </label>
              {lastUploadResult[s.id] && (
                <div
                  className={
                    lastUploadResult[s.id].error ? "upload-result upload-result-error" : "upload-result upload-result-ok"
                  }
                >
                  {lastUploadResult[s.id].error ? (
                    <p>{lastUploadResult[s.id].error}</p>
                  ) : (
                    <>
                      <p className="upload-result-title">
                        «{lastUploadResult[s.id].fileName}» — {lastUploadResult[s.id].savedRows} поз. в прайсе
                        {lastUploadResult[s.id].newPriceItems > 0 && (
                          <span className="muted-inline"> (+{lastUploadResult[s.id].newPriceItems} новых)</span>
                        )}
                      </p>
                      {(lastUploadResult[s.id].relinked ?? 0) > 0 && (
                        <p className="upload-result-ok-hint">
                          Привязок SKU восстановлено автоматически: {lastUploadResult[s.id].relinked}.
                        </p>
                      )}
                      {lastUploadResult[s.id].brokenSkuLinks > 0 ? (
                        <div className="upload-result-warn">
                          <p className="upload-result-warn-title">
                            В новом прайсе нет строки для {lastUploadResult[s.id].brokenSkuLinks} привязок в Словаре —
                            откройте Словарь и выберите другое название из файла:
                          </p>
                          <ul className="upload-broken-sku-list">
                            {(lastUploadResult[s.id].brokenItems || []).map((item) => (
                              <li key={`${item.product_id}-${item.name_in_price}`}>
                                <strong>{item.product_name}</strong>
                                <span className="muted-inline">
                                  {" "}
                                  — в прайсе искали: «{item.name_in_price}»
                                </span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : (
                        <p className="upload-result-ok-hint">Все привязки SKU этого поставщика совпали с прайсом.</p>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          </article>
        ))}
      </div>
      {formatHelp && (
        <details className="format-help-details">
          <summary>Требования к файлам прайсов</summary>
          <ul>
            {formatHelp.common?.map((line: string, idx: number) => (
              <li key={`common-${idx}`}>{line}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
