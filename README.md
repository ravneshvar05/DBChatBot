# 📊 Data Analytics Assistant

A powerful, conversation-aware analytics chatbot that allows you to query your database using natural language. This system is designed to dynamically connect to any local or cloud database and seamlessly convert your plain-English questions into secure SQL queries. 

Built with **Streamlit** (Frontend) and **FastAPI** (Backend) leveraging a robust **4-layer LLM Fallback Architecture** to guarantee high availability and accurate SQL generations.

---

## 🚀 Key Features

*   **Dynamic Database Connections:** Connect dynamically to any PostgreSQL or MySQL database directly from the UI using manual credentials or a database URL.
*   **CSV Data Uploads:** Upload raw CSV files, which the system automatically parses, infers schema, and loads into your connected database using bulk inserting optimizations.
*   **Natural Language to SQL:** Ask questions in plain English. The system intelligently converts intent to optimized SQL queries without hallucinating non-existent columns.
*   **Deep AI Insights (Gemini):** Optional toggle to generate an "Executive Brief." The system mathematically analyzes numerical query results (averages, distributions) and passes these metrics to Google Gemini to write a comprehensive strategy overview.
*   **Data Visualization:** Automatically renders dynamic Plotly charts on the frontend whenever appropriate data structures are queried.
*   **Dual-Layer Memory:**
    *   *Short-Term Memory:* Thread-safe, cross-session, in-memory caching for rapid multi-turn conversations.
    *   *Long-Term Memory (Persistent):* MySQL-backed persistent storage that preserves full chat history and *SQL context metadata* across server restarts.
*   **Bulletproof Fallback Strategy:** Built-in multi-provider fallback layers between Groq (LLaMA) and Google (Gemini) to bypass rate limits or provider downtimes.
*   **Security & Safety:** Read-only queries, rate limiting mechanisms, and audit logging to ensure database integrity.

---

## 🏗️ System Architecture & Pipeline

The pipeline is split between a **Streamlit** user interface and a high-performance **FastAPI** backend endpoint.

1. **Connection & Ingestion Phase:**
   - **Database Connection (`connection.py`):** Connection pools are established dynamically via SQLAlchemy. The system supports dynamic connection strings mapped from the frontend.
   - **CSV Loader (`loader.py`):** For local datasets, the system employs streaming CSV reads and bulk schema inferences and insertions to support massive files without crashing the memory.
2. **User Interaction & Schema Context Phase:**
   - Users prompt the system through the chat interface. The backend retrieves the current database schema context (tables, references) attached to the current active session.
   - The **Persistent Memory Manager** pulls any previous conversation metrics, preserving logic and applied filters across multi-turn chats.
3. **LLM Generation Phase (`llm/client.py`):**
   - The user intent and schema context are passed to the **LLM Client**. The client generates an optimized SQL query securely based on user intent.
4. **Execution & Analytics Phase (`api/routes` & `analytics/`):**
   - The SQL query is extracted, validated for destructive commands (e.g., preventing `DROP` or `DELETE`), and executed securely against the database.
   - **Insights Generator (`insights.py`):** Computes row metrics (sum, average, standard deviation) and optionally queries Gemini for a Deep Analysis Executive Brief.
   - The resultant rows, tokens used, and generated AI insights are displayed elegantly in the Streamlit frontend UI via intuitive metric views and **Plotly** charts.

---

## 🧠 Models Used & Roles

The system uses a highly resilient **4-Layer Cascading Architecture** using different LLMs assigned to distinct fallback priorities to guarantee 100% uptime and generation accuracy.

1. **Layer 1: Llama-3.3-70b-versatile (via Groq)**  
   - **Role:** The **Primary Reasoning Engine**. Excellent at complex SQL generation, joins, and analytics logic with ultra-fast generation speeds.
2. **Layer 2: Gemini-2.0-Flash (via Google)**  
   - **Role:** The **Smart Fallback**. Used if Groq's 70B hits a rate limit or goes down. Equivalent reasoning capability using a completely distinct quota pool.
3. **Layer 3: Llama-3.1-8b-instant (via Groq)**  
   - **Role:** The **Lightweight Speed Engine**. For rapid generations when larger models are exhausted. 
4. **Layer 4: Gemini-1.5-Flash (via Google)**  
   - **Role:** The **Volume Model**. Used as the final safety net if all other providers face issues.

*This system prevents the dreaded `429 Rate Limit` issues commonly faced with conversational SQL systems.*

---

## ⚙️ Quickstart & Setup Guide

Get the project running locally in a few simple steps.

### Prerequisites

*   Python 3.10+
*   Local database installed (MySQL or PostgreSQL) or an existing Cloud Database.
*   API Keys for **Groq** and **Google Gemini**.

### 1. Clone the repository

```bash
git clone https://github.com/ravneshvar05/DBChatBot.git
cd DBChatBot
```

### 2. Set up the Environment

Create a virtual environment and install the dependencies:

```bash
python -m venv venv

# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Configure the `.env` variables

Copy the example environment variables file and fill it with your credentials:

```bash
cp .env.example .env
```

Ensure the following variables are appropriately populated in your `.env`:
```env
# API Keys
GROQ_API_KEY="your_groq_key_here"
GOOGLE_API_KEY="your_google_key_here"

# Default Local Database (Optional - can also connect dynamically in UI)
DATABASE_URL="mysql+pymysql://root:password@localhost:3306/footwear_db"
# or postgresql://user:password@localhost:5432/dbname
```

### 4. Run the Backend (FastAPI)

In a new terminal, start the FastAPI backend server:

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```
> **Backend API Docs:** Once running, visit `http://127.0.0.1:8000/docs` to see the complete API endpoint documentation.

### 5. Run the Frontend (Streamlit)

In a separate terminal, launch the Streamlit frontend interface:

```bash
streamlit run streamlit_app.py
```
> The application will automatically open in your browser at `http://localhost:8501`.

### 6. Usage Instructions

1. **Connect:** Use the "Database" sidebar section to configure your Database URL or manual connection fields. You can also upload a raw CSV.
2. **Chat:** Ask any question in the main chat (e.g., *"How many total sales were made in Q3?"*).
3. **Analyze:** Receive standard data rows, metrics, and backend SQL queries to verify your data!