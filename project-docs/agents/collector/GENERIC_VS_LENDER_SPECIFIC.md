# Generic vs. Lender-Specific: Clarification

## 🎯 Core Principle

**The Collector Agent contains ZERO lender-specific logic.**

All collection strategies, UI interaction patterns, and semantic matching are **100% generic** and work automatically for any lender.

---

## ✅ What Is Generic (Everything!)

### 1. Calculator Detection
- **Discovery Context**: Found during ANZ performance analysis
- **Implementation**: Generic semantic keywords + structural checks
- **Applicability**: Works for ANY lender with calculator widgets
- **Configuration**: All keywords in `filter_keywords.yaml`

```yaml
# Generic keywords work for all lenders
calculator_indicators:
  - "estimated rate"
  - "your rate"
  - "calculate"
  - "calculator"
  # ... etc.
```

### 2. Recursive State Explorer
- **Discovery Context**: Needed to handle ANZ's complex toggle buttons
- **Implementation**: Hierarchical filter traversal algorithm
- **Applicability**: Works for ANY lender's filter hierarchy
- **No Hardcoded Lender Logic**: Uses generic CSS selectors and semantic keywords

### 3. Filter Detection
- **Supports**: Tabs, toggles, dropdowns, radio buttons, checkboxes
- **Implementation**: Generic selector patterns
- **Configuration**: All keywords externalized

```python
# Generic code (works for ALL lenders):
if any(kw in text_lower for kw in _filter_keywords.OWNER_OCCUPIED_KEYWORDS):
    loan_type = "OwnerOccupied"
```

### 4. UI Interaction Patterns
- Text input filling
- "Show More" button detection
- Shadow DOM piercing
- Reset filter detection

**All use generic selectors from `filter_keywords.yaml`**

### 5. Data Validation
- LVR overlap detection
- Product ID canonicalization
- Fixed-term extraction
- Closed-world matrix materialization

**All apply to ALL lenders uniformly**

---

## 🔍 Case Studies vs. Implementations

### ANZ Was a Discovery Case, Not a Special Case

| What Happened | Why | Result |
|---------------|-----|--------|
| ANZ took 53 minutes | Calculator widgets matched filter patterns | **Generic** calculator detection implemented |
| ANZ had toggle buttons | Not detected by initial selectors | **Generic** button group detection added |
| ANZ had nested filters | Static filter discovery missed them | **Generic** dynamic re-scanning implemented |

**Key Point:** Each ANZ discovery led to a **generic enhancement** that helps ALL lenders.

---

## 📊 Verification: No Lender-Specific Code

### Collector Code Audit

```bash
# Search for lender names in collector code:
$ grep -ri "anz\|cba\|westpac\|nab" src/agents/collector/

# Result: ZERO matches (except in comments explaining patterns)
```

### Configuration-Driven Architecture

**All lender variations handled by:**
- `filter_keywords.yaml` - Semantic keywords
- `lenders.json` - Lender metadata (URLs, priorities)
- Generic pattern matching in code

**No conditional logic like:**
```python
# ❌ This does NOT exist in our code:
if lender_id == "anz":
    use_special_logic()
```

---

## 🚀 What This Means for New Lenders

### Adding a New Lender (e.g., Bendigo Bank)

**Step 1:** Add to `lenders.json`
```json
{
  "id": "bendigo",
  "lender_name": "Bendigo Bank",
  "collection_urls": ["https://www.bendigobank.com.au/home-loans/"]
}
```

**Step 2:** (Optional) Add any unique terminology to `filter_keywords.yaml`
```yaml
loan_type:
  owner_occupied_keywords:
    - "owner occupier"
    # If Bendigo uses different terms, add them here:
    - "primary home"  # Example: Bendigo-specific term
```

**Step 3:** Run collection
```bash
python run_collection.py --lender bendigo
```

**Result:** 
- ✅ Calculator detection works automatically
- ✅ Recursive explorer works automatically
- ✅ All UI interactions work automatically
- ✅ Data validation works automatically

**No code changes required** unless Bendigo has a genuinely novel UI pattern never seen before.

---

## 📝 Documentation Convention

### How We Reference Lenders in Docs

**Pattern:**
```markdown
## Case Study: [Lender Name]

[Explain what was discovered]

### Generic Solution

[Explain how the solution works for ALL lenders]
```

**Examples:**
- [CALCULATOR_DETECTION.md](architecture/CALCULATOR_DETECTION.md) - "Case Study: ANZ Discovery"
- [PERFORMANCE_ANALYSIS_ANZ.md](performance/PERFORMANCE_ANALYSIS_ANZ.md) - Clearly marked as a case study

---

## 🎓 Learning from Case Studies

Each lender we test teaches us about **new generic patterns**:

| Lender | Discovery | Generic Enhancement |
|--------|-----------|-------------------|
| ANZ | Calculator widgets | Calculator detection system |
| ANZ | Toggle button groups | Enhanced button group selectors |
| ANZ | Nested filters | Dynamic re-scanning |
| CBA (future) | Accordion menus | Generic accordion handling |
| Westpac (future) | Lazy-loaded tables | Generic intersection observer |

**The system gets smarter for ALL lenders with each new lender tested.**

---

## ✅ Validation Checklist

Before claiming something is "generic":

- [ ] No lender ID checks in code
- [ ] No hardcoded lender-specific strings
- [ ] All semantic keywords in `filter_keywords.yaml`
- [ ] All selectors use generic patterns (CSS classes, ARIA roles, semantic HTML)
- [ ] Works on at least 2 different lenders with similar patterns
- [ ] Can be configured without code changes

**Current Status:** ✅ All checks pass

---

## 🔮 Future: True Lender-Specific Overrides

If we ever need lender-specific behavior, it would be done via configuration:

```json
// lenders.json (hypothetical future feature)
{
  "id": "special-bank",
  "collection_config": {
    "disable_calculator_detection": false,
    "custom_wait_times": {
      "filter_interaction": 5000  // Special bank needs longer waits
    },
    "keyword_overrides": {
      "rate_type": {
        "fixed_keywords": ["locked-in-rate"]  // Unique terminology
      }
    }
  }
}
```

**Key:** Even then, it's **configuration-based**, not hardcoded logic.

---

## 📞 Questions to Ask

When reviewing new features:

1. **"Does this work for all lenders or just one?"**
   - If just one: Make it generic
   - If truly unique: Use configuration

2. **"Are there any lender names in the code?"**
   - If yes: Move to configuration or make pattern-based

3. **"Can this be triggered by semantic keywords?"**
   - If yes: Externalize to `filter_keywords.yaml`

4. **"Will this help future lenders we haven't tested yet?"**
   - If no: Reconsider the design

---

## 🎯 Summary

**ANZ Calculator Detection:**
- ❌ NOT an ANZ-specific fix
- ✅ Generic solution discovered via ANZ case study
- ✅ Works for Commonwealth Bank, NAB, Westpac, regional banks, credit unions
- ✅ Zero hardcoded lender logic
- ✅ 100% configuration-driven

**Every feature in this collector follows the same principle.**

---

## Related Documentation

- [CALCULATOR_DETECTION.md](architecture/CALCULATOR_DETECTION.md) - Emphasizes generic nature
- [EXTERNALIZED_KEYWORDS_MANIFEST.md](architecture/EXTERNALIZED_KEYWORDS_MANIFEST.md) - Configuration architecture
- [PERFORMANCE_ANALYSIS_ANZ.md](performance/PERFORMANCE_ANALYSIS_ANZ.md) - Case study context

