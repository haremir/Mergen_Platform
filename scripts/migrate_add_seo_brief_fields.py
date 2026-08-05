"""
scripts/migrate_add_seo_brief_fields.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Adds SEO Brief columns to katip_topics_queue table (safe IF NOT EXISTS).
Run once: uv run python scripts/migrate_add_seo_brief_fields.py
"""
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (_ROOT, os.path.join(_ROOT, "shared"), os.path.join(_ROOT, "core"),
           os.path.join(_ROOT, "packages"), os.path.join(_ROOT, "products")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(_ROOT, ".env"))

db_url = os.getenv("DATABASE_URL", "")
# Parse credentials
import re
m = re.match(r"postgresql(?:\+[^:]+)?://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/([^?]+)", db_url)
if m:
    user, password, host, port, dbname = m.group(1), m.group(2), m.group(3), int(m.group(4) or 5432), m.group(5)
else:
    user, password, host, port, dbname = "postgres", "postgres", "127.0.0.1", 5432, "mergen_db"

conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)
conn.autocommit = True
cur = conn.cursor()

migrations = [
    ("target_subheadings", "ALTER TABLE katip_topics_queue ADD COLUMN IF NOT EXISTS target_subheadings JSONB DEFAULT '[]'::jsonb"),
    ("special_instructions", "ALTER TABLE katip_topics_queue ADD COLUMN IF NOT EXISTS special_instructions TEXT"),
    ("scheduled_for", "ALTER TABLE katip_topics_queue ADD COLUMN IF NOT EXISTS scheduled_for TIMESTAMPTZ"),
]

for col_name, sql in migrations:
    try:
        cur.execute(sql)
        print(f"  [OK] Column '{col_name}' ensured.")
    except Exception as e:
        print(f"  [ERR] {col_name}: {e}")

cur.close()
conn.close()
print("\n[DONE] SEO Brief columns migration complete.")
