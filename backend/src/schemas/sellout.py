from pydantic import BaseModel, Field


class SelloutInput(BaseModel):
    date: str = Field(min_length=10, max_length=10)
    served: float | None = None
    expected_vouchers: int = Field(default=1, ge=1, le=50)
    note: str = Field(default='', max_length=500)


class SupplementInput(BaseModel):
    voucher_no: str = Field(min_length=1, max_length=80)
    portions: float
    note: str = Field(default='', max_length=500)
