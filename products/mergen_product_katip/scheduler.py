"""
mergen_product_katip.scheduler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Katip Autonomy & Async Background Scheduler.

İnsan müdahalesi olmadan otonom olarak çalışan ve konu kuyruğunu tüketen
zamanlayıcı servisi.

Özellikler:
- PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED` ile multi-process yarış durumunu önler.
- `pending` statüsündeki konuları öncelik sırasına göre çeker.
- `draft_service` üzerinden LLM + RAG taslak üretimini tetikler.
- LLM veya veritabanı hatalarında konuyu `failed` olarak işaretler, `retry_count` artırır,
  detaylı hata logu yazar (sistem asla kilitlenmez / tıkanmaz).
- FastAPI `lifespan` döngüsüne entegre edilebilir asenkron `KatipBackgroundScheduler`.

Author: Mergen Platform -- Kâtip Team
"""

from __future__ import annotations

import asyncio
import logging
import os
import traceback
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from mergen_core.database import SessionLocal
from mergen_product_katip.draft_service import generate_draft_for_topic
from mergen_product_katip.models import KatipTopicQueue
from mergen_product_katip.prompt_engine import KatipPromptEngine

logger = logging.getLogger(__name__)

# Konu işleme periyodu (saniye)
DEFAULT_INTERVAL_SECONDS = int(os.getenv("KATIP_SCHEDULER_INTERVAL_SECONDS", "30"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def fetch_and_lock_next_topic(db: Session) -> Optional[KatipTopicQueue]:
    """
    Kuyruktaki sıradaki 'pending' konuyu `SELECT ... FOR UPDATE SKIP LOCKED`
    mantığıyla kilitler ve döndürür.

    PostgreSQL üzerinde birden fazla worker aynı anda çalışsa bile aynı
    konuyu çekmelerini (race condition) imkansız kılar.
    """
    try:
        # PostgreSQL dialect kontrolü — SKIP LOCKED desteği
        stmt = (
            select(KatipTopicQueue)
            .where(KatipTopicQueue.status == "pending")
            .order_by(KatipTopicQueue.priority.desc(), KatipTopicQueue.created_at.asc())
            .limit(1)
        )

        bind = db.get_bind()
        dialect_name = bind.dialect.name if bind else ""

        if dialect_name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)

        topic = db.scalars(stmt).first()
        return topic
    except Exception as exc:
        logger.error("Konu kilitleme hatası (SKIP LOCKED): %s", exc)
        return None


def process_single_pending_topic(
    db: Session,
    prompt_engine: Optional[KatipPromptEngine] = None,
) -> bool:
    """
    Kuyruktan 1 adet bekleyen konuyu güvenli bir şekilde çeker ve işler.

    Returns:
        True if a topic was processed, False if queue was empty.
    """
    topic = fetch_and_lock_next_topic(db)
    if not topic:
        return False

    topic_id = topic.id
    tenant_id = topic.tenant_id
    topic_title = topic.topic_title

    logger.info("Scheduler: Konu kilitlendi! ID: %s Title: '%s' Tenant: %s", topic_id, topic_title, tenant_id)

    # İki aşamalı kilit: status='processing' set edip hemen commit et
    topic.status = "processing"
    topic.locked_at = _utcnow()
    db.commit()

    try:
        # draft_service üzerinden üretimi tetikle
        result = generate_draft_for_topic(
            db=db,
            tenant_id=tenant_id,
            topic_id=topic_id,
            prompt_engine=prompt_engine,
        )

        logger.info(
            "Scheduler: Konu başarıyla tamamlandı! TopicID: %s DraftID: %s Versiyon: v%d",
            topic_id, result.get("draft_id"), result.get("version_number", 1)
        )
        return True

    except Exception as exc:
        # Hata Yönetimi: Sessizce bekletme! Statüyü failed yap, logla, sistemi tıkama.
        db.rollback()
        err_msg = f"{type(exc).__name__}: {str(exc)}\n{traceback.format_exc()[:500]}"
        
        # Konuyu tekrar bulup failed olarak güncelle
        failed_topic = db.query(KatipTopicQueue).filter(KatipTopicQueue.id == topic_id).first()
        if failed_topic:
            failed_topic.status = "failed"
            failed_topic.retry_count += 1
            failed_topic.error_message = err_msg
            db.commit()

        logger.error(
            "Scheduler HATA: Topic '%s' (%s) işlenirken hata oluştu ve 'failed' yapıldı: %s",
            topic_title, topic_id, exc
        )
        return True


def run_scheduler_batch(
    max_topics: int = 5,
    prompt_engine: Optional[KatipPromptEngine] = None,
) -> int:
    """
    Tek bir çalışma döngüsünde en fazla `max_topics` adet konuyu tüketir.

    Returns:
        İşlenen konu sayısı.
    """
    db = SessionLocal()
    processed_count = 0
    try:
        for _ in range(max_topics):
            has_more = process_single_pending_topic(db, prompt_engine=prompt_engine)
            if not has_more:
                break
            processed_count += 1
    finally:
        db.close()

    return processed_count


class KatipBackgroundScheduler:
    """
    FastAPI lifespan entegrasyonu için asenkron zamanlayıcı sınıfı.
    """

    def __init__(self, interval_seconds: int = DEFAULT_INTERVAL_SECONDS):
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._prompt_engine: Optional[KatipPromptEngine] = None

    async def _loop(self):
        logger.info("KatipBackgroundScheduler başlatıldı (Periyot: %ds)...", self.interval_seconds)
        self._prompt_engine = KatipPromptEngine()

        while self._running:
            try:
                # Sync DB işlemlerini threadpool'da async olarak çalıştır
                count = await asyncio.to_thread(
                    run_scheduler_batch,
                    max_topics=5,
                    prompt_engine=self._prompt_engine,
                )
                if count > 0:
                    logger.info("KatipBackgroundScheduler bu turda %d konu işledi.", count)
            except Exception as exc:
                logger.error("KatipBackgroundScheduler döngü hatası: %s", exc)

            await asyncio.sleep(self.interval_seconds)

    def start(self):
        """Zamanlayıcıyı başlatır."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    def stop(self):
        """Zamanlayıcıyı durdurur."""
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("KatipBackgroundScheduler durduruldu.")


# Modül seviyesinde singleton scheduler instance'ı
_scheduler_instance = KatipBackgroundScheduler()


def get_katip_scheduler() -> KatipBackgroundScheduler:
    return _scheduler_instance
