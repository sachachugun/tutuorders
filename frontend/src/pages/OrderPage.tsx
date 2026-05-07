import { useState } from "react";
import { matchOrder, parseOrder } from "../api";

type Props = {
  onMatched: (result: any) => void;
};

export function OrderPage({ onMatched }: Props) {
  const [orderText, setOrderText] = useState("");
  const [error, setError] = useState("");
  const [parsePreview, setParsePreview] = useState<any | null>(null);
  const [isParsing, setIsParsing] = useState(false);
  const [isMatching, setIsMatching] = useState(false);

  const onParse = async () => {
    if (!orderText.trim()) {
      setError("Введите список заказа");
      return;
    }
    setError("");
    setIsParsing(true);
    try {
      const preview = await parseOrder(orderText);
      setParsePreview(preview);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось разобрать заказ");
    } finally {
      setIsParsing(false);
    }
  };

  const onSubmit = async () => {
    if (!orderText.trim()) {
      setError("Введите список заказа");
      return;
    }
    if (!parsePreview?.parsed_count) {
      setError("Сначала проверьте ввод кнопкой 'Проверить ввод'");
      return;
    }
    setError("");
    setIsMatching(true);
    try {
      const result = await matchOrder(orderText);
      onMatched(result);
    } catch (e) {
      setError(
        e instanceof Error && e.name === "AbortError"
          ? "Сопоставление заняло слишком много времени (>5 минут). Попробуйте еще раз или уменьшите объем заказа."
          : e instanceof Error
            ? e.message
            : "Не удалось выполнить сопоставление"
      );
    } finally {
      setIsMatching(false);
    }
  };

  return (
    <section>
      <h2 className="section-title">Заказ</h2>
      <p className="muted">Вставьте список строк в формате "Название количество единица".</p>
      <textarea
        className="order-textarea"
        value={orderText}
        onChange={(e) => {
          setOrderText(e.target.value);
          setParsePreview(null);
        }}
        rows={14}
        placeholder="Брокколи 3 кг"
        disabled={isMatching || isParsing}
      />
      <div className="actions-row">
        <button className="btn" onClick={onParse} disabled={isParsing || isMatching}>
          {isParsing ? "Проверка..." : "Проверить ввод"}
        </button>
        <button className="btn btn-primary" onClick={onSubmit} disabled={isMatching || isParsing}>
          {isMatching ? "Сопоставление..." : "Сопоставить"}
        </button>
      </div>
      {parsePreview && (
        <div className="parse-preview">
          <p className="muted">
            Разобрано: {parsePreview.parsed_count} из {parsePreview.total_lines} строк
          </p>
          {!!parsePreview.unparsed_lines?.length && (
            <div className="parse-warning">
              <strong>Не удалось разобрать строки:</strong>
              <ul>
                {parsePreview.unparsed_lines.map((line: string, idx: number) => (
                  <li key={`${line}-${idx}`}>{line}</li>
                ))}
              </ul>
            </div>
          )}
          {!!parsePreview.parsed_items?.length && (
            <div className="table-wrap">
              <table className="result-table">
                <thead>
                  <tr>
                    <th>Название</th>
                    <th>Количество</th>
                    <th>Ед.</th>
                  </tr>
                </thead>
                <tbody>
                  {parsePreview.parsed_items.map((item: any, idx: number) => (
                    <tr key={`${item.name}-${idx}`}>
                      <td>{item.name}</td>
                      <td>{Number(item.quantity).toFixed(3)}</td>
                      <td>{item.unit}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
      {error && <p className="error">{error}</p>}
    </section>
  );
}
