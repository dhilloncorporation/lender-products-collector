# Quick Start Guide - Enterprise Financial Data Collector v2.0

## 🚀 Getting Started

### Prerequisites
```bash
# Python 3.11+
python --version

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install
```

### Environment Setup (Optional)
```bash
# For AI Quality Gate (optional)
export OPENAI_API_KEY="your-key-here"  # Git Bash
$env:OPENAI_API_KEY="your-key-here"    # PowerShell
```

---

## 📊 Running the Collector

### Basic Collection
```bash
python run_collection.py
```

This will:
1. Load lenders from `src/configs/lenders.json`
2. Discover URLs for each lender
3. **Recursively explore** all pricing states (OO×PI, OO×IO, INV×PI, INV×IO)
4. **Materialize complete matrix** (8 states per product)
5. **Run AI Quality Gate** (confidence scoring)
6. **Save or quarantine** data based on quality

---

## 📁 Output Locations

### Successful Collections
```
data/current/by_lender/
├── ANZ.json          # Latest ANZ products
├── CBA.json          # Latest CBA products
└── WBC.json          # Latest WBC products
```

### Quarantined Data (Low Quality)
```
data/quarantine/
└── ANZ/
    ├── 2025-12-25-10-30-00.json              # Quarantined data
    └── 2025-12-25-10-30-00_quality_report.json  # Quality assessment
```

### Historical Snapshots
```
data/snapshots/parsed/
└── ANZ/
    ├── 2025-12-25-10-30-00.json
    └── 2025-12-24-09-15-00.json
```

### Collection Index
```
data/index.json  # Catalog of all collections
```

---

## ✅ Validating Results

### Run Automated Validation
```bash
python validate_definition_of_done.py
```

### Expected Output
```
==============================================================
DEFINITION OF DONE VALIDATION
==============================================================

Check 1: ANZ.json Pricing States
============================================================
✅ PASS: 'Simplicity PLUS' (Variable): 4/4 states
   States: OO_PI_VAR, OO_IO_VAR, INV_PI_VAR, INV_IO_VAR
✅ PASS: '2 year fixed rate' (Fixed): 4/4 states
   States: OO_PI_FIX, OO_IO_FIX, INV_PI_FIX, INV_IO_FIX

Check 2: Product ID Format (Slugification)
============================================================
✅ PASS: ANZ - 'Simplicity PLUS'
   Product ID: 'australia-and-new-zealand-banking-group-simplicity-plus'

Check 3: LVR Overlap Detection
============================================================
✅ PASS: No LVR overlaps detected

Check 4: Fixed Rate Products Have fixed_term_years
============================================================
✅ PASS: ANZ - '2 year fixed rate'
   Rate Type: Fixed
   fixed_term_years: 2

Check 5: Quality Assessment Reports
============================================================
Found 2 lender(s): ANZ, CBA
ℹ️  Quality assessment is integrated into the workflow.
   Reports are generated during collection and logged to console.

==============================================================
SUMMARY
==============================================================

✅ PASS - Check 1: ANZ Pricing States (8 states per product)
✅ PASS - Check 2: Product ID Format (slugified)
✅ PASS - Check 3: No LVR Overlaps
✅ PASS - Check 4: Fixed Products Have fixed_term_years
✅ PASS - Check 5: Quality Assessment Reports

Result: 5/5 checks passed

🎉 ALL CHECKS PASSED! Definition of Done satisfied.
```

---

## 🔍 Understanding the Output

### Schema v2.0.0 Structure
```json
{
  "schema_version": "2.0.0",
  "product": {
    "product_id": "australia-and-new-zealand-banking-group-simplicity-plus",
    "product_name": "Simplicity PLUS",
    "lender": {
      "lender_id": "australia-and-new-zealand-banking-group",
      "lender_name": "Australia and New Zealand Banking Group",
      "jurisdiction": "AU"
    },
    "product_type": "HomeLoan",
    "rate_type": "Variable"
  },
  "pricing_states": [
    {
      "state_id": "OO_PI_VAR",
      "state_parameters": {
        "loan_type": "OwnerOccupied",
        "repayment_type": "PrincipalAndInterest"
      },
      "pricing": {
        "rate_tiers": [
          {
            "lvr_min": 0.0,
            "lvr_max": 0.8,
            "interest_rate": 7.29,
            "comparison_rate": 7.29
          }
        ]
      },
      "provenance": {
        "extraction_method": "ui_enumeration_tab",
        "extraction_strategy": "ui_enumeration",
        "confidence_score": 70,
        "capture_status": "complete"
      }
    }
    // ... 7 more states
  ]
}
```

### Key Features

