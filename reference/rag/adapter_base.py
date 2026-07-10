from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable, Optional, Dict, Any, List, TypedDict

DEFAULT_SETTINGS: Dict[str, Any] = {
    "working_hours": {"start": "09:00", "end": "18:00"},
    "breaks": [{"start": "12:30", "end": "13:30"}],
}


class DentistData(TypedDict, total=False):
    tenant_id: str
    full_name: str
    specialty: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    working_hours: Dict[str, Any]
    telegram_chat_id: Optional[int]
    is_active: bool
    delay_minutes: int
    title: Optional[str]
    specialties: Optional[str]
    bio: Optional[str]



class TreatmentData(TypedDict, total=False):
    tenant_id: str
    name: str
    duration_minutes: int
    price: float
    required_specialty: Optional[str]
    requires_approval: bool
    description: Optional[str]
    is_active: bool
    clinic_specific_equipment: Optional[str]
    aftercare_instructions: Optional[str]


class AppointmentData(TypedDict, total=False):
    tenant_id: str
    dentist_id: str
    patient_id: Optional[str]
    patient_name: str
    patient_phone: str
    patient_email: str
    start_time: str
    end_time: str
    duration_minutes: int
    treatment_id: Optional[str]
    treatment_type: Optional[str]
    status: str
    notes: Optional[str]
    medical_notes: Optional[str]
    reference_code: Optional[str]
    ai_summary: Dict[str, Any]
    delay_minutes: int


