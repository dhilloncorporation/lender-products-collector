# Google Custom Search API Setup

## Quick Setup

1. Enable Custom Search API in Google Cloud Console
2. Create API key (restrict to Custom Search API)
3. Create Programmable Search Engine (CSE)
4. Set environment variables:
   ```env
   CUSTOM_SEARCH_API_KEY=your_key
   CUSTOM_SEARCH_CX=your_cse_id
   ```

## Cost

- Free: 100 queries/day
- Paid: $5 per 1,000 queries
- Usage: ~6 queries per lender

## Benefits

✅ Compliant (official API)  
✅ Fast (1-2s vs 8-10s)  
✅ Reliable (no CAPTCHA)

**Detailed setup**: See code comments in `src/agents/discovery/google_custom_search.py`
