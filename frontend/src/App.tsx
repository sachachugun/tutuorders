import { useState } from "react";
import { PricesPage } from "./pages/PricesPage";
import { OrderPage } from "./pages/OrderPage";
import { ResultPage } from "./pages/ResultPage";

type Screen = "prices" | "order" | "result";

export function App() {
  const [screen, setScreen] = useState<Screen>("prices");
  const [matchResult, setMatchResult] = useState<any>(null);
  const [orderText, setOrderText] = useState("");
  const [orderParsePreview, setOrderParsePreview] = useState<any | null>(null);

  return (
    <main className="container">
      <header className="header">
        <div className="brand-block">
          <p className="eyebrow">Culinary procurement</p>
          <div className="brand-logo-wrap">
            <img className="brand-logo" src="/tutuorders-logo.png" alt="tutuorders" />
          </div>
        </div>
        <nav className="tabs">
          <button className={screen === "prices" ? "tab active" : "tab"} onClick={() => setScreen("prices")}>Прайсы</button>
          <button className={screen === "order" ? "tab active" : "tab"} onClick={() => setScreen("order")}>Заказ</button>
          <button className={screen === "result" ? "tab active" : "tab"} onClick={() => setScreen("result")}>Результат</button>
        </nav>
      </header>

      <section className="panel">
        {screen === "prices" && <PricesPage />}
        {screen === "order" && (
          <OrderPage
            orderText={orderText}
            parsePreview={orderParsePreview}
            onOrderTextChange={(text) => {
              setOrderText(text);
              setOrderParsePreview(null);
            }}
            onParsePreviewChange={setOrderParsePreview}
            onMatched={(result) => {
              setMatchResult(result);
              setScreen("result");
            }}
            onClear={() => {
              setOrderText("");
              setOrderParsePreview(null);
            }}
          />
        )}
        {screen === "result" && <ResultPage result={matchResult} />}
      </section>
    </main>
  );
}
