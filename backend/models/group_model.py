from sqlalchemy import Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base


class GroupModel(Base):
    __tablename__ = "group_models"
    __table_args__ = (
        UniqueConstraint("group_id", "model_id", name="uq_group_model"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id"))
    model_id: Mapped[int] = mapped_column(Integer, ForeignKey("models.id"))
    weight: Mapped[int] = mapped_column(Integer, default=1)

    group: Mapped["Group"] = relationship("Group", back_populates="model_links")
    model: Mapped["Model"] = relationship("Model", back_populates="group_links")
