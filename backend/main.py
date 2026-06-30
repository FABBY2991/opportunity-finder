import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import get_db
from scraper import run_all_scrapers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def save_opportunities(items: list[dict]):
    db = get_db()
    for item in items:
        try:
            db.table("opportunities").upsert(
                {**item, "scraped_at": datetime.now(timezone.utc).isoformat()},
                on_conflict="url",
            ).execute()
        except Exception as e:
            logger.warning(f"DB upsert failed for {item.get('url')}: {e}")
    logger.info(f"Saved {len(items)} opportunities")


def scrape_and_save():
    logger.info("Starting scheduled scrape...")
    items = run_all_scrapers()
    save_opportunities(items)
    logger.info(f"Scrape done. {len(items)} items found.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scrape_and_save()  # run once on startup
    scheduler.add_job(scrape_and_save, "interval", hours=1, id="hourly_scrape")
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="OpportunityFinder", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.get("/api/opportunities")
def get_opportunities(
    category: str = Query(default=""),
    country: str = Query(default=""),
    search: str = Query(default=""),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
):
    db = get_db()
    query = db.table("opportunities").select("*").order("scraped_at", desc=True)

    if category:
        query = query.eq("category", category)
    if country:
        query = query.eq("country", country)
    if search:
        query = query.ilike("title", f"%{search}%")

    result = query.range(offset, offset + limit - 1).execute()
    return {"data": result.data, "count": len(result.data)}


@app.get("/api/categories")
def get_categories():
    db = get_db()
    result = db.table("opportunities").select("category").execute()
    cats = sorted({r["category"] for r in result.data if r.get("category")})
    return {"categories": cats}


@app.get("/api/countries")
def get_countries():
    db = get_db()
    result = db.table("opportunities").select("country").execute()
    countries = sorted({r["country"] for r in result.data if r.get("country")})
    return {"countries": countries}


@app.post("/api/scrape")
def trigger_scrape():
    scrape_and_save()
    return {"status": "done"}


@app.get("/", response_class=FileResponse)
def serve_frontend():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
