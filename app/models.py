from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BatchRun(Base):
    __tablename__ = "batch_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items_fetched: Mapped[int] = mapped_column(Integer, default=0)
    flags_extracted: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[str] = mapped_column(String(32), index=True)
    source_name: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    red_flags: Mapped[list["RedFlag"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class RedFlag(Base):
    __tablename__ = "red_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"), index=True)
    category: Mapped[str] = mapped_column(String(128), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    text: Mapped[str] = mapped_column(Text)
    confidence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[SourceDocument] = relationship(back_populates="red_flags")
