# Technical Stack

## 🛠️ Technology Choices and Rationale

### Core Technologies

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| **Language** | Python | 3.11+ | Industry standard for AI/ML, excellent async support |
| **Agent Framework** | LangGraph | 0.6.8 | State machine for complex workflows, LangChain integration |
| **LLM Framework** | LangChain | Latest | Agent orchestration, tool use (not for extraction - cost) |
| **Web Scraping** | Playwright | 1.40+ | Modern, async, multi-browser, JS execution |
| **HTTP Client** | httpx | 0.25+ | Async HTTP for API calls, Google search |
| **Web Framework** | FastAPI | 0.104+ | Fast, async, auto-docs, type-safe |
| **Data Validation** | Pydantic | 2.5+ | Runtime validation, JSON schema, type safety |
| **Storage** | JSON files | - | Simple, portable, human-readable (DB later if needed) |
| **Testing** | pytest | 7.4+ | Standard Python testing, async support |
| **Async I/O** | aiofiles | 24.1+ | Async file operations |

### Supporting Libraries

| Library | Purpose |
|---------|---------|
| BeautifulSoup4 | HTML parsing (backup to Playwright) |
| deepdiff | Change detection (future) |
| APScheduler | Scheduled collection (future) |
| uvicorn | ASGI server for FastAPI |

---

## 🎯 Why These Choices?

### LangGraph over alternatives

**Considered**:
- ✅ LangGraph (chosen)
- ❌ AutoGen
- ❌ CrewAI
- ❌ Custom state machine

**Reasons**:
1. Native LangChain integration
2. Built-in state management
3. Checkpointing for long-running workflows
4. Easy to visualize and debug
5. Production-ready

### Playwright over Selenium

**Reasons**:
1. Modern async API
2. Faster and more reliable
3. Multi-browser support
4. Better network interception
5. Active development

### JSON Storage over PostgreSQL

**Reasons**:
1. Simpler setup (no DB required)
2. Portable (easy to backup/restore)
3. Human-readable (easy debugging)
4. Git-friendly (can track schema changes)
5. Sufficient for 15 lenders
6. **Future**: Can migrate to PostgreSQL when scale demands

### FastAPI over Flask

**Reasons**:
1. Async by default
2. Automatic OpenAPI docs
3. Type hints everywhere
4. Better performance
5. Modern and actively developed

### Pydantic V2

**Reasons**:
1. Runtime validation
2. JSON schema generation
3. Excellent error messages
4. Type safety
5. BIAN schema mapping

---

## 🔧 Development Tools

### Code Quality
- **Linting**: Pylint, Flake8 (future)
- **Formatting**: Black (future)
- **Type Checking**: mypy (future)

### IDE Support
- VSCode with Python extension
- Cursor AI integration
- IntelliSense for type hints

### Version Control
- Git for code
- `.gitignore` for data, env, cache

---

## 📦 Dependency Management

### requirements.txt Structure
```python
# Core web scraping
playwright>=1.40.0
httpx>=0.25.0
beautifulsoup4>=4.12.0

# API & Web framework
fastapi>=0.104.0
uvicorn[standard]>=0.24.0

# Data validation & models
pydantic>=2.5.0

# AI/LLM frameworks
langchain>=0.1.0
langgraph>=0.0.40
langchain-openai>=0.0.5

# Data processing
deepdiff>=6.7.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-mock>=3.11.0
```

### Installation
```bash
pip install -r requirements.txt
playwright install  # Install browser binaries
```

---

## 🌐 External Services

### Currently Used
- **Google Search**: URL discovery (public scraping)
- **Lender Websites**: Data source

### Not Used (Considered)
- ❌ Google Custom Search API (paid)
- ❌ SerpAPI (paid, more reliable)
- ❌ Firecrawl (replaced by Playwright)
- ❌ CDR Product Reference API (future consideration)

---

## 🔒 Security Considerations

### Data Privacy
- No PII collected
- Only public product information
- Respect robots.txt (future)

### API Security
- Rate limiting (future)
- Authentication (future)
- CORS configured

### Web Scraping Ethics
- Respectful user-agent
- Rate limiting between requests
- Respect Terms of Service
- No aggressive scraping

---

## 📈 Scalability Considerations

### Current Capacity
- 15 lenders
- ~200 products total
- Daily collection
- JSON file storage

### Future Scale (if needed)
- PostgreSQL for 100+ lenders
- Redis for caching
- Distributed scraping with Celery
- S3 for long-term storage
- Kubernetes for deployment

---

## 🚀 Deployment (Future)

### Local Development
```bash
python run_collection.py
uvicorn src.api.main:app --reload
```

### Production (Future)
- Docker containers
- Kubernetes orchestration
- Cloud storage (S3)
- Monitoring (Prometheus, Grafana)
- Alerting (PagerDuty, Slack)

---

## 🔄 Update Strategy

### Dependencies
- Review monthly
- Test before upgrading major versions
- Pin versions in production

### Technology Migrations
- **From**: JSON files
- **To**: PostgreSQL (when >50 lenders)

- **From**: Public Google search
- **To**: Google Custom Search API (if needed)

---

## 💡 Technology Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-09-30 | LangGraph for orchestration | State management, LangChain integration |
| 2025-09-30 | Playwright for scraping | Modern, reliable, async |
| 2025-09-30 | JSON storage (not DB) | Simple, sufficient for current scale |
| 2025-09-30 | BIAN schema | Industry standard, comprehensive |
| 2025-09-30 | Multi-strategy extraction | Generic solution, no per-bank code |
| 2025-09-30 | Google search discovery | Dynamic URL finding, self-healing |
| 2025-09-30 | No LLM for extraction | Cost-prohibitive for regular scraping |
