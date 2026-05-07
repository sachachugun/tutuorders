import { useState } from "react";
import { PricesPage } from "./pages/PricesPage";
import { OrderPage } from "./pages/OrderPage";
import { ResultPage } from "./pages/ResultPage";

type Screen = "prices" | "order" | "result";

export function App() {
  const [screen, setScreen] = useState<Screen>("prices");
  const [matchResult, setMatchResult] = useState<any>(null);

  return (
    <main className="container">
      <header className="header">
        <h1>tutuorders</h1>
        <nav className="tabs">
          <button onClick={() => setScreen("prices")}>Прайсы</button>
          <button onClick={() => setScreen("order")}>Заказ</button>
          <button onClick={() => setScreen("result")}>Результат</button>
        </nav>
      </header>

      {screen === "prices" && <PricesPage />}
      {screen === "order" && <OrderPage onMatched={(result) => {
        setMatchResult(result);
        setScreen("result");
      }} />}
      {screen === "result" && <ResultPage result={matchResult} />}
    </main>
  );
}
