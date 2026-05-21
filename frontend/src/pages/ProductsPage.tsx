import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createProduct,
  createProductSku,
  deleteProduct,
  updateProduct,
  deleteProductSku,
  getProductDeleteImpact,
  getProducts,
  getSuppliers,
  suggestProductSkus,
} from "../api";

const UNITS = ["кг", "г", "л", "мл"];

function linkSkuSuggestKey(productId: number, supplierId: number) {
  return `${productId}:${supplierId}`;
}

export function ProductsPage() {
  const [products, setProducts] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [message, setMessage] = useState("");
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [onlyWithoutSku, setOnlyWithoutSku] = useState(false);
  const [newProduct, setNewProduct] = useState({ name: "", default_unit: "кг", category: "" });
  const [newProductSkuSuggest, setNewProductSkuSuggest] = useState<any | null>(null);
  const [newProductSkuPicks, setNewProductSkuPicks] = useState<Record<number, string>>({});
  const [newProductSkuManual, setNewProductSkuManual] = useState<Record<number, string>>({});
  const [isSuggestingSkus, setIsSuggestingSkus] = useState(false);
  const [skuDrafts, setSkuDrafts] = useState<Record<number, { supplier_id: string; name_in_price: string; is_preferred: boolean }>>(
    {}
  );
  const [linkSkuSuggestByKey, setLinkSkuSuggestByKey] = useState<
    Record<string, { candidates: any[]; ai_used?: boolean }>
  >({});
  const [linkSkuSuggestLoading, setLinkSkuSuggestLoading] = useState<string | null>(null);
  const [isEditingProduct, setIsEditingProduct] = useState(false);
  const [editProductName, setEditProductName] = useState("");
  const [isSavingProduct, setIsSavingProduct] = useState(false);

  const loadData = () => {
    Promise.all([getProducts(), getSuppliers()])
      .then(([productsData, suppliersData]) => {
        const nextProducts = productsData.items || [];
        setProducts(nextProducts);
        setSuppliers(suppliersData.items || []);
        setSelectedProductId((prev) => {
          if (!nextProducts.length) return null;
          if (prev && nextProducts.some((row: any) => row.id === prev)) return prev;
          return nextProducts[0].id;
        });
      })
      .catch(() => {
        setProducts([]);
        setSuppliers([]);
      });
  };

  useEffect(() => {
    loadData();
  }, []);

  const onSuggestSkusForNewProduct = async () => {
    const name = newProduct.name.trim();
    if (!name) {
      setMessage("Сначала укажите название продукта");
      return;
    }
    setIsSuggestingSkus(true);
    try {
      const data = await suggestProductSkus(name, newProduct.default_unit);
      setNewProductSkuSuggest(data);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось подобрать SKU");
    } finally {
      setIsSuggestingSkus(false);
    }
  };

  const onCreateProduct = async () => {
    const name = newProduct.name.trim();
    if (!name) {
      setMessage("Укажите название канонического продукта");
      return;
    }
    setMessage("");
    try {
      const created = await createProduct({
        name,
        default_unit: newProduct.default_unit,
        category: newProduct.category.trim() || null,
        is_active: true,
      });
      let skusLinked = 0;
      for (const block of newProductSkuSuggest?.suppliers || []) {
        const sid = block.supplier_id;
        const picked = (newProductSkuPicks[sid] || newProductSkuManual[sid] || "").trim();
        if (!picked) continue;
        try {
          await createProductSku(created.id, {
            supplier_id: sid,
            name_in_price: picked,
            is_preferred: false,
          });
          skusLinked += 1;
        } catch {
          /* skip invalid price row */
        }
      }
      setNewProduct({ name: "", default_unit: "кг", category: "" });
      setNewProductSkuSuggest(null);
      setNewProductSkuPicks({});
      setNewProductSkuManual({});
      setMessage(`Продукт «${name}» добавлен${skusLinked ? `, SKU: ${skusLinked}` : ""}`);
      loadData();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось добавить продукт");
    }
  };

  const onAddSku = async (productId: number) => {
    const draft = skuDrafts[productId];
    if (!draft) return;
    const supplierId = Number(draft.supplier_id);
    if (!supplierId || !draft.name_in_price.trim()) {
      setMessage("Для привязки SKU выберите поставщика и название из прайса");
      return;
    }
    setMessage("");
    try {
      await createProductSku(productId, {
        supplier_id: supplierId,
        name_in_price: draft.name_in_price.trim(),
        is_preferred: draft.is_preferred,
      });
      setSkuDrafts((prev) => ({
        ...prev,
        [productId]: { supplier_id: "", name_in_price: "", is_preferred: false },
      }));
      setLinkSkuSuggestByKey((prev) => {
        const next = { ...prev };
        for (const key of Object.keys(next)) {
          if (key.startsWith(`${productId}:`)) delete next[key];
        }
        return next;
      });
      setMessage("SKU привязан");
      loadData();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось привязать SKU");
    }
  };

  const formatDeleteImpactMessage = (impact: any) => {
    const parts = [
      `Удалить продукт «${impact.product_name}»?`,
      "",
      "Будет удалено:",
      `• привязок SKU: ${impact.sku_count}`,
      `• правил спецификаций: ${impact.spec_count}`,
    ];
    if (impact.demand_line_count) {
      parts.push(`• привязок в планах закупки: ${impact.demand_line_count} (продукт отвяжется, строки спроса останутся)`);
    }
    if (impact.allocation_count) {
      parts.push(`• распределений: ${impact.allocation_count}`);
    }
    if (impact.order_line_count) {
      parts.push(`• строк заказов поставщикам: ${impact.order_line_count}`);
    }
    if (impact.batch_titles?.length) {
      parts.push(`• затронутые планы: ${impact.batch_titles.join(", ")}`);
      parts.push("  (на этих планах нужно будет заново запустить распределение и сборку заказов)");
    }
    parts.push("", "Действие необратимо.");
    return parts.join("\n");
  };

  const onDeleteProduct = async (productId: number) => {
    setMessage("");
    try {
      const impact = await getProductDeleteImpact(productId);
      if (!window.confirm(formatDeleteImpactMessage(impact))) return;
      await deleteProduct(productId);
      setMessage(`Продукт «${impact.product_name}» удалён`);
      setSelectedProductId(null);
      loadData();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось удалить продукт");
    }
  };

  const onDeleteSku = async (productId: number, skuId: number) => {
    if (!window.confirm("Удалить привязку SKU?")) return;
    setMessage("");
    try {
      await deleteProductSku(productId, skuId);
      setMessage("SKU удален");
      loadData();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось удалить SKU");
    }
  };

  const filteredProducts = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return products.filter((row) => {
      const byQuery =
        !query ||
        String(row.name || "").toLowerCase().includes(query) ||
        String(row.category || "").toLowerCase().includes(query);
      const bySku = !onlyWithoutSku || !(row.skus || []).length;
      return byQuery && bySku;
    });
  }, [products, searchQuery, onlyWithoutSku]);

  const selectedProduct = filteredProducts.find((row) => row.id === selectedProductId) || filteredProducts[0] || null;

  const suppliersAvailableForLink = useMemo(() => {
    if (!selectedProduct) return suppliers;
    const linked = new Set((selectedProduct.skus || []).map((sku: any) => sku.supplier_id));
    return suppliers.filter((s) => !linked.has(s.id));
  }, [suppliers, selectedProduct]);

  const fetchLinkSkuSuggest = useCallback(async (product: any, supplierId: number) => {
    const key = linkSkuSuggestKey(product.id, supplierId);
    setLinkSkuSuggestLoading(key);
    try {
      const data = await suggestProductSkus(product.name, product.default_unit);
      const block = (data.suppliers || []).find((b: any) => b.supplier_id === supplierId);
      setLinkSkuSuggestByKey((prev) => ({
        ...prev,
        [key]: { candidates: block?.candidates || [], ai_used: data.ai_used },
      }));
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось найти позиции в прайсе");
    } finally {
      setLinkSkuSuggestLoading(null);
    }
  }, []);

  const selectedLinkSupplierId = selectedProduct
    ? Number(skuDrafts[selectedProduct.id]?.supplier_id) || null
    : null;
  const selectedLinkSuggestKey =
    selectedProduct && selectedLinkSupplierId
      ? linkSkuSuggestKey(selectedProduct.id, selectedLinkSupplierId)
      : null;
  const selectedLinkSuggest = selectedLinkSuggestKey ? linkSkuSuggestByKey[selectedLinkSuggestKey] : null;
  const isSelectedLinkSuggestLoading = selectedLinkSuggestKey != null && linkSkuSuggestLoading === selectedLinkSuggestKey;

  useEffect(() => {
    if (!selectedProduct || !selectedLinkSupplierId) return;
    void fetchLinkSkuSuggest(selectedProduct, selectedLinkSupplierId);
  }, [selectedProduct?.id, selectedLinkSupplierId, fetchLinkSkuSuggest]);

  useEffect(() => {
    setIsEditingProduct(false);
    setEditProductName("");
  }, [selectedProduct?.id]);

  const onStartEditProduct = () => {
    if (!selectedProduct) return;
    setEditProductName(selectedProduct.name);
    setIsEditingProduct(true);
  };

  const onCancelEditProduct = () => {
    setIsEditingProduct(false);
    setEditProductName("");
  };

  const onSaveProductName = async () => {
    if (!selectedProduct) return;
    const name = editProductName.trim();
    if (!name) {
      setMessage("Укажите название продукта");
      return;
    }
    if (name === selectedProduct.name) {
      setIsEditingProduct(false);
      return;
    }
    setIsSavingProduct(true);
    setMessage("");
    try {
      await updateProduct(selectedProduct.id, {
        name,
        default_unit: selectedProduct.default_unit,
        category: selectedProduct.category,
        notes: selectedProduct.notes,
        is_active: selectedProduct.is_active !== false,
      });
      setIsEditingProduct(false);
      setMessage(`Название обновлено: «${name}»`);
      loadData();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось сохранить название");
    } finally {
      setIsSavingProduct(false);
    }
  };

  return (
    <section className="page-stack">
      <h2 className="section-title">Словарь продуктов</h2>
      {message && <p className="status-message">{message}</p>}

      <article className="card add-supplier-card">
        <h3 className="card-title">Новый канонический продукт</h3>
        <div className="product-create-row">
          <label className="field">
            <span>Название</span>
            <input value={newProduct.name} onChange={(e) => setNewProduct((p) => ({ ...p, name: e.target.value }))} />
          </label>
          <label className="field">
            <span>Единица</span>
            <select
              value={newProduct.default_unit}
              onChange={(e) => setNewProduct((p) => ({ ...p, default_unit: e.target.value }))}
            >
              {UNITS.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Категория</span>
            <input
              value={newProduct.category}
              onChange={(e) => setNewProduct((p) => ({ ...p, category: e.target.value }))}
              placeholder="овощи / ягоды"
            />
          </label>
          <button type="button" className="btn btn-secondary" onClick={() => void onSuggestSkusForNewProduct()} disabled={isSuggestingSkus}>
            {isSuggestingSkus ? "Поиск..." : "Найти в прайсах"}
          </button>
          <button type="button" className="btn btn-primary" onClick={() => void onCreateProduct()}>
            Добавить
          </button>
        </div>
        {newProductSkuSuggest && (
          <div className="new-product-sku-suggest">
            <p className="muted">
              Кандидаты из прайсов{newProductSkuSuggest.ai_used ? " (с ИИ)" : ""} — выберите по поставщикам или введите
              вручную.
            </p>
            {(newProductSkuSuggest.suppliers || []).map((block: any) => (
              <div key={block.supplier_id} className="modal-supplier-block">
                <h4 className="card-subtitle">{block.supplier_name}</h4>
                {(block.candidates || []).slice(0, 5).map((c: any) => (
                  <label key={c.name_in_price} className="sku-candidate-item">
                    <input
                      type="radio"
                      name={`new-sku-${block.supplier_id}`}
                      checked={newProductSkuPicks[block.supplier_id] === c.name_in_price}
                      onChange={() =>
                        setNewProductSkuPicks((prev) => ({ ...prev, [block.supplier_id]: c.name_in_price }))
                      }
                    />
                    <span>
                      {c.name_in_price} — {c.price} ₽
                    </span>
                  </label>
                ))}
                <input
                  className="sku-manual-input"
                  placeholder="Или название из прайса"
                  value={newProductSkuManual[block.supplier_id] || ""}
                  onChange={(e) =>
                    setNewProductSkuManual((prev) => ({ ...prev, [block.supplier_id]: e.target.value }))
                  }
                />
              </div>
            ))}
          </div>
        )}
      </article>

      <p className="muted">
        Продукты и спецификации не удаляются при обновлении прайса. Если позиция исчезла у поставщика, привязка SKU
        сохраняется и отображается как «нет в прайсе».
      </p>

      <div className="card product-toolbar">
        <input
          placeholder="Поиск по названию или категории"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        <label className="checkbox-inline">
          <input type="checkbox" checked={onlyWithoutSku} onChange={(e) => setOnlyWithoutSku(e.target.checked)} />
          <span>Только без SKU</span>
        </label>
        <p className="muted product-toolbar-stat">Найдено: {filteredProducts.length}</p>
      </div>

      <div className="products-registry-layout">
        <article className="card">
          <h3 className="card-title">Реестр продуктов</h3>
          <div className="table-wrap registry-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Продукт</th>
                  <th>Ед.</th>
                  <th>Категория</th>
                  <th>SKU</th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.map((row) => {
                  const skuCount = (row.skus || []).length;
                  const rowClass = [
                    "registry-row",
                    selectedProduct?.id === row.id ? "selected" : "",
                    skuCount === 0 ? "problem" : "",
                  ]
                    .join(" ")
                    .trim();
                  return (
                    <tr key={row.id} className={rowClass} onClick={() => setSelectedProductId(row.id)}>
                      <td>{row.name}</td>
                      <td>{row.default_unit}</td>
                      <td>{row.category || "—"}</td>
                      <td>{skuCount}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </article>

        <article className="card product-details-card">
          {selectedProduct ? (
            <>
              <div className="product-details-header">
                <h3 className="card-title">Детали продукта</h3>
                <div className="product-details-actions">
                  {isEditingProduct ? (
                    <>
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={isSavingProduct}
                        onClick={() => void onSaveProductName()}
                      >
                        {isSavingProduct ? "Сохранение..." : "Сохранить"}
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        disabled={isSavingProduct}
                        onClick={onCancelEditProduct}
                      >
                        Отмена
                      </button>
                    </>
                  ) : (
                    <>
                      <button type="button" className="btn btn-secondary" onClick={onStartEditProduct}>
                        Изменить
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost-danger"
                        onClick={() => void onDeleteProduct(selectedProduct.id)}
                      >
                        Удалить
                      </button>
                    </>
                  )}
                </div>
              </div>

              <div className="product-details-body">
                <div className="product-details-meta">
                  {isEditingProduct ? (
                    <label className="field product-name-edit-field">
                      <span>Название</span>
                      <input
                        value={editProductName}
                        onChange={(e) => setEditProductName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") void onSaveProductName();
                          if (e.key === "Escape") onCancelEditProduct();
                        }}
                        autoFocus
                      />
                    </label>
                  ) : (
                    <p className="product-details-title">
                      {selectedProduct.name}{" "}
                      <span className="muted-inline">({selectedProduct.default_unit})</span>
                    </p>
                  )}
                  <p className="muted product-details-category">Категория: {selectedProduct.category || "—"}</p>
                </div>

                <div className="table-wrap product-table-wrap">
                  <table className="data-table product-sku-table">
                    <thead>
                      <tr>
                        <th>Поставщик</th>
                        <th>Название в прайсе</th>
                        <th>Цена</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {(selectedProduct.skus || []).map((sku: any) => (
                        <tr key={sku.id} className={!sku.price_id ? "registry-row problem" : ""}>
                          <td>{sku.supplier_name}</td>
                          <td>{sku.name_in_price}</td>
                          <td>
                            {sku.price_id ? (
                              <>
                                {sku.price} ₽ / {sku.unit}
                              </>
                            ) : (
                              <span className="muted" title="Позиции нет в текущем прайсе — связь сохранена">
                                нет в прайсе
                              </span>
                            )}
                          </td>
                          <td className="product-sku-actions">
                            <button
                              type="button"
                              className="btn btn-ghost-danger btn-compact"
                              onClick={() => void onDeleteSku(selectedProduct.id, sku.id)}
                            >
                              Удалить
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="product-sku-link">
                  <div className="product-sku-add">
                    <select
                      value={skuDrafts[selectedProduct.id]?.supplier_id || ""}
                      onChange={(e) =>
                        setSkuDrafts((prev) => ({
                          ...prev,
                          [selectedProduct.id]: {
                            ...(prev[selectedProduct.id] || { is_preferred: false }),
                            supplier_id: e.target.value,
                            name_in_price: "",
                          },
                        }))
                      }
                    >
                      <option value="">Поставщик...</option>
                      {suppliersAvailableForLink.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      disabled={!selectedLinkSupplierId || isSelectedLinkSuggestLoading}
                      onClick={() => {
                        if (!selectedLinkSupplierId) return;
                        void fetchLinkSkuSuggest(selectedProduct, selectedLinkSupplierId);
                      }}
                    >
                      {isSelectedLinkSuggestLoading ? "Поиск..." : "Найти в прайсе"}
                    </button>
                    <button type="button" className="btn btn-primary" onClick={() => void onAddSku(selectedProduct.id)}>
                      Привязать SKU
                    </button>
                  </div>

                  {!suppliersAvailableForLink.length && (selectedProduct.skus || []).length > 0 && (
                    <p className="muted">SKU привязаны ко всем поставщикам.</p>
                  )}

                  {selectedLinkSupplierId && (
                    <div className="new-product-sku-suggest link-sku-suggest">
                      {isSelectedLinkSuggestLoading && <p className="muted">Ищем в прайсе поставщика…</p>}
                      {!isSelectedLinkSuggestLoading && selectedLinkSuggest?.ai_used && (
                        <p className="muted">Подсказки дополнены ИИ.</p>
                      )}
                      {!isSelectedLinkSuggestLoading &&
                        (selectedLinkSuggest?.candidates?.length ? (
                          <>
                            <p className="muted">Выберите позицию из прайса или введите название вручную:</p>
                            {(selectedLinkSuggest.candidates || []).slice(0, 8).map((c: any) => (
                              <label key={c.name_in_price} className="sku-candidate-item">
                                <input
                                  type="radio"
                                  name={`link-sku-${selectedLinkSuggestKey}`}
                                  checked={skuDrafts[selectedProduct.id]?.name_in_price === c.name_in_price}
                                  onChange={() =>
                                    setSkuDrafts((prev) => ({
                                      ...prev,
                                      [selectedProduct.id]: {
                                        ...(prev[selectedProduct.id] || {
                                          supplier_id: String(selectedLinkSupplierId),
                                          is_preferred: false,
                                        }),
                                        name_in_price: c.name_in_price,
                                      },
                                    }))
                                  }
                                />
                                <span>
                                  {c.name_in_price} — {c.price} ₽ / {c.unit}
                                  <span className="muted-inline"> ({Math.round(c.score * 100)}%)</span>
                                </span>
                              </label>
                            ))}
                          </>
                        ) : (
                          <p className="muted">В прайсе нет похожих — введите название вручную.</p>
                        ))}
                      <input
                        className="sku-manual-input"
                        placeholder="Название из прайса"
                        value={skuDrafts[selectedProduct.id]?.name_in_price || ""}
                        onChange={(e) =>
                          setSkuDrafts((prev) => ({
                            ...prev,
                            [selectedProduct.id]: {
                              ...(prev[selectedProduct.id] || {
                                supplier_id: String(selectedLinkSupplierId),
                                is_preferred: false,
                              }),
                              name_in_price: e.target.value,
                            },
                          }))
                        }
                      />
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <>
              <h3 className="card-title">Детали продукта</h3>
              <p className="muted">Нет продуктов под текущий фильтр.</p>
            </>
          )}
        </article>
      </div>
    </section>
  );
}
