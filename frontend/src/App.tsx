import { useEffect, useState } from "react";
import { authMe, clearAuthToken, login } from "./api";
import { PricesPage } from "./pages/PricesPage";
import { OrderPage } from "./pages/OrderPage";
import { ResultPage } from "./pages/ResultPage";

type Screen = "prices" | "order" | "result";

export function App() {
  const isLocalDev = typeof window !== "undefined" && ["localhost", "127.0.0.1"].includes(window.location.hostname);
  const [screen, setScreen] = useState<Screen>("prices");
  const [matchResult, setMatchResult] = useState<any>(null);
  const [authLoading, setAuthLoading] = useState(!isLocalDev);
  const [isAuthenticated, setIsAuthenticated] = useState(isLocalDev);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [authError, setAuthError] = useState("");

  useEffect(() => {
    if (isLocalDev) return;
    authMe()
      .then(() => setIsAuthenticated(true))
      .catch(() => {
        clearAuthToken();
        setIsAuthenticated(false);
      })
      .finally(() => setAuthLoading(false));
  }, [isLocalDev]);

  const onLogin = async () => {
    setAuthError("");
    try {
      await login(username.trim(), password);
      setIsAuthenticated(true);
      setPassword("");
    } catch (e) {
      setAuthError(e instanceof Error ? e.message : "Не удалось выполнить вход");
    }
  };

  const onLogout = () => {
    if (isLocalDev) return;
    clearAuthToken();
    setIsAuthenticated(false);
    setScreen("prices");
    setMatchResult(null);
  };

  if (authLoading) {
    return (
      <main className="container">
        <section className="panel">
          <p className="muted">Проверка доступа...</p>
        </section>
      </main>
    );
  }

  if (!isAuthenticated) {
    return (
      <main className="container">
        <section className="panel auth-card">
          <h2 className="section-title">Вход в tutuorders</h2>
          <label className="field">
            Логин
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
          </label>
          <label className="field">
            Пароль
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>
          <button className="btn btn-primary" onClick={onLogin}>Войти</button>
          {authError && <p className="error">{authError}</p>}
        </section>
      </main>
    );
  }

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
          {!isLocalDev && <button className="tab" onClick={onLogout}>Выйти</button>}
        </nav>
      </header>

      <section className="panel">
        {screen === "prices" && <PricesPage />}
        {screen === "order" && <OrderPage onMatched={(result) => {
          setMatchResult(result);
          setScreen("result");
        }} />}
        {screen === "result" && <ResultPage result={matchResult} />}
      </section>
    </main>
  );
}
