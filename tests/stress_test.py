"""
stress_test.py
~~~~~~~~~~~~~~

Stress testing script for the Mergen Panel FastAPI backend.
Simulates high-concurrency client registrations to test backend stability and performance.

Spawns exactly 100 concurrent POST requests to http://localhost:8000/api/onboarding.
Uses standard Python asyncio and httpx.AsyncClient (no locust or heavy frameworks).

Usage:
    uv run stress_test.py
"""

from __future__ import annotations

import asyncio
import time
import httpx
from typing import List

TARGET_URL = "http://localhost:8000/api/onboarding"
CONCURRENT_REQUESTS = 100


async def worker(client: httpx.AsyncClient, worker_id: int) -> int:
    """Send a single registration request and return the HTTP status code (or 0 on error)."""
    payload = {
        "business_name": f"Stress Test Business {worker_id}",
        "phone_number": f"+90555000{worker_id:04d}",
        "business_hours": {"monday": "09:00-18:00", "tuesday": "09:00-18:00"},
        "location": "Kadikoy, Istanbul",
        "cancellation_policy": "24 hours notice required",
        "contact_info": f"stress_{worker_id}@example.com",
        "services": [{"name": "Testing service", "price": "100 TL", "description": "Testing description"}],
        "pricing": "Testing pricing",
        "plan": "starter"
    }
    
    try:
        response = await client.post(TARGET_URL, json=payload)
        return response.status_code
    except httpx.RequestError as exc:
        # Gracefully handle connection drops or timeouts under load
        print(f"[Worker {worker_id}] Connection error: {exc}")
        return 0


async def main() -> None:
    print("=" * 60)
    print(" Starting FastAPI Onboarding Stress Test...")
    print(f" Target: {TARGET_URL}")
    print(f" Concurrency: {CONCURRENT_REQUESTS} requests")
    print("=" * 60)
    print()

    # Use a large timeout (30s) to handle server delays under load
    limits = httpx.Limits(max_keepalive_connections=CONCURRENT_REQUESTS, max_connections=CONCURRENT_REQUESTS)
    async with httpx.AsyncClient(timeout=30.0, limits=limits) as client:
        start_time = time.perf_counter()
        
        # Spawn exactly 100 concurrent tasks
        tasks = [worker(client, i) for i in range(CONCURRENT_REQUESTS)]
        status_codes: List[int] = await asyncio.gather(*tasks)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time

    # Calculate statistics
    success_count = sum(1 for code in status_codes if 200 <= code < 300)
    failed_count = sum(1 for code in status_codes if (400 <= code < 600) or code == 0)
    
    # Group results for reporting
    status_summary = {}
    for code in status_codes:
        label = f"HTTP {code}" if code != 0 else "Connection Error"
        status_summary[label] = status_summary.get(label, 0) + 1

    print("-" * 60)
    print(" Stress Test Summary")
    print("-" * 60)
    print(f" Total Execution Time:  {total_time:.4f} seconds")
    print(f" Average Request Time:  {(total_time / CONCURRENT_REQUESTS) * 1000:.2f} ms")
    print(f" Successful (2xx):      {success_count}")
    print(f" Failed (4xx/5xx/err):  {failed_count}")
    print("\n Detailed Status Codes:")
    for label, count in sorted(status_summary.items()):
        print(f"   - {label}: {count} request(s)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
