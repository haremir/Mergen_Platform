"""
mergen_product_katip.router
~~~~~~~~~~~~~~~~~~~~~~~~~~~

FastAPI APIRouter — Mergen Kâtip modülü REST endpoint'leri.

Tüm endpoint'ler X-Tenant-ID header'ını zorunlu tutar.
Router, panel/api_server.py tarafından prefix="/api/katip" ile mount edilir.

Auth notu: Bu router şu aşamada header-based tenant kimliği kullanır.
Üretim ortamında JWT middleware buraya eklenmelidir.

Author: Mergen Platform -- Kâtip Team
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from mergen_core.database import SessionLocal
from mergen_core.tenant_manager import get_tenant_manager, TenantNotFoundError
from mergen_product_katip.models import (
    KatipTopicQueue,
    KatipDraft,
    KatipDraftVersion,
    KatipFeedbackNote,
    KatipGenerationLog,
    KatipBrandGuide,
)
from mergen_product_katip.draft_service import generate_draft_for_topic, revise_existing_draft
from mergen_product_katip.prompt_engine import KatipPromptEngine
from mergen_product_katip.cms_service import dispatch_cms_publication

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Kâtip"])

# Singleton prompt engine — model her request'te yüklenmez
_prompt_engine = KatipPromptEngine()


# ---------------------------------------------------------------------------
# Yardımcı: DB session bağımlılığı
# ---------------------------------------------------------------------------

def _get_db() -> Session:
    """Sync SQLAlchemy session (mevcut api_server.py ile uyumlu)."""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def _resolve_tenant(tenant_id: str) -> str:
    """
    X-Tenant-ID'yi tenant_manager üzerinden doğrula.
    Bulunamazsa otomatik olarak yeni tenant oluşturur ve Katip verilerini initialize eder.
    """
    if not tenant_id or not tenant_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID header zorunludur.",
        )
    tid = tenant_id.strip()
    tm = get_tenant_manager()
    try:
        tm.get_tenant_by_id(tid)
    except TenantNotFoundError:
        # Otomatik tenant oluştur ve kaydet
        try:
            from mergen_common.models import Tenant
            new_t = Tenant(
                tenant_id=tid,
                business_name=f"Ajans / İşletme {tid}",
                sector="other",
                plan="starter",
                whatsapp_phone_number_id="",
                created_at=datetime.now(timezone.utc),
                persona="friendly_energetic",
                telegram_token=None,
            )
            tm.create_tenant(new_t)

            # KatipBrandGuide ve ilk başlangıç konusunu ekle
            db = SessionLocal()
            try:
                bg = db.query(KatipBrandGuide).filter(KatipBrandGuide.tenant_id == tid).first()
                if not bg:
                    bg = KatipBrandGuide(
                        tenant_id=tid,
                        sector="other",
                        target_audience=f"{tid} Hedef Kitlesi",
                        rules_json={
                            "tone": "friendly_energetic",
                            "forbidden_words": ["genellikle", "bazı", "gibi", "benzer"],
                            "sector_notes": f"{tid} için otomatik Kâtip yayınlama kuralları.",
                        },
                    )
                    db.add(bg)
                    topic1 = KatipTopicQueue(
                        tenant_id=tid,
                        topic_title=f"{tid} - İlk Otomatik Blog ve İçerik Rehberi",
                        target_keywords=["rehber", "kalite", "otonomi"],
                        priority=8,
                        status="pending",
                    )
                    db.add(topic1)
                    db.commit()
                    logger.info("Katip auto-provisioned BrandGuide & topic for tenant '%s'", tid)
            finally:
                db.close()
        except Exception as inner_exc:
            logger.error("Failed to auto-create tenant '%s': %s", tid, inner_exc, exc_info=True)
    except Exception as exc:
        logger.warning("_resolve_tenant lookup warning: %s", exc)

# ---------------------------------------------------------------------------
# Pydantic Şemalar — Proje / BrandGuide & Kuyruk
# ---------------------------------------------------------------------------

class ProjectCreateRequest(BaseModel):
    brand_name: str = Field(..., min_length=2, max_length=200, description="Marka veya Proje adı")
    sector: str = Field(default="general", max_length=100, description="Sektör (ör. dental_clinic, real_estate)")
    tone_rules: Optional[List[str]] = Field(default=None)
    forbidden_words: Optional[List[str]] = Field(default=None)
    cms_config: Optional[Dict[str, Any]] = Field(default=None, description="WordPress URL/Pass veya Webhook ayarları")


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
    note: str = Field(..., min_length=5, max_length=4000, description="Editör revizyon notu.")
    author_label: Optional[str] = Field(default=None, max_length=100)


class FeedbackResponse(BaseModel):
    status: str
    feedback_id: str
    draft_id: str
    source_version_number: int
    message: str


class TopicCreateRequest(BaseModel):
    topic_title: str = Field(..., min_length=3, max_length=500)
    brand_guide_id: Optional[str] = Field(default=None, description="Bağlı olduğu Proje/BrandGuide ID")
    target_keywords: Optional[List[str]] = Field(default=None)
    priority: int = Field(default=5, ge=1, le=10)


class TopicCreateResponse(BaseModel):
    status: str
    topic_id: str
    tenant_id: str
    brand_guide_id: Optional[str]
    topic_title: str


# ---------------------------------------------------------------------------
# Endpoints: Projects (Marka/Proje Yönetimi)
# ---------------------------------------------------------------------------

@router.get(
    "/projects",
    response_model=ProjectListResponse,
    status_code=status.HTTP_200_OK,
    summary="Ajansın tüm alt marka/projelerini listele",
)
def list_projects(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> ProjectListResponse:
    tenant_id = _resolve_tenant(x_tenant_id)
    db = _get_db()
    try:
        projects = db.query(KatipBrandGuide).filter(KatipBrandGuide.tenant_id == tenant_id).all()
        
        # Eğer henüz proje yoksa varsayılan ana projeyi oluştur
        if not projects:
            default_p = KatipBrandGuide(
                tenant_id=tenant_id,
                brand_name="Ana Marka Projesi",
                sector="dental_clinic",
                is_default=True,
                rules_json={"sector": "dental_clinic"},
                tone_rules=["Profesyonel ve otoriter uzman hekim dili"],
                forbidden_words=["genellikle", "bazı"],
            )
            db.add(default_p)
            db.commit()
            db.refresh(default_p)
            projects = [default_p]

        items = [
            ProjectResponse(
                id=p.id,
                tenant_id=p.tenant_id,
                brand_name=p.brand_name or "Proje",
                sector=p.sector or "general",
                tone_rules=p.tone_rules,
                forbidden_words=p.forbidden_words,
                cms_config=p.cms_config,
                is_default=p.is_default,
                created_at=p.created_at.isoformat(),
            )
            for p in projects
        ]
        return ProjectListResponse(tenant_id=tenant_id, total=len(items), items=items)
    finally:
        db.close()


@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yeni marka/proje ekle",
)
def create_project(
    body: ProjectCreateRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> ProjectResponse:
    tenant_id = _resolve_tenant(x_tenant_id)
    db = _get_db()
    try:
        project = KatipBrandGuide(
            tenant_id=tenant_id,
            brand_name=body.brand_name.strip(),
            sector=body.sector.strip(),
            tone_rules=body.tone_rules or ["Profesyonel uzman dili"],
            forbidden_words=body.forbidden_words or ["genellikle"],
            cms_config=body.cms_config,
            rules_json={"sector": body.sector.strip()},
            is_default=False,
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        return ProjectResponse(
            id=project.id,
            tenant_id=project.tenant_id,
            brand_name=project.brand_name,
            sector=project.sector,
            tone_rules=project.tone_rules,
            forbidden_words=project.forbidden_words,
            cms_config=project.cms_config,
            is_default=project.is_default,
            created_at=project.created_at.isoformat(),
        )
    finally:
        db.close()


@router.put(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Marka/proje ayarlarını güncelle",
)
def update_project(
    body: ProjectCreateRequest,
    project_id: str = Path(..., description="Project UUID"),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> ProjectResponse:
    tenant_id = _resolve_tenant(x_tenant_id)
    db = _get_db()
    try:
        project = db.query(KatipBrandGuide).filter(
            KatipBrandGuide.id == project_id,
            KatipBrandGuide.tenant_id == tenant_id
        ).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proje bulunamadı.")

        project.brand_name = body.brand_name.strip()
        project.sector = body.sector.strip()
        project.tone_rules = body.tone_rules
        project.forbidden_words = body.forbidden_words
        if body.cms_config is not None:
            project.cms_config = body.cms_config
        project.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(project)

        return ProjectResponse(
            id=project.id,
            tenant_id=project.tenant_id,
            brand_name=project.brand_name,
            sector=project.sector,
            tone_rules=project.tone_rules,
            forbidden_words=project.forbidden_words,
            cms_config=project.cms_config,
            is_default=project.is_default,
            created_at=project.created_at.isoformat(),
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoint: GET /topics — Konu kuyruğunu listele
# ---------------------------------------------------------------------------

@router.get(
    "/topics",
    response_model=TopicsListResponse,
    status_code=status.HTTP_200_OK,
    summary="Tenant/Proje konu kuyruğunu listele",
)
def list_topics(
    brand_guide_id: Optional[str] = None,
    topic_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> TopicsListResponse:
    tenant_id = _resolve_tenant(x_tenant_id)
    db = _get_db()
    try:
        query = db.query(KatipTopicQueue).filter(KatipTopicQueue.tenant_id == tenant_id)
        if brand_guide_id:
            query = query.filter(KatipTopicQueue.brand_guide_id == brand_guide_id)
        if topic_status:
            query = query.filter(KatipTopicQueue.status == topic_status)

        total = query.count()
        topics = (
            query.order_by(
                KatipTopicQueue.priority.desc(),
                KatipTopicQueue.created_at.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        items = [
            TopicQueueItem(
                id=t.id,
                tenant_id=t.tenant_id,
                brand_guide_id=t.brand_guide_id,
                topic_title=t.topic_title,
                target_keywords=t.target_keywords,
                status=t.status,
                priority=t.priority,
                retry_count=t.retry_count,
                created_at=t.created_at.isoformat(),
                locked_at=t.locked_at.isoformat() if t.locked_at else None,
                processed_at=t.processed_at.isoformat() if t.processed_at else None,
            )
            for t in topics
        ]

        return TopicsListResponse(tenant_id=tenant_id, total=total, items=items)
    finally:
        db.close()


@router.post(
    "/topics",
    response_model=TopicCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Konu kuyruğuna yeni konu ekle",
)
def create_topic(
    body: TopicCreateRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> TopicCreateResponse:
    tenant_id = _resolve_tenant(x_tenant_id)
    db = _get_db()
    try:
        topic = KatipTopicQueue(
            tenant_id=tenant_id,
            brand_guide_id=body.brand_guide_id,
            topic_title=body.topic_title.strip(),
            target_keywords=body.target_keywords,
            priority=body.priority,
            status="pending",
        )
        db.add(topic)
        db.commit()
        db.refresh(topic)

        return TopicCreateResponse(
            status="created",
            topic_id=topic.id,
            tenant_id=tenant_id,
            brand_guide_id=topic.brand_guide_id,
            topic_title=topic.topic_title,
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoint: GET /drafts/{draft_id} — Taslak detayı + versiyon geçmişi
# ---------------------------------------------------------------------------

@router.get(
    "/drafts/{draft_id}",
    response_model=DraftDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Taslak detayını ve versiyon geçmişini getir",
)
def get_draft(
    draft_id: str = Path(..., description="Taslak UUID'si"),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> DraftDetailResponse:
    tenant_id = _resolve_tenant(x_tenant_id)
    db = _get_db()
    try:
        draft = (
            db.query(KatipDraft)
            .filter(
                KatipDraft.id == draft_id,
                KatipDraft.tenant_id == tenant_id,  # tenant izolasyon kontrolü
            )
            .first()
        )
        if not draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Taslak '{draft_id}' bulunamadı.",
            )

        versions = (
            db.query(KatipDraftVersion)
            .filter(KatipDraftVersion.draft_id == draft_id)
            .order_by(KatipDraftVersion.version_number.asc())
            .all()
        )

        # En son versiyonun tam içeriğini de döndür
        latest: Optional[Dict[str, Any]] = None
        if versions:
            lv = versions[-1]
            latest = {
                "id": lv.id,
                "version_number": lv.version_number,
                "content": lv.content,
                "word_count": lv.word_count,
                "parent_version_id": lv.parent_version_id,
                "created_at": lv.created_at.isoformat(),
            }

        version_items = [
            DraftVersionItem(
                id=v.id,
                version_number=v.version_number,
                content=v.content,
                word_count=v.word_count,
                parent_version_id=v.parent_version_id,
                created_at=v.created_at.isoformat(),
            )
            for v in versions
        ]

        logger.info(
            "GET /api/katip/drafts/%s: tenant=%s version_count=%d",
            draft_id, tenant_id, len(versions),
        )
        return DraftDetailResponse(
            draft_id=draft.id,
            topic_id=draft.topic_id,
            tenant_id=draft.tenant_id,
            status=draft.status,
            created_at=draft.created_at.isoformat(),
            updated_at=draft.updated_at.isoformat(),
            latest_version=latest,
            versions=version_items,
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoint: GET /drafts — Taslak listesi
# ---------------------------------------------------------------------------

@router.get(
    "/drafts",
    status_code=status.HTTP_200_OK,
    summary="Tenant/Proje taslak listesini getir",
)
def list_drafts(
    brand_guide_id: Optional[str] = None,
    draft_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> Dict[str, Any]:
    tenant_id = _resolve_tenant(x_tenant_id)
    db = _get_db()
    try:
        query = db.query(KatipDraft).filter(KatipDraft.tenant_id == tenant_id)
        if brand_guide_id:
            query = query.filter(KatipDraft.brand_guide_id == brand_guide_id)
        if draft_status:
            query = query.filter(KatipDraft.status == draft_status)

        total = query.count()
        drafts = (
            query.order_by(KatipDraft.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        items = []
        for d in drafts:
            # Topic başlığını da çek
            t_row = db.query(KatipTopicQueue.topic_title).filter(KatipTopicQueue.id == d.topic_id).first()
            latest_version_row = (
                db.query(KatipDraftVersion.version_number)
                .filter(KatipDraftVersion.draft_id == d.id)
                .order_by(KatipDraftVersion.version_number.desc())
                .first()
            )
            items.append({
                "draft_id": d.id,
                "topic_id": d.topic_id,
                "topic_title": t_row[0] if t_row else "Konu",
                "tenant_id": d.tenant_id,
                "brand_guide_id": d.brand_guide_id,
                "status": d.status,
                "latest_version_number": latest_version_row[0] if latest_version_row else None,
                "created_at": d.created_at.isoformat(),
                "updated_at": d.updated_at.isoformat(),
            })

        logger.info(
            "GET /api/katip/drafts: tenant=%s total=%d status_filter=%s",
            tenant_id, total, draft_status,
        )
        return {"tenant_id": tenant_id, "total": total, "items": items}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoint: POST /drafts/{draft_id}/feedback — Revizyon notu gönder
# ---------------------------------------------------------------------------

@router.post(
    "/drafts/{draft_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Taslak için revizyon notu gönder",
    description=(
        "Editörün girdiği revizyon notunu FeedbackNotes tablosuna kaydeder "
        "ve yeni bir DraftVersion üretimi için sinyal oluşturur. "
        "Bu endpoint notu kayıt altına alır; asenkron scheduler yeni versiyonu üretir."
    ),
)
def submit_feedback(
    body: FeedbackRequest,
    draft_id: str = Path(..., description="Taslak UUID'si"),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> FeedbackResponse:
    tenant_id = _resolve_tenant(x_tenant_id)
    db = _get_db()
    try:
        # 1. Taslak var mı ve bu tenant'a mı ait?
        draft = (
            db.query(KatipDraft)
            .filter(
                KatipDraft.id == draft_id,
                KatipDraft.tenant_id == tenant_id,
            )
            .first()
        )
        if not draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Taslak '{draft_id}' bulunamadı.",
            )

        # 2. En son versiyonu bul — feedback bu versiyona bağlanır
        latest_version = (
            db.query(KatipDraftVersion)
            .filter(KatipDraftVersion.draft_id == draft_id)
            .order_by(KatipDraftVersion.version_number.desc())
            .first()
        )
        if not latest_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bu taslağa ait henüz bir versiyon yok; önce taslak üretilmeli.",
            )

        # 3. FeedbackNote kaydını oluştur
        feedback = KatipFeedbackNote(
            draft_version_id=latest_version.id,
            note=body.note.strip(),
            author_label=body.author_label,
        )
        db.add(feedback)

        # 4. Taslak durumunu "in_review" → "draft" geri al (yeni versiyon bekliyor)
        draft.status = "draft"
        draft.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(feedback)

        logger.info(
            "POST /api/katip/drafts/%s/feedback: tenant=%s feedback_id=%s source_version=%d",
            draft_id, tenant_id, feedback.id, latest_version.version_number,
        )
        return FeedbackResponse(
            status="feedback_recorded",
            feedback_id=feedback.id,
            draft_id=draft_id,
            source_version_number=latest_version.version_number,
            message=(
                f"Revizyon notu kaydedildi. "
                f"Versiyon {latest_version.version_number + 1} üretim kuyruğuna alındı."
            ),
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoint: PUT /drafts/{draft_id}/status — Taslak durumu güncelle
# ---------------------------------------------------------------------------

class DraftStatusUpdateRequest(BaseModel):
    status: str = Field(
        ...,
        description="Yeni durum: draft | in_review | approved | published | archived",
    )


@router.put(
    "/drafts/{draft_id}/status",
    status_code=status.HTTP_200_OK,
    summary="Taslak durumunu güncelle",
)
def update_draft_status(
    body: DraftStatusUpdateRequest,
    draft_id: str = Path(..., description="Taslak UUID'si"),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> Dict[str, Any]:
    _valid_statuses = {"draft", "in_review", "approved", "published", "archived"}
    if body.status not in _valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Geçersiz durum. İzin verilen değerler: {sorted(_valid_statuses)}",
        )

    tenant_id = _resolve_tenant(x_tenant_id)
    db = _get_db()
    try:
        draft = (
            db.query(KatipDraft)
            .filter(
                KatipDraft.id == draft_id,
                KatipDraft.tenant_id == tenant_id,
            )
            .first()
        )
        if not draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Taslak '{draft_id}' bulunamadı.",
            )

        old_status = draft.status
        draft.status = body.status
        draft.updated_at = datetime.now(timezone.utc)
        db.commit()

        pub_result = None
        if body.status == "published":
            try:
                pub_result = dispatch_cms_publication(db, tenant_id, draft_id)
            except Exception as pub_err:
                logger.warning("CMS yayınlama tetikleme hatası: %s", pub_err)

        logger.info(
            "PUT /api/katip/drafts/%s/status: tenant=%s %s→%s",
            draft_id, tenant_id, old_status, body.status,
        )
        return {
            "status": "updated",
            "draft_id": draft_id,
            "previous_status": old_status,
            "new_status": body.status,
            "publication": pub_result,
        }
    finally:
        db.close()
