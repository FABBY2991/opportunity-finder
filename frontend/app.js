const API = "";  // same origin — Render serves both API and frontend
let offset = 0;
const PAGE_SIZE = 50;
let autoRefreshTimer = null;

const CATEGORY_CLASSES = {
  "Writing & Content":    "tag-writing",
  "Chatting & Companion": "tag-chatting",
  "OnlyFans Agency":      "tag-onlyfans",
  "Virtual Assistant":    "tag-va",
  "Social Media":         "tag-social",
  "Customer Support":     "tag-support",
  "Transcription & Data": "tag-data",
  "Tutoring & Coaching":  "tag-tutoring",
  "Voiceover & Narration":"tag-voice",
};

const COUNTRY_FLAGS = {
  "USA": "🇺🇸", "UK": "🇬🇧", "Canada": "🇨🇦",
  "Australia": "🇦🇺", "Germany": "🇩🇪",
  "Worldwide": "🌍", "Remote": "💻",
};

function categoryClass(cat) {
  return CATEGORY_CLASSES[cat] || "tag-other";
}

function countryFlag(country) {
  return COUNTRY_FLAGS[country] || "🌐";
}

async function fetchJSON(path) {
  const res = await fetch(API + path);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function populateFilters() {
  try {
    const [catData, countryData] = await Promise.all([
      fetchJSON("/api/categories"),
      fetchJSON("/api/countries"),
    ]);
    const catSel = document.getElementById("filter-category");
    catData.categories.forEach(c => {
      const o = document.createElement("option");
      o.value = c; o.textContent = c;
      catSel.appendChild(o);
    });
    const countrySel = document.getElementById("filter-country");
    countryData.countries.forEach(c => {
      const o = document.createElement("option");
      o.value = c; o.textContent = `${countryFlag(c)} ${c}`;
      countrySel.appendChild(o);
    });
  } catch (e) {
    console.warn("Filter population failed:", e);
  }
}

function buildParams(extra = {}) {
  const params = new URLSearchParams();
  const search = document.getElementById("search").value.trim();
  const cat = document.getElementById("filter-category").value;
  const country = document.getElementById("filter-country").value;
  if (search) params.set("search", search);
  if (cat) params.set("category", cat);
  if (country) params.set("country", country);
  params.set("limit", PAGE_SIZE);
  params.set("offset", extra.offset ?? 0);
  return params.toString();
}

function renderCard(job) {
  const flag = countryFlag(job.country);
  const catCls = categoryClass(job.category);
  const timeAgo = job.scraped_at ? timeSince(job.scraped_at) : "";
  return `
    <div class="job-card">
      <div class="card-top">
        <div class="job-title">${escHtml(job.title)}</div>
        <div class="country-badge">
          <span class="flag">${flag}</span>${escHtml(job.country)}
        </div>
      </div>
      <span class="category-tag ${catCls}">${escHtml(job.category)}</span>
      <p class="job-desc">${escHtml(job.description || "")}</p>
      <div class="card-bottom">
        <span class="pay">${escHtml(job.pay || "Negotiable")}</span>
        <span class="source">${escHtml(job.source)} · ${timeAgo}</span>
      </div>
      ${job.url ? `<a class="apply-btn" href="${escHtml(job.url)}" target="_blank" rel="noopener">Apply / View →</a>` : ""}
    </div>`;
}

async function loadJobs() {
  offset = 0;
  const grid = document.getElementById("job-grid");
  grid.innerHTML = '<div class="spinner"></div>';
  document.getElementById("btn-more").style.display = "none";
  try {
    const data = await fetchJSON(`/api/opportunities?${buildParams({ offset: 0 })}`);
    const jobs = data.data || [];
    if (jobs.length === 0) {
      grid.innerHTML = '<p class="empty">No opportunities found. Try changing filters or refresh soon.</p>';
    } else {
      grid.innerHTML = jobs.map(renderCard).join("");
      offset = jobs.length;
      if (jobs.length >= PAGE_SIZE) document.getElementById("btn-more").style.display = "inline-block";
    }
    document.getElementById("result-count").textContent = `${jobs.length} listings`;
    document.getElementById("last-updated").textContent = `Updated ${timeSince(new Date().toISOString())} ago`;
  } catch (e) {
    grid.innerHTML = `<p class="empty">Could not load jobs — scraper is still warming up. Wait 1 minute and click Refresh.</p>`;
  }
}

async function loadMore() {
  try {
    const data = await fetchJSON(`/api/opportunities?${buildParams({ offset })}`);
    const jobs = data.data || [];
    const grid = document.getElementById("job-grid");
    grid.insertAdjacentHTML("beforeend", jobs.map(renderCard).join(""));
    offset += jobs.length;
    if (jobs.length < PAGE_SIZE) document.getElementById("btn-more").style.display = "none";
  } catch (e) {
    console.warn("Load more failed:", e);
  }
}

function timeSince(isoStr) {
  const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
  if (diff < 60) return `${diff}s`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

function escHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Debounced search
let searchTimer;
document.getElementById("search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadJobs, 400);
});
document.getElementById("filter-category").addEventListener("change", loadJobs);
document.getElementById("filter-country").addEventListener("change", loadJobs);

// Auto-refresh every hour to pick up new scrape results
function startAutoRefresh() {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer);
  autoRefreshTimer = setInterval(() => {
    loadJobs();
  }, 60 * 60 * 1000);
}

// Init
populateFilters();
loadJobs();
startAutoRefresh();
