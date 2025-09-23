import os
import json
import re
import sys
from typing import List, Dict, Any

try:
    from firecrawl import FirecrawlApp
except Exception as import_error:  # pragma: no cover
    print("Error: firecrawl SDK not installed. Run: pip install firecrawl-py", file=sys.stderr)
    raise


TARGET_URLS: List[str] = [
    # ANZ Australia home loans (public product/rates pages)
    "https://www.anz.com.au/personal/home-loans/interest-rates/",
    "https://www.anz.com.au/personal/home-loans/",
]


def extract_candidates(markdown: str) -> List[Dict[str, Any]]:
    """Very lightweight heuristic extraction from markdown.

    Note: Firecrawl can also be prompted to produce JSON directly via /extract
    or via the agent prompt. This simple parser provides a quick baseline.
    """
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    results: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}

    rate_regex = re.compile(r"(\d{1,2}\.\d{1,3})\s*%")
    product_regex = re.compile(r"^(?:#+\s*)?([A-Z][\w&\- +'’]+(Home|Fixed|Variable|Loan)[\w&\- +'’]*)$", re.I)

    for line in lines:
        if product_regex.match(line):
            if current:
                results.append(current)
            current = {"product_name": line, "rates": [], "notes": []}
            continue

        for m in rate_regex.findall(line):
            try:
                rate = float(m)
            except Exception:
                continue
            current.setdefault("rates", []).append({"rate_percent": rate, "source": line})

        if any(k in line.lower() for k in ["comparison", "intro", "fixed", "variable", "cashback", "fee"]):
            current.setdefault("notes", []).append(line)

    if current:
        results.append(current)
    return results


def scrape_anz() -> Dict[str, Any]:
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        print("Error: Set FIRECRAWL_API_KEY in your environment.", file=sys.stderr)
        sys.exit(1)

    app = FirecrawlApp(api_key=api_key)

    aggregated: List[Dict[str, Any]] = []

    for url in TARGET_URLS:
        scrape = app.scrape_url(
            url,
            {
                "formats": ["markdown", "html"],
                "agent": {
                    "model": "FIRE-1",
                    "prompt": (
                        "You are collecting ANZ home loan product info. "
                        "Identify product names, variable/fixed rates, comparison rates, fees, and any current offers/cashback. "
                        "Prefer concise bullet points in markdown."
                    ),
                },
            },
        )

        markdown = scrape.get("markdown") or ""
        html = scrape.get("html") or ""

        items = extract_candidates(markdown) or []
        aggregated.append({
            "url": url,
            "found_items": items,
            "raw_lengths": {"markdown": len(markdown), "html": len(html)},
        })

    return {"source": "anz", "results": aggregated}


if __name__ == "__main__":
    data = scrape_anz()
    print(json.dumps(data, indent=2))


