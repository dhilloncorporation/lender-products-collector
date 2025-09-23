# Lender Products Collector — Environment Setup

This project uses Python 3.11 and Firecrawl to scrape public lender pages and output structured data.

## Prerequisites
- Python 3.11+
- Git

## Create and activate a virtual environment (Windows)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Git Bash:
```bash
python3 -m venv .venv
source .venv/Scripts/activate
```

## Install dependencies
```bash
pip install -r requirements.txt
```

## Configure environment
Set your Firecrawl API key:
- PowerShell:
```powershell
$env:FIRECRAWL_API_KEY="YOUR_KEY"
```
- Git Bash:
```bash
export FIRECRAWL_API_KEY="YOUR_KEY"
```

## Run the sample script
```bash
python test.py
```

## Notes
- Keep a separate `.venv` per project; `.venv/` is git‑ignored.
- Respect each lender website's Terms of Use and robots.txt.
- Reference: https://www.firecrawl.dev/blog/best-open-source-agent-frameworks-2025
