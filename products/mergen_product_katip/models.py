"""
mergen_product_katip.models
~~~~~~~~~~~~~~~~~~~~~~~~~~~

SQLAlchemy ORM modelleri — Mergen Kâtip modülü için tüm veritabanı şeması.

Tasarım kararları:
- BrandGuides: token_count sütunu prompt budget kontrolü için tutulur;
  her güncelleme sonrası llm_gateway.count_tokens() ile yeniden hesaplanmalı.
- ExampleArticles ve RevisionPatterns: pgvector entegrasyonu için ARRAY(Float)
  embedding sütunu taşır; SQLite geliştirme ortamında bu sütun JSON olarak
  serialize edilemez, sadece PostgreSQL'de aktif kullanılır.
- DraftVersions.parent_version_id: self-referential FK ile versiyon ağacı
  (tree) tutulur. UNIQUE(draft_id, version_number) çakışmayı DB seviyesinde engeller.
- GenerationLog: hangi prompt ve hangi feedback notu ile hangi versiyonun
  üretildiğini tam olarak kayıt altına alır; maliyet takibi ve debugging için kritik.

Author: Mergen Platform -- Kâtip Team
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from mergen_core.database import Base


# ---------------------------------------------------------------------------
# Yardımcı
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# BrandGuides — Proje/Marka Kuralları (B2B Proje Hiyerarşisi)
# ---------------------------------------------------------------------------

class KatipBrandGuide(Base):
    """
    Ajansın (Tenant) altındaki bağımsız Marka/Proje kaydı.
    Örn: DentSmile Klinik, Elite İnşaat vb.
    """

    __tablename__ = "katip_brand_guides"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    brand_name: Mapped[str] = mapped_column(String(200), nullable=False, default="Genel Marka Projesi")
    sector: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    rules_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    tone_rules: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    forbidden_words: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    cms_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_katip_brand_guides_tenant", "tenant_id"),
    )


# ---------------------------------------------------------------------------
# ExampleArticles — referans makaleler (RAG üzerinden top-k getirilir)
# ---------------------------------------------------------------------------

class KatipExampleArticle(Base):
    """
    Tenant/BrandGuide'a ait örnek/referans makaleler.
    """

    __tablename__ = "katip_example_articles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    brand_guide_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("katip_brand_guides.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_katip_example_articles_tenant", "tenant_id"),
        Index("ix_katip_example_articles_brand", "brand_guide_id"),
    )


# ---------------------------------------------------------------------------
# RevisionPatterns — geçmiş düzeltme örnekleri (Proje bazlı RAG izolasyonu)
# ---------------------------------------------------------------------------

class KatipRevisionPattern(Base):
    """
    Editörün geçmişte talep ettiği düzeltmelerin özeti.
    Hafıza zehirlenmesini önlemek için brand_guide_id ve sector ile izole edilir.
    """

    __tablename__ = "katip_revision_patterns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    brand_guide_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("katip_brand_guides.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    original_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    revised_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    pattern_tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    embedding: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_katip_revision_patterns_tenant", "tenant_id"),
        Index("ix_katip_revision_patterns_brand", "brand_guide_id"),
    )


# ---------------------------------------------------------------------------
# TopicsQueue — üretim bekleyen konular (Proje bazlı)
# ---------------------------------------------------------------------------

class KatipTopicQueue(Base):
    """
    Scheduler tarafından tüketilen konu kuyruğu.
    """

    __tablename__ = "katip_topics_queue"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    brand_guide_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("katip_brand_guides.id", ondelete="SET NULL"), nullable=True, index=True
    )
    topic_title: Mapped[str] = mapped_column(String(500), nullable=False)
    target_keywords: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # İlişkiler
    drafts: Mapped[List["KatipDraft"]] = relationship("KatipDraft", back_populates="topic", lazy="select")

    __table_args__ = (
        Index("ix_katip_topics_queue_status_tenant", "status", "tenant_id"),
        Index("ix_katip_topics_queue_brand", "brand_guide_id"),
    )


# ---------------------------------------------------------------------------
# Drafts — taslak kök tablosu
# ---------------------------------------------------------------------------

class KatipDraft(Base):
    """
    Taslak kök tablosu — bir konuya ait tüm versiyonların çatısı.
    """

    __tablename__ = "katip_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    topic_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("katip_topics_queue.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    brand_guide_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("katip_brand_guides.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    # İlişkiler
    topic: Mapped["KatipTopicQueue"] = relationship("KatipTopicQueue", back_populates="drafts")
    versions: Mapped[List["KatipDraftVersion"]] = relationship(
        "KatipDraftVersion", back_populates="draft", lazy="select",
        foreign_keys="KatipDraftVersion.draft_id"
    )

    __table_args__ = (
        Index("ix_katip_drafts_tenant_status", "tenant_id", "status"),
        Index("ix_katip_drafts_brand", "brand_guide_id"),
    )


# ---------------------------------------------------------------------------
# DraftVersions — versiyonlanmış taslak içeriği (ağaç yapısı)
# ---------------------------------------------------------------------------

class KatipDraftVersion(Base):
    """
    Taslak versiyonları.

    parent_version_id: self-referential FK — hangi versiyondan türetildi.
    Ağaç yapısında kök versiyonlar için NULL.

    UNIQUE(draft_id, version_number): aynı taslakta çakışan versiyon numarasını
    uygulama katmanına güvenmeden DB seviyesinde engeller.
    """

    __tablename__ = "katip_draft_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    draft_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("katip_drafts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Self-referential FK: bu versiyonun türetildiği ebeveyn versiyon
    parent_version_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("katip_draft_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # İlişkiler
    draft: Mapped["KatipDraft"] = relationship(
        "KatipDraft", back_populates="versions", foreign_keys=[draft_id]
    )
    parent: Mapped[Optional["KatipDraftVersion"]] = relationship(
        "KatipDraftVersion",
        remote_side="KatipDraftVersion.id",
        foreign_keys=[parent_version_id],
        lazy="select",
    )
    children: Mapped[List["KatipDraftVersion"]] = relationship(
        "KatipDraftVersion",
        back_populates="parent",
        foreign_keys=[parent_version_id],
        lazy="select",
    )
    feedback_notes: Mapped[List["KatipFeedbackNote"]] = relationship(
        "KatipFeedbackNote", back_populates="draft_version", lazy="select"
    )
    generation_logs: Mapped[List["KatipGenerationLog"]] = relationship(
        "KatipGenerationLog", back_populates="draft_version", lazy="select"
    )

    __table_args__ = (
        # Aynı taslakta aynı versiyon numarası olamaz
        UniqueConstraint("draft_id", "version_number", name="uq_katip_draft_version"),
        Index("ix_katip_draft_versions_draft", "draft_id"),
    )


# ---------------------------------------------------------------------------
# FeedbackNotes — editör revizyon notları
# ---------------------------------------------------------------------------

class KatipFeedbackNote(Base):
    """
    Editörün belirli bir versiyon için girdiği revizyon notu.

    Bu not bir sonraki DraftVersion üretiminde prompta eklenir.
    GenerationLog.feedback_note_id üzerinden hangi versiyonun bu nottan
    üretildiği takip edilir.
    """

    __tablename__ = "katip_feedback_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    draft_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("katip_draft_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)
    author_label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # İlişkiler
    draft_version: Mapped["KatipDraftVersion"] = relationship(
        "KatipDraftVersion", back_populates="feedback_notes"
    )
    generation_logs: Mapped[List["KatipGenerationLog"]] = relationship(
        "KatipGenerationLog", back_populates="feedback_note", lazy="select"
    )


# ---------------------------------------------------------------------------
# GenerationLog — her LLM çağrısının tam kaydı
# ---------------------------------------------------------------------------

class KatipGenerationLog(Base):
    """
    Her LLM üretim çağrısının teknik kaydı.

    prompt_hash: SHA-256 — aynı prompt'un tekrar çağrılmasını tespit eder.
    token_count: giriş + çıkış toplamı — maliyet hesaplaması için.
    model_used: llm_gateway'in seçtiği gerçek model slug'ı (ör. "qwen-turbo").
    feedback_note_id: NULL ise ilk üretim; doluysa hangi feedbackten türetildi.
    """

    __tablename__ = "katip_generation_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    draft_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("katip_draft_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feedback_note_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("katip_feedback_notes.id", ondelete="SET NULL"), nullable=True
    )
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # İlişkiler
    draft_version: Mapped["KatipDraftVersion"] = relationship(
        "KatipDraftVersion", back_populates="generation_logs"
    )
    feedback_note: Mapped[Optional["KatipFeedbackNote"]] = relationship(
        "KatipFeedbackNote", back_populates="generation_logs"
    )

    __table_args__ = (
        Index("ix_katip_gen_log_draft_version", "draft_version_id"),
        Index("ix_katip_gen_log_feedback", "feedback_note_id"),
    )
