from pydantic import BaseModel, Field


class SupplierOut(BaseModel):
    id: int
    name: str
    min_order_amount: float
    price_items_count: int
    unmatched_price_items_count: int
    last_price_upload_at: str | None


class SuppliersResponse(BaseModel):
    items: list[SupplierOut]


class SupplierCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    min_order_amount: float = Field(ge=0, default=0)


class SupplierUpdateRequest(BaseModel):
    name: str
    min_order_amount: float


class MatchRequest(BaseModel):
    order_text: str = Field(min_length=1)


class SettingsOut(BaseModel):
    folder_id: str
    model_name: str
    api_key_configured: bool


class SettingsUpdateRequest(BaseModel):
    folder_id: str
    model_name: str


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class DepartmentOut(BaseModel):
    id: int
    code: str
    name: str


class DepartmentsResponse(BaseModel):
    items: list[DepartmentOut]


class LocationOut(BaseModel):
    id: int
    code: str
    name: str
    sort_order: int
    is_active: bool


class LocationsResponse(BaseModel):
    items: list[LocationOut]


class LocationCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = True


class LocationUpdateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    sort_order: int = Field(ge=0)
    is_active: bool = True


class SupplierSkuOut(BaseModel):
    id: int
    supplier_id: int
    supplier_name: str
    price_id: int | None
    name_in_price: str
    unit: str
    price: float
    is_preferred: bool
    is_active: bool
    match_source: str
    match_score: float | None


class CanonicalProductOut(BaseModel):
    id: int
    name: str
    default_unit: str
    category: str | None
    notes: str | None
    is_active: bool
    skus: list[SupplierSkuOut]


class CanonicalProductsResponse(BaseModel):
    items: list[CanonicalProductOut]


class CanonicalProductCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    default_unit: str = Field(default="кг")
    category: str | None = None
    notes: str | None = None
    is_active: bool = True


class CanonicalProductUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    default_unit: str
    category: str | None = None
    notes: str | None = None
    is_active: bool = True


class ProductDeleteImpactOut(BaseModel):
    product_id: int
    product_name: str
    sku_count: int
    spec_count: int
    demand_line_count: int
    allocation_count: int
    order_line_count: int
    batch_titles: list[str]


class ProductDeleteResultOut(BaseModel):
    ok: bool
    deleted: ProductDeleteImpactOut


class SupplierSkuCreateRequest(BaseModel):
    supplier_id: int
    name_in_price: str = Field(min_length=1)
    is_preferred: bool = False
    match_source: str = Field(default="manual")


class SupplierSkuUpdateRequest(BaseModel):
    supplier_id: int
    name_in_price: str = Field(min_length=1)
    is_preferred: bool = False
    is_active: bool = True


class ProductSpecOut(BaseModel):
    id: int
    canonical_product_id: int
    version: int
    scope_type: str
    scope_label: str
    scope_summary: str
    scope_location_id: int | None
    scope_department_id: int | None
    scope_supplier_id: int | None
    spec_text: str
    append_to_supplier_order: bool
    valid_from: str | None
    valid_to: str | None
    is_active: bool
    created_at: str | None


class ProductSpecsResponse(BaseModel):
    items: list[ProductSpecOut]


class ProductSpecCreateRequest(BaseModel):
    scope_type: str = Field(default="global")
    scope_location_id: int | None = None
    scope_department_id: int | None = None
    scope_supplier_id: int | None = None
    spec_text: str = Field(min_length=1)
    append_to_supplier_order: bool = True
    valid_from: str | None = None
    valid_to: str | None = None
    is_active: bool = True


class ProductSpecUpdateRequest(BaseModel):
    scope_type: str
    scope_location_id: int | None = None
    scope_department_id: int | None = None
    scope_supplier_id: int | None = None
    spec_text: str = Field(min_length=1)
    append_to_supplier_order: bool = True
    valid_from: str | None = None
    valid_to: str | None = None
    is_active: bool = True


class ProductSpecPreviewRequest(BaseModel):
    supplier_id: int | None = None
    location_id: int | None = None
    department_id: int | None = None


class ProductSpecPreviewOut(BaseModel):
    spec_text: str
    matched_spec_id: int | None
    matched_scope_type: str | None
    matched_scope_label: str | None


class ProcurementBatchCreateRequest(BaseModel):
    plan_label: str = Field(min_length=1, max_length=200)
    responsible: str | None = Field(default=None, max_length=64)


class ProcurementBatchOut(BaseModel):
    id: int
    title: str
    plan_label: str | None = None
    responsible: str | None = None
    status: str
    created_at: str | None
    created_by: str | None
    demand_lines_count: int
    filled_slots_count: int
    total_slots_count: int
    parse_ok_count: int
    parse_problem_count: int
    match_ok_count: int = 0
    match_problem_count: int = 0


class DemandLineOut(BaseModel):
    id: int
    batch_id: int
    location_id: int
    location_name: str
    department_id: int
    department_name: str
    canonical_product_id: int | None
    canonical_product_name: str | None
    raw_text: str
    quantity: float
    unit: str
    normalized_quantity: float | None
    normalized_unit: str | None
    parse_status: str
    line_notes: str | None
    sort_order: int


class SupplierSkuCoverageOut(BaseModel):
    supplier_id: int
    supplier_name: str
    has_sku: bool
    sku_linked: bool = False
    missing_in_price: bool = False
    sku_id: int | None
    name_in_price: str | None
    price: float | None


class ProductSuggestionOut(BaseModel):
    product_id: int
    name: str
    default_unit: str
    score: float


