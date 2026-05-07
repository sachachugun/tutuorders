import { useEffect, useMemo, useState } from "react";
import { exportXlsx } from "../api";

type Props = {
  result: any;
};

export function ResultPage({ result }: Props) {
  if (!result) return <p>Результат пока не получен.</p>;

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
      <h2>Результат</h2>
      <p>Валюта: {result.currency}</p>
      <p>Неразобранных строк: {(result.unparsed_lines || []).length}</p>
      <p>Время: {result.elapsed_ms} ms</p>

      <table>
        <thead>
          <tr>
            <th>Продукт</th>
            <th>Ед.</th>
            <th>Кол-во к заказу</th>
            {supplierIds.map((id) => (
              <th key={`alloc-${id}`}>Кол-во {supplierNames[id] || `S${id}`}</th>
            ))}
            <th>Сумма, RUB</th>
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
          </tr>
          {items.map((item: any, idx: number) => (
            <tr key={`${item.canonical_name}-${idx}`}>
              <td>{item.canonical_name}</td>
              <td>{item.unit}</td>
              <td>{Number(item.quantity).toFixed(3)}</td>
              {supplierIds.map((supplierId) => {
                const allocation = (item.allocation || []).find((a: any) => a.supplier_id === supplierId);
                return <td key={`${idx}-${supplierId}`}>{Number(allocation?.quantity || 0).toFixed(3)}</td>;
              })}
              <td>{Number(item.row_total || 0).toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <button onClick={onDownload}>Скачать xlsx</button>
    </section>
  );
}
