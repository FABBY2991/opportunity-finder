import re
import httpx
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

COUNTRY_PATTERNS = [
    (r"\bUSA?\b|\bUnited States\b|\bU\.S\.A?\b", "USA"),
    (r"\bUK\b|\bUnited Kingdom\b|\bEngland\b|\bBritain\b", "UK"),
    (r"\bCanada\b|\bCA\b", "Canada"),
    (r"\bAustralia\b|\bAUS?\b", "Australia"),
    (r"\bGermany\b|\bDeutschland\b", "Germany"),
    (r"\bWorldwide\b|\bGlobal\b|\bAnywhere\b|\bRemote\b", "Worldwide"),
]

ENTRY_LEVEL_KEYWORDS = [
    "entry", "no experience", "beginner", "junior", "starter",
    "training provided", "we train", "train you", "no degree",
    "flexible", "part.?time", "work from home", "remote",
]

SKIP_KEYWORDS = [
    "senior", "lead", "manager", "director", "5+ years", "7+ years",
    "10+ years", "phd", "medical", "lawyer", "attorney",
]

CATEGORIES = {
    "Writing & Content": [
        "writer", "writing", "content", "blog", "copywrite", "copy",
        "editor", "proofreader", "ghostwriter", "journalist", "article",
        "SEO", "creative writing", "technical writer",
    ],
    "Chatting & Companion": [
        "chat operator", "chatter", "online chatter", "companion",
        "text chat", "chat agent", "messaging", "chat moderator",
        "fan engagement", "fan page", "aroa", "chat support agent",
    ],
    "OnlyFans Agency": [
        "onlyfans", "only fans", "of agency", "model manager",
        "content creator manager", "adult content", "creator support",
        "agency chatter", "fan management",
    ],
    "Virtual Assistant": [
        "virtual assistant", "VA", "admin assistant", "administrative",
        "data entry", "remote assistant", "online assistant",
    ],
    "Social Media": [
        "social media", "instagram", "tiktok", "twitter", "facebook",
        "influencer", "community manager", "social manager",
        "content moderator", "pinterest",
    ],
    "Customer Support": [
        "customer support", "customer service", "support agent",
        "help desk", "live chat support", "email support",
        "online support", "client support",
    ],
    "Transcription & Data": [
        "transcription", "transcribe", "data entry", "caption",
        "subtitle", "annotation", "labeling", "data collection",
    ],
    "Tutoring & Coaching": [
        "tutor", "tutoring", "teach", "teacher", "instructor",
        "coach", "mentor", "online teacher", "ESL", "English teacher",
        "language teacher",
    ],
    "Voiceover & Narration": [
        "voiceover", "voice over", "voice actor", "narrator",
        "podcast", "audio", "recording",
    ],
}


def detect_country(text: str) -> str:
    combined = (text or "").upper()
    for pattern, country in COUNTRY_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            return country
    return "Remote"


def detect_category(text: str) -> str:
    lower = (text or "").lower()
    for cat, keywords in CATEGORIES.items():
        if any(kw.lower() in lower for kw in keywords):
            return cat
    return "Other Online"


def is_entry_level(text: str) -> bool:
    lower = (text or "").lower()
    if any(re.search(kw, lower) for kw in SKIP_KEYWORDS):
        return False
    return True


