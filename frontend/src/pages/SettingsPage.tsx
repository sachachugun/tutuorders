import { useEffect, useState } from "react";
import {
  createLocation,
  deleteLocation,
  getDepartments,
  getLocations,
  updateLocation,
} from "../api";

type LocationRow = {
  id: number;
  code: string;
  name: string;
  sort_order: number;
  is_active: boolean;
};

type LocationDraft = {
  code: string;
  name: string;
  sort_order: string;
  is_active: boolean;
};

type DepartmentRow = {
  id: number;
  code: string;
  name: string;
};

const emptyDraft = (): LocationDraft => ({
  code: "",
  name: "",
  sort_order: "0",
  is_active: true,
});

export function SettingsPage() {
  const [locations, setLocations] = useState<LocationRow[]>([]);
  const [departments, setDepartments] = useState<DepartmentRow[]>([]);
  const [drafts, setDrafts] = useState<Record<number, LocationDraft>>({});
  const [newDraft, setNewDraft] = useState<LocationDraft>(emptyDraft);
  const [message, setMessage] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  const loadData = () => {
    Promise.all([getLocations(), getDepartments()])
      .then(([locationsData, departmentsData]) => {
        const items: LocationRow[] = locationsData.items || [];
        setLocations(items);
        setDepartments(departmentsData.items || []);
        const nextDrafts: Record<number, LocationDraft> = {};
        for (const row of items) {
          nextDrafts[row.id] = {
            code: row.code,
            name: row.name,
            sort_order: String(row.sort_order),
            is_active: row.is_active,
          };
        }
        setDrafts(nextDrafts);
      })
      .catch(() => {
        setLocations([]);
        setDepartments([]);
      });
  };

  useEffect(() => {
    loadData();
  }, []);

  const onCreate = async () => {
    const code = newDraft.code.trim();
    const name = newDraft.name.trim();
    if (!code || !name) {
      setMessage("Укажите код и название локации");
      return;
    }
    setMessage("");
    setIsCreating(true);
    try {
      await createLocation({
        code,
        name,
        sort_order: Number(newDraft.sort_order) || 0,
        is_active: newDraft.is_active,
      });
      setNewDraft(emptyDraft());
      setMessage(`Локация «${name}» добавлена`);
      loadData();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось добавить локацию");
    } finally {
      setIsCreating(false);
    }
  };

  const onSave = async (locationId: number) => {
    const draft = drafts[locationId];
    if (!draft) return;
    setMessage("");
    try {
      await updateLocation(locationId, {
        code: draft.code.trim(),
        name: draft.name.trim(),
        sort_order: Number(draft.sort_order) || 0,
        is_active: draft.is_active,
      });
      setMessage("Локация сохранена");
      loadData();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось сохранить локацию");
    }
  };

  const onDelete = async (locationId: number, name: string) => {
    if (!window.confirm(`Удалить локацию «${name}»?`)) return;
    setMessage("");
    try {
      await deleteLocation(locationId);
      setMessage(`Локация «${name}» удалена`);
      loadData();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось удалить локацию");
    }
  };

  return (
    <section className="page-stack">
      <h2 className="section-title">Настройки</h2>
      {message && <p className="status-message">{message}</p>}

      <article className="card">
        <h3 className="card-title">Отделы (кухня / бар)</h3>
        <p className="muted">Справочник фиксированный — используется в плане закупки.</p>
        <table className="data-table">
          <thead>
            <tr>
              <th>Код</th>
              <th>Название</th>
            </tr>
          </thead>
          <tbody>
            {departments.map((d) => (
              <tr key={d.id}>
                <td>{d.code}</td>
                <td>{d.name}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </article>

      <article className="card add-supplier-card">
        <h3 className="card-title">Новая локация</h3>
        <div className="add-supplier-row">
          <label className="field">
            <span>Код</span>
            <input
              value={newDraft.code}
              onChange={(e) => setNewDraft((prev) => ({ ...prev, code: e.target.value }))}
              placeholder="loc_5"
              disabled={isCreating}
            />
          </label>
          <label className="field">
            <span>Название</span>
            <input
              value={newDraft.name}
              onChange={(e) => setNewDraft((prev) => ({ ...prev, name: e.target.value }))}
              placeholder="Ресторан на Невском"
              disabled={isCreating}
            />
          </label>
          <label className="field">
            <span>Порядок</span>
            <input
              type="number"
              value={newDraft.sort_order}
              onChange={(e) => setNewDraft((prev) => ({ ...prev, sort_order: e.target.value }))}
              disabled={isCreating}
            />
          </label>
          <label className="field checkbox-field">
            <span>Активна</span>
            <input
              type="checkbox"
              checked={newDraft.is_active}
              onChange={(e) => setNewDraft((prev) => ({ ...prev, is_active: e.target.checked }))}
              disabled={isCreating}
            />
          </label>
          <button type="button" className="btn btn-primary" onClick={() => void onCreate()} disabled={isCreating}>
            {isCreating ? "Добавление..." : "Добавить локацию"}
          </button>
        </div>
      </article>

      <div className="cards">
        {locations.map((row) => (
          <article className="card" key={row.id}>
            <h3 className="card-title">
              {row.name} <span className="muted-inline">#{row.id}</span>
            </h3>
            <label className="field">
              <span>Код</span>
              <input
                value={drafts[row.id]?.code ?? row.code}
                onChange={(e) =>
                  setDrafts((prev) => ({
                    ...prev,
                    [row.id]: { ...(prev[row.id] || emptyDraft()), code: e.target.value },
                  }))
                }
              />
            </label>
            <label className="field">
              <span>Название</span>
              <input
                value={drafts[row.id]?.name ?? row.name}
                onChange={(e) =>
                  setDrafts((prev) => ({
                    ...prev,
                    [row.id]: { ...(prev[row.id] || emptyDraft()), name: e.target.value },
                  }))
                }
              />
            </label>
            <label className="field">
              <span>Порядок сортировки</span>
              <input
                type="number"
                value={drafts[row.id]?.sort_order ?? String(row.sort_order)}
                onChange={(e) =>
                  setDrafts((prev) => ({
                    ...prev,
                    [row.id]: { ...(prev[row.id] || emptyDraft()), sort_order: e.target.value },
                  }))
                }
              />
            </label>
            <label className="field checkbox-field">
              <span>Активна</span>
              <input
                type="checkbox"
                checked={drafts[row.id]?.is_active ?? row.is_active}
                onChange={(e) =>
                  setDrafts((prev) => ({
                    ...prev,
                    [row.id]: { ...(prev[row.id] || emptyDraft()), is_active: e.target.checked },
                  }))
                }
              />
            </label>
            <div className="actions-row">
              <button type="button" className="btn btn-primary" onClick={() => void onSave(row.id)}>
                Сохранить
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => void onDelete(row.id, row.name)}>
                Удалить
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
