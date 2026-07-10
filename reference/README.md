# reference/ — Read-Only Legacy Reference

This folder contains **read-only copies** of proven production files from the
`dent_bot` project. They are provided here so Mergen Platform engineers can
study the existing, battle-tested patterns without importing or modifying the
legacy codebase.

> [!CAUTION]
> **DO NOT** import from `reference/` in any Mergen Platform package.
> These files are documentation artifacts, not executable code.
> They exist solely to accelerate development by providing proven patterns.

## Contents

### `llm/`
| File | Origin | Purpose |
|------|--------|---------|
| `llm.py` | `dent_bot/src/dentbot/llm.py` | LLMClient with OpenRouter primary + Ollama fallback, token telemetry, and retry chain. Reference for `core/mergen_core/llm/` implementation. |

### `webhooks/`
| File | Origin | Purpose |
|------|--------|---------|
| `webhooks.py` | `dent_bot/src/dentbot/channels/webhooks.py` | FastAPI webhook server with 3-layer security firewall (HMAC-SHA256 signature verification, DB-driven multi-tenant routing, instant-200 + BackgroundTasks). Reference for `packages/mergen_pkg_whatsapp/webhook.py`. |
| `whatsapp_transport.py` | `dent_bot/src/dentbot/channels/whatsapp.py` | Meta Cloud API send/receive transport (`send_message`, `send_template_message`, `parse_update`). Reference for `packages/mergen_pkg_whatsapp/transport.py`. |
| `tenant_resolution.py` | `dent_bot/src/dentbot/services/tenant_resolution.py` | Channel-identifier → tenant UUID resolver with TENANT_MAP env support and ACTIVE_TENANT_ID fallback. Reference for `core/mergen_core/tenant/`. |

### `rag/`
| File | Origin | Purpose |
|------|--------|---------|
| `adapter_base.py` | `dent_bot/src/dentbot/adapters/base.py` | `AppointmentAdapter` Protocol defining the full persistence layer contract (TypedDicts, CRUD signatures). Reference for designing the Mergen Platform's `StorageAdapter` Protocol. |
| `appointment_model.py` | `dent_bot/src/dentbot/models/appointment.py` | Richly annotated `Appointment` dataclass with `to_dict` / `from_dict` serialization and backward-compat datetime coercion. Reference for sector-specific domain models in `core/mergen_core/models/`. |

## Key Patterns to Reuse

1. **HMAC-SHA256 webhook firewall** (`webhooks.py` → `_verify_meta_signature`)
2. **Instant-200 + BackgroundTasks** pattern (`webhooks.py` → `receive_whatsapp_secure`)
3. **Multi-tenant DB routing via `phone_number_id`** (`webhooks.py` + `tenant_resolution.py`)
4. **OpenRouter → fallback → Ollama LLM chain** (`llm.py` → `LLMClient.chat`)
5. **Protocol-based adapter pattern** (`adapter_base.py` → `AppointmentAdapter`)
6. **`from_dict` / `to_dict` with datetime coercion** (`appointment_model.py`)