#### 1. Complete Matrix (8 States)
Every product has **all 8 pricing states** materialized:
- `OO_PI_VAR` - Owner Occupied, Principal & Interest, Variable
- `OO_IO_VAR` - Owner Occupied, Interest Only, Variable
- `INV_PI_VAR` - Investment, Principal & Interest, Variable
- `INV_IO_VAR` - Investment, Interest Only, Variable
- `OO_PI_FIX` - Owner Occupied, Principal & Interest, Fixed
- `OO_IO_FIX` - Owner Occupied, Interest Only, Fixed
- `INV_PI_FIX` - Investment, Principal & Interest, Fixed
- `INV_IO_FIX` - Investment, Interest Only, Fixed

#### 2. Explicit Unavailability
If a state is not available:
```json
{
  "state_id": "OO_IO_VAR",
  "pricing": null,
  "provenance": {
    "capture_status": "not_available",
    "reason": "State not found during UI exploration"
  }
}
```

#### 3. Slugified IDs
All IDs are **lowercase-hyphenated**:
- ✅ `australia-and-new-zealand-banking-group-simplicity-plus`
- ❌ `Australia and New Zealand Banking Group Simplicity PLUS`

#### 4. Mandatory Metadata
Fixed products **always** have `fixed_term_years`:
```json
{
  "product": {
    "rate_type": "Fixed",
    "fixed_term_years": 2  // ← REQUIRED
  }
}
```

---

## 🎯 Quality Gate Explained

### Confidence Scoring (0-100)

**Starting Score**: 100

**Penalties**:
- **-40 pts**: Overlapping LVR tiers (same LVR, different rates)
- **-20 pts**: Missing Investment loan surfaces
- **-20 pts**: Missing Interest Only surfaces
- **-20 pts**: Fixed product missing `fixed_term_years`
- **-10 pts**: Missing comparison rates
- **-10 pts**: Missing features

**Thresholds**:
- **≥70**: ✅ Passed (saved normally)
- **40-69**: ⚠️ Warning (saved with warning)
- **<40**: ❌ Quarantined (saved to quarantine folder)

### Example Quality Report
```json
{
  "lender": "ANZ",
  "scores": {
    "confidence": 70,
    "completeness": 80,
    "consistency": 90
  },
  "status": "passed",
  "quarantined": false,
  "issues": [
    {
      "severity": "warning",
      "category": "completeness",
      "message": "Missing Interest Only surfaces for 'Simplicity PLUS'",
      "penalty": 20
    }
  ]
}
```

---

## 🛠️ Configuration

### Enable/Disable Lenders
Edit `src/configs/lenders.json`:
```json
{
  "id": "anz",
  "lender_name": "Australia and New Zealand Banking Group",
  "abbreviation": "ANZ",
  "enabled": true,  // ← Set to false to disable
  "priority": 1,
  "collection_urls": [
    "https://www.anz.com.au/personal/home-loans/interest-rates/"
  ]
}
```

### Adjust Collection Settings
Edit `src/configs/collection_settings.yaml`:
```yaml
schema:
  version: "2.0.0"  # Schema version

rate_limits:
  per_url_delay_seconds: 5  # Delay between URLs

validation:
  min_products_per_lender: 1
  max_rate_percent: 20.0
```

---

## 🐛 Troubleshooting

### Issue: No products collected
**Solution**: Check logs for extraction strategy used
```bash
# Look for:
# "✅ Strategy selected: ui_enumeration"
# "🌳 Starting recursive state exploration..."
```

### Issue: Data quarantined
**Solution**: Review quality report
```bash
# Check:
data/quarantine/{LENDER}/{timestamp}_quality_report.json
```

### Issue: Missing pricing states
**Solution**: Check if UI has those states
- Some products genuinely don't offer Interest Only
- System will mark as `not_available` (correct behavior)

### Issue: LVR overlaps detected
**Solution**: This indicates product variants (e.g., special offers)
- System keeps highest rate (most conservative)
- Consider splitting into separate products

---

## 📚 Further Reading

- **`UPGRADE_SUMMARY.md`** - Complete implementation details
- **`project-docs/ARCHITECTURE.md`** - System architecture
- **`project-docs/DESIGN.md`** - Detailed design
- **`src/configs/FILTER_KEYWORDS_README.md`** - Filter keyword configuration

---

## 🎉 Success Indicators

After running collection, you should see:

1. ✅ **8 pricing states** per product in `ANZ.json`
2. ✅ **Slugified product IDs** (lowercase-hyphenated)
3. ✅ **No LVR overlaps** (data integrity)
4. ✅ **Fixed products have `fixed_term_years`**
5. ✅ **Quality scores logged** to console
6. ✅ **Validation script passes** all checks

**If all indicators are green, the system is working correctly!** 🎊

---

**Version**: 2.0.0  
**Last Updated**: December 25, 2025

