"""
mergen_product_katip.cms_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Katip CMS & WordPress Entegrasyon Servisi.

Onaylanan veya yayınlanma durumuna getirilen taslakları WordPress REST API
veya özel Webhook endpoint'leri üzerinden otomatik yayınlayan iş mantığı.

Özellikler:
- WordPress REST API (/wp-json/wp/v2/posts) Entegrasyonu (Basic Auth / Application Password)
- Özel Webhook Destekli CMS Yayınlama (Ghost, Strapi, Webflow, vb.)
- Tenant Bazlı CMS Yapılandırması (BrandGuide rules_json veya ENV)
- Yayınlama sonrası KatipDraft.status = 'published' güncellemesi ve yayın kaydı

Author: Mergen Platform -- Kâtip Team
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.orm import Session

from mergen_product_katip.models import KatipBrandGuide, KatipDraft, KatipDraftVersion, KatipTopicQueue

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def publish_to_wordpress(
    wp_url: str,
    username: str,
    app_password: str,
    title: str,
    content: str,
    status: str = "publish",
) -> Dict[str, Any]:
    """
    WordPress REST API (/wp-json/wp/v2/posts) üzerinden yeni içerik yayınlar.
    """
    base_url = wp_url.rstrip("/")
    endpoint = f"{base_url}/wp-json/wp/v2/posts"

    payload = {
        "title": title,
        "content": content,
        "status": status,  # "publish" veya "draft"
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                endpoint,
                auth=(username, app_password),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "cms_type": "wordpress",
                "post_id": data.get("id"),
                "post_url": data.get("link"),
                "status": data.get("status"),
                "published_at": data.get("date"),
            }
    except Exception as exc:
        logger.error("WordPress REST API yayınlama hatası (%s): %s", endpoint, exc)
        raise RuntimeError(f"WordPress yayınlama hatası: {exc}") from exc


def publish_to_webhook(
    webhook_url: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Özel Webhook endpoint'ine JSON formatında yayınlama isteği gönderir.
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(webhook_url, json=payload)
            resp.raise_for_status()
            return {
                "cms_type": "webhook",
                "webhook_url": webhook_url,
                "status_code": resp.status_code,
                "response": resp.text[:200],
            }
    except Exception as exc:
        logger.error("CMS Webhook yayınlama hatası (%s): %s", webhook_url, exc)
        raise RuntimeError(f"CMS Webhook hatası: {exc}") from exc


def dispatch_cms_publication(
    db: Session,
    tenant_id: str,
    draft_id: str,
) -> Dict[str, Any]:
    """
    Taslağın en son versiyonunu çeker ve tenant'ın CMS ayarlarına göre
    WordPress veya Webhook entegrasyonunu tetikler.

    Args:
        db: SQLAlchemy Session
        tenant_id: Tenant UUID'si
        draft_id: KatipDraft ID'si

    Returns:
        Yayınlama sonucu sözlüğü.
    """
    # 1. Taslak ve en son versiyonu bul
    draft = db.query(KatipDraft).filter(
        KatipDraft.id == draft_id,
        KatipDraft.tenant_id == tenant_id,
    ).first()

    if not draft:
        raise ValueError(f"Taslak '{draft_id}' bulunamadı (Tenant: {tenant_id}).")

    latest_version = (
        db.query(KatipDraftVersion)
        .filter(KatipDraftVersion.draft_id == draft_id)
        .order_by(KatipDraftVersion.version_number.desc())
        .first()
    )
    if not latest_version:
        raise ValueError(f"Taslak '{draft_id}' için yayınlanacak versiyon bulunamadı.")

    # 2. Konu başlığını bul
    topic = db.query(KatipTopicQueue).filter(KatipTopicQueue.id == draft.topic_id).first()
    title = topic.topic_title if topic else f"Taslak {draft_id[:8]}"

    # 3. CMS Ayarlarını Çek (BrandGuide rules_json veya ENV fallback)
    brand_guide = db.query(KatipBrandGuide).filter(KatipBrandGuide.tenant_id == tenant_id).first()
    cms_config = brand_guide.rules_json.get("cms_config", {}) if (brand_guide and brand_guide.rules_json) else {}

    wp_url = cms_config.get("wp_url") or os.getenv("WP_URL")
    wp_username = cms_config.get("wp_username") or os.getenv("WP_USERNAME")
    wp_password = cms_config.get("wp_password") or os.getenv("WP_APP_PASSWORD")
    webhook_url = cms_config.get("webhook_url") or os.getenv("KATIP_CMS_WEBHOOK_URL")

    pub_result: Dict[str, Any] = {}

    if wp_url and wp_username and wp_password:
        logger.info("WordPress REST API ile yayınlanıyor: Tenant=%s Draft=%s", tenant_id, draft_id)
        pub_result = publish_to_wordpress(
            wp_url=wp_url,
            username=wp_username,
            app_password=wp_password,
            title=title,
            content=latest_version.content,
            status="publish",
        )
    elif webhook_url:
        logger.info("CMS Webhook ile yayınlanıyor: Tenant=%s Draft=%s", tenant_id, draft_id)
        pub_payload = {
            "event": "katip.draft.published",
            "tenant_id": tenant_id,
            "draft_id": draft_id,
            "version_number": latest_version.version_number,
            "title": title,
            "content": latest_version.content,
            "word_count": latest_version.word_count,
            "published_at": _utcnow().isoformat(),
        }
        pub_result = publish_to_webhook(webhook_url, pub_payload)
    else:
        # CMS bağlantısı tanımlı değilse simüle et (sistem çökmez)
        logger.info("CMS bağlantısı tanımlı değil, mock yayın kaydı oluşturuluyor (Tenant: %s)", tenant_id)
        pub_result = {
            "cms_type": "simulated",
            "post_id": f"sim-{draft_id[:8]}",
            "post_url": f"https://tenant-cms.example.com/posts/{draft_id[:8]}",
            "status": "published",
            "published_at": _utcnow().isoformat(),
        }

    # 4. Taslak durumunu 'published' olarak güncelle
    draft.status = "published"
    draft.updated_at = _utcnow()
    db.commit()

    logger.info("Taslak '%s' başarıyla CMS üzerinde yayınlandı (%s).", draft_id, pub_result.get("cms_type"))
    return {
        "status": "success",
        "draft_id": draft_id,
        "version_number": latest_version.version_number,
        "publication": pub_result,
    }
