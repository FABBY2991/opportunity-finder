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

from database import db_select, db_upsert, health_check
from scraper import run_all_scrapers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")


def save_opportunities(items: list[dict]):
    saved = 0
    last_error = None
    for item in items:
        try:
            db_upsert("opportunities", {
                **item,
                "scraped_at": datetime.now(timezone.utc).isoformat()
            })
            saved += 1
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Upsert failed: {e}")
    logger.info(f"Saved {saved}/{len(items)} opportunities. Last error: {last_error}")


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
    return health_check()


@app.get("/api/opportunities")
def get_opportunities(
    category: str = Query(default=""),
    country: str = Query(default=""),
    search: str = Query(default=""),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
):
    try:
        filters = {}
        if category:
            filters["category"] = f"eq.{category}"
        if country:
            filters["country"] = f"eq.{country}"
        if search:
            filters["title"] = f"ilike.*{search}*"
        data = db_select(
            "opportunities",
            filters=filters,
            limit=limit,
            offset=offset,
            order="scraped_at.desc"
        )
        return {"data": data, "count": len(data)}
    except Exception as e:
        logger.error(f"get_opportunities error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/categories")
def get_categories():
    try:
        rows = db_select("opportunities", columns="category", limit=1000)
        cats = sorted({r["category"] for r in rows if r.get("category")})
        return {"categories": cats}
    except Exception as e:
        return {"categories": []}


@app.get("/api/countries")
def get_countries():
    try:
        rows = db_select("opportunities", columns="country", limit=1000)
        countries = sorted({r["country"] for r in rows if r.get("country")})
        return {"countries": countries}
    except Exception as e:
        return {"countries": []}


@app.post("/api/scrape")
def trigger_scrape():
    threading.Thread(target=scrape_and_save, daemon=True).start()
    return {"status": "scraping in background"}


if os.path.isdir(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
else:
    @app.get("/")
    def root():
        return {"message": "API running", "static_dir": STATIC_DIR}
