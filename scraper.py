"""
Trust & Safety / Risk job hunter.

Modes:
    python scraper.py daily    -> only NEW jobs since last run -> email + append to excel
    python scraper.py weekly   -> full current snapshot of every matching job -> email + excel

Requires environment variables (set as GitHub Actions secrets):
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_TO
    (SMTP_USER/PASS for a Gmail account: use an "app password", not your real password)

State is kept in data/seen_jobs.json, committed back to the repo by the
GitHub Action after each run so "new since yesterday" works across runs.
"""

import os
import sys
import json
import time
import smtplib
import requests
import yaml
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from openpyxl import Workbook, load_workbook

CONFIG_PATH = "config.yaml"
STATE_PATH = "data/seen_jobs.json"
EXCEL_PATH = "data/jobs.xlsx"
TIMEOUT = 15


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f)
    return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def matches_keywords(title, keywords):
    title_lower = title.lower()
    return [kw for kw in keywords if kw.lower() in title_lower]


def fetch_greenhouse(token):
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    jobs = []
    for j in r.json().get("jobs", []):
        jobs.append({
            "id": str(j["id"]),
            "title": j["title"],
            "location": j.get("location", {}).get("name", ""),
            "url": j["absolute_url"],
        })
    return jobs


def fetch_lever(token):
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    jobs = []
    for j in r.json():
        jobs.append({
            "id": j["id"],
            "title": j["text"],
            "location": j.get("categories", {}).get("location", ""),
            "url": j["hostedUrl"],
        })
    return jobs


def fetch_ashby(token):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    jobs = []
    for j in r.json().get("jobs", []):
        jobs.append({
            "id": j["id"],
            "title": j["title"],
            "location": j.get("location", ""),
            "url": j["jobUrl"],
        })
    return jobs


def fetch_custom(company):
    # Custom career sites vary too much for one generic scraper to handle
    # reliably (JS-rendered pages, different HTML structures, etc).
    # This is a placeholder that companies of type "custom" hit --
    # see README.md "Custom sites" section for how to fill these in
    # (e.g. with Playwright) once you know each site's structure.
    return []


def fetch_company_jobs(company):
    ctype = company["type"]
    try:
        if ctype == "greenhouse":
            return fetch_greenhouse(company["token"])
        elif ctype == "lever":
            return fetch_lever(company["token"])
        elif ctype == "ashby":
            return fetch_ashby(company["token"])
        elif ctype == "custom":
            return fetch_custom(company)
    except Exception as e:
        print(f"  [warn] {company['name']}: fetch failed ({e})")
        return []
    return []


def collect_matches(config):
    """Returns list of dicts: company, title, location, url, matched_keywords, job_key"""
    all_matches = []
    for company in config["companies"]:
        jobs = fetch_company_jobs(company)
        for job in jobs:
            hits = matches_keywords(job["title"], config["keywords"])
            if hits:
                all_matches.append({
                    "company": company["name"],
                    "title": job["title"],
                    "location": job.get("location", ""),
                    "url": job["url"],
                    "matched_keywords": ", ".join(hits),
                    "job_key": f"{company['name']}::{job['id']}",
                })
        time.sleep(0.3)  # be polite to the APIs
    return all_matches


def write_excel(matches, path, mode):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        wb = load_workbook(path)
    else:
        wb = Workbook()
        wb.remove(wb.active)

    sheet_name = "Weekly Snapshot" if mode == "weekly" else "Daily New"
    if sheet_name in wb.sheetnames:
        del wb[sheet_name]
    ws = wb.create_sheet(sheet_name, 0)
    ws.append(["Date Found", "Company", "Title", "Location", "Matched Keywords", "URL"])

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for m in matches:
        ws.append([today, m["company"], m["title"], m["location"], m["matched_keywords"], m["url"]])

    for col in ws.columns:
        max_len = max(len(str(c.value)) for c in col if c.value)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 60)

    wb.save(path)


def send_email(subject, matches, mode):
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    email_to = os.environ["EMAIL_TO"]

    if not matches:
        body = "No new matching roles today." if mode == "daily" else "No matching roles found this week."
    else:
        lines = []
        for m in matches:
            lines.append(
                f"{m['company']} -- {m['title']} ({m['location']})\n"
                f"  matched: {m['matched_keywords']}\n"
                f"  {m['url']}\n"
            )
        body = "\n".join(lines)

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = email_to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    # attach the excel file
    if os.path.exists(EXCEL_PATH):
        with open(EXCEL_PATH, "rb") as f:
            from email.mime.base import MIMEBase
            from email import encoders
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename="jobs.xlsx")
            msg.attach(part)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)


def run(mode):
    config = load_config()
    state = load_state()
    all_matches = collect_matches(config)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if mode == "daily":
        new_matches = [m for m in all_matches if m["job_key"] not in state]
        for m in new_matches:
            state[m["job_key"]] = today
        save_state(state)
        write_excel(new_matches, EXCEL_PATH, "daily")
        print(f"Found {len(new_matches)} NEW matching jobs.")
        send_email(f"[Job Agent] {len(new_matches)} new T&S/Risk roles today", new_matches, "daily")
    elif mode == "weekly":
        # weekly = full snapshot, regardless of "seen" status
        for m in all_matches:
            state.setdefault(m["job_key"], today)
        save_state(state)
        write_excel(all_matches, EXCEL_PATH, "weekly")
        print(f"Found {len(all_matches)} matching jobs (full snapshot).")
        send_email(f"[Job Agent] Weekly snapshot: {len(all_matches)} matching roles", all_matches, "weekly")
    else:
        print("Usage: python scraper.py [daily|weekly]")
        sys.exit(1)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "daily"
    run(mode)
