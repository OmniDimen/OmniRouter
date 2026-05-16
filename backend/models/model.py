from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base


class Model(Base):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(Integer, ForeignKey("providers.id"))
    model_id: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200), unique=True)
    has_vision: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    provider: Mapped["Provider"] = relationship("Provider", back_populates="models")
    group_links: Mapped[list["GroupModel"]] = relationship(
        "GroupModel", back_populates="model", cascade="all, delete-orphan"
    )