class DemandMatchLineOut(DemandLineOut):
    match_status: str
    demand_name: str
    supplier_skus: list[SupplierSkuCoverageOut]
    suggestions: list[ProductSuggestionOut] = []


class DictionaryGapOut(BaseModel):
    demand_name: str
    default_unit: str
    line_count: int
    line_ids: list[int]


class ProcurementMatchResponse(BaseModel):
    batch_id: int
    batch_status: str
    total_lines: int
    ok_count: int
    problem_count: int
    needs_product_count: int
    needs_sku_count: int
    partial_sku_count: int = 0
    unparsed_count: int
    dictionary_gaps: list[DictionaryGapOut] = []
    items: list[DemandMatchLineOut]
    match_mode: str = "local"
    ai_assigned_count: int = 0
    ai_available: bool = False
    yandex: dict | None = None
    products_missing_price_count: int = 0


class SkuLinkInput(BaseModel):
    supplier_id: int
    name_in_price: str = Field(min_length=1)


class PriceSkuCandidateOut(BaseModel):
    name_in_price: str
    unit: str
    price: float
    score: float


class SupplierSkuSuggestBlockOut(BaseModel):
    supplier_id: int
    supplier_name: str
    candidates: list[PriceSkuCandidateOut]


class ProductSkuSuggestRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    unit: str | None = None


class ProductSkuSuggestResponse(BaseModel):
    product_name: str
    suppliers: list[SupplierSkuSuggestBlockOut]
    ai_used: bool = False


class AddProductFromDemandRequest(BaseModel):
    demand_name: str = Field(min_length=1, max_length=255)
    default_unit: str = Field(default="кг")
    sku_links: list[SkuLinkInput] = []


class AddProductFromDemandResponse(BaseModel):
    product_id: int
    product_name: str
    assigned_lines: int
    skus_created: int = 0
    match: ProcurementMatchResponse


class DemandLineAssignProductRequest(BaseModel):
    canonical_product_id: int


class DemandLineSuggestResponse(BaseModel):
    line_id: int
    demand_name: str
    suggestions: list[ProductSuggestionOut]


class DemandSaveRequest(BaseModel):
    location_id: int
    department_id: int
    order_text: str = Field(min_length=1)


class DemandLinesResponse(BaseModel):
    items: list[DemandLineOut]


class ProductSupplierOverrideRequest(BaseModel):
    supplier_id: int


class SupplierTotalOut(BaseModel):
    supplier_id: int
    supplier_name: str
    amount: float
    min_order_amount: float
    min_order_passed: bool


class ProductAssignmentOut(BaseModel):
    canonical_product_id: int
    canonical_product_name: str
    total_quantity: float
    unit: str
    supplier_id: int
    supplier_name: str
    line_cost: float


class LineAllocationOut(BaseModel):
    allocation_id: int
    demand_line_id: int
    location_name: str
    department_name: str
    raw_text: str
    canonical_product_id: int | None
    canonical_product_name: str | None
    supplier_id: int
    supplier_name: str
    name_in_price: str
    quantity: float
    unit: str
    unit_price: float
    amount: float
    source: str


class ProcurementOptimizeResponse(BaseModel):
    batch_id: int
    batch_status: str
    optimizer_mode: str
    total_amount: float
    warning: str | None
    skipped_lines_count: int
    supplier_totals: list[SupplierTotalOut]
    product_assignments: list[ProductAssignmentOut]
    line_allocations: list[LineAllocationOut]
    available_suppliers: list[dict]
    optimizable_products: list[dict]


class SupplierOrderLineOut(BaseModel):
    id: int
    batch_id: int
    supplier_id: int
    supplier_name: str
    location_id: int
    location_name: str
    department_id: int
    department_name: str
    allocation_id: int
    supplier_product_name: str
    quantity: float
    unit: str
    unit_price: float
    amount: float
    spec_text: str | None
    line_comment: str | None
    sort_order: int


class SupplierOrderGroupOut(BaseModel):
    supplier_id: int
    supplier_name: str
    location_id: int
    location_name: str
    department_id: int
    department_name: str
    lines: list[SupplierOrderLineOut]
    total_amount: float


class SummaryAllocationOut(BaseModel):
    supplier_id: int
    quantity: float
    amount: float
    price: float


class SummaryMatchOut(BaseModel):
    supplier_id: int
    price: float
    name_in_price: str
    note: str | None = None


class SummaryItemOut(BaseModel):
    canonical_product_id: int | None
    canonical_name: str
    unit: str
    quantity: float
    matches: list[SummaryMatchOut]
    allocation: list[SummaryAllocationOut]
    row_total: float
    comment: str = ""
    has_allocation: bool = True


class SummaryProblemOut(BaseModel):
    demand_line_id: int
    raw_text: str
    location_name: str = ""
    department_name: str = ""
    canonical_product_name: str | None = None
    reason: str


class ProcurementSummaryResponse(BaseModel):
    batch_id: int
    batch_title: str
    batch_status: str
    total_amount: float
    currency: str
    location_id: int | None
    location_name: str | None
    department_id: int | None
    department_name: str | None
    suppliers: list[dict]
    supplier_ids: list[int]
    supplier_totals: list[dict]
    items: list[SummaryItemOut]
    problems: list[SummaryProblemOut]
    items_count: int
    problems_count: int


class SupplierOrdersResponse(BaseModel):
    batch_id: int
    batch_title: str
    batch_status: str
    created_at: str | None
    lines_count: int
    groups_count: int
    groups: list[SupplierOrderGroupOut]
    lines: list[SupplierOrderLineOut]
    suppliers: list[dict]
    locations: list[dict]
    departments: list[dict]


class SupplierOrderCommentUpdate(BaseModel):
    line_comment: str = ""
