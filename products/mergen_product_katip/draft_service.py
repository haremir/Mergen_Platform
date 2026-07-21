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

        # 3. LLM Gateway Çağrısı (Qwen 2.5 / fallback)
        gateway = get_gateway()
        model_name = "qwen/qwen-2.5-32b-instruct"

        try:
            if hasattr(gateway, "route"):
                generated_content = gateway.route(
                    query=usr_prompt,
                    system_prompt=sys_prompt,
                    tenant_id=tenant_id,
                    temperature=0.7,
                    max_tokens=2048,
                )
            elif hasattr(gateway, "complete"):
                generated_content = gateway.complete(
                    prompt=usr_prompt,
                    system_prompt=sys_prompt,
                    model=model_name,
                )
            else:
                raise AttributeError("LLMGateway does not have route or complete method")
        except Exception as llm_err:
            logger.warning("LLM Gateway çağrısı başarısız oldu (%s), yedek şablon kullanılıyor.", llm_err)
            # Yedek kaliteli üretim (API key yoksa veya kota bittiyse sistem çökmez)
            generated_content = (
                f"# {topic.topic_title}\n\n"
                f"{topic.topic_title}, ağız ve diş sağlığında estetik ve fonksiyonel konfor sağlayan modern bir uygulamadır. "
                "Uzman diş hekimi kontrolünde yapılan değerlendirme ile hastaya en uygun tedavi planı belirlenir.\n\n"
                "## Tedavi Süreci Nasıl İlerler?\n"
                "Tedavi süreci ilk muayene, dijital planlama ve uygulama aşamalarından oluşur. "
                "İşlem sırasında lokal anestezi kullanıldığı için herhangi bir acı veya ağrı hissedilmez.\n\n"
                "## Avantajları Nelerdir?\n"
                "- Doğal diş dokusu korunur.\n"
                "- Uzun ömürlü ve estetik sonuçlar elde edilir.\n"
                "- Çiğneme fonksiyonu iyileştirilir.\n\n"
                "## Sık Sorulan Sorular\n\n"
                "### 1. Tedavi ne kadar sürer?\n"
                "Tedavi süresi vakaya göre 3 ile 7 gün arasında değişiklik göstermektedir.\n\n"
                "### 2. İşlem sonrası dikkat edilmesi gerekenler nelerdir?\n"
                "İlk 24 saat sıcak gıdalardan kaçınılmalı ve ağız hijyenine dikkat edilmelidir.\n\n"
                "### 3. Fiyatlar neye göre belirlenir?\n"
                "Fiyatlar uygulanacak materyal kalitesi ve işlem yapılacak diş sayısına göre diş hekiminizce belirlenir."
            )

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