@runtime_checkable
class AppointmentAdapter(Protocol):
    """
    Tüm veri kalıcılığı (persistence) katmanları için soyut protokol (interface).
    Multi-tenant architecture için tasarlanmıştır.
    
    IMPORTANT:
    - Tüm metodlar tenant_id parametresi alır (ilk parametre)
    - ID'ler UUID string formatındadır
    - user_id optional parametredir (audit trail için)
    """

    # ------------------------------------
    # Lifecycle
    # ------------------------------------
    def init(self) -> None: 
        """Veritabanı şemasını başlatır ve gerekirse tabloları oluşturur."""
        ...

    def get_clinic_settings(self, tenant_id: str) -> Dict[str, Any]: ...

    def update_clinic_settings(self, tenant_id: str, settings_data: Dict[str, Any]) -> Dict[str, Any]: ...

    def get_tenant_conversations(self, tenant_id: str) -> List[Dict[str, Any]]: ...

    def get_conversation_messages(self, tenant_id: str, session_id: str) -> List[Dict[str, Any]]: ...

    # ------------------------------------
    # Dentist CRUD
    # ------------------------------------
    def create_dentist(
        self, 
        tenant_id: str, 
        data: DentistData,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]: ...
    
    def get_dentist(
        self, 
        tenant_id: str, 
        dentist_id: str
    ) -> Optional[Dict[str, Any]]: ...
    
    def get_dentist_by_name(
        self,
        tenant_id: str,
        full_name: str
    ) -> Optional[Dict[str, Any]]: ...
    
    def list_dentists(
        self, 
        tenant_id: str,
        is_active: Optional[bool] = True
    ) -> List[Dict[str, Any]]: ...
    
    def update_dentist(
        self, 
        tenant_id: str,
        dentist_id: str, 
        data: DentistData,
        user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]: ...
    
    def update_dentist_chat_id(
        self,
        tenant_id: str,
        dentist_id: str,
        chat_id: int
    ) -> None: ...
    
    def delete_dentist(
        self, 
        tenant_id: str,
        dentist_id: str
    ) -> bool: ...

    # ------------------------------------
    # Treatment CRUD
    # ------------------------------------
    def create_treatment(
        self, 
        tenant_id: str,
        data: TreatmentData,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]: ...
    
    def get_treatment(
        self, 
        tenant_id: str,
        treatment_id: str
    ) -> Optional[Dict[str, Any]]: ...
    
    def get_treatment_by_name(
        self,
        tenant_id: str,
        treatment_name: str
    ) -> Optional[Dict[str, Any]]: ...
    
    def get_treatment_duration(
        self,
        tenant_id: str,
        treatment_name: str
    ) -> int: ...
    
    def list_treatments(
        self, 
        tenant_id: str,
        is_active: Optional[bool] = True
    ) -> List[Dict[str, Any]]: ...
    
    def update_treatment(
        self, 
        tenant_id: str,
        treatment_id: str, 
        data: TreatmentData,
        user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]: ...
    
    def delete_treatment(
        self, 
        tenant_id: str,
        treatment_id: str
    ) -> bool: ...

    # ------------------------------------
    # Appointment CRUD
    # ------------------------------------
    def create_appointment(
        self, 
        tenant_id: str,
        data: AppointmentData,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]: ...
    
    def get_appointment(
        self, 
        tenant_id: str,
        appointment_id: str
    ) -> Optional[Dict[str, Any]]: ...
    
    def get_appointment_details(
        self,
        tenant_id: str,
        appointment_id: str
    ) -> Dict[str, Any]: ...

    def list_appointments(
        self, 
        tenant_id: str,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]: ...
    
    def get_appointments_by_tenant(
        self,
        tenant_id: str
    ) -> List[Dict[str, Any]]: ...

    def get_tenant_stats(
        self,
        tenant_id: str
    ) -> Dict[str, Any]: ...
    
    def list_appointments_by_dentist(
        self, 
        tenant_id: str,
        dentist_id: str, 
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]: ...
    
    def list_appointments_by_date(
        self, 
        tenant_id: str,
        date: str, 
        dentist_id: Optional[str] = None
    ) -> List[Dict[str, Any]]: ...
    
    def update_appointment(
        self, 
        tenant_id: str,
        appointment_id: str, 
        data: AppointmentData,
        user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]: ...
    
    def update_appointment_status(
        self,
        tenant_id: str,
        appointment_id: str,
        status: str
    ) -> None: ...

    def delete_appointment(
        self, 
        tenant_id: str,
        appointment_id: str
    ) -> bool: ...

    # ------------------------------------
    # Slot & Approval İşlemleri
    # ------------------------------------
    def get_booked_slots(
        self, 
        tenant_id: str,
        dentist_id: str,
        date: str
    ) -> List[Dict[str, Any]]: ...
    
    def approve_appointment(
        self, 
        tenant_id: str,
        appointment_id: str
    ) -> Optional[Dict[str, Any]]: ...
    
    def reject_appointment(
        self, 
        tenant_id: str,
        appointment_id: str
    ) -> Optional[Dict[str, Any]]: ...

    # ------------------------------------
    # Patient CRUD (subset)
    # ------------------------------------
    def get_patient_by_id(
        self,
        tenant_id: str,
        patient_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]: ...
    
    def get_or_create_patient_from_telegram(
        self,
        tenant_id: str,
        telegram_chat_id: str,
        full_name: str
    ) -> str: ...
    
    def update_patient_email(
        self, 
        tenant_id: str, 
        patient_id: str, 
        email: str, 
        user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]: ...
    
    # ------------------------------------
    # Tenant / Clinic Administration
    # ------------------------------------
    def get_all_tenants(self) -> List[Dict[str, Any]]: ...
    def create_tenant(self, data: Dict[str, Any]) -> Dict[str, Any]: ...
    def get_platform_stats(self) -> Dict[str, Any]: ...

    def get_clinic_by_id(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single clinic row by its primary key (UUID).

        Used by NotificationService and ReassignmentWorker to dynamically
        resolve per-tenant WhatsApp credentials at send time instead of
        relying on a static .env token.

        Args:
            tenant_id: The UUID string of the clinic/tenant.

        Returns:
            Full clinic row dict (including ``id``, ``whatsapp_active``,
            ``whatsapp_token``, ``phone_number_id``, ``waba_id``) or
            ``None`` if no matching record is found.
        """
        ...

    def save_whatsapp_credentials(
        self,
        tenant_id: str,
        encrypted_token: str,
        waba_id: str,
        phone_number_id: str,
    ) -> None:
        """Persist encrypted WhatsApp credentials for a tenant's clinic row.

        Args:
            tenant_id:       UUID of the clinic / tenant.
            encrypted_token: Fernet-encrypted permanent system-user token.
            waba_id:         WhatsApp Business Account ID.
            phone_number_id: The phone number ID used as the webhook routing key.
                             MUST NOT be empty — callers are responsible for
                             validating this before calling.
        """
        ...

    def get_clinic_by_phone_number_id(
        self,
        phone_number_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Look up a clinic record by its WhatsApp phone_number_id routing key.

        Used by the webhook firewall to resolve inbound Meta messages to a tenant.
        Returns the full clinic row (including ``id``, ``whatsapp_active``,
        ``whatsapp_token``) or ``None`` if no matching active clinic is found.

        Args:
            phone_number_id: The ``metadata.phone_number_id`` extracted from the
                             Meta webhook JSON payload.

        Returns:
            Dict with at minimum ``{"id": <tenant_uuid>, "whatsapp_active": bool,
            "whatsapp_token": <encrypted_str>}`` or ``None``.
        """
        ...

    # ------------------------------------
    # Scheduled Tasks (Async Jobs)
    # ------------------------------------
    def create_scheduled_task(
        self,
        tenant_id: str,
        task_type: str,
        payload: Dict[str, Any],
        status: str = "pending"
    ) -> None: ...

    def has_pending_checkup(
        self,
        tenant_id: str,
        chat_id: str,
    ) -> bool: ...

    def save_checkup_response(
        self,
        tenant_id: str,
        chat_id: str,
        score: int,
    ) -> None: ...

    def save_medical_record(
        self,
        tenant_id: str,
        patient_chat_id: str,
        record_data: dict,
    ) -> None: ...

    def get_medical_record(
        self,
        tenant_id: str,
        patient_chat_id: str,
    ) -> Optional[dict]: ...

    def update_dentist_delay(
        self,
        tenant_id: str,
        dentist_id: str,
        delay_minutes: int,
    ) -> None: ...

    def get_dentist_delay(
        self,
        tenant_id: str,
        dentist_id: str,
    ) -> int: ...

    def check_appointment_availability(
        self,
        tenant_id: str,
        dentist_id: str,
        start_time: datetime,
        duration_minutes: int,
        exclude_appointment_id: Optional[str] = None,
    ) -> None:
        """Validate slot availability: checks working hours and absence of conflicts.

        Raises SlotConflictError if the slot overlaps an existing booking.
        Raises OutOfHoursError if the slot falls outside clinic working hours.
        Returns None if the slot is valid.
        """
        ...