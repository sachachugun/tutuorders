import { useEffect, useMemo, useState } from "react";
import {
  addProductFromDemandGap,
  assignDemandLineProduct,
  buildProcurementOrders,
  createProcurementBatch,
  downloadProcurementExport,
  downloadProcurementSummaryExport,
  getDepartments,
  getLocations,
  getProcurementBatch,
  getProcurementBatches,
  getProcurementAllocations,
  getProcurementMatch,
  getProcurementOrders,
  getProcurementSummary,
  getProducts,
  listBatchDemand,
  optimizeProcurementBatch,
  overrideProductSupplier,
  parseProcurementBatch,
  runProcurementMatch,
  saveBatchDemand,
  updateSupplierOrderComment,
} from "../api";
import { AddProductModal } from "../components/AddProductModal";

type WizardStep = "demand" | "match" | "optimize" | "orders" | "summary";

function optimizerModeLabel(mode: string) {
  if (mode === "milp") return "MILP";
  if (mode === "greedy_fallback") return "Запасной (мин. цена)";
  return mode;
}

function slotKey(locationId: number, departmentId: number) {
  return `${locationId}-${departmentId}`;
}

function defaultPlanLabel() {
  return `Заказ ${new Date().toLocaleDateString("ru-RU")}`;
}

function matchReadyForAllocation(status: string) {
  return status === "ok" || status === "partial_sku";
}

function matchStatusLabel(status: string) {
  if (status === "ok") return "OK";
  if (status === "partial_sku") return "Частично";
  if (status === "needs_product") return "Нужен продукт";
  if (status === "needs_sku") return "Нет SKU";
  return "Не разобрано";
}

function matchStatusBadgeClass(status: string) {
  if (status === "ok") return "ok";
  if (status === "partial_sku") return "info";
  return "degraded";
}

