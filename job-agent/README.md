# Trust & Safety / Risk Job Agent

Watches career pages at 35+ companies for roles matching your keyword list,
emails you daily (new roles only) and weekly (full snapshot), and keeps an
Excel file (`data/jobs.xlsx`) updated automatically via GitHub Actions.

## How it works

- **Greenhouse, Lever, and Ashby** all expose free public JSON APIs for job
  listings — no scraping needed, no API key required. Most of the companies
  in your list are likely on one of these.
- Companies on **Workday or a fully custom career site** (Google, Apple,
  Amazon, Uber, etc.) don't have a simple public API, so they need actual
  page scraping. Those are stubbed in `config.yaml` as `type: custom` for now
  — see "Custom sites" below.
- A GitHub Action runs the script on a schedule (free, no server required),
  commits the updated Excel file + "seen jobs" state back to your repo, and
  emails you.

## Setup steps

### 1. Verify which ATS each company actually uses

Company career pages change ATS providers over time, so don't trust guesses.
Run:

```bash
pip install requests
python discover_ats.py
```

This tests each company against Greenhouse/Lever/Ashby and prints what it
finds, plus writes `discovery_results.json`. Update `config.yaml` with any
corrected tokens (the ones marked `# GUESS -- verify` need checking).

### 2. Create a GitHub repo

Push this whole folder to a new **private** GitHub repo (private matters —
your job search preferences and the state file will live there).

```bash
cd job-agent
git init
git add .
git commit -m "Initial job agent"
gh repo create job-agent --private --source=. --push
# (or create the repo on github.com and `git remote add origin ...` + push)
```

### 3. Set up email sending (Gmail example)

1. Turn on 2-Step Verification on the Gmail account you'll send from.
2. Create an **App Password**: Google Account → Security → 2-Step
   Verification → App passwords → generate one for "Mail".
3. In your GitHub repo: Settings → Secrets and variables → Actions → New
   repository secret. Add these four:
   - `SMTP_HOST` = `smtp.gmail.com`
   - `SMTP_PORT` = `587`
   - `SMTP_USER` = your Gmail address
   - `SMTP_PASS` = the app password (not your normal password)
   - `EMAIL_TO` = the address you want alerts sent to

(Any SMTP provider works, not just Gmail — SendGrid, Mailgun, Outlook, etc.
Just change `SMTP_HOST`/`SMTP_PORT` accordingly.)

### 4. Turn on the schedule

The two workflows (`.github/workflows/daily.yml` and `weekly.yml`) are
already set to run automatically once pushed — daily at 1pm UTC, weekly on
Mondays at 1pm UTC. Edit the `cron` lines if you want different times
([crontab.guru](https://crontab.guru) helps with the syntax).

You can also trigger a run manually any time: repo → Actions tab → select
the workflow → "Run workflow".

### 5. First run

Trigger the daily workflow manually once to make sure secrets are wired up
correctly and you receive a test email. The first daily run will treat
*every* current match as "new" since there's no prior state yet — that's
expected, it settles into true daily-diff mode after that.

## Custom sites (Google, Apple, Amazon, Uber, Airbnb, eBay, PayPal, SoFi,
## Snap, Spotify, TikTok, Walmart)

These don't have a simple public JSON API. Three options, roughly in order
of effort:

1. **Cheapest to build, small ongoing cost**: use a job-aggregator API
   (e.g. a service that already indexes 50+ ATS platforms including Workday
   and custom sites) instead of scraping these yourself. Point the `custom`
   entries at that instead.
2. **Free, more maintenance**: write a per-site scraper using Playwright
   (needed because most of these render job listings with JavaScript) with
   CSS selectors specific to each site. I can build these out for specific
   companies if you tell me which ones matter most — they're brittle and
   need occasional fixing when a site redesigns.
3. **Manual fallback**: leave these off the automation and just check them
   yourself occasionally; let the agent handle the ~20 companies that are
   on Greenhouse/Lever/Ashby.

Let me know which companies from that list are highest priority and I can
build the actual scraper for those specifically.

## Files

- `config.yaml` — keyword list + company list/tokens (edit this to add/remove companies or keywords)
- `discover_ats.py` — one-time helper to verify ATS tokens
- `scraper.py` — main script (`daily` or `weekly` mode)
- `data/seen_jobs.json` — tracks which jobs have already been alerted on
- `data/jobs.xlsx` — the running Excel export
- `.github/workflows/` — the two scheduled jobs
