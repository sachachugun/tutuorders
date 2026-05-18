import { useEffect, useState } from "react";
import { createSupplier, getPriceFormatHelp, getSuppliers, updateSupplier, uploadPrice } from "../api";

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
  const [lastUploadFlash, setLastUploadFlash] = useState<
    Record<number, { at: number; fileName: string; savedRows: number }>
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
    setMessage("");
    try {
      const result = await uploadPrice(supplierId, file);
      const uploadedAt = Date.now();
      setLastUploadFlash((prev) => ({
        ...prev,
        [supplierId]: {
          at: uploadedAt,
          fileName: file.name,
          savedRows: result.saved_rows,
        },
      }));
      setMessage(`Прайс загружен: сохранено ${result.saved_rows} позиций`);
      loadSuppliers();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось загрузить прайс");
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
    <section>
      <h2 className="section-title">Прайсы поставщиков</h2>
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
      {formatHelp && (
        <div className="format-help">
          <strong>Требования к файлам прайсов</strong>
          <ul>
            {formatHelp.common?.map((line: string, idx: number) => <li key={`common-${idx}`}>{line}</li>)}
          </ul>
        </div>
      )}
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
            <p className="muted">Отдельно загрузите файл прайса (заменяет старый)</p>
            <p className="muted">
              Загружено позиций: {s.price_items_count}
              {formatUploadDate(s.last_price_upload_at) ? (
                <> · последняя загрузка: {formatUploadDate(s.last_price_upload_at)}</>
              ) : s.price_items_count > 0 ? (
                <> · дата загрузки неизвестна</>
              ) : null}
            </p>
            {lastUploadFlash[s.id] && (
              <p className="upload-just-now">
                Файл «{lastUploadFlash[s.id].fileName}» только что загружен, сохранено{" "}
                {lastUploadFlash[s.id].savedRows} позиций
              </p>
            )}
            <input
              className="file-input"
              type="file"
              accept=".xls,.xlsx"
              onChange={(e) => {
                const file = e.target.files?.[0] || null;
                void onUpload(s.id, file);
                // Allow re-uploading the same file name consecutively.
                e.target.value = "";
              }}
            />
          </article>
        ))}
      </div>
    </section>
  );
}
