import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_client: Client | None = None

def get_db() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS opportunities (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    url TEXT UNIQUE NOT NULL,
    source TEXT,
    category TEXT,
    country TEXT DEFAULT 'USA',
    pay TEXT,
    posted_at TIMESTAMPTZ DEFAULT NOW(),
    scraped_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_opportunities_scraped_at ON opportunities(scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_opportunities_category ON opportunities(category);
"""
