import { useEffect, useState } from "react";
import { getSuppliers, updateSupplier, uploadPrice } from "../api";

export function PricesPage() {
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [drafts, setDrafts] = useState<Record<number, { name: string; min_order_amount: string }>>({});
  const [message, setMessage] = useState("");

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

  useEffect(() => loadSuppliers(), []);

  const onUpload = async (supplierId: number, file: File | null) => {
    if (!file) return;
    setMessage("");
    try {
      const result = await uploadPrice(supplierId, file);
      setMessage(`Прайс загружен: сохранено ${result.saved_rows} позиций`);
      loadSuppliers();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось загрузить прайс");
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
      <h2>Прайсы</h2>
      {message && <p>{message}</p>}
      <div className="cards">
        {suppliers.map((s) => (
          <article className="card" key={s.id}>
            <h3>Поставщик #{s.id}</h3>
            <label>
              Имя:
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
            <label>
              Минимум:
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
            <p>Загружено позиций: {s.price_items_count}</p>
            <input
              type="file"
              accept=".xls,.xlsx"
              onChange={(e) => onUpload(s.id, e.target.files?.[0] || null)}
            />
            <div>
              <button onClick={() => onSave(s.id)}>Сохранить</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
