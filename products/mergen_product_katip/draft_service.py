"""
mergen_product_katip.draft_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Katip Draft Generation Service — Konu kuyruğundan konu alıp Qwen LLM
üzerinden ilk taslağı (v1) üreten iş mantığı servisi.

Özellikler:
- Idempotency & Locking (locked_at, processed_at)
- KatipPromptEngine ile RAG destekli prompt inşası
- LLM Gateway entegrasyonu (Qwen 2.5 32B Instruct / fallback mock)
- Versiyonlama ve GenerationLog kayıtları

Author: Mergen Platform -- Kâtip Team
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from mergen_core.llm_gateway import get_gateway
from mergen_product_katip.models import (
    KatipDraft,
    KatipDraftVersion,
    KatipFeedbackNote,
    KatipGenerationLog,
    KatipTopicQueue,
)
from mergen_product_katip.prompt_engine import KatipPromptEngine

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _compute_hash(text_content: str) -> str:
    return hashlib.sha256(text_content.encode("utf-8")).hexdigest()


def generate_draft_for_topic(
    db: Session,
    tenant_id: str,
    topic_id: str,
    prompt_engine: Optional[KatipPromptEngine] = None,
) -> Dict[str, Any]:
    """
    Belirtilen konu için ilk taslak versiyonunu (v1) üretir ve veritabanına işler.

    Args:
        db: Sync SQLAlchemy Session
        tenant_id: Müşteri UUID'si
        topic_id: TopicsQueue ID'si
        prompt_engine: İsteğe bağlı KatipPromptEngine örneği

    Returns:
        {
            "status": "success",
            "draft_id": str,
            "version_id": str,
            "version_number": 1,
            "word_count": int,
            "model_used": str,
            "latency_ms": int,
            "token_count": int
        }
    """
    if prompt_engine is None:
        prompt_engine = KatipPromptEngine()

    start_time = time.time()

    # 1. Konu var mı ve işlenebilir durumda mı?
    topic = db.query(KatipTopicQueue).filter(
        KatipTopicQueue.id == topic_id,
        KatipTopicQueue.tenant_id == tenant_id,
    ).first()

    if not topic:
        raise ValueError(f"Konu '{topic_id}' bulunamadı (Tenant: {tenant_id}).")

    if topic.status == "done":
        logger.info("Konu '%s' zaten işlenmiş, tekrar üretilmiyor.", topic_id)
        existing_draft = db.query(KatipDraft).filter(KatipDraft.topic_id == topic_id).first()
        if existing_draft:
            latest = db.query(KatipDraftVersion).filter(KatipDraftVersion.draft_id == existing_draft.id).order_by(KatipDraftVersion.version_number.desc()).first()
            return {
                "status": "already_processed",
                "draft_id": existing_draft.id,
                "version_id": latest.id if latest else "",
                "version_number": latest.version_number if latest else 1,
            }

    # Kilit koy
    topic.status = "processing"
    topic.locked_at = _utcnow()
    db.commit()

    try:
        # 2. Prompt Engine ile Zengin Prompt Üret
        prompt_data = prompt_engine.build_prompt(
            db=db,
            tenant_id=tenant_id,
            topic_title=topic.topic_title,
            target_keywords=topic.target_keywords,
        )

        sys_prompt = prompt_data["system_prompt"]
        usr_prompt = prompt_data["user_prompt"]
        full_text = prompt_data["full_prompt_text"]

        # 3. LLM Gateway Çağrısı (Qwen 2.5)
        gateway = get_gateway()
        model_name = "qwen/qwen-2.5-72b-instruct"

        if hasattr(gateway, "route"):
            generated_content = gateway.route(
                query=usr_prompt,
                system_prompt=sys_prompt,
                tenant_id=tenant_id,
                temperature=0.7,
                max_tokens=2048,
                model=model_name,
            )
        elif hasattr(gateway, "complete"):
            generated_content = gateway.complete(
                prompt=usr_prompt,
                system_prompt=sys_prompt,
                model=model_name,
            )
        else:
            raise AttributeError("LLMGateway does not have route or complete method")

        latency_ms = int((time.time() - start_time) * 1000)
        words = len(generated_content.split())
        approx_tokens = len(full_text.split()) + len(generated_content.split())
        prompt_hash = _compute_hash(full_text)

        # 4. KatipDraft Kök Kaydı Oluştur
        draft = KatipDraft(
            topic_id=topic_id,
            tenant_id=tenant_id,
            status="draft",
        )
        db.add(draft)
        db.flush()

        # 5. KatipDraftVersion (v1) Oluştur
        draft_version = KatipDraftVersion(
            draft_id=draft.id,
            version_number=1,
            content=generated_content,
            word_count=words,
            parent_version_id=None,
        )
        db.add(draft_version)
        db.flush()

        # 6. KatipGenerationLog Kaydı Oluştur
        gen_log = KatipGenerationLog(
            draft_version_id=draft_version.id,
            feedback_note_id=None,
            prompt_hash=prompt_hash,
            token_count=approx_tokens,
            model_used=model_name,
            latency_ms=latency_ms,
        )
        db.add(gen_log)

        # 7. TopicsQueue Durumunu Güncelle
        topic.status = "done"
        topic.processed_at = _utcnow()

        db.commit()

        logger.info(
            "Taslak v1 başarıyla üretildi! DraftID: %s VersionID: %s Kelime: %d Süre: %dms",
            draft.id, draft_version.id, words, latency_ms
        )

        return {
            "status": "success",
            "draft_id": draft.id,
            "version_id": draft_version.id,
            "version_number": 1,
            "word_count": words,
            "model_used": model_name,
            "latency_ms": latency_ms,
            "token_count": approx_tokens,
        }

    except Exception as exc:
        db.rollback()
        topic.status = "failed"
        topic.retry_count += 1
        topic.error_message = str(exc)
        db.commit()
        logger.exception("Taslak üretimi başarısız oldu (Topic: %s): %s", topic_id, exc)
        raise


def revise_existing_draft(
    db: Session,
    tenant_id: str,
    draft_id: str,
    feedback_text: str,
    author_label: Optional[str] = None,
    prompt_engine: Optional[KatipPromptEngine] = None,
) -> Dict[str, Any]:
    """
    Editör revizyon notunu dikkate alarak mevcut taslak için strüktürel ChatML mesaj
    dizisi ile yeni bir versiyon (v2, v3 ...) üretir.

    Args:
        db: Sync SQLAlchemy Session
        tenant_id: Müşteri UUID'si
        draft_id: KatipDraft UUID'si
        feedback_text: Editörün revizyon/düzeltme notu
        author_label: Opsiyonel editör etiketi/imza
        prompt_engine: İsteğe bağlı KatipPromptEngine örneği

    Returns:
        {
            "status": "regenerated",
            "draft_id": str,
            "feedback_id": str,
            "new_version_id": str,
            "new_version_number": int,
            "word_count": int,
            "latency_ms": int,
        }
    """
    if prompt_engine is None:
        prompt_engine = KatipPromptEngine()

    start_t = time.time()

    # 1. Taslak ve tenant kontrolü
    draft = (
        db.query(KatipDraft)
        .filter(KatipDraft.id == draft_id, KatipDraft.tenant_id == tenant_id)
        .first()
    )
    if not draft:
        raise ValueError(f"Taslak '{draft_id}' bulunamadı (Tenant: {tenant_id}).")

    # 2. Kaynak (en son) versiyonu bul
    latest_version = (
        db.query(KatipDraftVersion)
        .filter(KatipDraftVersion.draft_id == draft_id)
        .order_by(KatipDraftVersion.version_number.desc())
        .first()
    )
    if not latest_version:
        raise ValueError(f"Taslak '{draft_id}' için henüz bir versiyon bulunmuyor.")

    old_draft_content = latest_version.content

    # 3. FeedbackNote kaydı oluştur
    feedback = KatipFeedbackNote(
        draft_version_id=latest_version.id,
        note=feedback_text.strip(),
        author_label=author_label,
    )
    db.add(feedback)
    db.flush()

    # 4. Konu başlığını ve anahtar kelimeleri çek
    topic = db.query(KatipTopicQueue).filter(KatipTopicQueue.id == draft.topic_id).first()
    topic_title = topic.topic_title if topic else "Konu"
    target_keywords = topic.target_keywords if topic else []

    # 5. Prompt Engine'den System Prompt Al
    prompt_data = prompt_engine.build_prompt(
        db=db,
        tenant_id=tenant_id,
        topic_title=topic_title,
        target_keywords=target_keywords,
        additional_feedback=feedback_text.strip(),
    )
    system_prompt = prompt_data["system_prompt"]

    # 6. Strüktürel ChatML Mesaj Dizisi (Array Dict) İnşası
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Konu: {topic_title}\n\n"
                f"Önceki Taslağın:\n{old_draft_content}\n\n"
                f"Bu taslak reddedildi. Editörün Revizyon Notu: {feedback_text.strip()}\n\n"
                f"GÖREV: Editörün notunu HARFİYEN uygulayarak, başlıktaki spesifik soruyu cevaplayan, "
                f"en az 800 kelimelik yeni bir versiyon yaz. Eski metni kopyalama."
            ),
        },
    ]

    # 7. LLM Gateway Çağrısı (Array Dict Yapısı ile)
    gateway = get_gateway()
    model_name = "qwen/qwen-2.5-72b-instruct"

    try:
        if hasattr(gateway, "route_messages"):
            generated_content = gateway.route_messages(
                messages=messages,
                tenant_id=tenant_id,
                temperature=0.65,
                max_tokens=2048,
                model=model_name,
            )
        elif hasattr(gateway, "route"):
            generated_content = gateway.route(
                query=messages[1]["content"],
                system_prompt=system_prompt,
                tenant_id=tenant_id,
                temperature=0.65,
                max_tokens=2048,
                model=model_name,
            )
        else:
            raise AttributeError("LLMGateway does not have route or route_messages method")
    except Exception as exc:
        db.rollback()
        draft.status = "failed"
        db.commit()
        logger.error("Revizyon LLM Gateway çağrısı başarısız oldu", exc_info=True)
        raise

    latency_ms = int((time.time() - start_t) * 1000)
    words = len(generated_content.split())
    full_text = f"=== SYSTEM ===\n{system_prompt}\n\n=== USER ===\n{messages[1]['content']}"
    prompt_hash = _compute_hash(full_text)
    new_version_number = latest_version.version_number + 1

    # 8. Yeni DraftVersion (v2+) Oluştur
    new_version = KatipDraftVersion(
        draft_id=draft_id,
        version_number=new_version_number,
        content=generated_content,
        word_count=words,
        parent_version_id=latest_version.id,
    )
    db.add(new_version)
    db.flush()

    # 9. GenerationLog Kaydı Oluştur
    gen_log = KatipGenerationLog(
        draft_version_id=new_version.id,
        feedback_note_id=feedback.id,
        prompt_hash=prompt_hash,
        token_count=len(full_text.split()) + words,
        model_used=model_name,
        latency_ms=latency_ms,
    )
    db.add(gen_log)

    # 10. Taslak Durumunu Güncelle
    draft.status = "draft"
    draft.updated_at = _utcnow()
    db.commit()

    logger.info(
        "Taslak v%d başarıyla revize edildi! DraftID: %s NewVersionID: %s Kelime: %d Süre: %dms",
        new_version_number, draft_id, new_version.id, words, latency_ms
    )

    return {
        "status": "regenerated",
        "draft_id": draft_id,
        "feedback_id": feedback.id,
        "new_version_id": new_version.id,
        "new_version_number": new_version_number,
        "word_count": words,
        "latency_ms": latency_ms,
    }
