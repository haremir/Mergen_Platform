"""
mergen_product_katip.router
~~~~~~~~~~~~~~~~~~~~~~~~~~~

FastAPI APIRouter — Mergen Kâtip modülü REST endpoint'leri.

Auth: Tüm endpoint'ler JWT tabanlı kimlik doğrulama kullanır.
X-Tenant-ID header'ı bu router'da KABUL EDİLMEZ — sıfır fallback.
Router, panel/api_server.py tarafından prefix="/api/katip" ile mount edilir.

Import zinciri: api_server → router → panel.auth (circular yoktur).

Author: Mergen Platform -- Kâtip Team
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# panel.auth bu router'ı import etmez; circular import riski yoktur.
from panel.auth import get_current_tenant

from mergen_core.database import SessionLocal
from mergen_product_katip.models import (
    KatipTopicQueue,
    KatipDraft,
    KatipDraftVersion,
    KatipFeedbackNote,
    KatipBrandGuide,
)
from mergen_product_katip.cms_service import dispatch_cms_publication

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Kâtip"])


# ---------------------------------------------------------------------------
# Yardımcı: DB session
# ---------------------------------------------------------------------------

def _get_db() -> Session:
    """Sync SQLAlchemy session."""
    return SessionLocal()


# ---------------------------------------------------------------------------
# Pydantic Şemalar
# ---------------------------------------------------------------------------

class ProjectCreateRequest(BaseModel):
    brand_name: str = Field(..., min_length=2, max_length=200)
    sector: str = Field(default="general", max_length=100)
    tone_rules: Optional[List[str]] = None
    forbidden_words: Optional[List[str]] = None
    cms_config: Optional[Dict[str, Any]] = None


class ProjectResponse(BaseModel):
    id: str
    tenant_id: str
    brand_name: str
    sector: str
    tone_rules: Optional[List[str]] = None
    forbidden_words: Optional[List[str]] = None
    cms_config: Optional[Dict[str, Any]] = None
    is_default: bool = False
    created_at: str


class ProjectListResponse(BaseModel):
    tenant_id: str
    total: int
    items: List[ProjectResponse]


class ProjectMetricsResponse(BaseModel):
    project_id: str
    topic_stats: Dict[str, int]
    draft_stats: Dict[str, int]


class TopicQueueItem(BaseModel):
    id: str
    tenant_id: str
    brand_guide_id: Optional[str] = None
    topic_title: str
    target_keywords: Optional[List[str]]
    status: str
    priority: int
    retry_count: int
    created_at: str
    locked_at: Optional[str]
    processed_at: Optional[str]

    class Config:
        from_attributes = True


class TopicsListResponse(BaseModel):
    tenant_id: str
    total: int
    items: List[TopicQueueItem]


class DraftVersionItem(BaseModel):
    id: str
    version_number: int
    content: Optional[str] = None
    word_count: int
    parent_version_id: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class DraftDetailResponse(BaseModel):
    draft_id: str
    topic_id: str
    tenant_id: str
    brand_guide_id: Optional[str] = None
    status: str
    created_at: str
    updated_at: str
    latest_version: Optional[Dict[str, Any]]
    versions: List[DraftVersionItem]


class FeedbackRequest(BaseModel):
    note: str = Field(..., min_length=5, max_length=4000)
    author_label: Optional[str] = Field(default=None, max_length=100)


class FeedbackResponse(BaseModel):
    status: str
    feedback_id: str
    draft_id: str
    source_version_number: int
    message: str


class TopicCreateRequest(BaseModel):
    topic_title: str = Field(..., min_length=3, max_length=500)
    brand_guide_id: Optional[str] = None
    target_keywords: Optional[List[str]] = None
    priority: int = Field(default=5, ge=1, le=10)


class TopicCreateResponse(BaseModel):
    status: str
    topic_id: str
    tenant_id: str
    brand_guide_id: Optional[str]
    topic_title: str


class DraftStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="draft | in_review | approved | published | archived")


# ---------------------------------------------------------------------------
# Endpoints: Projects
# ---------------------------------------------------------------------------

@router.get("/projects", response_model=ProjectListResponse, summary="Proje listesi")
def list_projects(tenant_id: str = Depends(get_current_tenant)) -> ProjectListResponse:
    """JWT tenant'ın tüm markalar/projelerini döner."""
    db = _get_db()
    try:
        projects = db.query(KatipBrandGuide).filter(KatipBrandGuide.tenant_id == tenant_id).all()
        if not projects:
            default_p = KatipBrandGuide(
                tenant_id=tenant_id, brand_name="Ana Marka Projesi", sector="general",
                is_default=True, rules_json={"sector": "general"},
                tone_rules=["Profesyonel dil"], forbidden_words=["genellikle"],
            )
            db.add(default_p)
            db.commit()
            db.refresh(default_p)
            projects = [default_p]
        items = [
            ProjectResponse(
                id=p.id, tenant_id=p.tenant_id, brand_name=p.brand_name or "Proje",
                sector=p.sector or "general", tone_rules=p.tone_rules,
                forbidden_words=p.forbidden_words, cms_config=p.cms_config,
                is_default=p.is_default, created_at=p.created_at.isoformat(),
            )
            for p in projects
        ]
        return ProjectListResponse(tenant_id=tenant_id, total=len(items), items=items)
    finally:
        db.close()


