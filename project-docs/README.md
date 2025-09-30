# Lender Products Collector - Documentation

> Professional documentation for the AI-powered loan product collection system

## 📚 Documentation Structure

### 1️⃣ Requirements & Scope
**[REQUIREMENTS.md](REQUIREMENTS.md)** - What we're building
- Functional requirements (FR-1 to FR-8)
- Use cases (UC-1 to UC-4)
- Success metrics
- Out of scope items

### 2️⃣ Architecture & Design  
**[ARCHITECTURE.md](ARCHITECTURE.md)** - How it's structured
- Complete end-to-end flow
- Agent architecture (LangGraph)
- Data flow visualization
- Component diagram

**[DESIGN.md](DESIGN.md)** - Module-by-module details
- Workflow orchestration design
- URL discovery design
- Data collection design
- Storage design
- API design

**[EXTRACTION_STRATEGIES.md](EXTRACTION_STRATEGIES.md)** - Data extraction approach
- 5 extraction strategies explained
- When each strategy is used
- Strategy selection logic
- Per-bank strategy mapping

### 3️⃣ Development Standards
**[CODING_STANDARDS.md](CODING_STANDARDS.md)** - Python best practices
- Code organization rules
- Mock data guidelines
- API design patterns
- Error handling standards

**[TESTING.md](TESTING.md)** - Testing strategy
- Test pyramid (unit/integration/e2e)
- Testing guidelines
- Coverage goals
- Debug tools

### 4️⃣ Technical Reference
**[TECHNICAL_STACK.md](TECHNICAL_STACK.md)** - Technology choices
- Full technology stack
- Rationale for each choice
- Deployment considerations
- Technology decision log

---

## 🎯 Quick Start Guide

**For New Developers**:
1. Read [REQUIREMENTS.md](REQUIREMENTS.md) → Understand the problem
2. Read [ARCHITECTURE.md](ARCHITECTURE.md) → See the solution
3. Read [CODING_STANDARDS.md](CODING_STANDARDS.md) → Learn standards
4. Read [DESIGN.md](DESIGN.md) → Deep dive into modules

**For Contributors**:
1. [TESTING.md](TESTING.md) → Write tests
2. [EXTRACTION_STRATEGIES.md](EXTRACTION_STRATEGIES.md) → Add extraction logic
3. [CODING_STANDARDS.md](CODING_STANDARDS.md) → Follow conventions

---

## 📋 Document Summary

| Document | Purpose | Audience | Status |
|----------|---------|----------|--------|
| **REQUIREMENTS.md** | Functional requirements & use cases | Product, Dev | ✅ Complete |
| **ARCHITECTURE.md** | System architecture & flow | Dev, Architects | ✅ Complete |
| **DESIGN.md** | Module design details | Developers | ✅ Complete |
| **EXTRACTION_STRATEGIES.md** | Data extraction methods | Dev, Data Engineers | ✅ Complete |
| **CODING_STANDARDS.md** | Development best practices | All Developers | ✅ Complete |
| **TESTING.md** | Testing strategy & guidelines | QA, Developers | ✅ Complete |
| **TECHNICAL_STACK.md** | Technology choices & rationale | Architects, Ops | ✅ Complete |

---

## 🔍 Finding Information

**"How does URL discovery work?"**  
→ [ARCHITECTURE.md](ARCHITECTURE.md) (overview) + [DESIGN.md](DESIGN.md) (details)

**"What extraction strategies exist?"**  
→ [EXTRACTION_STRATEGIES.md](EXTRACTION_STRATEGIES.md)

**"How do I add a new lender?"**  
→ [REQUIREMENTS.md](REQUIREMENTS.md) - UC-4

**"What are the coding standards?"**  
→ [CODING_STANDARDS.md](CODING_STANDARDS.md)

**"How do I test my code?"**  
→ [TESTING.md](TESTING.md)

**"Why LangGraph?"**  
→ [TECHNICAL_STACK.md](TECHNICAL_STACK.md)

---

## 📝 Maintenance

Documentation should be updated when:
- ✅ New features added → Update REQUIREMENTS.md
- ✅ Architecture changes → Update ARCHITECTURE.md
- ✅ New modules created → Update DESIGN.md
- ✅ Extraction strategies added → Update EXTRACTION_STRATEGIES.md
- ✅ Standards change → Update CODING_STANDARDS.md
- ✅ Technology changes → Update TECHNICAL_STACK.md