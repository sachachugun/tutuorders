export type AppScreen =
  | "procurement"
  | "products"
  | "specs"
  | "prices"
  | "settings"
  | "order"
  | "result";

type NavItem = { id: AppScreen; label: string };

const REFERENCE_ITEMS: NavItem[] = [
  { id: "products", label: "Словарь" },
  { id: "specs", label: "Спецификации" },
];

const CONFIG_ITEMS: NavItem[] = [
  { id: "prices", label: "Прайсы" },
  { id: "settings", label: "Настройки" },
];

const QUICK_ORDER_ITEMS: NavItem[] = [
  { id: "order", label: "Заказ" },
  { id: "result", label: "Результат" },
];

function NavTabs({
  items,
  screen,
  onSelect,
  subdued,
}: {
  items: NavItem[];
  screen: AppScreen;
  onSelect: (id: AppScreen) => void;
  subdued?: boolean;
}) {
  return (
    <div className={`nav-tabs${subdued ? " nav-tabs-subdued" : ""}`}>
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          className={screen === item.id ? "tab active" : "tab"}
          onClick={() => onSelect(item.id)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

export function AppNav({ screen, onSelect }: { screen: AppScreen; onSelect: (id: AppScreen) => void }) {
  return (
    <nav className="app-nav" aria-label="Основная навигация">
      <div className="nav-group nav-group-work">
        <span className="nav-group-label">работа</span>
        <button
          type="button"
          className={screen === "procurement" ? "tab tab-primary active" : "tab tab-primary"}
          onClick={() => onSelect("procurement")}
        >
          План закупки
        </button>
      </div>

      <div className="nav-separator" aria-hidden />

      <div className="nav-group nav-group-ref">
        <span className="nav-group-label">справочники</span>
        <NavTabs items={REFERENCE_ITEMS} screen={screen} onSelect={onSelect} />
      </div>

      <div className="nav-separator" aria-hidden />

      <div className="nav-group nav-group-config">
        <span className="nav-group-label">конфигурация</span>
        <NavTabs items={CONFIG_ITEMS} screen={screen} onSelect={onSelect} />
      </div>

      <div className="nav-separator nav-separator-quick" aria-hidden />

      <div className="nav-group nav-group-quick">
        <span className="nav-group-label">быстрый заказ</span>
        <NavTabs items={QUICK_ORDER_ITEMS} screen={screen} onSelect={onSelect} subdued />
      </div>
    </nav>
  );
}
