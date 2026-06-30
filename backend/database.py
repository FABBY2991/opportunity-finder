import os
import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}


def db_select(table: str, filters: dict = None, columns: str = "*", limit: int = 200, offset: int = 0, order: str = None) -> list[dict]:
    params = {"select": columns, "limit": limit, "offset": offset}
    if order:
        params["order"] = order
    if filters:
        params.update(filters)
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    with httpx.Client(timeout=10) as client:
        resp = client.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        return resp.json()


def db_upsert(table: str, data: dict) -> None:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {**HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"}
    with httpx.Client(timeout=10) as client:
        resp = client.post(url, headers=headers, json=data)
        resp.raise_for_status()


def health_check() -> dict:
    try:
        rows = db_select("opportunities", limit=1)
        return {"status": "ok", "db": "connected", "rows": len(rows)}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
