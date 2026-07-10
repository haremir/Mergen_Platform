from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, ClassVar
import uuid

@dataclass
class Appointment:
    """Diş Kliniği Randevu Modeli (Multi-tenant UUID destekli)."""

    # Zorunlu Alanlar
    tenant_id: str
    dentist_id: str  # UUID format
    patient_name: str
    patient_phone: str
    patient_email: str
    start_time: datetime
    end_time: datetime
    treatment_type: str    # Örn: "Dolgu", "Kontrol"
    duration_minutes: int  # Tedavinin tahmini süresi

    # Opsiyonel Alanlar
    id: Optional[str] = field(default=None)  # ✅ UUID string
    patient_id: Optional[str] = field(default=None)  # ✅ UUID string
    notes: Optional[str] = field(default=None)
    medical_notes: Optional[str] = field(default=None)
    patient_chat_id: Optional[str] = field(default=None)
    appointment_date: Optional[str] = field(default=None)
    time_slot: Optional[str] = field(default=None)
    channel: str = field(default="telegram")

    # Durum ve Zaman Bilgileri (Sınıf değişkenleri)
    STATUS_PENDING: ClassVar[str] = "pending"
    STATUS_APPROVED: ClassVar[str] = "approved"
    STATUS_COMPLETED: ClassVar[str] = "completed"
    STATUS_CANCELLED: ClassVar[str] = "cancelled"
    
    status: str = field(default=STATUS_PENDING)
    created_at: Optional[datetime] = field(default_factory=datetime.now)

    # ------------------------------------
    # Metodlar
    # ------------------------------------

    def get_reference_code(self) -> str:
        """'REQ-XXXXXXXX' formatında referans kodu üretir."""
        if self.id:
            # UUID'nin ilk 8 karakterini kullan
            short_id = str(self.id).replace('-', '')[:8].upper()
            return f"REQ-{short_id}"
        # Temporary ID
        return f"TEMP-{uuid.uuid4().hex[:6].upper()}"

    def is_pending(self) -> bool:
        return self.status == self.STATUS_PENDING

    def is_approved(self) -> bool:
        return self.status == self.STATUS_APPROVED

    def is_completed(self) -> bool:
        return self.status == self.STATUS_COMPLETED

    def is_cancelled(self) -> bool:
        return self.status == self.STATUS_CANCELLED

    def to_dict(self) -> Dict[str, Any]:
        data = self.__dict__.copy()
        for time_key in ('start_time', 'end_time', 'created_at'):
            if isinstance(data.get(time_key), datetime):
                data[time_key] = data[time_key].isoformat()
        
        # Remove class constants
        for key in list(data.keys()):
            if key.startswith('STATUS_'):
                data.pop(key)
                
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Appointment:
        data = data.copy()
        
        # Ensure tenant_id is present
        if "tenant_id" not in data or not data["tenant_id"]:
            data["tenant_id"] = "default_tenant"
            
        # Parse datetime fields
        for time_key in ('start_time', 'end_time', 'created_at'):
            time_str = data.get(time_key)
            if time_str and isinstance(time_str, str):
                try:
                    data[time_key] = datetime.fromisoformat(time_str)
                except ValueError:
                    data[time_key] = None
        
        # Ensure all IDs are strings
        for id_field in ['id', 'dentist_id', 'patient_id', 'patient_chat_id']:
            if id_field in data and data[id_field] is not None:
                data[id_field] = str(data[id_field])

        # Backward compatibility: derive start/end from appointment_date and time_slot when absent
        if not data.get('start_time'):
            date_str = data.get('appointment_date')
            slot_str = data.get('time_slot')
            if isinstance(date_str, str) and isinstance(slot_str, str):
                try:
                    data['start_time'] = datetime.fromisoformat(f"{date_str}T{slot_str}:00")
                except ValueError:
                    data['start_time'] = datetime.now()
            else:
                data['start_time'] = datetime.now()

        if not data.get('end_time'):
            duration = int(data.get('duration_minutes') or 30)
            if isinstance(data.get('start_time'), datetime):
                data['end_time'] = data['start_time'] + timedelta(minutes=duration)
            else:
                data['end_time'] = datetime.now() + timedelta(minutes=duration)
        
        # Filter to known fields only
        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in field_names}

        return cls(**filtered_data)