export function ProcurementPage() {
  const [wizardStep, setWizardStep] = useState<WizardStep>("demand");
  const [batches, setBatches] = useState<any[]>([]);
  const [batchId, setBatchId] = useState<number | null>(null);
  const [batchSummary, setBatchSummary] = useState<any | null>(null);
  const [locations, setLocations] = useState<any[]>([]);
  const [departments, setDepartments] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [locationId, setLocationId] = useState<number | null>(null);
  const [departmentId, setDepartmentId] = useState<number | null>(null);
  const [demandTexts, setDemandTexts] = useState<Record<string, string>>({});
  const [demandLines, setDemandLines] = useState<any[]>([]);
  const [matchState, setMatchState] = useState<any | null>(null);
  const [onlyProblems, setOnlyProblems] = useState(false);
  const [message, setMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isParsing, setIsParsing] = useState(false);
  const [isMatching, setIsMatching] = useState(false);
  const [addProductGap, setAddProductGap] = useState<{
    demand_name: string;
    default_unit: string;
    line_count: number;
  } | null>(null);
  const [allocState, setAllocState] = useState<any | null>(null);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [ordersState, setOrdersState] = useState<any | null>(null);
  const [filterSupplierId, setFilterSupplierId] = useState<number | null>(null);
  const [filterLocationId, setFilterLocationId] = useState<number | null>(null);
  const [filterDepartmentId, setFilterDepartmentId] = useState<number | null>(null);
  const [editingCommentLineId, setEditingCommentLineId] = useState<number | null>(null);
  const [commentDraft, setCommentDraft] = useState("");
  const [isBuildingOrders, setIsBuildingOrders] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [copiedSupplierId, setCopiedSupplierId] = useState<number | null>(null);
  const [summaryState, setSummaryState] = useState<any | null>(null);
  const [summaryLocationId, setSummaryLocationId] = useState<number | null>(null);
  const [summaryDepartmentId, setSummaryDepartmentId] = useState<number | null>(null);
  const [showNewBatchModal, setShowNewBatchModal] = useState(false);
  const [newBatchPlanLabel, setNewBatchPlanLabel] = useState(defaultPlanLabel);
  const [newBatchResponsible, setNewBatchResponsible] = useState<"Женя" | "Андрей" | null>(null);
  const [isCreatingBatch, setIsCreatingBatch] = useState(false);
  const [isSummaryExporting, setIsSummaryExporting] = useState(false);

  const activeLocations = useMemo(() => locations.filter((l) => l.is_active), [locations]);

  const filledSlots = useMemo(() => {
    const keys = new Set<string>();
    for (const line of demandLines) {
      keys.add(slotKey(line.location_id, line.department_id));
    }
    return keys.size;
  }, [demandLines]);

  const totalSlots = (activeLocations.length || 0) * (departments.length || 0);

  const visibleMatchRows = useMemo(() => {
    const rows = matchState?.items || [];
    if (!onlyProblems) return rows;
    return rows.filter((row: any) => !matchReadyForAllocation(row.match_status));
  }, [matchState, onlyProblems]);

  const loadBatches = () => {
    getProcurementBatches()
      .then((data) => {
        const items = data.items || [];
        setBatches(items);
        if (!batchId && items.length) {
          setBatchId(items[0].id);
        }
      })
      .catch((e) => {
        setBatches([]);
        setBatchId(null);
        setMessage(e instanceof Error ? e.message : "Не удалось загрузить планы закупки");
      });
  };

  const loadRefs = () => {
    Promise.all([getLocations(), getDepartments(), getProducts()])
      .then(([locData, depData, productsData]) => {
        const locs = (locData.items || []).filter((l: any) => l.is_active);
        const deps = depData.items || [];
        setLocations(locs);
        setDepartments(deps);
        setProducts((productsData.items || []).filter((p: any) => p.is_active));
        if (!locationId && locs.length) setLocationId(locs[0].id);
        if (!departmentId && deps.length) setDepartmentId(deps[0].id);
      })
      .catch((e) => {
        setLocations([]);
        setDepartments([]);
        setProducts([]);
        const err = e instanceof Error ? e.message : "Не удалось загрузить справочники";
        setMessage((prev) => (prev ? `${prev}. ${err}` : err));
      });
  };

  const loadBatchData = (id: number) => {
    Promise.all([getProcurementBatch(id), listBatchDemand(id)])
      .then(([summary, demand]) => {
        setBatchSummary(summary);
        const lines = demand.items || [];
        setDemandLines(lines);
        const texts: Record<string, string> = {};
        for (const loc of activeLocations.length ? activeLocations : locations) {
          for (const dep of departments) {
            const key = slotKey(loc.id, dep.id);
            const slotLines = lines.filter(
              (row: any) => row.location_id === loc.id && row.department_id === dep.id
            );
            texts[key] = slotLines.map((row: any) => row.raw_text).join("\n");
          }
        }
        setDemandTexts(texts);
      })
      .catch(() => {
        setBatchSummary(null);
        setDemandLines([]);
      });
  };

  const loadMatchData = (id: number) => {
    getProcurementMatch(id)
      .then((data) => setMatchState(data))
      .catch(() => setMatchState(null));
  };

  const loadAllocData = (id: number) => {
    getProcurementAllocations(id)
      .then((data) => setAllocState(data))
      .catch(() => setAllocState(null));
  };

  const applyOrderFilters = (data: any) => {
    setOrdersState(data);
    const firstGroup = data.groups?.[0];
    if (firstGroup) {
      setFilterSupplierId(firstGroup.supplier_id);
      setFilterLocationId(firstGroup.location_id);
      setFilterDepartmentId(firstGroup.department_id);
    } else {
      setFilterSupplierId(null);
      setFilterLocationId(null);
      setFilterDepartmentId(null);
    }
  };

  const loadOrdersData = (id: number) => {
    getProcurementOrders(id)
      .then((data) => applyOrderFilters(data))
      .catch(() => setOrdersState(null));
  };

  const activeOrderGroup = useMemo(() => {
    if (!ordersState?.groups?.length) return null;
    return (
      ordersState.groups.find(
        (g: any) =>
          g.supplier_id === filterSupplierId &&
          g.location_id === filterLocationId &&
          g.department_id === filterDepartmentId
      ) || null
    );
  }, [ordersState, filterSupplierId, filterLocationId, filterDepartmentId]);

  const activeOrderLines = activeOrderGroup?.lines || [];

  const supplierMessages = useMemo(() => {
    if (!ordersState?.groups?.length) return [];

    const cleanOneLine = (s: unknown) =>
      String(s || "")
        .replace(/\r?\n/g, " ")
        .replace(/\s+/g, " ")
        .trim();

    const formatQty = (q: unknown) => {
      const n = Number(q || 0);
      // до 3 знаков после запятой, без лишних нулей
      return String(n.toFixed(3)).replace(/\.?0+$/, "");
    };

    const groups = ordersState.groups as any[];
    const suppliers = ordersState.suppliers as any[];
    const groupsBySupplier: Record<number, any[]> = {};
    for (const g of groups) {
      if (!groupsBySupplier[g.supplier_id]) groupsBySupplier[g.supplier_id] = [];
      groupsBySupplier[g.supplier_id].push(g);
    }

    const result = (suppliers.length ? suppliers : Object.keys(groupsBySupplier).map((k) => ({ id: Number(k), name: `S${k}` }))).map(
      (s: any) => {
        const sGroups = groupsBySupplier[s.id] || [];
        sGroups.sort((a: any, b: any) => {
          const d1 = (a.location_name || "").localeCompare(b.location_name || "");
          if (d1 !== 0) return d1;
          return (a.department_name || "").localeCompare(b.department_name || "");
        });

        const parts: string[] = [];
        parts.push(`Поставщик: ${s.name}`);
        for (const g of sGroups) {
          parts.push(`${g.location_name} + ${g.department_name}`);
          for (const ln of g.lines || []) {
            const qtyText = `${formatQty(ln.quantity)} ${ln.unit}`;
            const specText = cleanOneLine(ln.spec_text);
            if (specText) {
              parts.push(`${ln.supplier_product_name}, ${qtyText}, ${specText}`);
            } else {
              // fallback: если spec_text пустой, используем line_comment (внутри него обычно тоже есть spec)
              const commentText = cleanOneLine(ln.line_comment);
              parts.push(commentText ? `${ln.supplier_product_name}, ${qtyText}, ${commentText}` : `${ln.supplier_product_name}, ${qtyText}`);
            }
          }
          parts.push("");
        }
        return { supplierId: s.id as number, supplierName: s.name as string, text: parts.join("\n").trimEnd() };
      }
    );

    // отфильтровать пустые
    return result.filter((m: any) => m.text && m.text.trim());
  }, [ordersState]);

  const onCopySupplierMessage = async (supplierId: number, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedSupplierId(supplierId);
      window.setTimeout(() => setCopiedSupplierId(null), 1200);
    } catch {
      // fallback: просто выделить через prompt
      window.prompt("Скопируйте текст вручную:", text);
    }
  };

  const summarySupplierIds = useMemo(
    () => (summaryState?.supplier_ids || []).slice().sort((a: number, b: number) => a - b),
    [summaryState]
  );

  const summarySupplierNames = useMemo(() => {
    const map: Record<number, string> = {};
    for (const s of summaryState?.suppliers || []) {
      map[s.id] = s.name;
    }
    return map;
  }, [summaryState]);

  const summarySupplierTotals = useMemo(() => {
    const totals: Record<number, number> = {};
    for (const item of summaryState?.items || []) {
      for (const alloc of item.allocation || []) {
        totals[alloc.supplier_id] = Number(
          ((totals[alloc.supplier_id] || 0) + Number(alloc.amount || 0)).toFixed(2)
        );
      }
    }
    return totals;
  }, [summaryState]);

  const loadSummaryData = (id: number, locId: number | null, depId: number | null) => {
    getProcurementSummary(id, {
      location_id: locId || undefined,
      department_id: depId || undefined,
    })
      .then((data) => setSummaryState(data))
      .catch(() => setSummaryState(null));
  };

  useEffect(() => {
    loadBatches();
    loadRefs();
  }, []);

  useEffect(() => {
    if (batchId) {
      loadBatchData(batchId);
      if (wizardStep === "match") loadMatchData(batchId);
      if (wizardStep === "optimize") loadAllocData(batchId);
      if (wizardStep === "orders") loadOrdersData(batchId);
      if (wizardStep === "summary") loadSummaryData(batchId, summaryLocationId, summaryDepartmentId);
    }
  }, [batchId, locations.length, departments.length, wizardStep, summaryLocationId, summaryDepartmentId]);

  const currentText =
    locationId && departmentId ? demandTexts[slotKey(locationId, departmentId)] || "" : "";

  const openNewBatchModal = () => {
    setNewBatchPlanLabel(defaultPlanLabel());
    setNewBatchResponsible(null);
    setShowNewBatchModal(true);
  };

  const onCreateBatch = async () => {
    const plan_label = newBatchPlanLabel.trim();
    if (!plan_label) {
      setMessage("Укажите название плана");
      return;
    }
    setMessage("");
    setIsCreatingBatch(true);
    try {
      const batch = await createProcurementBatch({
        plan_label,
        responsible: newBatchResponsible,
      });
      setBatchId(batch.id);
      setWizardStep("demand");
      setShowNewBatchModal(false);
      setMessage(`Создан план «${batch.title}»`);
      loadBatches();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось создать план");
    } finally {
      setIsCreatingBatch(false);
    }
  };

  const onSaveSlot = async () => {
    if (!batchId || !locationId || !departmentId) return;
    const text = currentText.trim();
    if (!text) {
      setMessage("Введите список для этой локации и отдела");
      return;
    }
    setMessage("");
    setIsSaving(true);
    try {
      const result = await saveBatchDemand(batchId, {
        location_id: locationId,
        department_id: departmentId,
        order_text: text,
      });
      setMessage(
        `Сохранено: ${result.saved_lines} строк (разобрано ${result.parsed_count}, не разобрано ${result.unparsed_count})`
      );
      loadBatchData(batchId);
      loadBatches();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось сохранить спрос");
    } finally {
      setIsSaving(false);
    }
  };

  const onParseBatch = async () => {
    if (!batchId) return;
    setMessage("");
    setIsParsing(true);
    try {
      const result = await parseProcurementBatch(batchId);
      setMessage(
        `Переразбор: OK ${result.ok_count}, без продукта ${result.needs_product_count}, не разобрано ${result.unparsed_count}`
      );
      loadBatchData(batchId);
      loadBatches();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось разобрать план");
    } finally {
      setIsParsing(false);
    }
  };

  const onRunMatch = async () => {
    if (!batchId) return;
    setMessage("");
    setIsMatching(true);
    try {
      const result = await runProcurementMatch(batchId);
      setMatchState(result);
      const aiPart =
        result.ai_assigned_count > 0
          ? `, с ИИ: ${result.ai_assigned_count}`
          : result.ai_available
            ? ""
            : " (ИИ не настроен — только локальная проверка)";
      setMessage(
        `Проверка (${result.match_mode || "local"}): готово ${result.ok_count}, частично SKU ${result.partial_sku_count ?? 0}, без продукта ${result.needs_product_count}, без SKU ${result.needs_sku_count}, не разобрано ${result.unparsed_count}${aiPart}`
      );
      loadBatches();
      if (batchId) {
        const summary = await getProcurementBatch(batchId);
        setBatchSummary(summary);
      }
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось выполнить проверку");
    } finally {
      setIsMatching(false);
    }
  };

  const onGoToMatch = () => {
    if (!batchId || !demandLines.length) {
      setMessage("Сначала сохраните спрос хотя бы для одного блока");
      return;
    }
    setWizardStep("match");
    loadMatchData(batchId);
  };

  const reloadProducts = () => {
    getProducts()
      .then((data) => setProducts((data.items || []).filter((p: any) => p.is_active)))
      .catch(() => setProducts([]));
  };

  const onAssignProduct = async (lineId: number, productId: number) => {
    if (!batchId || !productId) return;
    setMessage("");
    try {
      await assignDemandLineProduct(batchId, lineId, { canonical_product_id: productId });
      loadMatchData(batchId);
      loadBatchData(batchId);
      loadBatches();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось назначить продукт");
    }
  };

  const onSaveNewDictionaryProduct = async (payload: {
    demand_name: string;
    default_unit: string;
    sku_links: { supplier_id: number; name_in_price: string }[];
  }) => {
    if (!batchId) return;
    setMessage("");
    try {
      const result = await addProductFromDemandGap(batchId, payload);
      setMatchState(result.match);
      setAddProductGap(null);
      setMessage(
        `«${result.product_name}» добавлен · строк плана: ${result.assigned_lines}, SKU: ${result.skus_created || 0}`
      );
      reloadProducts();
      loadBatchData(batchId);
      loadBatches();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось добавить в словарь");
      throw e;
    }
  };

  const onBuildOrders = async () => {
    if (!batchId) return;
    setMessage("");
    setIsBuildingOrders(true);
    try {
      const data = await buildProcurementOrders(batchId);
      applyOrderFilters(data);
      setMessage(`Собрано заказов: ${data.lines_count} строк в ${data.groups_count} листах`);
      loadBatches();
      const summary = await getProcurementBatch(batchId);
      setBatchSummary(summary);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось собрать заказы");
    } finally {
      setIsBuildingOrders(false);
    }
  };

  const onDownloadSummaryExport = async () => {
    if (!batchId) return;
    setIsSummaryExporting(true);
    try {
      const blob = await downloadProcurementSummaryExport(batchId, {
        location_id: summaryLocationId || undefined,
        department_id: summaryDepartmentId || undefined,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `svodka_${batchId}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      setMessage("Сводный xlsx скачан");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось скачать сводку");
    } finally {
      setIsSummaryExporting(false);
    }
  };

  const onDownloadExport = async () => {
    if (!batchId) return;
    setMessage("");
    setIsExporting(true);
    try {
      const blob = await downloadProcurementExport(batchId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `zakupka_${batchId}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      setMessage("Файл xlsx скачан");
      loadBatches();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось скачать xlsx");
    } finally {
      setIsExporting(false);
    }
  };

  const onSaveComment = async (lineId: number) => {
    if (!batchId) return;
    try {
      await updateSupplierOrderComment(batchId, lineId, { line_comment: commentDraft });
      setEditingCommentLineId(null);
      loadOrdersData(batchId);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось сохранить комментарий");
    }
  };

  const onOptimize = async () => {
    if (!batchId) return;
    setMessage("");
    setIsOptimizing(true);
    try {
      const result = await optimizeProcurementBatch(batchId);
      setAllocState(result);
      setMessage(
        `Распределение: ${result.total_amount.toLocaleString("ru-RU")} ₽ · режим ${optimizerModeLabel(result.optimizer_mode)}`
      );
      if (result.warning) setMessage((prev) => `${prev} · ${result.warning}`);
      loadBatches();
      const summary = await getProcurementBatch(batchId);
      setBatchSummary(summary);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось пересчитать");
    } finally {
      setIsOptimizing(false);
    }
  };

  const onOverrideSupplier = async (productId: number, supplierId: number) => {
    if (!batchId || !supplierId) return;
    try {
      const result = await overrideProductSupplier(batchId, productId, { supplier_id: supplierId });
      setAllocState(result);
      loadBatches();
      const summary = await getProcurementBatch(batchId);
      setBatchSummary(summary);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось сменить поставщика");
    }
  };

  const parseStatusLabel = (status: string) => {
    if (status === "ok") return "OK";
    if (status === "needs_product") return "Нужен продукт";
    return "Не разобрано";
  };

  return (
    <section className="page-stack">
      <h2 className="section-title">План закупки</h2>
      {message && (
        <p className={`status-message${message.includes("Не удалось") || message.includes("Требуется") ? " error" : ""}`}>
          {message}
        </p>
      )}

      <div className="procurement-wizard-tabs">
        <button
          type="button"
          className={wizardStep === "demand" ? "tab active" : "tab"}
          onClick={() => setWizardStep("demand")}
        >
          1. Спрос
        </button>
        <button
          type="button"
          className={wizardStep === "match" ? "tab active" : "tab"}
          onClick={() => {
            if (!batchId || !demandLines.length) return;
            setWizardStep("match");
            loadMatchData(batchId);
          }}
          disabled={!batchId || !demandLines.length}
        >
          2. Проверка
        </button>
        <button
          type="button"
          className={wizardStep === "optimize" ? "tab active" : "tab"}
          onClick={() => {
            if (!batchId) return;
            setWizardStep("optimize");
            loadAllocData(batchId);
          }}
          disabled={!batchId}
        >
          3. Распределение
        </button>
        <button
          type="button"
          className={wizardStep === "orders" ? "tab active" : "tab"}
          onClick={() => {
            if (!batchId) return;
            setWizardStep("orders");
            loadOrdersData(batchId);
          }}
          disabled={!batchId}
        >
          4. Заказы
        </button>
        <button
          type="button"
          className={wizardStep === "summary" ? "tab active" : "tab"}
          onClick={() => {
            if (!batchId) return;
            setWizardStep("summary");
            loadSummaryData(batchId, summaryLocationId, summaryDepartmentId);
          }}
          disabled={!batchId}
        >
          5. Сводка
        </button>
      </div>

      <article className="card procurement-batch-bar">
        <div className="procurement-batch-bar-row">
          <label className="field field-inline procurement-batch-field">
            <span>План</span>
            <select value={batchId ?? ""} onChange={(e) => setBatchId(Number(e.target.value) || null)}>
              <option value="" disabled>
                {batches.length ? "— выберите план —" : "— нет планов —"}
              </option>
              {batches.map((b) => (
                <option key={b.id} value={b.id}>
                  #{b.id} {b.title}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="btn btn-primary" onClick={openNewBatchModal}>
            Новый план
          </button>
          {batchSummary && (
            <p className="muted procurement-batch-stat">
              Слотов: {filledSlots}/{totalSlots || batchSummary.total_slots_count} · строк:{" "}
              {batchSummary.demand_lines_count}
              {batchSummary.match_problem_count != null && (
                <> · проверка OK: {batchSummary.match_ok_count}/{batchSummary.demand_lines_count}</>
              )}
            </p>
          )}
        </div>
        {!batchId && !batches.length && (
          <p className="muted procurement-batch-hint">
            Планов пока нет или не удалось загрузить список — нажмите «Новый план». Если сверху красное сообщение об
            ошибке, на сервере нужны миграции БД (см. docs/deploy-vps.md).
          </p>
        )}
        {!batchId && batches.length > 0 && (
          <p className="muted procurement-batch-hint">Выберите план в списке или создайте новый.</p>
        )}
      </article>

      {batchId && wizardStep === "demand" && (
        <div className="page-stack">
          <article className="card">
            <h3 className="card-title">Спрос по локации и отделу</h3>
            <div className="spec-preview-row">
              <select value={locationId ?? ""} onChange={(e) => setLocationId(Number(e.target.value) || null)}>
                {activeLocations.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </select>
              <select value={departmentId ?? ""} onChange={(e) => setDepartmentId(Number(e.target.value) || null)}>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
            <textarea
              className="order-textarea"
              rows={10}
              placeholder="Брокколи 3 кг"
              value={currentText}
              onChange={(e) => {
                if (!locationId || !departmentId) return;
                const key = slotKey(locationId, departmentId);
                setDemandTexts((prev) => ({ ...prev, [key]: e.target.value }));
              }}
            />
            <div className="actions-row">
              <button className="btn btn-primary" onClick={() => void onSaveSlot()} disabled={isSaving}>
                {isSaving ? "Сохранение..." : "Сохранить блок"}
              </button>
              <button className="btn btn-secondary" onClick={() => void onParseBatch()} disabled={isParsing}>
                {isParsing ? "Разбор..." : "Переразобрать весь план"}
              </button>
              <button className="btn btn-secondary" onClick={() => onGoToMatch()} disabled={!demandLines.length}>
                Далее к проверке →
              </button>
            </div>
          </article>

          <article className="card">
            <h3 className="card-title">Все строки спроса</h3>
            <div className="table-wrap registry-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Локация</th>
                    <th>Отдел</th>
                    <th>Спрос</th>
                    <th>Канон</th>
                    <th>Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {demandLines.map((row) => (
                    <tr key={row.id} className={row.parse_status !== "ok" ? "registry-row problem" : ""}>
                      <td>{row.location_name}</td>
                      <td>{row.department_name}</td>
                      <td>
                        {row.raw_text} ({row.quantity} {row.unit})
                      </td>
                      <td>{row.canonical_product_name || "—"}</td>
                      <td>{parseStatusLabel(row.parse_status)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!demandLines.length && <p className="muted">Пока нет сохранённого спроса.</p>}
          </article>
        </div>
      )}

      {batchId && wizardStep === "match" && (
        <article className="card">
          <div className="card-header-row">
            <h3 className="card-title">Проверка</h3>
            {matchState && (
              <p className="muted product-toolbar-stat">
                Проблемных строк: {matchState.problem_count} из {matchState.total_lines}
                {matchState.ai_available ? " · локально + ИИ" : " · только локально"}
              </p>
            )}
          </div>
          {matchState && !matchState.ai_available && matchState.yandex && (
            <p className="parse-warning">
              ИИ не подключён на сервере:{" "}
              {!matchState.yandex.api_key_configured && "нет YANDEX_API_KEY "}
              {!matchState.yandex.folder_id_configured && "нет folder_id "}
              — проверьте /opt/tutuorders/backend/.env и перезапустите backend (curl /api/health →
              yandex.configured).
            </p>
          )}
          {matchState?.products_missing_price_count > 0 && (
            <p className="parse-warning">
              У {matchState.products_missing_price_count} продукт(ов) в словаре есть привязка SKU, но позиции нет в
              текущем прайсе — перевыберите в Словаре (отмечено ⚠).
            </p>
          )}

          <div className="actions-row">
            <button className="btn btn-primary" onClick={() => void onRunMatch()} disabled={isMatching}>
              {isMatching ? "Поиск..." : "Поиск продукта в словаре"}
            </button>
            <label className="field field-inline">
              <input
                type="checkbox"
                checked={onlyProblems}
                onChange={(e) => setOnlyProblems(e.target.checked)}
              />
              <span>Только проблемные</span>
            </label>
          </div>

          {matchState?.dictionary_gaps?.length > 0 && (
            <>
              <h4 className="card-subtitle">Нет в словаре — предложено добавить</h4>
              <p className="muted dictionary-gaps-hint">
                Продукт ещё не в словаре. Откройте мастер: создать канон + привязать строки из прайсов поставщиков.
              </p>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Название из заказа</th>
                    <th>Ед.</th>
                    <th>Строк в плане</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {matchState.dictionary_gaps.map((gap: any) => (
                    <tr key={gap.demand_name} className="registry-row problem">
                      <td>{gap.demand_name}</td>
                      <td>{gap.default_unit}</td>
                      <td>{gap.line_count}</td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-primary btn-small"
                          onClick={() => setAddProductGap(gap)}
                        >
                          Добавить и привязать SKU
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          <div className="table-wrap registry-table-wrap">
            <table className="data-table match-table">
              <thead>
                <tr>
                  <th>Локация</th>
                  <th>Отдел</th>
                  <th>Спрос</th>
                  <th>Канон. продукт</th>
                  <th>SKU поставщиков</th>
                  <th>Статус</th>
                </tr>
              </thead>
              <tbody>
                {visibleMatchRows.map((row: any) => (
                  <tr
                    key={row.id}
                    className={
                      !matchReadyForAllocation(row.match_status)
                        ? "registry-row problem"
                        : row.match_status === "partial_sku"
                          ? "registry-row partial"
                          : ""
                    }
                  >
                    <td>{row.location_name}</td>
                    <td>{row.department_name}</td>
                    <td>
                      {row.demand_name}
                      <span className="muted">
                        {" "}
                        ({row.quantity} {row.unit})
                      </span>
                    </td>
                    <td>
                      <select
                        value={row.canonical_product_id ?? ""}
                        onChange={(e) => void onAssignProduct(row.id, Number(e.target.value))}
                      >
                        <option value="">— выбрать —</option>
                        {products.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name}
                          </option>
                        ))}
                      </select>
                      {(row.suggestions || []).length > 0 && (
                        <div className="match-row-actions">
                          <span className="match-suggest-label">Похожие:</span>
                          {(row.suggestions || []).map((s: any) => (
                            <button
                              key={s.product_id}
                              type="button"
                              className="btn btn-secondary btn-small"
                              title={`Совпадение ${Math.round(s.score * 100)}%`}
                              onClick={() => void onAssignProduct(row.id, s.product_id)}
                            >
                              {s.name}
                            </button>
                          ))}
                        </div>
                      )}
                      {row.match_status === "needs_product" && !(row.suggestions || []).length && (
                        <p className="muted match-no-suggest">В словаре нет похожих — «Добавить и привязать SKU» выше</p>
                      )}
                    </td>
                    <td>
                      <div className="sku-coverage-list">
                        {(row.supplier_skus || []).map((sku: any) => (
                          <span
                            key={sku.supplier_id}
                            className={
                              sku.has_sku
                                ? "sku-chip ok"
                                : sku.missing_in_price
                                  ? "sku-chip warn"
                                  : "sku-chip missing"
                            }
                            title={
                              sku.has_sku
                                ? `${sku.name_in_price} — ${sku.price} ₽`
                                : sku.missing_in_price
                                  ? `${sku.name_in_price} — нет в текущем прайсе, перевыберите в Словаре`
                                  : "Нет привязки в Словаре"
                            }
                          >
                            {sku.supplier_name}: {sku.has_sku ? "✓" : sku.missing_in_price ? "⚠" : "✗"}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <span className={`match-status-badge ${matchStatusBadgeClass(row.match_status)}`}>
                        {matchStatusLabel(row.match_status)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!visibleMatchRows.length && (
            <p className="muted">
              {matchState?.problem_count === 0
                ? "Все строки готовы к распределению — откройте шаг «3. Распределение»."
                : "Нет строк для отображения. Нажмите «Поиск продукта в словаре»."}
            </p>
          )}
        </article>
      )}

      {batchId && wizardStep === "optimize" && (
        <article className="card">
          <div className="card-header-row">
            <h3 className="card-title">Распределение по поставщикам</h3>
            {allocState && (
              <p className="muted product-toolbar-stat">
                Итого: {allocState.total_amount.toLocaleString("ru-RU")} ₽ · {optimizerModeLabel(allocState.optimizer_mode)}
                {allocState.skipped_lines_count > 0 && (
                  <> · пропущено строк: {allocState.skipped_lines_count}</>
                )}
              </p>
            )}
          </div>
          {allocState?.warning && <p className="status-message">{allocState.warning}</p>}
          <div className="actions-row">
            <button className="btn btn-primary" onClick={() => void onOptimize()} disabled={isOptimizing}>
              {isOptimizing ? "Расчёт..." : "Пересчитать"}
            </button>
          </div>

          {allocState?.supplier_totals?.length > 0 && (
            <>
              <h4 className="card-subtitle">Поставщики</h4>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Поставщик</th>
                    <th>Сумма</th>
                    <th>Мин. заказ</th>
                    <th>Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {allocState.supplier_totals.map((row: any) => (
                    <tr key={row.supplier_id} className={!row.min_order_passed ? "registry-row problem" : ""}>
                      <td>{row.supplier_name}</td>
                      <td>{row.amount.toLocaleString("ru-RU")} ₽</td>
                      <td>{row.min_order_amount.toLocaleString("ru-RU")} ₽</td>
                      <td>{row.min_order_passed ? "✓" : "ниже мин."}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {allocState?.product_assignments?.length > 0 && (
            <>
              <h4 className="card-subtitle">Продукт → поставщик (один на все локации)</h4>
              <table className="data-table match-table">
                <thead>
                  <tr>
                    <th>Продукт</th>
                    <th>Кол-во</th>
                    <th>Поставщик</th>
                    <th>Сумма</th>
                  </tr>
                </thead>
                <tbody>
                  {allocState.product_assignments.map((row: any) => (
                    <tr key={row.canonical_product_id}>
                      <td>{row.canonical_product_name}</td>
                      <td>
                        {row.total_quantity} {row.unit}
                      </td>
                      <td>
                        <select
                          value={row.supplier_id}
                          onChange={(e) =>
                            void onOverrideSupplier(row.canonical_product_id, Number(e.target.value))
                          }
                        >
                          {(allocState.optimizable_products || [])
                            .find((p: any) => p.canonical_product_id === row.canonical_product_id)
                            ?.options?.map((opt: any) => (
                              <option key={opt.supplier_id} value={opt.supplier_id}>
                                {opt.supplier_name}
                              </option>
                            )) || (
                            <option value={row.supplier_id}>{row.supplier_name}</option>
                          )}
                        </select>
                      </td>
                      <td>{row.line_cost.toLocaleString("ru-RU")} ₽</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {!allocState?.product_assignments?.length && (
            <p className="muted">Нажмите «Пересчитать» после успешной проверки.</p>
          )}
        </article>
      )}

      {batchId && wizardStep === "orders" && (
        <article className="card">
          <div className="card-header-row">
            <h3 className="card-title">Заказы поставщикам</h3>
            {ordersState && (
              <p className="muted product-toolbar-stat">
                {ordersState.lines_count} строк · {ordersState.groups_count} листов для xlsx
              </p>
            )}
          </div>
          <div className="actions-row">
            <button className="btn btn-primary" onClick={() => void onBuildOrders()} disabled={isBuildingOrders}>
              {isBuildingOrders ? "Сборка..." : "Собрать заказы"}
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => void onDownloadExport()}
              disabled={isExporting || !ordersState?.lines_count}
            >
              {isExporting ? "Скачивание..." : "Скачать все xlsx"}
            </button>
          </div>

          {!ordersState?.lines_count && (
            <p className="muted">
              Нажмите «Собрать заказы» после распределения — подставятся названия из прайсов и комментарии из
              спецификаций.
            </p>
          )}

          {ordersState?.lines_count > 0 && (
            <>
              <div className="spec-preview-row">
                <select
                  value={filterSupplierId ?? ""}
                  onChange={(e) => setFilterSupplierId(Number(e.target.value) || null)}
                >
                  {(ordersState.suppliers || []).map((s: any) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
                <select
                  value={filterLocationId ?? ""}
                  onChange={(e) => setFilterLocationId(Number(e.target.value) || null)}
                >
                  {(ordersState.locations || []).map((l: any) => (
                    <option key={l.id} value={l.id}>
                      {l.name}
                    </option>
                  ))}
                </select>
                <select
                  value={filterDepartmentId ?? ""}
                  onChange={(e) => setFilterDepartmentId(Number(e.target.value) || null)}
                >
                  {(ordersState.departments || []).map((d: any) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
                {activeOrderGroup && (
                  <span className="muted">Сумма листа: {activeOrderGroup.total_amount.toLocaleString("ru-RU")} ₽</span>
                )}
              </div>

              <div className="table-wrap registry-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Название (прайс)</th>
                      <th>Кол-во</th>
                      <th>Ед.</th>
                      <th>Цена</th>
                      <th>Сумма</th>
                      <th>Комментарий</th>
                    </tr>
                  </thead>
                  <tbody>
                    {!activeOrderLines.length && (
                      <tr>
                        <td colSpan={6} className="muted">
                          Нет строк для выбранной комбинации поставщик / локация / отдел
                        </td>
                      </tr>
                    )}
                    {activeOrderLines.map((row: any) => (
                      <tr key={row.id}>
                        <td>{row.supplier_product_name}</td>
                        <td>{row.quantity}</td>
                        <td>{row.unit}</td>
                        <td>{row.unit_price.toLocaleString("ru-RU")}</td>
                        <td>{row.amount.toLocaleString("ru-RU")} ₽</td>
                        <td className="order-comment-cell">
                          {editingCommentLineId === row.id ? (
                            <div className="comment-edit-block">
                              <textarea
                                className="order-textarea"
                                rows={3}
                                value={commentDraft}
                                onChange={(e) => setCommentDraft(e.target.value)}
                              />
                              <div className="match-row-actions">
                                <button
                                  type="button"
                                  className="btn btn-primary btn-small"
                                  onClick={() => void onSaveComment(row.id)}
                                >
                                  Сохранить
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-secondary btn-small"
                                  onClick={() => setEditingCommentLineId(null)}
                                >
                                  Отмена
                                </button>
                              </div>
                            </div>
                          ) : (
                            <>
                              <span className="order-comment-text">{row.line_comment || "—"}</span>
                              <button
                                type="button"
                                className="btn btn-secondary btn-small"
                                onClick={() => {
                                  setEditingCommentLineId(row.id);
                                  setCommentDraft(row.line_comment || "");
                                }}
                              >
                                Изменить
                              </button>
                            </>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="supplier-messages">
                <h4 className="card-subtitle">Сообщения поставщикам</h4>
                {supplierMessages.length === 0 && <p className="muted">Нет данных для сообщений.</p>}
                {supplierMessages.map((m: any) => (
                  <details key={m.supplierId} className="supplier-message-block">
                    <summary>
                      <span>{m.supplierName}</span>
                      <span className="muted">· текст для отправки</span>
                    </summary>
                    <textarea className="supplier-message-textarea" readOnly value={m.text} />
                    <div className="actions-row supplier-message-actions">
                      <button
                        type="button"
                        className="btn btn-primary btn-small"
                        onClick={() => void onCopySupplierMessage(m.supplierId, m.text)}
                      >
                        {copiedSupplierId === m.supplierId ? "Скопировано" : "Скопировать"}
                      </button>
                    </div>
                  </details>
                ))}
              </div>
            </>
          )}
        </article>
      )}

      {batchId && wizardStep === "summary" && (
        <article className="card">
          <div className="result-header-row">
            <h3 className="card-title">Сводка закупки</h3>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void onDownloadSummaryExport()}
              disabled={isSummaryExporting || !summaryState?.items_count}
            >
              {isSummaryExporting ? "Скачивание..." : "Скачать сводный xlsx"}
            </button>
          </div>
          <p className="muted">
            Внутренний обзор: продукт × поставщики (цена / кол-во / сумма). Не для отправки поставщику — для
            проверки расчёта.
          </p>

          <div className="spec-preview-row">
            <select
              value={summaryLocationId ?? ""}
              onChange={(e) => {
                const v = e.target.value ? Number(e.target.value) : null;
                setSummaryLocationId(v);
                if (batchId) loadSummaryData(batchId, v, summaryDepartmentId);
              }}
            >
              <option value="">Все локации</option>
              {locations.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
            <select
              value={summaryDepartmentId ?? ""}
              onChange={(e) => {
                const v = e.target.value ? Number(e.target.value) : null;
                setSummaryDepartmentId(v);
                if (batchId) loadSummaryData(batchId, summaryLocationId, v);
              }}
            >
              <option value="">Все отделы</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
            {summaryState && (
              <span className="muted">
                Итого: {summaryState.total_amount.toLocaleString("ru-RU")} {summaryState.currency}
              </span>
            )}
          </div>

          {summaryState?.supplier_totals?.length > 0 && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Поставщик</th>
                  <th>Сумма (фильтр)</th>
                  <th>Мин. заказ</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {summaryState.supplier_totals
                  .filter((row: any) => row.used_in_filter || row.amount > 0)
                  .map((row: any) => (
                    <tr key={row.supplier_id} className={!row.min_order_passed ? "registry-row problem" : ""}>
                      <td>{row.supplier_name}</td>
                      <td>{row.amount.toLocaleString("ru-RU")} ₽</td>
                      <td>{row.min_order_amount.toLocaleString("ru-RU")} ₽</td>
                      <td>{row.min_order_passed ? "✓" : "ниже мин."}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}

          {summaryState?.problems_count > 0 && (
            <div className="parse-warning">
              <strong>Строки без распределения ({summaryState.problems_count}):</strong>
              <ul>
                {summaryState.problems.map((p: any) => (
                  <li key={p.demand_line_id}>
                    {p.raw_text} — {p.location_name}, {p.department_name}
                    {p.reason === "needs_product" ? " (нет продукта)" : " (нет allocation)"}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="table-wrap registry-table-wrap">
            <table className="data-table result-table">
              <thead>
                <tr>
                  <th>Продукт</th>
                  <th>Ед.</th>
                  <th>Кол-во</th>
                  {summarySupplierIds.map((id: number) => (
                    <th key={`p-${id}`}>Цена {summarySupplierNames[id]}</th>
                  ))}
                  {summarySupplierIds.map((id: number) => (
                    <th key={`q-${id}`}>Кол-во {summarySupplierNames[id]}</th>
                  ))}
                  <th>Сумма</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Итого</td>
                  <td />
                  <td>{summaryState?.items_count || 0}</td>
                  {summarySupplierIds.map((id: number) => (
                    <td key={`sp-${id}`} />
                  ))}
                  {summarySupplierIds.map((id: number) => (
                    <td key={`sq-${id}`}>{Number(summarySupplierTotals[id] || 0).toFixed(2)}</td>
                  ))}
                  <td>{(summaryState?.total_amount || 0).toLocaleString("ru-RU")}</td>
                </tr>
                {(summaryState?.items || []).map((item: any, idx: number) => (
                  <tr
                    key={`${item.canonical_product_id}-${idx}`}
                    className={!item.allocation?.length ? "registry-row problem" : ""}
                  >
                    <td>{item.canonical_name}</td>
                    <td>{item.unit}</td>
                    <td>{Number(item.quantity).toFixed(3)}</td>
                    {summarySupplierIds.map((sid: number) => {
                      const match = (item.matches || []).find((m: any) => m.supplier_id === sid);
                      return (
                        <td key={`${idx}-p-${sid}`}>{match ? Number(match.price).toFixed(2) : "—"}</td>
                      );
                    })}
                    {summarySupplierIds.map((sid: number) => {
                      const alloc = (item.allocation || []).find((a: any) => a.supplier_id === sid);
                      return <td key={`${idx}-q-${sid}`}>{Number(alloc?.quantity || 0).toFixed(3)}</td>;
                    })}
                    <td>{Number(item.row_total || 0).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {!summaryState?.items_count && (
            <p className="muted">Нет данных — сначала выполните распределение на шаге 3.</p>
          )}

          <div className="actions-row">
            <button className="btn btn-secondary" onClick={() => setWizardStep("orders")}>
              ← Назад к заказам
            </button>
          </div>
        </article>
      )}
      {showNewBatchModal && (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <article className="card modal-card">
            <h3 className="card-title">Новый план закупки</h3>
            <label className="field">
              <span>Название</span>
              <input
                value={newBatchPlanLabel}
                onChange={(e) => setNewBatchPlanLabel(e.target.value)}
                placeholder={defaultPlanLabel()}
              />
            </label>
            <div className="field">
              <span>Ответственный</span>
              <div className="batch-responsible-options">
                <label className="checkbox-inline">
                  <input
                    type="checkbox"
                    checked={newBatchResponsible === "Женя"}
                    onChange={() => setNewBatchResponsible(newBatchResponsible === "Женя" ? null : "Женя")}
                  />
                  <span>Женя</span>
                </label>
                <label className="checkbox-inline">
                  <input
                    type="checkbox"
                    checked={newBatchResponsible === "Андрей"}
                    onChange={() => setNewBatchResponsible(newBatchResponsible === "Андрей" ? null : "Андрей")}
                  />
                  <span>Андрей</span>
                </label>
              </div>
            </div>
            <p className="muted batch-create-hint">
              В списке планов: название · ответственный (статус). Статус обновится при прохождении этапов.
            </p>
            <div className="actions-row">
              <button
                type="button"
                className="btn btn-primary"
                disabled={isCreatingBatch}
                onClick={() => void onCreateBatch()}
              >
                {isCreatingBatch ? "Создание..." : "Создать"}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={isCreatingBatch}
                onClick={() => setShowNewBatchModal(false)}
              >
                Отмена
              </button>
            </div>
          </article>
        </div>
      )}
      {addProductGap && (
        <AddProductModal
          gap={addProductGap}
          onClose={() => setAddProductGap(null)}
          onSave={onSaveNewDictionaryProduct}
        />
      )}
    </section>
  );
}
