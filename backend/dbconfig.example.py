"""Neon PostgreSQL connection config — TEMPLATE.

Deployment (Hugging Face Space): set the DATABASE_URL secret in the Space's
settings; the app reads it from the environment automatically.

Local development: copy this file to dbconfig.py and paste in the
connection string (get it from the team lead privately — it contains the
database password).
"""

import os

DATABASE_URL = os.environ.get("DATABASE_URL") or (
    "postgresql://USER:PASSWORD@YOUR-NEON-HOST.neon.tech/neondb?sslmode=require"
)
