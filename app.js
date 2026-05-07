const app = document.getElementById("app");

const AUTH_KEY = "callqa_auth";
const DEMO_LOGIN = "admin@company.ru";
const DEMO_PASSWORD = "demo";
const STAGES = ["greeting", "needs", "pain", "presentation", "objections", "closing"];
const STAGE_LABELS = {
  greeting: "Приветствие",
  needs: "Выявление потребностей",
  pain: "Усиление боли",
  presentation: "Презентация",
  objections: "Отработка возражений",
  closing: "Закрытие (след. шаг)"
};
const RISK_STATUS_LABELS = { new: "Новый", progress: "В работе", closed: "Закрыт" };

const state = {
  activeTab: "dashboard",
  settingsTab: "sales",
  filters: {
    period: "week",
    manager: "all",
    score: "all",
    version: "v1",
    onlyRisk: false
  },
  salesSettings: {
    goal: "Согласовать и отправить КП клиенту, договориться о предоплате.",
    products: "Организация бизнес-мероприятий, частных мероприятий, аренда площадки.",
    nextSteps: "Договориться о встрече; выслать материалы; отправить КП; договориться о предоплате.",
    riskRules: "Фиксировать риск при отсутствии конкретного CTA и согласованного следующего шага.",
    usp: "Гибкие форматы, прозрачная смета, быстрый запуск.",
    trueObjections: "Дорого; не приоритет; пока сравниваем площадки.",
    falseObjections: "Я подумаю; ничего не нужно; перезвоните позже."
  },
  criteria: {
    greeting: {
      "0-20": "Нет структуры, давление, клиент не понимает контекст.",
      "21-40": "Представился, но нет повестки звонка.",
      "41-60": "Есть контекст, но рамка разговора слабая.",
      "61-80": "Установлен контакт и алгоритм разговора.",
      "81-100": "Четкая структура, управляет темпом, вовлекает клиента."
    },
    needs: {
      "0-20": "Вопросов нет или 1-2 формальных.",
      "21-40": "Поверхностное выяснение без глубины.",
      "41-60": "Часть параметров собрана, нет резюме.",
      "61-80": "Почти полная квалификация, есть резюме.",
      "81-100": "Полная квалификация, подтверждение потребностей клиентом."
    },
    pain: {
      "0-20": "Боль не выявлена.",
      "21-40": "1 уточнение без масштаба последствий.",
      "41-60": "Последствия частично раскрыты.",
      "61-80": "Клиент признает риск/потери.",
      "81-100": "Сильная связка боли с срочностью решения."
    },
    presentation: {
      "0-20": "Нет продажной презентации.",
      "21-40": "Шаблонно, без привязки к клиенту.",
      "41-60": "Средний уровень, частичная связка с потребностями.",
      "61-80": "Четкие выгоды, уверенное знание продукта.",
      "81-100": "Индивидуальная презентация через ценность клиента."
    },
    objections: {
      "0-20": "Возражения игнорируются.",
      "21-40": "Частичная отработка без выявления причины.",
      "41-60": "Частично отрабатывает истинные возражения.",
      "61-80": "Качественно разделяет ложные/истинные возражения.",
      "81-100": "Закрывает возражения с проверкой принятия."
    },
    closing: {
      "0-20": "Звонок завершен без шага.",
      "21-40": "Шаг есть, но без сроков и ответственности.",
      "41-60": "Шаг конкретный, но без снятия стоп-факторов.",
      "61-80": "Есть резюме и договоренность по действиям/срокам.",
      "81-100": "Точное закрепление следующего шага и контроля."
    }
  },
  calls: [
    { id: "#56282", date: "2026-04-01 18:32", manager: "Воскобойникова", total: 70, greeting: 50, needs: 65, pain: 30, presentation: 70, objections: 60, closing: 80, risk: false, riskReason: "Обсуждены изменения в плане, следующий шаг зафиксирован.", riskType: "none", version: "v1" },
    { id: "#56281", date: "2026-04-01 18:31", manager: "Воскобойникова", total: 55, greeting: 75, needs: 40, pain: 20, presentation: 60, objections: 40, closing: 40, risk: true, riskReason: "Нет следующего шага и слабое закрытие сделки.", riskType: "next_step", version: "v1" },
    { id: "#56280", date: "2026-04-01 18:31", manager: "Воскобойникова", total: 65, greeting: 75, needs: 70, pain: 60, presentation: 65, objections: 60, closing: 60, risk: false, riskReason: "Обсуждены альтернативы, клиент готов к встрече.", riskType: "none", version: "v1" },
    { id: "#56278", date: "2026-04-01 18:30", manager: "Петрова", total: 65, greeting: 75, needs: 60, pain: 20, presentation: 60, objections: 60, closing: 40, risk: true, riskReason: "Клиент сомневается, следующее действие не подтверждено.", riskType: "objections", version: "v1" },
    { id: "#56277", date: "2026-04-01 18:26", manager: "Иванов", total: 45, greeting: 40, needs: 35, pain: 20, presentation: 50, objections: 35, closing: 30, risk: true, riskReason: "Итоговая оценка ниже 50, отсутствует CTA.", riskType: "low_score", version: "v1" },
    { id: "#56270", date: "2026-03-31 17:40", manager: "Иванов", total: 78, greeting: 80, needs: 75, pain: 70, presentation: 80, objections: 75, closing: 85, risk: false, riskReason: "Сильное закрытие и четкие договоренности.", riskType: "none", version: "v1" }
  ],
  risks: [
    { id: "R-101", callId: "#56281", manager: "Воскобойникова", level: "high", type: "next_step", reason: "Не согласован следующий шаг", status: "new" },
    { id: "R-102", callId: "#56278", manager: "Петрова", level: "medium", type: "objections", reason: "Некачественная отработка возражений", status: "progress" },
    { id: "R-103", callId: "#56277", manager: "Иванов", level: "high", type: "low_score", reason: "Итоговая оценка ниже порога", status: "new" }
  ],
  csvMessage: ""
};

