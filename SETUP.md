# OpportunityFinder — Setup Guide

## Step 1 — Create Supabase database (free, takes 3 minutes)

1. Go to https://supabase.com → Sign up free
2. Create a new project (pick any region, set a password)
3. Once ready, go to **SQL Editor** and paste this:

```sql
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
```

4. Click **Run**
5. Go to **Settings → API** and copy:
   - `Project URL` → this is your SUPABASE_URL
   - `anon public` key → this is your SUPABASE_KEY

---

## Step 2 — Deploy to Render (free, takes 5 minutes)

1. Push this project to a GitHub repo (public or private)
2. Go to https://render.com → Sign up free
3. Click **New → Web Service** → connect your GitHub repo
4. Set:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Under **Environment Variables**, add:
   - `SUPABASE_URL` → paste from Step 1
   - `SUPABASE_KEY` → paste from Step 1
6. Click **Create Web Service**

Render gives you a free URL like: `https://opportunity-finder-xxxx.onrender.com`

---

## What it does

- On startup, immediately scrapes all sources
- Scrapes again every hour automatically
- When you open the website, live feed loads instantly
- Filter by category, country, or search by keyword
- Each card shows: job title, country flag, category, pay, source, and apply link

## Sources scraped

- We Work Remotely (writing, support, marketing)
- Remote.co
- Working Nomads
- ProBlogger Jobs
- Freelance Writing Gigs
- ChatOperatorJobs.com (chatting & companion agencies)
- Reddit r/forhire
- Hubstaff Talent
- Indeed (remote entry-level queries)
- Upwork (public listings)
- Blogging Pro

## Categories tracked

- Writing & Content
- Chatting & Companion (chat operators, companion platforms)
- OnlyFans Agency (chatters, model managers)
- Virtual Assistant
- Social Media Management
- Customer Support
- Transcription & Data Entry
- Tutoring & Coaching
- Voiceover & Narration

## Note on free tier

Render's free tier spins down after 15 min of inactivity.
First load after sleep takes ~30 seconds to wake up.
Upgrade to Render's $7/month plan for always-on if needed.
