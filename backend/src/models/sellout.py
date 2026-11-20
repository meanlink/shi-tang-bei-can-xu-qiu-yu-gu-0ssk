from sqlalchemy import String, Double, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base


class SelloutDay(Base):
    """售罄日登记：当日午餐卖光，实领份数只是真实需求的下限。"""
    __tablename__ = 'sellout_days'
    __table_args__ = (UniqueConstraint('dataset_id', 'date', name='uq_sellout_dataset_date'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'), index=True)
    date: Mapped[str] = mapped_column(String(10))
    meal: Mapped[str] = mapped_column(String(120))
    served: Mapped[float] = mapped_column(Double)
    expected_vouchers: Mapped[int] = mapped_column(Integer, default=1)
    note: Mapped[str] = mapped_column(String(500), default='')
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)


class SupplementBatch(Base):
    """按凭证分批补报的未领份数。同一售罄日的凭证号唯一，重试不会重复入账。"""
    __tablename__ = 'supplement_batches'
    __table_args__ = (UniqueConstraint('sellout_id', 'voucher_no', name='uq_supplement_voucher'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    sellout_id: Mapped[int] = mapped_column(ForeignKey('sellout_days.id'), index=True)
    voucher_no: Mapped[str] = mapped_column(String(80))
    portions: Mapped[float] = mapped_column(Double)
    note: Mapped[str] = mapped_column(String(500), default='')
    reported_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
