import { useState } from "react";
import { matchOrder } from "../api";

type Props = {
  onMatched: (result: any) => void;
};

export function OrderPage({ onMatched }: Props) {
  const [orderText, setOrderText] = useState("");
  const [error, setError] = useState("");
  const [isMatching, setIsMatching] = useState(false);

  const onSubmit = async () => {
    if (!orderText.trim()) {
      setError("Введите список заказа");
      return;
    }
    setError("");
    setIsMatching(true);
    try {
      const result = await matchOrder(orderText);
      onMatched(result);
    } catch (e) {
      setError(e instanceof Error && e.name === "AbortError" ? "Слишком долгое сопоставление, попробуйте еще раз" : "Обратитесь к разработчику");
    } finally {
      setIsMatching(false);
    }
  };

  return (
    <section>
      <h2>Заказ</h2>
      <textarea
        value={orderText}
        onChange={(e) => setOrderText(e.target.value)}
        rows={14}
        placeholder="Брокколи 3 кг"
        disabled={isMatching}
      />
      <div>
        <button onClick={onSubmit} disabled={isMatching}>
          {isMatching ? "Сопоставление..." : "Сопоставить"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </section>
  );
}