function isAuth() {
  return localStorage.getItem(AUTH_KEY) === "1";
}

function scoreTone(score) {
  if (score < 41) return "risk";
  if (score < 61) return "warn";
  return "ok";
}

function riskTone(level) {
  if (level === "high") return "risk";
  if (level === "medium") return "warn";
  return "ok";
}

function fmt(n) {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

function toNum(value, fallback = 0) {
  const n = Number(String(value || "").trim());
  return Number.isFinite(n) ? n : fallback;
}

function deriveRisk(call) {
  const triggers = [];
  if (call.closing < 41) triggers.push("next_step");
  if (call.objections < 41) triggers.push("objections");
  if (call.total < 50) triggers.push("low_score");

  const risk = triggers.length > 0;
  const riskType = triggers[0] || "none";
  const riskReason = risk
    ? `Триггеры: ${triggers.join(", ")}`
    : "Рисков не выявлено";
  return { risk, riskType, riskReason, triggers };
}

function rebuildRisksFromCalls() {
  let idx = 1;
  state.risks = state.calls
    .filter((call) => call.risk)
    .map((call) => {
      const level = call.total < 50 || call.closing < 41 ? "high" : "medium";
      const risk = {
        id: `R-${String(100 + idx)}`,
        callId: call.id,
        manager: call.manager,
        level,
        type: call.riskType,
        reason: call.riskReason,
        status: "new"
      };
      idx += 1;
      return risk;
    });
}

function parseCsvLine(line) {
  const out = [];
  let cur = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') {
      if (quoted && line[i + 1] === '"') {
        cur += '"';
        i += 1;
      } else {
        quoted = !quoted;
      }
    } else if (ch === "," && !quoted) {
      out.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out.map((x) => x.trim());
}

function applyCsvData(csvText) {
  const rows = csvText.split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
  if (rows.length < 2) {
    throw new Error("CSV пустой или содержит только заголовок.");
  }

  const headers = parseCsvLine(rows[0]).map((h) => h.toLowerCase());
  const required = ["id", "date", "manager", "total", "greeting", "needs", "pain", "presentation", "objections", "closing"];
  const missing = required.filter((col) => !headers.includes(col));
  if (missing.length) {
    throw new Error(`В CSV не хватает колонок: ${missing.join(", ")}`);
  }

  const get = (obj, key) => obj[headers.indexOf(key)];
  const calls = [];
  for (let i = 1; i < rows.length; i += 1) {
    const cols = parseCsvLine(rows[i]);
    const raw = {};
    headers.forEach((h, idx) => { raw[h] = cols[idx] ?? ""; });
    const call = {
      id: get(cols, "id") || `#AUTO-${i}`,
      date: get(cols, "date") || "",
      manager: get(cols, "manager") || "Не указан",
      total: toNum(get(cols, "total")),
      greeting: toNum(get(cols, "greeting")),
      needs: toNum(get(cols, "needs")),
      pain: toNum(get(cols, "pain")),
      presentation: toNum(get(cols, "presentation")),
      objections: toNum(get(cols, "objections")),
      closing: toNum(get(cols, "closing")),
      version: get(cols, "version") || "v1"
    };
    const risk = deriveRisk(call);
    calls.push({ ...call, ...risk });
  }

  state.calls = calls;
  state.filters.manager = "all";
  state.filters.version = "all";
  rebuildRisksFromCalls();
  state.csvMessage = `Загружено ${calls.length} звонков из CSV`;
}

function currentCalls() {
  return state.calls.filter((c) => {
    if (state.filters.manager !== "all" && c.manager !== state.filters.manager) return false;
    if (state.filters.version !== "all" && c.version !== state.filters.version) return false;
    if (state.filters.score === "high" && c.total < 61) return false;
    if (state.filters.score === "mid" && (c.total < 41 || c.total > 60)) return false;
    if (state.filters.score === "low" && c.total > 40) return false;
    if (state.filters.onlyRisk && !c.risk) return false;
    return true;
  });
}

function dashboardMetrics() {
  const calls = currentCalls();
  const totalCalls = calls.length;
  const riskCalls = calls.filter((c) => c.risk).length;
  const avgTotal = totalCalls ? calls.reduce((s, c) => s + c.total, 0) / totalCalls : 0;
  const byStage = {};
  STAGES.forEach((stage) => {
    byStage[stage] = totalCalls ? calls.reduce((s, c) => s + c[stage], 0) / totalCalls : 0;
  });
  return { totalCalls, riskCalls, avgTotal, byStage };
}

function renderLogin() {
  app.innerHTML = `
    <main class="container">
      <section class="card login-card">
        <h1 class="title">Сайт оценки звонков</h1>
        <p class="subtitle">MVP по ТЗ: дашборд, риски, менеджеры, настройки</p>
        <form id="login-form">
          <label>Email</label>
          <input name="login" type="email" value="${DEMO_LOGIN}" required />
          <label>Пароль</label>
          <input name="password" type="password" value="${DEMO_PASSWORD}" required />
          <button class="btn" type="submit">Войти</button>
          <div id="login-error" class="error"></div>
        </form>
      </section>
    </main>
  `;
  document.getElementById("login-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    const login = String(form.get("login") || "").trim();
    const password = String(form.get("password") || "");
    if (login === DEMO_LOGIN && password === DEMO_PASSWORD) {
      localStorage.setItem(AUTH_KEY, "1");
      render();
      return;
    }
    document.getElementById("login-error").textContent = "Неверный логин или пароль.";
  });
}

