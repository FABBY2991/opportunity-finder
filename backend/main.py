import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from database import get_db
from scraper import run_all_scrapers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")


def save_opportunities(items: list[dict]):
    try:
        db = get_db()
        for item in items:
            try:
                db.table("opportunities").upsert(
                    {**item, "scraped_at": datetime.now(timezone.utc).isoformat()},
                    on_conflict="url",
                ).execute()
            except Exception as e:
                logger.warning(f"DB upsert failed: {e}")
        logger.info(f"Saved {len(items)} opportunities")
    except Exception as e:
        logger.error(f"save_opportunities failed: {e}")


def scrape_and_save():
    logger.info("Scrape started...")
    try:
        items = run_all_scrapers()
        save_opportunities(items)
        logger.info(f"Scrape complete: {len(items)} items")
    except Exception as e:
        logger.error(f"Scrape failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run first scrape in background thread so port binds immediately
    threading.Thread(target=scrape_and_save, daemon=True).start()
    scheduler.add_job(scrape_and_save, "interval", hours=1, id="hourly_scrape")
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="OpportunityFinder", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    try:
        db = get_db()
        result = db.table("opportunities").select("id").limit(1).execute()
        return {"status": "ok", "db": "connected", "rows": len(result.data)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


@app.get("/api/opportunities")
def get_opportunities(
    category: str = Query(default=""),
    country: str = Query(default=""),
    search: str = Query(default=""),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
):
    try:
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
    except Exception as e:
        logger.error(f"get_opportunities error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/categories")
def get_categories():
    try:
        db = get_db()
        result = db.table("opportunities").select("category").execute()
        cats = sorted({r["category"] for r in result.data if r.get("category")})
        return {"categories": cats}
    except Exception as e:
        return {"categories": []}


@app.get("/api/countries")
def get_countries():
    try:
        db = get_db()
        result = db.table("opportunities").select("country").execute()
        countries = sorted({r["country"] for r in result.data if r.get("country")})
        return {"countries": countries}
    except Exception as e:
        return {"countries": []}


@app.post("/api/scrape")
def trigger_scrape():
    threading.Thread(target=scrape_and_save, daemon=True).start()
    return {"status": "scraping in background"}


# Serve frontend static files
if os.path.isdir(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
else:
    @app.get("/")
    def root():
        return {"message": "OpportunityFinder API running", "frontend_dir": STATIC_DIR}