def extract_pay(text: str) -> str:
    patterns = [
        r"\$[\d,]+(?:\.\d+)?(?:\s*[-–]\s*\$[\d,]+(?:\.\d+)?)?(?:\s*/\s*(?:hr|hour|mo|month|yr|year|week|article|word))?",
        r"[\d,]+\s*(?:USD|GBP|EUR|AUD)(?:\s*/\s*(?:hr|hour|mo|month|yr|year))?",
        r"(?:up to|starting at|from)\s+\$[\d,]+",
    ]
    for p in patterns:
        m = re.search(p, text or "", re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return "Negotiable"


# ── RSS-based sources ──────────────────────────────────────────────────────────

RSS_FEEDS = [
    # We Work Remotely
    ("https://weworkremotely.com/categories/remote-writing-editing-jobs.rss", "We Work Remotely"),
    ("https://weworkremotely.com/categories/remote-customer-support-jobs.rss", "We Work Remotely"),
    ("https://weworkremotely.com/categories/remote-sales-and-marketing-jobs.rss", "We Work Remotely"),
    # Remote.co
    ("https://remote.co/remote-jobs/feed/", "Remote.co"),
    # Working Nomads
    ("https://www.workingnomads.com/feed?category=writing", "Working Nomads"),
    ("https://www.workingnomads.com/feed?category=customer-support", "Working Nomads"),
    ("https://www.workingnomads.com/feed?category=virtual-assistant", "Working Nomads"),
    # ProBlogger
    ("https://problogger.com/jobs/feed/", "ProBlogger"),
    # Freelance Writing Gigs
    ("https://www.freelancewritinggigs.com/feed/", "Freelance Writing Gigs"),
    # Reddit r/forhire
    ("https://www.reddit.com/r/forhire/new/.rss?limit=50", "Reddit r/forhire"),
    # Hubstaff Talent
    ("https://hubstafftalent.net/rss_feed", "Hubstaff Talent"),
]


def parse_rss_feeds() -> list[dict]:
    results = []
    for url, source in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                link = entry.get("link", "")
                combined = f"{title} {summary}"

                if not is_entry_level(combined):
                    continue

                results.append({
                    "title": title[:200],
                    "description": BeautifulSoup(summary, "lxml").get_text()[:500],
                    "url": link,
                    "source": source,
                    "category": detect_category(combined),
                    "country": detect_country(combined),
                    "pay": extract_pay(combined),
                })
        except Exception as e:
            logger.warning(f"RSS feed failed {url}: {e}")
    return results


# ── ChatOperatorJobs scraper ───────────────────────────────────────────────────

def scrape_chat_operator_jobs() -> list[dict]:
    results = []
    try:
        with httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True) as client:
            resp = client.get("https://chatoperatorjobs.com/jobs/")
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            for card in soup.select(".job_listing, .job-listing, article")[:30]:
                title_el = card.select_one("h3, h2, .job-title, .position")
                link_el = card.select_one("a[href]")
                loc_el = card.select_one(".location, .job-location")
                title = title_el.get_text(strip=True) if title_el else ""
                link = link_el["href"] if link_el else ""
                loc = loc_el.get_text(strip=True) if loc_el else ""
                if not title:
                    continue
                results.append({
                    "title": title[:200],
                    "description": f"Chat operator / online chatter position. Location: {loc}",
                    "url": link,
                    "source": "ChatOperatorJobs",
                    "category": "Chatting & Companion",
                    "country": detect_country(f"{title} {loc}"),
                    "pay": extract_pay(f"{title} {loc}"),
                })
    except Exception as e:
        logger.warning(f"ChatOperatorJobs scrape failed: {e}")
    return results


# ── Indeed scraper (public listing pages) ─────────────────────────────────────

INDEED_QUERIES = [
    ("online+chatter", "Chatting & Companion"),
    ("chat+operator+remote", "Chatting & Companion"),
    ("onlyfans+agency+chatter", "OnlyFans Agency"),
    ("online+content+writer+entry+level", "Writing & Content"),
    ("virtual+assistant+no+experience", "Virtual Assistant"),
    ("online+tutor+entry+level", "Tutoring & Coaching"),
    ("transcription+remote+entry+level", "Transcription & Data"),
    ("social+media+manager+entry+level+remote", "Social Media"),
    ("customer+support+remote+entry+level", "Customer Support"),
    ("voiceover+remote+entry+level", "Voiceover & Narration"),
]


