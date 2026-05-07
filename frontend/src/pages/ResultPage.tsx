import { useEffect, useMemo, useState } from "react";
import { exportXlsx } from "../api";

type Props = {
  result: any;
};

export function ResultPage({ result }: Props) {
  if (!result) return <p className="muted">Результат пока не получен.</p>;

  const [items, setItems] = useState<any[]>(result.items || []);
  useEffect(() => {
    setItems(result.items || []);
  }, [result]);
  const supplierNames = useMemo(() => {
    const mapping: Record<number, string> = {};
    for (const supplier of result.suppliers || []) {
      mapping[supplier.id] = supplier.name;
    }
    return mapping;
  }, [result]);
  const supplierIds = useMemo(() => {
    const ids: number[] = (result.suppliers || []).map((s: any) => s.id);
    for (const item of items) {
      for (const match of item.matches || []) {
        if (!ids.includes(match.supplier_id)) ids.push(match.supplier_id);
      }
      for (const allocation of item.allocation || []) {
        if (!ids.includes(allocation.supplier_id)) ids.push(allocation.supplier_id);
      }
    }
    return ids;
  }, [items]);
  const totalPositions = items.length;
  const notFound = result.not_found_in_suppliers || [];
  const isDegraded = Boolean(result.degraded_mode);
  const degradedReason = result.degraded_reason || "";
  const supplierTotals = useMemo(() => {
    const totals: Record<number, number> = {};
    for (const item of items) {
      for (const alloc of item.allocation || []) {
        totals[alloc.supplier_id] = Number(((totals[alloc.supplier_id] || 0) + Number(alloc.amount || 0)).toFixed(2));
      }
    }
    return totals;
  }, [items]);

  const onDownload = async () => {
    const supplier_name_payload: Record<string, string> = {};
    for (const supplierId of supplierIds) {
      supplier_name_payload[String(supplierId)] = supplierNames[supplierId] || `S${supplierId}`;
    }
    const blob = await exportXlsx({ currency: "RUB", items, supplier_names: supplier_name_payload });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "result.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section>
      <h2 className="section-title">Результат сопоставления</h2>
      <div className="match-status-row">
        <span className={isDegraded ? "match-status-badge info" : "match-status-badge ok"}>
          {isDegraded ? "Режим проверки: без ИИ" : "Режим проверки: с ИИ"}
        </span>
        {isDegraded && (
          <span className="match-status-reason">
            Причина: {degradedReason}
          </span>
        )}
      </div>
      <div className="meta-row">
        <p><span className="muted">Валюта:</span> {result.currency}</p>
        <p><span className="muted">Неразобранных строк:</span> {(result.unparsed_lines || []).length}</p>
        <p><span className="muted">Время:</span> {result.elapsed_ms} ms</p>
      </div>
      {!!notFound.length && (
        <div className="parse-warning">
          <strong>Не найдено в прайсах поставщиков:</strong>
          <ul>
            {notFound.map((item: any, idx: number) => (
              <li key={`${item.name}-${idx}`}>{item.name} — {Number(item.quantity).toFixed(3)} {item.unit}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="table-wrap">
      <table className="result-table">
        <thead>
          <tr>
            <th>Продукт</th>
            <th>Ед.</th>
            <th>Кол-во к заказу</th>
            {supplierIds.map((id) => (
              <th key={`alloc-${id}`}>Кол-во {supplierNames[id] || `S${id}`}</th>
            ))}
            <th>Сумма, RUB</th>
            <th>Комментарий</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Итого</td>
            <td />
            <td>{totalPositions}</td>
            {supplierIds.map((supplierId) => (
              <td key={`sum-${supplierId}`}>{Number(supplierTotals[supplierId] || 0).toFixed(2)}</td>
            ))}
            <td>{Number(items.reduce((acc: number, item: any) => acc + Number(item.row_total || 0), 0)).toFixed(2)}</td>
            <td />
          </tr>
          {items.map((item: any, idx: number) => (
            <tr key={`${item.canonical_name}-${idx}`} className={!item.matches?.length ? "row-not-found" : ""}>
              <td>{item.canonical_name}</td>
              <td>{item.unit}</td>
              <td>{Number(item.quantity).toFixed(3)}</td>
              {supplierIds.map((supplierId) => {
                const allocation = (item.allocation || []).find((a: any) => a.supplier_id === supplierId);
                return <td key={`${idx}-${supplierId}`}>{Number(allocation?.quantity || 0).toFixed(3)}</td>;
              })}
              <td>{Number(item.row_total || 0).toFixed(2)}</td>
              <td className="comment-cell">{item.comment || ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      <button className="btn btn-primary" onClick={onDownload}>Скачать xlsx</button>
    </section>
  );
}
