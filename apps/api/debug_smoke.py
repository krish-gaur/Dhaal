import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
os.environ["DATABASE_URL"] = "sqlite:///./test_debug.db"

from fastapi.testclient import TestClient
from main import app
from db.session_store import init_db
init_db()
client = TestClient(app, raise_server_exceptions=True)

r = client.post("/api/session", json={"use_fixture": True})
session_id = r.json()["session_id"]
print("session_id:", session_id)

fixture_pdf = Path(__file__).parent.parent.parent / "fixtures" / "policy_suraksha_shield.pdf"
print("fixture path:", fixture_pdf, "exists:", fixture_pdf.exists())

try:
    with open(fixture_pdf, "rb") as f:
        r2 = client.post(
            f"/api/session/{session_id}/document",
            files={"file": ("policy.pdf", f, "application/pdf")},
        )
    print("status:", r2.status_code, r2.text[:500])
except Exception as e:
    print("EXCEPTION:", type(e).__name__, e)