def scrape_indeed() -> list[dict]:
    results = []
    with httpx.Client(headers=HEADERS, timeout=20, follow_redirects=True) as client:
        for query, category in INDEED_QUERIES:
            try:
                url = f"https://www.indeed.com/jobs?q={query}&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11&sort=date"
                resp = client.get(url)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "lxml")
                for card in soup.select("[data-jk], .job_seen_beacon")[:10]:
                    title_el = card.select_one("h2 span, .jobTitle span")
                    company_el = card.select_one("[data-testid='company-name'], .companyName")
                    loc_el = card.select_one("[data-testid='text-location'], .companyLocation")
                    salary_el = card.select_one("[data-testid='attribute_snippet_testid'], .salary-snippet")
                    jk = card.get("data-jk", "")
                    title = title_el.get_text(strip=True) if title_el else ""
                    loc = loc_el.get_text(strip=True) if loc_el else "Remote"
                    pay = salary_el.get_text(strip=True) if salary_el else extract_pay(title)
                    if not title or not jk:
                        continue
                    if not is_entry_level(f"{title} {loc}"):
                        continue
                    results.append({
                        "title": title[:200],
                        "description": f"{company_el.get_text(strip=True) if company_el else ''} — {loc}",
                        "url": f"https://www.indeed.com/viewjob?jk={jk}",
                        "source": "Indeed",
                        "category": category,
                        "country": detect_country(loc),
                        "pay": pay or "Negotiable",
                    })
            except Exception as e:
                logger.warning(f"Indeed query '{query}' failed: {e}")
    return results


# ── Upwork public search ───────────────────────────────────────────────────────

UPWORK_QUERIES = [
    ("content+writer", "Writing & Content"),
    ("virtual+assistant", "Virtual Assistant"),
    ("social+media+manager", "Social Media"),
    ("transcription", "Transcription & Data"),
    ("online+tutor", "Tutoring & Coaching"),
    ("voiceover", "Voiceover & Narration"),
    ("customer+support+chat", "Customer Support"),
]


def scrape_upwork() -> list[dict]:
    results = []
    with httpx.Client(headers=HEADERS, timeout=20, follow_redirects=True) as client:
        for query, category in UPWORK_QUERIES:
            try:
                url = f"https://www.upwork.com/nx/search/jobs/?q={query}&sort=recency&page=1"
                resp = client.get(url)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "lxml")
                for card in soup.select("[data-test='job-tile-list'] article, .job-tile")[:8]:
                    title_el = card.select_one("h2 a, h3 a, [data-test='job-title']")
                    budget_el = card.select_one("[data-test='budget'], .js-budget")
                    desc_el = card.select_one("[data-test='job-description-text'], .js-job-snippet")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    href = title_el.get("href", "")
                    link = f"https://www.upwork.com{href}" if href.startswith("/") else href
                    desc = desc_el.get_text(strip=True)[:300] if desc_el else ""
                    pay = budget_el.get_text(strip=True) if budget_el else extract_pay(desc)
                    results.append({
                        "title": title[:200],
                        "description": desc,
                        "url": link,
                        "source": "Upwork",
                        "category": category,
                        "country": "Worldwide",
                        "pay": pay or "Negotiable",
                    })
            except Exception as e:
                logger.warning(f"Upwork query '{query}' failed: {e}")
    return results


# ── Blogging Pro ───────────────────────────────────────────────────────────────

def scrape_blogging_pro() -> list[dict]:
    results = []
    try:
        with httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True) as client:
            resp = client.get("https://www.bloggingpro.com/jobs/")
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            for card in soup.select(".job_listing, article.type-job_listing")[:15]:
                title_el = card.select_one("h3 a, h2 a")
                loc_el = card.select_one(".location")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                link = title_el.get("href", "")
                loc = loc_el.get_text(strip=True) if loc_el else "Remote"
                results.append({
                    "title": title[:200],
                    "description": f"Blogging/writing opportunity — {loc}",
                    "url": link,
                    "source": "Blogging Pro",
                    "category": "Writing & Content",
                    "country": detect_country(loc),
                    "pay": extract_pay(title),
                })
    except Exception as e:
        logger.warning(f"Blogging Pro scrape failed: {e}")
    return results


# ── Main runner ────────────────────────────────────────────────────────────────

def run_all_scrapers() -> list[dict]:
    all_results = []
    all_results.extend(parse_rss_feeds())
    all_results.extend(scrape_chat_operator_jobs())
    all_results.extend(scrape_indeed())
    all_results.extend(scrape_upwork())
    all_results.extend(scrape_blogging_pro())

    seen_urls = set()
    unique = []
    for item in all_results:
        url = (item.get("url") or "").strip()
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(item)
    return unique
