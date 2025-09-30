# Extraction Strategies - Complete Implementation

## Overview

Our system uses a **cascading multi-strategy approach** that tries methods in order of reliability and speed. This ensures maximum coverage across all Australian lenders.

## Implemented Strategies

### Strategy 0: Network Introspection ✅
**Status**: Fully implemented  
**Speed**: ⚡⚡⚡ Fastest  
**Reliability**: ⭐⭐⭐⭐⭐ Most reliable

**How it works**:
1. Playwright captures all JSON API calls made by the page
2. Parses response JSON directly
3. Recursively searches for product arrays
4. Maps to BIAN schema

**Best for**: Modern React/Next.js sites that load data via fetch/XHR

**Code**: `_extract_from_captured_apis()`

### Strategy 1: JSON-LD Structured Data ✅  
**Status**: Fully implemented  
**Speed**: ⚡⚡⚡ Very fast  
**Reliability**: ⭐⭐⭐⭐ Reliable

**How it works**:
1. Finds `<script type="application/ld+json">` tags
2. Parses schema.org Product/FinancialProduct objects
3. Maps offers/pricing to BIAN schema

**Best for**: Sites with SEO-optimized structured data

**Code**: `_extract_from_jsonld()`

### Strategy 2: Embedded JavaScript State ✅
**Status**: Fully implemented  
**Speed**: ⚡⚡⚡ Very fast  
**Reliability**: ⭐⭐⭐⭐ Reliable

**How it works**:
1. Executes JavaScript to access `window` objects
2. Checks: `__NEXT_DATA__`, `__NUXT__`, `dataLayer`, `Shopify`
3. Parses product data from state
4. Maps to BIAN schema

**Best for**: Next.js, Nuxt, or sites using Google Tag Manager (CBA, ANZ)

**Code**: `_extract_from_embedded_state()`, `_parse_datalayer()`, `_parse_nextjs_data()`

### Strategy 3: Select Dropdowns ✅
**Status**: Fully implemented & WORKING!  
**Speed**: ⚡⚡ Fast  
**Reliability**: ⭐⭐⭐⭐ Reliable

**How it works**:
1. Finds `<select>` elements with rate/interest in ID
2. Extracts `<option>` text values
3. Parses with regex: `"{rate}% p.a {name} {LVR}"`
4. Creates BIAN products

**Best for**: ANZ, banks that embed data in calculator dropdowns

**Proven**: ✅ ANZ - 8 products extracted!

**Code**: `_extract_from_select_dropdowns()`, `_parse_rate_dropdown_option()`

### Strategy 4: DOM Parsing ✅
**Status**: Implemented (fallback)  
**Speed**: ⚡ Slower  
**Reliability**: ⭐⭐ Less reliable

**How it works**:
1. Uses CSS selectors to find product containers
2. Extracts text from various elements
3. Attempts to parse rates, features, fees
4. Maps to BIAN schema

**Best for**: Simple HTML pages, last resort

**Code**: `_extract_products()` (legacy method)

### Strategy 5: Google Search Discovery ✅
**Status**: Fully implemented  
**Speed**: ⚡ Depends on search  
**Reliability**: ⭐⭐⭐⭐ Reliable

**How it works**:
1. Searches Google for lender pages: `"site:commbank.com.au home loan interest rates"`
2. Extracts top 3-5 result URLs
3. Returns URLs categorized by type (rates, products, fees)

**Best for**: Dynamic URL discovery, self-healing system

**Code**: `src/agents/discovery/google_search_discovery.py`

## Strategy Selection by Bank

Based on our batch analysis:

| Bank | Primary Strategy | Fallback | Status |
|------|------------------|----------|--------|
| ANZ | Select Dropdown | dataLayer, JSON-LD | ✅ 8 products |
| CBA | dataLayer (embedded state) | DOM parsing | ⚠️ 0 products |
| NAB | JSON-LD | DOM parsing | ⚠️ 0 products |
| Westpac | DOM parsing | Network introspection | ⚠️ 0 products |

## Execution Flow

```
Page loads → Playwright captures network calls
     ↓
Strategy 0: Check captured JSON APIs
     ↓ (if none)
Strategy 1: Check JSON-LD scripts
     ↓ (if none)
Strategy 2: Check embedded state (dataLayer, __NEXT_DATA__)
     ↓ (if none)
Strategy 3: Check select dropdowns
     ↓ (if none)
Strategy 4: Parse DOM with CSS selectors
     ↓
Return products (or empty list)
```

## Configuration

### Static URLs (Current):
- Defined in `src/configs/lenders.json`
- URLs auto-generated from abbreviation
- **Problem**: Hardcoded, breaks when URLs change

### Google Search Discovery (Recommended):
- Use `GoogleSearchDiscovery` to find pages dynamically
- Self-healing - adapts to URL changes
- More resilient

## Testing Each Strategy

```bash
# Test complete workflow
python run_collection.py

# Debug specific bank
python debug/scraper/batch_analyze_banks.py

# Test Google search discovery
python src/agents/discovery/google_search_discovery.py
```

## Next Steps to Improve Coverage

### For CBA (0 products):
1. Inspect `window.dataLayer` content
2. Find product data structure
3. Enhance `_parse_datalayer()` with CBA-specific logic

### For NAB (0 products):
1. Check JSON-LD content (2 scripts found)
2. Verify if they contain financial products
3. Enhance JSON-LD parsing if needed

### For Westpac (0 products):
1. Check for network calls (API endpoints)
2. Improve DOM selectors
3. Consider PDF extraction if rates are in PDFs

## Success Metrics

- **ANZ**: ✅ 100% (8/8 products via select dropdown)
- **CBA**: ❌ 0% (needs dataLayer implementation)
- **NAB**: ❌ 0% (needs JSON-LD enhancement)
- **Westpac**: ❌ 0% (needs investigation)

**Overall**: 25% (1/4 banks working)

**Goal**: 100% (all major banks)
