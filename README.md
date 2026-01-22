# Data Analytics Assistant

A production-grade conversational data analytics system powered by **LLaMA-3.3-70B-Versatile**.

## Overview

This system enables natural language querying of PostgreSQL databases:
- **Text-to-SQL**: Users ask questions in plain English
- **Safe Execution**: Only validated, read-only queries are executed
- **Analytics Insights**: Raw data is transformed into human-readable summaries
- **Multi-turn Conversations**: Short-term memory enables follow-up questions
- **Personalization**: Long-term memory stores user preferences

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python + FastAPI |
| Database | PostgreSQL (Aiven-managed) |
| ORM | SQLAlchemy |
| LLM | LLaMA-3.3-70B-Versatile (via Groq) |
| Configuration | Environment variables (python-dotenv) |

## Project Structure

```
├── src/
│   ├── api/           # FastAPI routes
│   ├── core/          # Config & logging
│   ├── services/      # Business logic
│   ├── llm/           # LLM integration
│   ├── database/      # PostgreSQL access
│   ├── memory/        # STM & LTM
│   └── models/        # Pydantic schemas
├── tests/             # Test files
├── data/              # CSV files for loading
└── logs/              # Application logs
```

## Setup

### Prerequisites

- Python 3.10+
- PostgreSQL (Aiven account)
- Groq API key

### Installation

```bash
# Clone repository
git clone <repository-url>
cd ChatBot

# Create virtual environment
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

### Running

```bash
# Development server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

## Development Phases

- [ ] **Phase 0**: Project setup ✅
- [ ] **Phase 1**: Base conversational chatbot
- [ ] **Phase 2**: Database layer
- [ ] **Phase 3**: Text-to-SQL (stateless)
- [ ] **Phase 4**: Short-term memory (STM)
- [ ] **Phase 5**: Analytics-style answers
- [ ] **Phase 6**: Long-term memory (LTM)
- [ ] **Phase 7**: Safety & reliability

## License

Proprietary - All rights reserved.
