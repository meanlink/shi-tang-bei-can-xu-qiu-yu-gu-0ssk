from sqlalchemy import String, JSON, Double, Integer
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class Dataset(Base):
    __tablename__ = 'datasets'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    source: Mapped[str] = mapped_column(String(200), default='manual.json')
    records: Mapped[list] = mapped_column(JSON)
    checksum: Mapped[str] = mapped_column(String(64))
    # 售罄登记与补报的版本号；任何补报都会递增，用于判断分析依据是否过期。
    sellout_revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[float] = mapped_column(Double)
