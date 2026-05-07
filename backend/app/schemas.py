from pydantic import BaseModel, Field


class SupplierOut(BaseModel):
    id: int
    name: str
    min_order_amount: float
    price_items_count: int
    last_price_upload_at: str | None


class SuppliersResponse(BaseModel):
    items: list[SupplierOut]


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
