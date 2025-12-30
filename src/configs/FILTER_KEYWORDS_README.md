# Filter Keywords Configuration - Design Document

## Version: 1.0.0
**Last Updated:** 2025-12-22

## Overview

This configuration file contains generic keyword patterns for detecting filters on lender websites. It uses a **hybrid approach**: keywords in YAML for easy updates, matching logic in Python for type safety and performance.

## Design Principles

### ✅ What We Include
- **Generic patterns only** - No bank-specific keywords
- **Common filter types** - Only patterns seen across multiple lenders
- **Versioned** - Safe evolution over time
- **Logging** - Unmatched filters logged for review

### ❌ What We Intentionally Exclude

#### 1. Borrower Profile Filters
- PAYG vs self-employed
- Professional/industry
- SMSF
- Guarantor

**Reason:** Rare, often eligibility-gated (not pricing-gated). Only add if targeting niche lenders.

#### 2. Promotional/Temporal Filters
- "Special offer"
- "Limited time"
- "Cashback"
- "Intro period"

**Reason:** These affect offers, not base pricing tables. Better handled downstream as offer metadata.

#### 3. Currency/Country Filters
- Non-AU currencies
- Cross-border lenders
- Expat products

**Reason:** Out of scope for AU-focused system.

#### 4. Anti-Patterns (Never Add)
- ❌ Hardcoded bank names
- ❌ UI-specific selectors
- ❌ Assumptions about filter order
- ❌ Inferred relationships between filters

## Evolution Strategy

### When to Add New Categories

**Only add when:**
1. You see the same pattern across **3+ different lenders**
2. It affects **pricing** (not just eligibility)
3. It's a **common pattern** (not edge case)

### Process

1. **Log unmatched filters** - System automatically logs candidates
2. **Review logs** - Identify patterns across multiple lenders
3. **Add to YAML** - Only after seeing repeated misses
4. **Version bump** - Update version when adding new categories

### Example Evolution Path

```
v1.0.0 - Initial: loan_type, repayment_type, lvr_tier, loan_term
v1.1.0 - Added: rate_type, loan_purpose (after seeing 5+ lenders use these)
v1.2.0 - Added: product_segment, region_residency (after seeing 3+ lenders)
```

## Current Filter Types

1. **loan_type** - Owner Occupied vs Investment
2. **repayment_type** - Principal & Interest vs Interest Only
3. **lvr_tier** - Loan-to-Value Ratio tiers
4. **loan_term** - Loan duration/term
5. **rate_type** - Fixed vs Variable rates
6. **loan_purpose** - First Home Buyer, Construction, etc.
7. **product_segment** - Package vs Basic, Offset, etc.
8. **region_residency** - State, Resident status
9. **rate_tier** - Loan amount bands, risk bands

## File Structure

```
filter_keywords.yaml          # Keywords (editable)
filter_keywords.py            # Matching logic (type-safe)
playwright_collector.py       # Uses keywords for detection
```

## Maintenance

- **Update keywords:** Edit YAML file
- **Update logic:** Edit Python file
- **Review logs:** Check for "Unmatched filter" messages
- **Version bump:** When adding new categories

## Logging

The system logs:
- ✅ **Matched filters** - What was successfully detected
- 📋 **Unmatched filters** - Candidates for future review
- 🔍 **Potential matches** - What aggressive search found

Review unmatched filters periodically to identify patterns that need new categories.

