# Collector Agent Documentation

## Overview

The **Collector Agent** is the core web scraping and data extraction engine of the Lender Products Collector system. It uses Playwright for browser automation and implements multiple extraction strategies to capture comprehensive, high-quality financial product data.

## Key Capabilities

### 1. Multi-Strategy Extraction
The collector employs 7 different extraction strategies, executed in priority order:
- **Network API Interception** (highest confidence)
- **JSON-LD Structured Data**
- **Embedded State Extraction**
- **Compare Cards**
- **UI State Enumeration** (most comprehensive)
- **DOM Parsing**
- **LLM Fallback** (lowest confidence)

### 2. Full Matrix State Explorer
The collector performs **recursive state exploration** to discover all possible pricing states by:
- Hierarchically interacting with UI filters (Rate Type → Loan Type → Repayment Type)
- Dynamically re-scanning for conditional filters after each interaction
- Materializing **explicit unavailable states** (not just omitting missing data)
- Generating stable product identities across the state matrix

### 3. Advanced UI Interaction
- **Text Input Simulation**: Fills numeric fields (loan amount, property value) to trigger dynamic content
- **"Show More" Button Detection**: Expands hidden content automatically
- **Shadow DOM Support**: Pierces Web Component boundaries with aggressive selectors
- **Calculator Detection**: Identifies and skips calculator widgets to optimize performance
- **Reset Filter Optimization**: Uses "Clear All" buttons instead of page reloads

### 4. Externalized Configuration
All semantic keywords, selectors, and patterns are externalized to `filter_keywords.yaml` and managed through `FilterKeywordManager`, ensuring the system remains generic and maintainable.

### 5. Data Validation & Quality
- **LVR Overlap Detection**: Validates and resolves conflicting rate tiers
- **Product ID/Name Alignment**: Ensures canonical, slugified identifiers
- **Partial Capture Flagging**: Explicitly marks incomplete data with confidence penalties
- **Fixed-Term Metadata Extraction**: Ensures fixed-rate products include term information
- **Closed-World Matrix Materialization**: Records all theoretical states, including explicit nulls

## Architecture Documentation

### Core Architecture
- **[Recursive State Explorer](architecture/RECURSIVE_STATE_EXPLORER.md)** - Hierarchical UI state enumeration system
- **[Closed-World Matrix](architecture/CLOSED_WORLD_MATRIX.md)** - Explicit null-state materialization
- **[Calculator Detection](architecture/CALCULATOR_DETECTION.md)** - Intelligent widget identification (rate calculators)
- **[Extensible Widget Detection](architecture/EXTENSIBLE_WIDGET_DETECTION.md)** - 🆕 Framework for detecting any widget type (calculators, eligibility checkers, comparison tools)
- **[Externalized Keywords](architecture/EXTERNALIZED_KEYWORDS_MANIFEST.md)** - Configuration-driven semantic matching
- **[Data Validation Fixes](architecture/DATA_VALIDATION_FIXES.md)** - 6 critical data quality improvements

### Performance
- **[ANZ Performance Analysis](performance/PERFORMANCE_ANALYSIS_ANZ.md)** - Deep-dive into optimization discoveries

### Design Principles
- **[Generic vs. Lender-Specific](GENERIC_VS_LENDER_SPECIFIC.md)** - 🎯 **Important:** Clarifies that ALL features are generic (no lender-specific code)

## Key Files

- **`src/agents/collector/playwright_collector.py`** - Core collector implementation
- **`src/agents/collector/filter_keywords.py`** - Keyword management system
- **`src/configs/filter_keywords.yaml`** - Externalized semantic keywords
- **`src/models/product.py`** - BIAN-aligned product models with v2.0.0 state-explicit schema

## Schema Version

The collector outputs data in **Schema v2.0.0 (State-Explicit Model)**, where:
- Product metadata is separated from pricing
- Pricing is explicitly bound to UI states
- All theoretical states are materialized (including unavailable ones)
- Confidence scoring reflects data completeness and quality

## Usage

```python
from src.agents.collector.playwright_collector import PlaywrightCollector

collector = PlaywrightCollector()
products = await collector.collect(url="https://example.com/home-loans")
```

For more details, see the main project [README](../../README.md).