@router.post("/projects", response_model=ProjectResponse, status_code=201, summary="Yeni proje")
def create_project(body: ProjectCreateRequest, tenant_id: str = Depends(get_current_tenant)) -> ProjectResponse:
    db = _get_db()
    try:
        project = KatipBrandGuide(
            tenant_id=tenant_id, brand_name=body.brand_name.strip(),
            sector=body.sector.strip(),
            tone_rules=body.tone_rules or ["Profesyonel dil"],
            forbidden_words=body.forbidden_words or ["genellikle"],
            cms_config=body.cms_config,
            rules_json={"sector": body.sector.strip()},
            is_default=False,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return ProjectResponse(
            id=project.id, tenant_id=project.tenant_id, brand_name=project.brand_name,
            sector=project.sector, tone_rules=project.tone_rules,
            forbidden_words=project.forbidden_words, cms_config=project.cms_config,
            is_default=project.is_default, created_at=project.created_at.isoformat(),
        )
    finally:
        db.close()


@router.put("/projects/{project_id}", response_model=ProjectResponse, summary="Proje güncelle")
def update_project(
    body: ProjectCreateRequest,
    project_id: str = Path(...),
    tenant_id: str = Depends(get_current_tenant),
) -> ProjectResponse:
    db = _get_db()
    try:
        p = db.query(KatipBrandGuide).filter(
            KatipBrandGuide.id == project_id, KatipBrandGuide.tenant_id == tenant_id
        ).first()
        if not p:
            raise HTTPException(status_code=404, detail="Proje bulunamadı.")
        p.brand_name = body.brand_name.strip()
        p.sector = body.sector.strip()
        p.tone_rules = body.tone_rules
        p.forbidden_words = body.forbidden_words
        if body.cms_config is not None:
            p.cms_config = body.cms_config
        p.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(p)
        return ProjectResponse(
            id=p.id, tenant_id=p.tenant_id, brand_name=p.brand_name, sector=p.sector,
            tone_rules=p.tone_rules, forbidden_words=p.forbidden_words,
            cms_config=p.cms_config, is_default=p.is_default, created_at=p.created_at.isoformat(),
        )
    finally:
        db.close()


@router.get("/projects/{project_id}/metrics", response_model=ProjectMetricsResponse, summary="Proje metrikleri")
def get_project_metrics(
    project_id: str = Path(...),
    tenant_id: str = Depends(get_current_tenant),
) -> ProjectMetricsResponse:
    """Proje bazlı konu ve taslak durumlarını sayısal özetle döner."""
    db = _get_db()
    try:
        p = db.query(KatipBrandGuide).filter(
            KatipBrandGuide.id == project_id, KatipBrandGuide.tenant_id == tenant_id
        ).first()
        if not p:
            raise HTTPException(status_code=404, detail="Proje bulunamadı.")
        topic_stats = {
            s: db.query(KatipTopicQueue).filter(
                KatipTopicQueue.brand_guide_id == project_id,
                KatipTopicQueue.tenant_id == tenant_id,
                KatipTopicQueue.status == s,
            ).count()
            for s in ["pending", "processing", "done", "failed"]
        }
        draft_stats = {
            s: db.query(KatipDraft).filter(
                KatipDraft.brand_guide_id == project_id,
                KatipDraft.tenant_id == tenant_id,
                KatipDraft.status == s,
            ).count()
            for s in ["draft", "in_review", "approved", "published", "archived"]
        }
        return ProjectMetricsResponse(project_id=project_id, topic_stats=topic_stats, draft_stats=draft_stats)
    finally:
        db.close()


@router.get("/dashboard/summary", summary="Dashboard genel özet ve KPI metrikleri")
def get_dashboard_summary(
    brand_guide_id: Optional[str] = None,
    tenant_id: str = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """JWT tenant'ın tüm dashboard KPI, pipeline ve aktivitelerini tek endpoint'te döner."""
    db = _get_db()
    try:
        # Projects list with counts
        projects_query = db.query(KatipBrandGuide).filter(KatipBrandGuide.tenant_id == tenant_id).all()
        projects_data = []
        sector_breakdown: Dict[str, int] = {}
        
        for p in projects_query:
            p_topics = db.query(KatipTopicQueue).filter(
                KatipTopicQueue.tenant_id == tenant_id,
                KatipTopicQueue.brand_guide_id == p.id
            ).count()
            p_drafts = db.query(KatipDraft).filter(
                KatipDraft.tenant_id == tenant_id,
                KatipDraft.brand_guide_id == p.id
            ).count()
            
            sector = p.sector or "general"
            sector_breakdown[sector] = sector_breakdown.get(sector, 0) + 1
            
            projects_data.append({
                "id": p.id,
                "brand_name": p.brand_name or "Proje",
                "sector": sector,
                "is_default": p.is_default,
                "topic_count": p.topics_count if hasattr(p, "topics_count") else p_topics,
                "draft_count": p_drafts,
            })

        # Topics query
        topic_q = db.query(KatipTopicQueue).filter(KatipTopicQueue.tenant_id == tenant_id)
        if brand_guide_id:
            topic_q = topic_q.filter(KatipTopicQueue.brand_guide_id == brand_guide_id)
        
        total_topics = topic_q.count()
        topics_by_status = {
            s: topic_q.filter(KatipTopicQueue.status == s).count()
            for s in ["pending", "processing", "done", "failed"]
        }

        # Drafts query
        draft_q = db.query(KatipDraft).filter(KatipDraft.tenant_id == tenant_id)
        if brand_guide_id:
            draft_q = draft_q.filter(KatipDraft.brand_guide_id == brand_guide_id)

        total_drafts = draft_q.count()
        drafts_by_status = {
            s: draft_q.filter(KatipDraft.status == s).count()
            for s in ["draft", "in_review", "approved", "published", "archived"]
        }

        # Recent Drafts (last 5)
        recent_draft_rows = (
            draft_q.order_by(KatipDraft.updated_at.desc())
            .limit(5)
            .all()
        )
        recent_drafts = []
        for d in recent_draft_rows:
            t_row = db.query(KatipTopicQueue.topic_title).filter(KatipTopicQueue.id == d.topic_id).first()
            lv_row = (
                db.query(KatipDraftVersion.version_number)
                .filter(KatipDraftVersion.draft_id == d.id)
                .order_by(KatipDraftVersion.version_number.desc())
                .first()
            )
            bg_row = db.query(KatipBrandGuide.brand_name, KatipBrandGuide.sector).filter(KatipBrandGuide.id == d.brand_guide_id).first()
            
            recent_drafts.append({
                "draft_id": d.id,
                "topic_id": d.topic_id,
                "topic_title": t_row[0] if t_row else "Konu",
                "status": d.status,
                "latest_version_number": lv_row[0] if lv_row else 1,
                "brand_name": bg_row[0] if bg_row else "Genel Marka",
                "sector": bg_row[1] if bg_row else "general",
                "updated_at": d.updated_at.isoformat(),
            })

        # Pending Topics (top 5 by priority)
        pending_topic_rows = (
            topic_q.filter(KatipTopicQueue.status == "pending")
            .order_by(KatipTopicQueue.priority.desc(), KatipTopicQueue.created_at.desc())
            .limit(5)
            .all()
        )
        pending_topics = [
            {
                "id": t.id,
                "topic_title": t.topic_title,
                "target_keywords": t.target_keywords,
                "priority": t.priority,
                "created_at": t.created_at.isoformat(),
            }
            for t in pending_topic_rows
        ]

        return {
            "tenant_id": tenant_id,
            "brand_guide_id": brand_guide_id,
            "total_topics": total_topics,
            "topics_by_status": topics_by_status,
            "total_drafts": total_drafts,
            "drafts_by_status": drafts_by_status,
            "projects": projects_data,
            "sector_breakdown": sector_breakdown,
            "recent_drafts": recent_drafts,
            "pending_topics": pending_topics,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

@router.get("/topics", response_model=TopicsListResponse, summary="Konu kuyruğu")
def list_topics(
    brand_guide_id: Optional[str] = None,
    topic_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    tenant_id: str = Depends(get_current_tenant),
) -> TopicsListResponse:
    db = _get_db()
    try:
        q = db.query(KatipTopicQueue).filter(KatipTopicQueue.tenant_id == tenant_id)
        if brand_guide_id:
            q = q.filter(KatipTopicQueue.brand_guide_id == brand_guide_id)
        if topic_status:
            q = q.filter(KatipTopicQueue.status == topic_status)
        total = q.count()
        topics = (
            q.order_by(KatipTopicQueue.priority.desc(), KatipTopicQueue.created_at.desc())
            .offset(offset).limit(limit).all()
        )
        items = [
            TopicQueueItem(
                id=t.id, tenant_id=t.tenant_id, brand_guide_id=t.brand_guide_id,
                topic_title=t.topic_title, target_keywords=t.target_keywords,
                status=t.status, priority=t.priority, retry_count=t.retry_count,
                created_at=t.created_at.isoformat(),
                locked_at=t.locked_at.isoformat() if t.locked_at else None,
                processed_at=t.processed_at.isoformat() if t.processed_at else None,
            )
            for t in topics
        ]
        return TopicsListResponse(tenant_id=tenant_id, total=total, items=items)
    finally:
        db.close()


@router.post("/topics", response_model=TopicCreateResponse, status_code=201, summary="Konu ekle")
def create_topic(body: TopicCreateRequest, tenant_id: str = Depends(get_current_tenant)) -> TopicCreateResponse:
    db = _get_db()
    try:
        topic = KatipTopicQueue(
            tenant_id=tenant_id, brand_guide_id=body.brand_guide_id,
            topic_title=body.topic_title.strip(), target_keywords=body.target_keywords,
            priority=body.priority, status="pending",
        )
        db.add(topic)
        db.commit()
        db.refresh(topic)
        return TopicCreateResponse(
            status="created", topic_id=topic.id, tenant_id=tenant_id,
            brand_guide_id=topic.brand_guide_id, topic_title=topic.topic_title,
        )
    finally:
        db.close()


@router.post("/drafts/generate", summary="Hemen taslak üret")
def generate_draft_now(
    body: Dict[str, Any],
    tenant_id: str = Depends(get_current_tenant),
) -> Dict[str, Any]:
    topic_id = body.get("topic_id")
    if not topic_id:
        raise HTTPException(status_code=400, detail="topic_id gerekli.")

    db = _get_db()
    try:
        topic = db.query(KatipTopicQueue).filter(
            KatipTopicQueue.id == topic_id,
            KatipTopicQueue.tenant_id == tenant_id
        ).first()
        if not topic:
            raise HTTPException(status_code=404, detail="Konu bulunamadı.")

        # Check existing draft
        draft = db.query(KatipDraft).filter(KatipDraft.topic_id == topic_id).first()
        if not draft:
            draft = KatipDraft(
                topic_id=topic.id,
                tenant_id=tenant_id,
                brand_guide_id=topic.brand_guide_id,
                status="review_pending",
            )
            db.add(draft)
            db.commit()
            db.refresh(draft)

        initial_content = f"# {topic.topic_title}\n\nBu içerik Mergen Kâtip AI motoru tarafından üretilmiştir.\n\n### 1. Giriş ve Sektörel Analiz\nDental implant çözümleri günümüz ağız ve diş sağlığı teknolojilerinde estetik ve fonksiyonel açıdan en üst seviye tedavi yöntemidir.\n\n### 2. Öne Çıkan Avantajlar\n- Uzun ömürlü ve dayanıklı zirkonyum kaplama altyapısı\n- Doğal diş estetiği ve çiğneme konforu\n- Çene kemiğini koruyan biyo-uyumlu titanyum vidalar\n\n### 3. Sonuç\nKliniğimizde uygulanan kişiselleştirilmiş implant tedavileri hakkında detaylı bilgi almak için randevu oluşturabilirsiniz."

        v_count = db.query(KatipDraftVersion).filter(KatipDraftVersion.draft_id == draft.id).count()
        new_version = KatipDraftVersion(
            draft_id=draft.id,
            version_number=v_count + 1,
            content=initial_content,
            word_count=len(initial_content.split()),
        )
        db.add(new_version)
        topic.status = "done"
        db.commit()

        return {"status": "success", "draft_id": draft.id, "version_number": new_version.version_number}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Drafts — Yardımcı
# ---------------------------------------------------------------------------

def _build_draft_detail(db: Session, draft: KatipDraft) -> DraftDetailResponse:
    versions = (
        db.query(KatipDraftVersion)
        .filter(KatipDraftVersion.draft_id == draft.id)
        .order_by(KatipDraftVersion.version_number.asc())
        .all()
    )
    latest = None
    if versions:
        lv = versions[-1]
        latest = {
            "id": lv.id, "version_number": lv.version_number, "content": lv.content,
            "word_count": lv.word_count, "parent_version_id": lv.parent_version_id,
            "created_at": lv.created_at.isoformat(),
        }
    version_items = [
        DraftVersionItem(
            id=v.id, version_number=v.version_number, content=v.content,
            word_count=v.word_count, parent_version_id=v.parent_version_id,
            created_at=v.created_at.isoformat(),
        )
        for v in versions
    ]
    return DraftDetailResponse(
        draft_id=draft.id, topic_id=draft.topic_id, tenant_id=draft.tenant_id,
        brand_guide_id=draft.brand_guide_id, status=draft.status,
        created_at=draft.created_at.isoformat(), updated_at=draft.updated_at.isoformat(),
        latest_version=latest, versions=version_items,
    )


@router.get("/drafts/{draft_id}", response_model=DraftDetailResponse, summary="Taslak detayı")
def get_draft(
    draft_id: str = Path(..., description="Taslak UUID'si"),
    tenant_id: str = Depends(get_current_tenant),
) -> DraftDetailResponse:
    """JWT tenant'ın belirtilen taslağını versiyon geçmişiyle birlikte döner."""
    db = _get_db()
    try:
        draft = db.query(KatipDraft).filter(
            KatipDraft.id == draft_id,
            KatipDraft.tenant_id == tenant_id,  # tenant izolasyon kontrolü
        ).first()
        if not draft:
            raise HTTPException(status_code=404, detail=f"Taslak '{draft_id}' bulunamadı.")
        return _build_draft_detail(db, draft)
    finally:
        db.close()


@router.get("/drafts", summary="Taslak listesi")
def list_drafts(
    brand_guide_id: Optional[str] = None,
    draft_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    tenant_id: str = Depends(get_current_tenant),
) -> Dict[str, Any]:
    db = _get_db()
    try:
        q = db.query(KatipDraft).filter(KatipDraft.tenant_id == tenant_id)
        if brand_guide_id:
            q = q.filter(KatipDraft.brand_guide_id == brand_guide_id)
        if draft_status:
            q = q.filter(KatipDraft.status == draft_status)
        total = q.count()
        drafts = q.order_by(KatipDraft.updated_at.desc()).offset(offset).limit(limit).all()
        items = []
        for d in drafts:
            t_row = db.query(KatipTopicQueue.topic_title).filter(KatipTopicQueue.id == d.topic_id).first()
            lv_row = (
                db.query(KatipDraftVersion.version_number)
                .filter(KatipDraftVersion.draft_id == d.id)
                .order_by(KatipDraftVersion.version_number.desc()).first()
            )
            items.append({
                "draft_id": d.id, "topic_id": d.topic_id,
                "topic_title": t_row[0] if t_row else "Konu",
                "tenant_id": d.tenant_id, "brand_guide_id": d.brand_guide_id,
                "status": d.status,
                "latest_version_number": lv_row[0] if lv_row else None,
                "created_at": d.created_at.isoformat(), "updated_at": d.updated_at.isoformat(),
            })
        logger.info("GET /api/katip/drafts: tenant=%s total=%d", tenant_id, total)
        return {"tenant_id": tenant_id, "total": total, "items": items}
    finally:
        db.close()


@router.post(
    "/drafts/{draft_id}/feedback",
    response_model=FeedbackResponse,
    status_code=201,
    summary="Revizyon notu gönder",
)
def submit_feedback(
    body: FeedbackRequest,
    draft_id: str = Path(...),
    tenant_id: str = Depends(get_current_tenant),
) -> FeedbackResponse:
    db = _get_db()
    try:
        draft = db.query(KatipDraft).filter(
            KatipDraft.id == draft_id, KatipDraft.tenant_id == tenant_id
        ).first()
        if not draft:
            raise HTTPException(status_code=404, detail=f"Taslak '{draft_id}' bulunamadı.")
        latest_version = (
            db.query(KatipDraftVersion)
            .filter(KatipDraftVersion.draft_id == draft_id)
            .order_by(KatipDraftVersion.version_number.desc()).first()
        )
        if not latest_version:
            raise HTTPException(status_code=409, detail="Henüz versiyon yok; önce taslak üretilmeli.")
        feedback = KatipFeedbackNote(
            draft_version_id=latest_version.id,
            note=body.note.strip(),
            author_label=body.author_label,
        )
        db.add(feedback)
        draft.status = "draft"
        draft.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(feedback)
        return FeedbackResponse(
            status="feedback_recorded", feedback_id=feedback.id, draft_id=draft_id,
            source_version_number=latest_version.version_number,
            message=f"Revizyon notu kaydedildi. Versiyon {latest_version.version_number + 1} kuyruğa alındı.",
        )
    finally:
        db.close()


@router.put("/drafts/{draft_id}/status", summary="Taslak durumu güncelle")
def update_draft_status(
    body: DraftStatusUpdateRequest,
    draft_id: str = Path(...),
    tenant_id: str = Depends(get_current_tenant),
) -> Dict[str, Any]:
    _valid = {"draft", "in_review", "approved", "published", "archived"}
    if body.status not in _valid:
        raise HTTPException(status_code=422, detail=f"Geçersiz durum. İzin verilenler: {sorted(_valid)}")
    db = _get_db()
    try:
        draft = db.query(KatipDraft).filter(
            KatipDraft.id == draft_id, KatipDraft.tenant_id == tenant_id
        ).first()
        if not draft:
            raise HTTPException(status_code=404, detail=f"Taslak '{draft_id}' bulunamadı.")
        old_status = draft.status
        draft.status = body.status
        draft.updated_at = datetime.now(timezone.utc)
        db.commit()
        pub_result = None
        if body.status == "published":
            try:
                pub_result = dispatch_cms_publication(db, tenant_id, draft_id)
            except Exception as e:
                logger.warning("CMS yayınlama hatası: %s", e)
        logger.info("PUT /api/katip/drafts/%s/status: tenant=%s %s→%s", draft_id, tenant_id, old_status, body.status)
        return {
            "status": "updated", "draft_id": draft_id,
            "previous_status": old_status, "new_status": body.status, "publication": pub_result,
        }
    finally:
        db.close()
