"""
scripts/audit_openapi_routes.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Extracts and audits all registered OpenAPI routes from the FastAPI application.
"""

import sys
import os

os.environ["FORCE_SQLITE"] = "1"

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (_ROOT, os.path.join(_ROOT, "shared"), os.path.join(_ROOT, "core"), os.path.join(_ROOT, "packages"), os.path.join(_ROOT, "products")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from panel.api_server import app

def audit_routes():
    print("=== AUDITING FASTAPI REGISTERED OPENAPI ROUTES ===")
    openapi = app.openapi()
    paths = openapi.get("paths", {})
    
    print(f"Total Endpoints Registered: {len(paths)}\n")
    
    katip_routes = []
    admin_routes = []
    other_routes = []

    for path, methods in sorted(paths.items()):
        for method, spec in methods.items():
            entry = f"{method.upper():<6} {path}"
            if path.startswith("/api/katip"):
                katip_routes.append(entry)
            elif path.startswith("/api/admin"):
                admin_routes.append(entry)
            else:
                other_routes.append(entry)

    print("--- KÂTİP PRODUCT ROUTES ---")
    for r in katip_routes:
        print(f"  {r}")

    print("\n--- ADMIN & AUTH ROUTES ---")
    for r in admin_routes:
        print(f"  {r}")

    print("\n--- DESK & CORE ROUTES ---")
    for r in other_routes:
        print(f"  {r}")

    # Explicit assertion check for essential Katip endpoints
    expected_katip = [
        "GET    /api/katip/projects",
        "POST   /api/katip/projects",
        "PUT    /api/katip/projects/{project_id}",
        "GET    /api/katip/projects/{project_id}/metrics",
        "GET    /api/katip/topics",
        "POST   /api/katip/topics",
        "GET    /api/katip/drafts",
        "GET    /api/katip/drafts/{draft_id}",
        "POST   /api/katip/drafts/generate",
        "POST   /api/katip/drafts/{draft_id}/feedback",
        "PUT    /api/katip/drafts/{draft_id}/status",
    ]

    all_entries = set()
    for path, methods in paths.items():
        for method in methods.keys():
            all_entries.add(f"{method.upper():<6} {path}")

    missing = [e for e in expected_katip if e not in all_entries]
    if missing:
        print(f"\n[ERROR] Missing expected Katip endpoints: {missing}")
        sys.exit(1)
    else:
        print("\n[OK] All expected Katip & Admin endpoints are present and correctly mounted!")

if __name__ == "__main__":
    audit_routes()
