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
        logger.warning("_resolve_tenant lookup warning for tenant '%s': %s", tid, exc)
    return tid


# ---------------------------------------------------------------------------
# Pydantic Şemalar — router içinde tutulur (panel/schemas.py'den izole)
# ---------------------------------------------------------------------------

class TopicQueueItem(BaseModel):
    id: str
    tenant_id: str
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
    target_keywords: Optional[List[str]] = Field(default=None)
    priority: int = Field(default=5, ge=1, le=10)


class TopicCreateResponse(BaseModel):
    status: str
    topic_id: str
    tenant_id: str
    topic_title: str


class GenerateDraftRequest(BaseModel):
    topic_id: str = Field(..., description="Kuyruktaki konunun UUID'si")


class GenerateDraftResponse(BaseModel):
    status: str
    draft_id: str
    version_id: str
    version_number: int
    word_count: int
    model_used: str
    latency_ms: int
    token_count: int


class RegenerateRequest(BaseModel):
    feedback_note: str = Field(..., min_length=5, max_length=4000, description="Editörün revizyon notu (yeni versiyon için)")
    author_label: Optional[str] = Field(default=None, max_length=100)


class RegenerateResponse(BaseModel):
    status: str
    draft_id: str
    feedback_id: str
    new_version_id: str
    new_version_number: int
    word_count: int
    latency_ms: int


# ---------------------------------------------------------------------------
# Endpoint: POST /drafts/generate — Yeni taslak üret (v1)
# ---------------------------------------------------------------------------

@router.post(
    "/drafts/generate",
    response_model=GenerateDraftResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Konu kuyruğundaki bir konu için v1 taslak üret",
    description=(
        "Belirtilen topic_id'ye ait konuyu alarak Prompt Engine + RAG + LLM Gateway "
        "üzerinden ilk taslağı (v1) üretir ve veritabanına kaydeder. "
        "Konu zaten işlenmişse idempotent yanıt döner."
    ),
)
def generate_draft(
    body: GenerateDraftRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> GenerateDraftResponse:
    tenant_id = _resolve_tenant(x_tenant_id)
    db = _get_db()
    try:
        result = generate_draft_for_topic(
            db=db,
            tenant_id=tenant_id,
            topic_id=body.topic_id,
            prompt_engine=_prompt_engine,
        )
        return GenerateDraftResponse(
            status=result["status"],
            draft_id=result["draft_id"],
            version_id=result["version_id"],
            version_number=result.get("version_number", 1),
            word_count=result.get("word_count", 0),
            model_used=result.get("model_used", "unknown"),
            latency_ms=result.get("latency_ms", 0),
            token_count=result.get("token_count", 0),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("POST /api/katip/drafts/generate HATA: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoint: POST /drafts/{draft_id}/regenerate — Feedback ile yeni versiyon üret (v2+)
# ---------------------------------------------------------------------------

@router.post(
    "/drafts/{draft_id}/regenerate",
    response_model=RegenerateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Editör notu ile yeni taslak versiyonu üret (v2+)",
    description=(
        "Editörün girdiği revizyon notunu dikkate alarak mevcut son versiyonu temel alıp "
        "yeni bir versiyon (v2, v3 …) üretir. FeedbackNote kaydı oluşturulur, "
        "ardından LLM Gateway çağrılır ve yeni DraftVersion DB'ye yazılır."
    ),
)
def regenerate_draft(
    body: RegenerateRequest,
    draft_id: str = Path(..., description="Taslak UUID'si"),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> RegenerateResponse:
    tenant_id = _resolve_tenant(x_tenant_id)
    db = _get_db()
    try:
        res = revise_existing_draft(
            db=db,
            tenant_id=tenant_id,
            draft_id=draft_id,
            feedback_text=body.feedback_note.strip(),
            author_label=body.author_label,
            prompt_engine=_prompt_engine,
        )
        return RegenerateResponse(
            status=res["status"],
            draft_id=res["draft_id"],
            feedback_id=res["feedback_id"],
            new_version_id=res["new_version_id"],
            new_version_number=res["new_version_number"],
            word_count=res["word_count"],
            latency_ms=res["latency_ms"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    finally:
        db.close()




@router.get(
    "/tenants",
    status_code=status.HTTP_200_OK,
    summary="Kâtip sistemindeki tüm kayıtlı kiracı/ajans listesini getir",
)
def get_katip_tenants() -> Dict[str, Any]:
    tm = get_tenant_manager()
    tenants = tm.list_tenants()
    return {
        "total": len(tenants),
        "items": tenants,
    }


@router.get(
    "/topics",
    response_model=TopicsListResponse,
    status_code=status.HTTP_200_OK,
    summary="Tenant'ın konu kuyruğunu listele",
    description=(
        "TopicsQueue tablosundaki konuları döndürür. "
        "status parametresiyle filtrelenebilir (pending, done, failed vb.)."
    ),
)
def list_topics(
    topic_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> TopicsListResponse:
    tenant_id = _resolve_tenant(x_tenant_id)
    db = _get_db()
    try:
        query = db.query(KatipTopicQueue).filter(
            KatipTopicQueue.tenant_id == tenant_id
        )
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

        logger.info(
            "GET /api/katip/topics: tenant=%s total=%d status_filter=%s",
            tenant_id, total, topic_status,
        )
        return TopicsListResponse(tenant_id=tenant_id, total=total, items=items)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoint: POST /topics — Manuel konu ekle
# ---------------------------------------------------------------------------

@router.post(
    "/topics",
    response_model=TopicCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Konu kuyruğuna manuel konu ekle",
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
            topic_title=body.topic_title.strip(),
            target_keywords=body.target_keywords,
            priority=body.priority,
            status="pending",
        )
        db.add(topic)
        db.commit()
        db.refresh(topic)

        logger.info(
            "POST /api/katip/topics: tenant=%s topic_id=%s title='%s'",
            tenant_id, topic.id, topic.topic_title,
        )
        return TopicCreateResponse(
            status="created",
            topic_id=topic.id,
            tenant_id=tenant_id,
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
    summary="Tenant'ın tüm taslak listesini getir",
)
def list_drafts(
    draft_status: Optional[str] = None,
    limit: int = 30,
    offset: int = 0,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> Dict[str, Any]:
    tenant_id = _resolve_tenant(x_tenant_id)
    db = _get_db()
    try:
        query = db.query(KatipDraft).filter(KatipDraft.tenant_id == tenant_id)
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
            # Her taslak için en son versiyon numarasını çek
            latest_version_row = (
                db.query(KatipDraftVersion.version_number)
                .filter(KatipDraftVersion.draft_id == d.id)
                .order_by(KatipDraftVersion.version_number.desc())
                .first()
            )
            items.append({
                "draft_id": d.id,
                "topic_id": d.topic_id,
                "tenant_id": d.tenant_id,
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
