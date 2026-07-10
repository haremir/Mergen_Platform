"""
mergen_pkg_whatsapp.client
~~~~~~~~~~~~~~~~~~~~~~~~~~

WhatsApp Business Cloud API client for the Mergen Platform.

Implements the **Single Platform Token** model — one ``platform_token`` scoped
to the WhatsApp Business Account (WABA) is used for all management operations.
Message delivery per phone number uses the same token passed at call-time,
keeping credential management simple and auditable.

No OAuth / Facebook Login is used or supported. This follows Meta's recommended
approach for independent software vendor (ISV) platform integrations.

Meta Graph API Base URL: https://graph.facebook.com/v19.0

API Reference:
    https://developers.facebook.com/docs/whatsapp/business-management-api/phone-numbers
    https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages

Author: Mergen Platform -- Core Team
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional

import httpx

# ---------------------------------------------------------------------------
# Import shared domain models
# ---------------------------------------------------------------------------
try:
    from mergen_common.models import OutboundMessage
except ModuleNotFoundError:
    _shared = os.path.join(os.path.dirname(__file__), "..", "..", "shared")
    sys.path.insert(0, os.path.abspath(_shared))
    from mergen_common.models import OutboundMessage  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

# Meta Graph API version — bump here when Meta deprecates a version
_GRAPH_API_VERSION = "v19.0"
_GRAPH_BASE_URL = f"https://graph.facebook.com/{_GRAPH_API_VERSION}"


class WhatsAppAPIError(RuntimeError):
    """Raised when a Meta Graph API call returns a non-2xx response."""

    def __init__(self, method: str, url: str, status_code: int, body: str) -> None:
        self.method = method
        self.url = url
        self.status_code = status_code
        self.body = body
        super().__init__(
            f"WhatsApp API {method} {url} returned HTTP {status_code}: {body[:200]}"
        )


class WhatsAppClient:
    """Meta WhatsApp Business Cloud API client (Single Platform Token model).

    All business-management calls (phone number registration, verification)
    use the ``platform_token`` scoped to the WABA.  Message delivery calls
    require passing the ``phone_number_id`` of the sending number.

    Constructor Args
    ----------------
    platform_token:
        Meta system user access token scoped to the WABA.
        In production, load from environment variable ``WHATSAPP_PLATFORM_TOKEN``.
    waba_id:
        WhatsApp Business Account ID (numeric string).
        In production, load from environment variable ``WHATSAPP_WABA_ID``.
    timeout:
        HTTP request timeout in seconds (default: 15).
    http_client:
        Optional pre-configured ``httpx.Client`` for testing / mocking.

    Example::
        client = WhatsAppClient(
            platform_token=os.environ["WHATSAPP_PLATFORM_TOKEN"],
            waba_id=os.environ["WHATSAPP_WABA_ID"],
        )
        phone_id = client.add_phone_number("+905551234567", "Acme Support")
        client.request_verification_code(phone_id)
        client.verify_code(phone_id, "123456")
        client.register_number(phone_id, pin="000000")
    """

    def __init__(
        self,
        platform_token: str,
        waba_id: str,
        timeout: float = 15.0,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        if not platform_token:
            raise ValueError("WhatsAppClient: platform_token must not be empty.")
        if not waba_id:
            raise ValueError("WhatsAppClient: waba_id must not be empty.")

        self._token = platform_token
        self._waba_id = waba_id
        self._timeout = timeout
        self._http = http_client or httpx.Client(timeout=timeout)

        logger.info(
            "WhatsAppClient: initialised for WABA=%s (Graph API %s).",
            waba_id,
            _GRAPH_API_VERSION,
        )

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    @property
    def _auth_headers(self) -> Dict[str, str]:
        """Standard auth + content-type headers for all API calls."""
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _post(self, url: str, payload: Dict) -> Dict:
        """Execute a POST request and return the parsed JSON body.

        Raises:
            WhatsAppAPIError: On any non-2xx response.
        """
        logger.debug("WhatsAppClient POST %s payload=%s", url, payload)
        try:
            response = self._http.post(url, json=payload, headers=self._auth_headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise WhatsAppAPIError(
                "POST", url, exc.response.status_code, exc.response.text
            ) from exc

    def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Execute a GET request and return the parsed JSON body."""
        logger.debug("WhatsAppClient GET %s params=%s", url, params)
        try:
            response = self._http.get(url, params=params, headers=self._auth_headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise WhatsAppAPIError(
                "GET", url, exc.response.status_code, exc.response.text
            ) from exc

    # ------------------------------------------------------------------
    # Phone Number Management
    # ------------------------------------------------------------------

    def add_phone_number(
        self,
        phone_number: str,
        display_name: str,
        country_code: Optional[str] = None,
    ) -> str:
        """Add a new phone number to the WhatsApp Business Account.

        Meta API Reference:
            POST /{waba_id}/phone_numbers
            https://developers.facebook.com/docs/whatsapp/business-management-api/phone-numbers

        Args:
            phone_number:  E.164 format (e.g. "+905551234567").
            display_name:  Business display name shown to customers.
            country_code:  Optional ISO 3166-1 alpha-2 override (e.g. "TR").

        Returns:
            ``phone_number_id`` (str) of the newly added number.

        Raises:
            WhatsAppAPIError: If Meta rejects the request.

        API call::
            POST https://graph.facebook.com/v19.0/{waba_id}/phone_numbers
            Authorization: Bearer {platform_token}
            {
                "cc": "90",
                "phone_number": "5551234567",
                "display_name": "Acme Support",
                "verified_name": "Acme Support"
            }
        """
        url = f"{_GRAPH_BASE_URL}/{self._waba_id}/phone_numbers"

        # Normalise E.164 number to cc + number components
        normalised = phone_number.lstrip("+").replace(" ", "").replace("-", "")

        payload: Dict[str, Any] = {
            "phone_number": phone_number,
            "display_name": display_name,
            "verified_name": display_name,
        }
        if country_code:
            payload["cc"] = country_code

        result = self._post(url, payload)
        phone_id: str = result.get("id", "")
        logger.info(
            "WhatsAppClient.add_phone_number: added phone=%s display='%s' -> id=%s",
            phone_number,
            display_name,
            phone_id,
        )
        return phone_id

    def request_verification_code(
        self,
        phone_number_id: str,
        code_method: str = "SMS",
        language: str = "en_US",
    ) -> bool:
        """Request an OTP verification code to be sent to the phone number.

        Meta API Reference:
            POST /{phone_number_id}/request_code
            https://developers.facebook.com/docs/whatsapp/business-management-api/phone-numbers#request-verification-code

        Args:
            phone_number_id: The ``id`` returned by ``add_phone_number``.
            code_method:     Delivery method — "SMS" or "VOICE".
            language:        Locale code for the message (e.g. "en_US", "tr_TR").

        Returns:
            ``True`` if the request was accepted by Meta.

        API call::
            POST https://graph.facebook.com/v19.0/{phone_number_id}/request_code
            { "code_method": "SMS", "language": "en_US" }
        """
        url = f"{_GRAPH_BASE_URL}/{phone_number_id}/request_code"
        payload = {"code_method": code_method, "language": language}

        result = self._post(url, payload)
        success = bool(result.get("success", False))
        logger.info(
            "WhatsAppClient.request_verification_code: phone_id=%s method=%s success=%s",
            phone_number_id,
            code_method,
            success,
        )
        return success

    def verify_code(self, phone_number_id: str, code: str) -> bool:
        """Submit the OTP received via SMS/VOICE to verify the phone number.

        Meta API Reference:
            POST /{phone_number_id}/verify_code
            https://developers.facebook.com/docs/whatsapp/business-management-api/phone-numbers#verify-phone-number

        Args:
            phone_number_id: Target phone number's ``id``.
            code:            6-digit OTP received via SMS or voice call.

        Returns:
            ``True`` if verification was successful.

        API call::
            POST https://graph.facebook.com/v19.0/{phone_number_id}/verify_code
            { "code": "123456" }
        """
        url = f"{_GRAPH_BASE_URL}/{phone_number_id}/verify_code"
        result = self._post(url, {"code": code})
        success = bool(result.get("success", False))
        logger.info(
            "WhatsAppClient.verify_code: phone_id=%s success=%s",
            phone_number_id,
            success,
        )
        return success

    def register_number(self, phone_number_id: str, pin: str = "000000") -> bool:
        """Register a verified phone number for Cloud API message sending.

        This step is required after ``verify_code`` to fully activate the
        number for sending messages through the Cloud API.

        Meta API Reference:
            POST /{phone_number_id}/register
            https://developers.facebook.com/docs/whatsapp/cloud-api/reference/registration

        Args:
            phone_number_id: Target phone number's ``id``.
            pin:             Two-factor authentication PIN (6 digits).
                             Defaults to "000000" for new registrations.

        Returns:
            ``True`` if registration was accepted.

        API call::
            POST https://graph.facebook.com/v19.0/{phone_number_id}/register
            {
                "messaging_product": "whatsapp",
                "pin": "000000"
            }
        """
        url = f"{_GRAPH_BASE_URL}/{phone_number_id}/register"
        payload = {"messaging_product": "whatsapp", "pin": pin}
        result = self._post(url, payload)
        success = bool(result.get("success", False))
        logger.info(
            "WhatsAppClient.register_number: phone_id=%s success=%s",
            phone_number_id,
            success,
        )
        return success

    # ------------------------------------------------------------------
    # Message Sending
    # ------------------------------------------------------------------

    def send_message(
        self,
        outbound_msg: OutboundMessage,
        phone_number_id: str,
    ) -> Dict:
        """Send a text or template message via the Cloud API.

        Inspects ``outbound_msg.template_name``:
        - If set  → sends a pre-approved template message.
        - If None → sends a free-form text message.

        Meta API Reference:
            POST /{phone_number_id}/messages
            https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages

        Args:
            outbound_msg:   ``OutboundMessage`` dataclass with recipient and text.
            phone_number_id: The sending number's ``phone_number_id``.

        Returns:
            Meta API response dict containing ``messages[0].id`` on success.

        Raises:
            WhatsAppAPIError: On non-2xx API response.

        API call (text)::
            POST https://graph.facebook.com/v19.0/{phone_number_id}/messages
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": "905551234567",
                "type": "text",
                "text": {"preview_url": false, "body": "Hello!"}
            }

        API call (template)::
            POST https://graph.facebook.com/v19.0/{phone_number_id}/messages
            {
                "messaging_product": "whatsapp",
                "to": "905551234567",
                "type": "template",
                "template": {
                    "name": "order_confirmation",
                    "language": {"code": "en_US"}
                }
            }
        """
        url = f"{_GRAPH_BASE_URL}/{phone_number_id}/messages"
        recipient = outbound_msg.recipient.lstrip("+").replace(" ", "").replace("-", "")

        if outbound_msg.template_name:
            payload: Dict[str, Any] = {
                "messaging_product": "whatsapp",
                "to": recipient,
                "type": "template",
                "template": {
                    "name": outbound_msg.template_name,
                    "language": {"code": "en_US"},
                },
            }
        else:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient,
                "type": "text",
                "text": {
                    "preview_url": False,
                    "body": outbound_msg.text,
                },
            }

        result = self._post(url, payload)
        msg_id = (result.get("messages") or [{}])[0].get("id", "")
        logger.info(
            "WhatsAppClient.send_message: tenant=%s to=%s type=%s msg_id=%s",
            outbound_msg.tenant_id,
            recipient,
            "template" if outbound_msg.template_name else "text",
            msg_id,
        )
        return result

    def list_phone_numbers(self) -> List[Dict]:
        """List all phone numbers registered under this WABA.

        API call::
            GET https://graph.facebook.com/v19.0/{waba_id}/phone_numbers
        """
        url = f"{_GRAPH_BASE_URL}/{self._waba_id}/phone_numbers"
        result = self._get(url)
        numbers: List[Dict] = result.get("data", [])
        logger.info(
            "WhatsAppClient.list_phone_numbers: %d number(s) found for WABA=%s.",
            len(numbers),
            self._waba_id,
        )
        return numbers

    def close(self) -> None:
        """Close the underlying HTTP client connection pool."""
        self._http.close()
        logger.debug("WhatsAppClient: HTTP client closed.")

    def __enter__(self) -> "WhatsAppClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()
