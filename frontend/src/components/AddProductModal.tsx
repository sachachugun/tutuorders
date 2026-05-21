import { useEffect, useState } from "react";
import { suggestProductSkus } from "../api";

export type DictionaryGap = {
  demand_name: string;
  default_unit: string;
  line_count: number;
};

type Props = {
  gap: DictionaryGap;
  onClose: () => void;
  onSave: (payload: {
    demand_name: string;
    default_unit: string;
    sku_links: { supplier_id: number; name_in_price: string }[];
  }) => Promise<void>;
};

export function AddProductModal({ gap, onClose, onSave }: Props) {
  const [name, setName] = useState(gap.demand_name);
  const [unit, setUnit] = useState(gap.default_unit || "кг");
  const [suggest, setSuggest] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [picked, setPicked] = useState<Record<number, string>>({});
  const [manual, setManual] = useState<Record<number, string>>({});

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    suggestProductSkus(name, unit)
      .then((data) => {
        if (!cancelled) setSuggest(data);
      })
      .catch(() => {
        if (!cancelled) setSuggest(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [name, unit]);

  const onSubmit = async () => {
    const sku_links: { supplier_id: number; name_in_price: string }[] = [];
    for (const block of suggest?.suppliers || []) {
      const sid = block.supplier_id;
      const value = (picked[sid] || manual[sid] || "").trim();
      if (value) sku_links.push({ supplier_id: sid, name_in_price: value });
    }
    setSaving(true);
    try {
      await onSave({ demand_name: name.trim(), default_unit: unit, sku_links });
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <article className="card modal-card">
        <h3 className="card-title">Добавить в словарь</h3>
        <p className="muted">
          Шаг 1 — каноническое название. Шаг 2 — привязка к строкам прайсов поставщиков (можно пропустить
          поставщика и донастроить в Словаре).
        </p>

        <div className="modal-product-meta">
          <label className="field">
            <span>Название в словаре</span>
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field">
            <span>Ед.</span>
            <select value={unit} onChange={(e) => setUnit(e.target.value)}>
              <option value="кг">кг</option>
              <option value="г">г</option>
              <option value="л">л</option>
              <option value="мл">мл</option>
            </select>
          </label>
        </div>

        {loading && <p className="muted">Ищем кандидатов в прайсах…</p>}
        {!loading && suggest?.ai_used && <p className="muted">Подсказки дополнены ИИ.</p>}

        {!loading &&
          (suggest?.suppliers || []).map((block: any) => (
            <div key={block.supplier_id} className="modal-supplier-block">
              <h4 className="card-subtitle">{block.supplier_name}</h4>
              {block.candidates?.length > 0 ? (
                <ul className="sku-candidate-list">
                  {block.candidates.map((c: any) => (
                    <li key={`${block.supplier_id}-${c.name_in_price}`}>
                      <label className="sku-candidate-item">
                        <input
                          type="radio"
                          name={`pick-${block.supplier_id}`}
                          checked={picked[block.supplier_id] === c.name_in_price}
                          onChange={() =>
                            setPicked((prev) => ({ ...prev, [block.supplier_id]: c.name_in_price }))
                          }
                        />
                        <span>
                          {c.name_in_price} — {c.price} ₽ / {c.unit}
                          <span className="muted-inline"> ({Math.round(c.score * 100)}%)</span>
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">В прайсе нет похожих — введите название вручную.</p>
              )}
              <input
                className="sku-manual-input"
                placeholder="Или введите название из прайса"
                value={manual[block.supplier_id] || ""}
                onChange={(e) => setManual((prev) => ({ ...prev, [block.supplier_id]: e.target.value }))}
              />
            </div>
          ))}

        <div className="actions-row">
          <button type="button" className="btn btn-primary" disabled={saving || !name.trim()} onClick={() => void onSubmit()}>
            {saving ? "Сохранение..." : "Сохранить и привязать"}
          </button>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>
            Отмена
          </button>
        </div>
      </article>
    </div>
  );
}
