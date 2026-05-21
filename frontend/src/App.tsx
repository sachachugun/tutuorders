import { useState } from "react";
import { AppNav, type AppScreen } from "./components/AppNav";
import { PricesPage } from "./pages/PricesPage";
import { OrderPage } from "./pages/OrderPage";
import { ResultPage } from "./pages/ResultPage";
import { SettingsPage } from "./pages/SettingsPage";
import { ProductsPage } from "./pages/ProductsPage";
import { SpecsPage } from "./pages/SpecsPage";
import { ProcurementPage } from "./pages/ProcurementPage";

export function App() {
  const [screen, setScreen] = useState<AppScreen>("procurement");
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
        <AppNav screen={screen} onSelect={setScreen} />
      </header>

      <section className="panel">
        {screen === "prices" && <PricesPage />}
        {screen === "products" && <ProductsPage />}
        {screen === "specs" && <SpecsPage />}
        {screen === "procurement" && <ProcurementPage />}
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
        {screen === "settings" && <SettingsPage />}
      </section>
    </main>
  );
}