function renderShell(content) {
  const managers = ["all", ...new Set(state.calls.map((c) => c.manager))];
  const versions = ["all", ...new Set(state.calls.map((c) => c.version || "v1"))];
  return `
    <main class="container">
      <header class="header card">
        <div>
          <h1 class="title">Оценка анализа звонков</h1>
          <div class="subtitle">Контроль качества работы менеджеров продаж</div>
        </div>
        <button class="btn secondary" id="logout-btn">Выйти</button>
      </header>

      <nav class="tabs">
        <button data-tab="dashboard" class="tab ${state.activeTab === "dashboard" ? "active" : ""}">Дашборд</button>
        <button data-tab="risks" class="tab ${state.activeTab === "risks" ? "active" : ""}">Риски</button>
        <button data-tab="managers" class="tab ${state.activeTab === "managers" ? "active" : ""}">Менеджеры</button>
        <button data-tab="settings" class="tab ${state.activeTab === "settings" ? "active" : ""}">Настройки</button>
      </nav>

      <section class="card filters">
        <label>Период</label>
        <select id="f-period">
          <option value="month" ${state.filters.period === "month" ? "selected" : ""}>Месяц</option>
          <option value="week" ${state.filters.period === "week" ? "selected" : ""}>Неделя</option>
          <option value="yesterday" ${state.filters.period === "yesterday" ? "selected" : ""}>Вчера</option>
          <option value="today" ${state.filters.period === "today" ? "selected" : ""}>Сегодня</option>
        </select>
        <label>Менеджер</label>
        <select id="f-manager">
          ${managers.map((m) => `<option value="${m}" ${state.filters.manager === m ? "selected" : ""}>${m === "all" ? "Все менеджеры" : m}</option>`).join("")}
        </select>
        <label>Оценка</label>
        <select id="f-score">
          <option value="all" ${state.filters.score === "all" ? "selected" : ""}>Любая оценка</option>
          <option value="high" ${state.filters.score === "high" ? "selected" : ""}>61-100</option>
          <option value="mid" ${state.filters.score === "mid" ? "selected" : ""}>41-60</option>
          <option value="low" ${state.filters.score === "low" ? "selected" : ""}>0-40</option>
        </select>
        <label>Версия продаж</label>
        <select id="f-version">
          ${versions.map((v) => `<option value="${v}" ${state.filters.version === v ? "selected" : ""}>${v === "all" ? "Любая версия" : v}</option>`).join("")}
        </select>
        <label class="checkbox-row">
          <input id="f-risk" type="checkbox" ${state.filters.onlyRisk ? "checked" : ""} />
          Показать с риском
        </label>
      </section>
      ${content}
    </main>
  `;
}

