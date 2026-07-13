import os
import sys

# Path setup
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _ROOT)

from fastapi.testclient import TestClient
from panel.api_server import app

client = TestClient(app)

print("--- Testing Platform Settings Endpoints ---")

# 1. GET Settings initially
resp = client.get("/api/platform/settings")
assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
data = resp.json()
print("Initial settings:", data)
assert "maintenance_mode" in data
assert "allow_new_registrations" in data
assert "global_system_alerts" in data

# 2. POST Settings to update
payload = {
    "maintenance_mode": True,
    "allow_new_registrations": False,
    "global_system_alerts": "Sistem Bakim Duyurusu: Bu gece servisler kapali olacaktir."
}
resp = client.post("/api/platform/settings", json=payload)
assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
data = resp.json()
print("Updated settings response:", data)
assert data["maintenance_mode"] == payload["maintenance_mode"]
assert data["allow_new_registrations"] == payload["allow_new_registrations"]
assert data["global_system_alerts"] == payload["global_system_alerts"]

# 3. GET Settings again to verify persistence
resp = client.get("/api/platform/settings")
assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
data = resp.json()
print("Verified persisted settings:", data)
assert data["maintenance_mode"] == payload["maintenance_mode"]
assert data["allow_new_registrations"] == payload["allow_new_registrations"]
assert data["global_system_alerts"] == payload["global_system_alerts"]

# 4. GET Analytics to verify analytics endpoint works
print()
print("--- Testing Platform Analytics Endpoint ---")
resp = client.get("/api/platform/analytics")
assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
stats = resp.json()
print("Analytics response:", stats)
assert "revenue" in stats
assert "expenses" in stats
assert "message_volume" in stats
assert "active_tenants" in stats

print("--- Platform Settings & Analytics Test PASSED ---")
