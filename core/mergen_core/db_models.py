"""
mergen_core.db_models
~~~~~~~~~~~~~~~~~~~~~

Declarative database models for the Mergen Platform.

Author: Mergen Platform -- Core Team
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, DateTime
from mergen_core.database import Base


class DBTenant(Base):
    """Database model for Tenant configuration."""

    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True, index=True)
    business_name = Column(String(120), nullable=False)
    sector = Column(String(100), nullable=False)
    plan = Column(String(20), nullable=False, default="starter")
    whatsapp_phone_number_id = Column(String(50), unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    bot_active = Column(Boolean, default=True, nullable=False)
    system_prompt_override = Column(String(1000), nullable=True)
    persona = Column(String(100), default="friendly_energetic", nullable=False)
    telegram_token = Column(String(100), nullable=True)


class DBPlanUsage(Base):
    """Database model to track monthly tenant message quotas."""

    __tablename__ = "plan_usages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(36), index=True, nullable=False)
    month_key = Column(String(7), nullable=False, index=True)  # Format: "YYYY-MM"
    used_messages = Column(Integer, default=0, nullable=False)


class DBPlatformSetting(Base):
    """Database model for global platform configurations."""

    __tablename__ = "platform_settings"

    key = Column(String(100), primary_key=True)
    value = Column(String(255), nullable=False)


class DBSectorPrompt(Base):
    """Database model for storing sector-specific base prompts."""

    __tablename__ = "sector_prompts"

    sector_id = Column(String(100), primary_key=True, index=True)
    base_prompt = Column(String(2000), nullable=False)


# ---------------------------------------------------------------------------
# Kâtip modülü modelleri — Base'e tanıtmak için import yeterli.
# Base.metadata.create_all(bind=engine) tüm katip_* tablolarını da yaratır.
# ---------------------------------------------------------------------------
try:
    import mergen_product_katip.models  # noqa: F401  # registers all Katip ORM classes
except ImportError:
    pass  # Kâtip paketi kurulu değilse platform sessizce devam eder