function renderDashboard() {
  const m = dashboardMetrics();
  const calls = currentCalls();
  const stageCards = STAGES.map((s) => `
    <div class="kpi ${scoreTone(m.byStage[s])}">
      <div class="kpi-title">${STAGE_LABELS[s]}</div>
      <div class="kpi-value">${fmt(m.byStage[s])}</div>
    </div>
  `).join("");

  const hourly = [{ h: "17:00", calls: 30, risk: 8 }, { h: "18:00", calls: 35, risk: 9 }, { h: "19:00", calls: 40, risk: 11 }];

  return renderShell(`
    <section class="card">
      <h3>Загрузка звонков из CSV</h3>
      <p class="muted">Колонки: id,date,manager,total,greeting,needs,pain,presentation,objections,closing,version (version необязательно)</p>
      <div class="upload-row">
        <input type="file" id="csv-file" accept=".csv,text/csv" />
        <button class="btn" id="csv-upload-btn">Загрузить CSV</button>
      </div>
      <div class="muted">${state.csvMessage}</div>
    </section>

    <section class="kpi-grid">
      <div class="kpi">
        <div class="kpi-title">Всего звонков</div>
        <div class="kpi-value">${m.totalCalls}</div>
      </div>
      <div class="kpi risk">
        <div class="kpi-title">Риски</div>
        <div class="kpi-value">${m.riskCalls}</div>
      </div>
      <div class="kpi warn">
        <div class="kpi-title">Общая оценка</div>
        <div class="kpi-value">${fmt(m.avgTotal)}</div>
      </div>
    </section>

    <section class="card">
      <h3>Качество обработки (средние показатели)</h3>
      <div class="kpi-grid">${stageCards}</div>
    </section>

    <section class="card">
      <h3>Динамика (сутки)</h3>
      ${hourly.map((item) => `
        <div class="bar-row">
          <div class="bar-label">${item.h}</div>
          <div class="bar-track"><span style="width:${item.calls * 2}%"></span></div>
          <div class="bar-meta">Звонков: ${item.calls} | Риски: ${item.risk}</div>
        </div>
      `).join("")}
    </section>

    <section class="card">
      <h3>Звонков (Продажи) (${calls.length})</h3>
      <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Дата / Менеджер</th><th>Сделка</th><th>Оценка</th><th>Привет.</th><th>Потреб.</th><th>Боль</th><th>Презент.</th><th>Возр.</th><th>Закрыт.</th><th>Результат / Риск</th>
          </tr>
        </thead>
        <tbody>
          ${calls.map((c) => `
            <tr>
              <td>${c.date}<br><span class="muted">${c.manager}</span></td>
              <td>${c.id}</td>
              <td><span class="pill ${scoreTone(c.total)}">${c.total}</span></td>
              <td>${c.greeting}</td><td>${c.needs}</td><td>${c.pain}</td><td>${c.presentation}</td><td>${c.objections}</td><td>${c.closing}</td>
              <td><span class="pill ${c.risk ? "risk" : "ok"}">${c.risk ? "Риск" : "OK"}</span><div class="muted">${c.riskReason}</div></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
      </div>
    </section>
  `);
}

function renderRisks() {
  const risks = state.risks.filter((r) => state.filters.manager === "all" || state.filters.manager === r.manager);
  return renderShell(`
    <section class="card">
      <h3>Риски (${risks.length})</h3>
      <div class="table-wrap">
      <table>
        <thead><tr><th>ID</th><th>Звонок</th><th>Менеджер</th><th>Уровень</th><th>Причина</th><th>Статус</th></tr></thead>
        <tbody>
          ${risks.map((r) => `
            <tr>
              <td>${r.id}</td>
              <td>${r.callId}</td>
              <td>${r.manager}</td>
              <td><span class="pill ${riskTone(r.level)}">${r.level}</span></td>
              <td>${r.reason}</td>
              <td>
                <select class="risk-status" data-risk-id="${r.id}">
                  <option value="new" ${r.status === "new" ? "selected" : ""}>${RISK_STATUS_LABELS.new}</option>
                  <option value="progress" ${r.status === "progress" ? "selected" : ""}>${RISK_STATUS_LABELS.progress}</option>
                  <option value="closed" ${r.status === "closed" ? "selected" : ""}>${RISK_STATUS_LABELS.closed}</option>
                </select>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
      </div>
    </section>
  `);
}

function renderManagers() {
  const calls = currentCalls();
  const grouped = {};
  calls.forEach((c) => {
    if (!grouped[c.manager]) grouped[c.manager] = [];
    grouped[c.manager].push(c);
  });
  const rows = Object.entries(grouped).map(([manager, items]) => {
    const total = items.length;
    const avg = items.reduce((s, c) => s + c.total, 0) / total;
    const riskPct = (items.filter((i) => i.risk).length / total) * 100;
    const weakStage = STAGES.map((s) => ({ s, val: items.reduce((sum, x) => sum + x[s], 0) / total })).sort((a, b) => a.val - b.val)[0];
    return { manager, total, avg, riskPct, weakStage: STAGE_LABELS[weakStage.s] };
  }).sort((a, b) => b.avg - a.avg);

  return renderShell(`
    <section class="card">
      <h3>Рейтинг менеджеров</h3>
      <div class="table-wrap">
      <table>
        <thead><tr><th>Менеджер</th><th>Звонков</th><th>Средняя оценка</th><th>% с риском</th><th>Зона роста</th></tr></thead>
        <tbody>
          ${rows.map((r) => `
            <tr>
              <td>${r.manager}</td>
              <td>${r.total}</td>
              <td><span class="pill ${scoreTone(r.avg)}">${fmt(r.avg)}</span></td>
              <td>${fmt(r.riskPct)}%</td>
              <td>${r.weakStage}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
      </div>
    </section>
  `);
}

function renderSettings() {
  const tabs = [
    { key: "quick", label: "Быстрая настройка" },
    { key: "base", label: "Основные" },
    { key: "qualification", label: "Квалификация" },
    { key: "sales", label: "Продажи" }
  ];

  const salesForm = `
    <div class="card">
      <h3>Настройки продаж</h3>
      <label>Какую главную цель должен выполнить менеджер на этапе продаж?</label>
      <textarea id="set-goal">${state.salesSettings.goal}</textarea>
      <label>Товары и услуги компании</label>
      <textarea id="set-products">${state.salesSettings.products}</textarea>
      <label>Все корректные следующие шаги успешного звонка</label>
      <textarea id="set-next">${state.salesSettings.nextSteps}</textarea>
      <label>При каких нарушениях фиксировать риск срыва сделки?</label>
      <textarea id="set-risk">${state.salesSettings.riskRules}</textarea>
      <h4>Дополнительные параметры</h4>
      <label>УТП компании</label>
      <textarea id="set-usp">${state.salesSettings.usp}</textarea>
      <label>Истинные возражения</label>
      <textarea id="set-true">${state.salesSettings.trueObjections}</textarea>
      <label>Ложные возражения</label>
      <textarea id="set-false">${state.salesSettings.falseObjections}</textarea>
    </div>
  `;

  const criteriaBlocks = STAGES.map((stage) => `
    <div class="card">
      <h3>${STAGE_LABELS[stage]}</h3>
      ${Object.entries(state.criteria[stage]).map(([range, text]) => `
        <div class="criteria-line">
          <div class="criteria-range">${range}</div>
          <textarea data-stage="${stage}" data-range="${range}" class="criteria-input">${text}</textarea>
        </div>
      `).join("")}
    </div>
  `).join("");

  return renderShell(`
    <section class="card settings-tabs">
      ${tabs.map((tab) => `<button data-settings-tab="${tab.key}" class="tab ${state.settingsTab === tab.key ? "active" : ""}">${tab.label}</button>`).join("")}
    </section>
    ${salesForm}
    <section class="card">
      <h3>Критерии оценки этапов</h3>
      <p class="muted">Диапазоны: 0-20, 21-40, 41-60, 61-80, 81-100</p>
    </section>
    ${criteriaBlocks}
    <section class="card">
      <button class="btn" id="save-settings">Сохранить</button>
      <span id="save-msg" class="muted"></span>
    </section>
  `);
}

function bindCommonEvents() {
  document.getElementById("logout-btn").addEventListener("click", () => {
    localStorage.removeItem(AUTH_KEY);
    render();
  });

  document.querySelectorAll(".tab[data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.activeTab = btn.dataset.tab;
      render();
    });
  });

  const bindFilter = (id, key, transform = (v) => v) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("change", () => {
      state.filters[key] = transform(el.type === "checkbox" ? el.checked : el.value);
      render();
    });
  };
  bindFilter("f-period", "period");
  bindFilter("f-manager", "manager");
  bindFilter("f-score", "score");
  bindFilter("f-version", "version");
  bindFilter("f-risk", "onlyRisk");
}

function bindScreenEvents() {
  if (state.activeTab === "dashboard") {
    const uploadBtn = document.getElementById("csv-upload-btn");
    if (uploadBtn) {
      uploadBtn.addEventListener("click", () => {
        const input = document.getElementById("csv-file");
        if (!input || !input.files || !input.files[0]) {
          state.csvMessage = "Выберите CSV-файл перед загрузкой.";
          render();
          return;
        }
        const file = input.files[0];
        const reader = new FileReader();
        reader.onload = () => {
          try {
            applyCsvData(String(reader.result || ""));
          } catch (err) {
            state.csvMessage = err instanceof Error ? err.message : "Ошибка при обработке CSV.";
          }
          render();
        };
        reader.onerror = () => {
          state.csvMessage = "Не удалось прочитать CSV-файл.";
          render();
        };
        reader.readAsText(file, "utf-8");
      });
    }
  }

  if (state.activeTab === "risks") {
    document.querySelectorAll(".risk-status").forEach((select) => {
      select.addEventListener("change", () => {
        const risk = state.risks.find((r) => r.id === select.dataset.riskId);
        if (risk) risk.status = select.value;
      });
    });
  }

  if (state.activeTab === "settings") {
    document.querySelectorAll("[data-settings-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.settingsTab = btn.dataset.settingsTab;
        render();
      });
    });

    const saveBtn = document.getElementById("save-settings");
    if (!saveBtn) return;
    saveBtn.addEventListener("click", () => {
      state.salesSettings.goal = document.getElementById("set-goal").value.trim();
      state.salesSettings.products = document.getElementById("set-products").value.trim();
      state.salesSettings.nextSteps = document.getElementById("set-next").value.trim();
      state.salesSettings.riskRules = document.getElementById("set-risk").value.trim();
      state.salesSettings.usp = document.getElementById("set-usp").value.trim();
      state.salesSettings.trueObjections = document.getElementById("set-true").value.trim();
      state.salesSettings.falseObjections = document.getElementById("set-false").value.trim();

      document.querySelectorAll(".criteria-input").forEach((el) => {
        const stage = el.dataset.stage;
        const range = el.dataset.range;
        state.criteria[stage][range] = el.value.trim();
      });

      document.getElementById("save-msg").textContent = "Сохранено";
      setTimeout(() => {
        const msg = document.getElementById("save-msg");
        if (msg) msg.textContent = "";
      }, 1200);
    });
  }
}

function render() {
  if (!isAuth()) {
    renderLogin();
    return;
  }
  if (state.activeTab === "dashboard") app.innerHTML = renderDashboard();
  if (state.activeTab === "risks") app.innerHTML = renderRisks();
  if (state.activeTab === "managers") app.innerHTML = renderManagers();
  if (state.activeTab === "settings") app.innerHTML = renderSettings();

  bindCommonEvents();
  bindScreenEvents();
}

render();
