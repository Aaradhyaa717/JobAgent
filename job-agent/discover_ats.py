"""
Run this ONCE before setting up the real scraper.

It tests a list of guessed company "tokens" against the three ATS platforms
that expose public, unauthenticated JSON APIs (Greenhouse, Lever, Ashby).
Companies that don't show up here are almost certainly on Workday, a custom
site, or some other ATS -- those need a scraping approach instead of an API.

Usage:
    pip install requests
    python discover_ats.py

Output: prints a confirmed/unconfirmed report and writes discovery_results.json
"""

import requests
import json
import time

TIMEOUT = 10

# candidate tokens to try per company -- most companies use a lowercase,
# no-space version of their name, but this varies, so we try a few guesses.
CANDIDATES = {
    "Anthropic":        ["anthropic"],
    "OpenAI":           ["openai"],
    "Roblox":           ["roblox"],
    "Pinterest":        ["pinterest"],
    "Reddit":           ["reddit"],
    "Etsy":             ["etsy"],
    "Discord":          ["discord"],
    "Stripe":           ["stripe"],
    "Block":            ["block", "squareup", "square"],
    "Coinbase":         ["coinbase"],
    "Robinhood":        ["robinhood"],
    "Chime":            ["chime"],
    "Plaid":            ["plaid"],
    "Brex":             ["brex"],
    "Ramp":             ["ramp"],
    "Instacart":        ["instacart"],
    "Lyft":             ["lyft"],
    "Shopify":          ["shopify"],
    "Yelp":             ["yelp"],
    "Nextdoor":         ["nextdoor"],
    "Patreon":          ["patreon"],
    "Eventbrite":       ["eventbrite"],
    "StubHub":          ["stubhub"],
    "Rover":            ["rover", "roverdotcom"],
    "Snap":             ["snap", "snapinc"],
    "Spotify":          ["spotify"],
    "Airbnb":           ["airbnb"],
    "eBay":             ["ebay"],
    "PayPal":           ["paypal"],
    "SoFi":             ["sofi"],
    "Walmart":          ["walmart", "walmartglobaltech"],
    "Twitch":           ["twitch"],
    "TikTok":           ["tiktok", "bytedance"],
    "Google":           ["google"],
    "Apple":            ["apple"],
    "Uber":             ["uber"],
    "Amazon":           ["amazon"],
}

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
LEVER_URL = "https://api.lever.co/v0/postings/{token}?mode=json"
ASHBY_URL = "https://api.ashbyhq.com/posting-api/job-board/{token}"


def check_greenhouse(token):
    try:
        r = requests.get(GREENHOUSE_URL.format(token=token), timeout=TIMEOUT)
        if r.status_code == 200:
            jobs = r.json().get("jobs", [])
            if jobs:
                return len(jobs)
    except Exception:
        pass
    return None


def check_lever(token):
    try:
        r = requests.get(LEVER_URL.format(token=token), timeout=TIMEOUT)
        if r.status_code == 200:
            jobs = r.json()
            if isinstance(jobs, list) and jobs:
                return len(jobs)
    except Exception:
        pass
    return None


def check_ashby(token):
    try:
        r = requests.get(ASHBY_URL.format(token=token), timeout=TIMEOUT)
        if r.status_code == 200:
            jobs = r.json().get("jobs", [])
            if jobs:
                return len(jobs)
    except Exception:
        pass
    return None


def main():
    results = {}
    print(f"{'Company':<12} {'Token':<20} {'ATS':<12} {'#Jobs':<8}")
    print("-" * 55)

    for company, tokens in CANDIDATES.items():
        found = False
        for token in tokens:
            for ats_name, checker in [
                ("greenhouse", check_greenhouse),
                ("lever", check_lever),
                ("ashby", check_ashby),
            ]:
                count = checker(token)
                if count:
                    print(f"{company:<12} {token:<20} {ats_name:<12} {count:<8}")
                    results[company] = {"token": token, "ats": ats_name, "job_count": count}
                    found = True
                    break
            if found:
                break
            time.sleep(0.2)
        if not found:
            print(f"{company:<12} {'(none of: ' + ', '.join(tokens) + ')':<20} {'NOT FOUND':<12}")
            results[company] = {"token": None, "ats": "unknown/custom", "job_count": 0}

    with open("discovery_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\nSaved full results to discovery_results.json")
    print("Companies marked 'unknown/custom' need a different approach")
    print("(Workday, custom career site scraping, etc.) -- see README.md")


if __name__ == "__main__":
    main()
