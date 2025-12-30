# Lender Products Collector - Documentation Index

## 📚 Overview

This directory contains comprehensive documentation for the Lender Products Collector system, organized by module and concept.

---

## 🚀 Getting Started

| Document | Purpose |
|----------|---------|
| [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) | Quick start guide and system overview |
| [REQUIREMENTS.md](REQUIREMENTS.md) | Functional requirements and use cases |
| [ENV_SETUP.md](ENV_SETUP.md) | Environment variables and configuration |
| [TESTING.md](TESTING.md) | Testing guidelines and practices |

---

## 🏗️ Architecture & Design

| Document | Purpose |
|----------|---------|
| [DESIGN.md](DESIGN.md) | High-level design decisions and rationale |
| [design/DataCollectionDesign.md](design/DataCollectionDesign.md) | Detailed data collection workflow design |
| [CODING_STANDARDS.md](CODING_STANDARDS.md) | Development best practices and conventions |

---

## 🤖 Agent-Specific Documentation

### Collector Agent

**Overview:** [agents/collector/README.md](agents/collector/README.md)

The Collector Agent is the core web scraping engine. Its documentation is organized into:

#### Design Principles
Fundamental design decisions:

| Document | Purpose |
|----------|---------|
| [GENERIC_VS_LENDER_SPECIFIC.md](agents/collector/GENERIC_VS_LENDER_SPECIFIC.md) | 🎯 **Important:** Explains why ALL features are generic (no lender-specific code) |

#### Architecture
Advanced technical designs and implementation patterns:

| Document | Purpose |
|----------|---------|
| [RECURSIVE_STATE_EXPLORER.md](agents/collector/architecture/RECURSIVE_STATE_EXPLORER.md) | Hierarchical UI state enumeration system ("Full Matrix Explorer") |
| [CLOSED_WORLD_MATRIX.md](agents/collector/architecture/CLOSED_WORLD_MATRIX.md) | Explicit null-state materialization for complete data mapping |
| [CALCULATOR_DETECTION.md](agents/collector/architecture/CALCULATOR_DETECTION.md) | Intelligent calculator widget detection for performance optimization |
| [EXTENSIBLE_WIDGET_DETECTION.md](agents/collector/architecture/EXTENSIBLE_WIDGET_DETECTION.md) | 🆕 Framework for detecting multiple widget types (calculators, eligibility checkers, comparison tools, simulators) |
| [EXTERNALIZED_KEYWORDS_MANIFEST.md](agents/collector/architecture/EXTERNALIZED_KEYWORDS_MANIFEST.md) | Configuration-driven semantic keyword architecture |
| [DATA_VALIDATION_FIXES.md](agents/collector/architecture/DATA_VALIDATION_FIXES.md) | 6 critical data quality improvements for production-grade output |

#### Performance
Optimization analysis and findings:

| Document | Purpose |
|----------|---------|
| [PERFORMANCE_ANALYSIS_ANZ.md](agents/collector/performance/PERFORMANCE_ANALYSIS_ANZ.md) | Deep-dive case study: ANZ collection performance and optimization discoveries |

---

## 🔧 Setup Guides

| Document | Purpose |
|----------|---------|
| [GOOGLE_CUSTOM_SEARCH_SETUP.md](GOOGLE_CUSTOM_SEARCH_SETUP.md) | Google Custom Search API configuration for lender URL discovery |

---

## 📖 Reading Guide

### For New Developers
1. Start with [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) for system overview
2. Read [REQUIREMENTS.md](REQUIREMENTS.md) to understand what we're building
3. Review [agents/collector/README.md](agents/collector/README.md) for the core collection engine
4. Deep-dive into [RECURSIVE_STATE_EXPLORER.md](agents/collector/architecture/RECURSIVE_STATE_EXPLORER.md) for the main algorithm

### For Data Quality Review
1. [DATA_VALIDATION_FIXES.md](agents/collector/architecture/DATA_VALIDATION_FIXES.md) - Critical quality improvements
2. [CLOSED_WORLD_MATRIX.md](agents/collector/architecture/CLOSED_WORLD_MATRIX.md) - Completeness guarantees
3. [PERFORMANCE_ANALYSIS_ANZ.md](agents/collector/performance/PERFORMANCE_ANALYSIS_ANZ.md) - Real-world findings

### For System Extension
1. [EXTERNALIZED_KEYWORDS_MANIFEST.md](agents/collector/architecture/EXTERNALIZED_KEYWORDS_MANIFEST.md) - How to add new lenders/keywords
2. [DESIGN.md](DESIGN.md) - System design principles
3. [CODING_STANDARDS.md](CODING_STANDARDS.md) - Development guidelines

### For Performance Optimization
1. [CALCULATOR_DETECTION.md](agents/collector/architecture/CALCULATOR_DETECTION.md) - Latest optimization
2. [PERFORMANCE_ANALYSIS_ANZ.md](agents/collector/performance/PERFORMANCE_ANALYSIS_ANZ.md) - Case study
3. [RECURSIVE_STATE_EXPLORER.md](agents/collector/architecture/RECURSIVE_STATE_EXPLORER.md) - Core algorithm efficiency

---

## 🗂️ Documentation Structure

```
project-docs/
├── README.md (this file)                     # Documentation index
├── PROJECT_SUMMARY.md                         # Quick start
├── REQUIREMENTS.md                            # Requirements
├── DESIGN.md                                  # High-level design
├── CODING_STANDARDS.md                        # Dev standards
├── ENV_SETUP.md                              # Configuration
├── GOOGLE_CUSTOM_SEARCH_SETUP.md             # API setup
├── TESTING.md                                # Testing
│
├── design/                                    # Detailed designs
│   └── DataCollectionDesign.md               # Collection workflow
│
└── agents/                                    # Agent-specific docs
    └── collector/                             # Collector Agent
        ├── README.md                          # Agent overview
        ├── architecture/                      # Technical architecture
        │   ├── RECURSIVE_STATE_EXPLORER.md
        │   ├── CLOSED_WORLD_MATRIX.md
        │   ├── CALCULATOR_DETECTION.md
        │   ├── EXTERNALIZED_KEYWORDS_MANIFEST.md
        │   └── DATA_VALIDATION_FIXES.md
        └── performance/                       # Performance analysis
            └── PERFORMANCE_ANALYSIS_ANZ.md
```

---

## 📝 Document Maintenance

### When to Update
- **Architecture docs**: When adding new collection strategies or algorithms
- **Performance docs**: After identifying bottlenecks or implementing optimizations
- **Agent docs**: When modifying agent behavior or capabilities
- **Design docs**: When making significant architectural decisions

### Naming Convention
- Use `SCREAMING_SNAKE_CASE.md` for conceptual/architectural documents
- Use `PascalCase.md` for detailed design documents
- Use descriptive names that clearly indicate content

---

## 🔗 Related Documentation

- **Main README**: [../README.md](../README.md) - Project root documentation
- **Code Documentation**: Comprehensive docstrings in Python files
- **API Documentation**: Generated from code docstrings

---

## 📞 Questions?

For questions about:
- **System architecture**: See DESIGN.md and agents/collector/architecture/
- **Specific features**: Check relevant agent documentation
- **Setup issues**: Refer to ENV_SETUP.md and GOOGLE_CUSTOM_SEARCH_SETUP.md
- **Code quality**: Review CODING_STANDARDS.md

**Note:** Code files contain extensive inline documentation. Use this project-docs folder for high-level concepts and architectural decisions.
