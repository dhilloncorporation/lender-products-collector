# System Architecture

## Workflow Flow

```
initialize → select_lender → discover_urls → analyze_page → 
collect_products → process_results → check_completion → [finalize | loop]
```

## Extraction Strategies (Priority Order)

1. Network Introspection (captured JSON APIs)
2. JSON-LD (structured data)
3. Embedded State (dataLayer, __NEXT_DATA__)
4. Select Dropdowns (ANZ-style) ✅
5. DOM Parsing (fallback)

## Data Storage Structure

```
data/
├── current/by_lender/{LENDER}.json
├── snapshots/parsed/{LENDER}/{timestamp}.json
└── index.json
```

## Agent Responsibilities

- **Orchestrator**: Coordinates workflow, manages state
- **Discovery**: Finds URLs via Google search
- **Collector**: Multi-strategy data extraction
- **Normalizer**: Standardizes to BIAN schema
- **Storage**: Persists data to JSON files
- **API**: Exposes data via REST endpoints

**Detailed agent documentation**: See docstrings in each agent file.
