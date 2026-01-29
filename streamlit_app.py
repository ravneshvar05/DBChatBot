"""
Data Analytics Assistant - Streamlit Frontend

A beautiful chat interface for the Data Analytics Chatbot.
Connects to the FastAPI backend for processing.

Run with: streamlit run streamlit_app.py
"""
import streamlit as st
import requests
import uuid
from datetime import datetime

# ============================================================
# Configuration
# ============================================================

import os
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="Data Analytics Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# Custom CSS
# ============================================================

st.markdown("""
<style>
    /* "Soft Paper" Warm Theme */
    
    /* Global Fonts & Colors */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Playfair+Display:wght@600&display=swap');
    
    /* Soft Text (Dark Slate/Brown-Grey) - Readable but not harsh black */
    html, body, [class*="css"], .stMarkdown, .stText, p {
        font-family: 'Inter', sans-serif;
        color: #334155 !important; /* Slate 700 */
    }
    
    /* App Background - Warm Cream */
    .stApp {
        background-color: #fdfbf7;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Playfair Display', serif;
        font-weight: 700;
        color: #1e293b !important; /* Slate 800 */
        letter-spacing: -0.5px;
    }
    
    /* Main container */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1000px;
    }
    
    /* Metric Cards - Warm White */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e5e7eb; /* Soft Grey */
        padding: 1.2rem;
        border-radius: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02); /* Very subtle shadow */
    }
    div[data-testid="stMetricValue"] {
        color: #d97706 !important; /* Amber 600 - Warm Gold */
        font-family: 'Playfair Display', serif;
        font-weight: 700;
    }
    div[data-testid="stMetricLabel"] {
        color: #64748b !important; /* Slate 500 */
        font-weight: 600;
        font-size: 1rem;
    }
    
    /* Chat Messages */
    .stChatMessage {
        background-color: #ffffff;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border-radius: 12px;
        border: 1px solid #f3f4f6; /* Very light border */
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    .stChatMessage[data-testid="stChatMessageAvatarUser"] {
        background-color: #d97706; /* Amber */
        color: white;
    }
    .stChatMessage[data-testid="stChatMessageAvatarAssistant"] {
        background-color: #fdfbf7; /* Matches bg */
        border: 1px solid #e5e7eb;
        color: #334155;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #f9f8f4; /* Slightly darker cream */
        border-right: 1px solid #e5e7eb;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 1.5rem;
        background-color: transparent;
        border-bottom: 2px solid #e5e7eb;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: transparent;
        border: none;
        color: #94a3b8;
        font-weight: 600;
        font-size: 1rem;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #d97706 !important; /* Amber */
        border-bottom: 3px solid #d97706;
    }
    
    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        border: 1px solid #e5e7eb;
        background-color: #ffffff;
        color: #334155;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    .stButton > button:hover {
        border-color: #d97706;
        color: #d97706;
        background-color: #fffbeb; /* Amber 50 */
    }
    
    /* SQL Code Blocks */
    .stCode {
        border: 1px solid #e5e7eb;
        background-color: #f9f8f4;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# Session State Initialization
# ============================================================

def init_session_state():
    """Initialize session state variables."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "backend_connected" not in st.session_state:
        st.session_state.backend_connected = False


def check_backend():
    """Check if backend is available."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        st.session_state.backend_connected = response.status_code == 200
        return st.session_state.backend_connected
    except:
        st.session_state.backend_connected = False
        return False


def get_or_create_session():
    """Get existing session or create a new one."""
    if st.session_state.session_id is None:
        try:
            response = requests.post(f"{API_BASE_URL}/session/new", timeout=30)
            if response.status_code == 200:
                data = response.json()
                st.session_state.session_id = data["session_id"]
                return True
        except requests.exceptions.ConnectionError:
            return False
    return True


def load_session(session_id: str):
    """Load messages from an existing session."""
    try:
        response = requests.get(f"{API_BASE_URL}/session/{session_id}/history", timeout=10)
        if response.status_code == 200:
            data = response.json()
            st.session_state.session_id = session_id
            st.session_state.messages = []
            
            # Convert backend messages to frontend format
            for msg in data.get("messages", []):
                frontend_msg = {
                    "role": msg["role"],
                    "content": msg["content"]
                }
                
                # Unpack metadata fields that the UI expects at the top level
                meta = msg.get("metadata", {})
                if meta:
                    for key in ["sql", "sql_queries", "data", "formatted_data_list", "row_count", "insights", "token_usage"]:
                        if key in meta:
                            frontend_msg[key] = meta[key]
                            
                st.session_state.messages.append(frontend_msg)
            return True
        else:
             st.toast(f"Failed to load history: {response.status_code}")
             return False
    except Exception as e:
        st.error(f"Error loading session: {e}")
        return False


# ============================================================
# API Functions
# ============================================================

def send_message(message: str, include_analysis: bool = False) -> dict:
    """Send a message to the chat API."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json={
                "message": message,
                "session_id": st.session_state.session_id,
                "mode": "sql",
                "include_analysis": include_analysis
            },
            timeout=120
        )
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            return {"error": "Rate limit exceeded. Please wait a moment."}
        else:
            detail = response.json().get("detail", "Unknown error")
            if isinstance(detail, dict):
                return {"error": detail.get("message", str(detail))}
            return {"error": str(detail)}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. Try a simpler question."}
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to backend server."}


def get_tables() -> list:
    """Get list of database tables."""
    try:
        response = requests.get(f"{API_BASE_URL}/database/schema", timeout=10)
        if response.status_code == 200:
            return response.json().get("tables", [])
        return []
    except:
        return []


def delete_table(table_name: str) -> dict:
    """Delete a database table."""
    try:
        response = requests.delete(f"{API_BASE_URL}/database/tables/{table_name}", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.json().get("detail", "Delete failed")}
    except Exception as e:
        return {"error": str(e)}


def upload_csv(file) -> dict:
    """Upload a CSV file to the database."""
    try:
        files = {"file": (file.name, file.getvalue(), "text/csv")}
        response = requests.post(f"{API_BASE_URL}/database/upload", files=files, timeout=120)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 409:
            return {"error": response.json().get("detail", "Table already exists")}
        else:
            return {"error": response.json().get("detail", "Upload failed")}
    except Exception as e:
        return {"error": str(e)}


def clear_all_sessions() -> dict:
    """Clear all conversation history."""
    try:
        response = requests.delete(f"{API_BASE_URL}/session/all", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.json().get("detail", "Failed to clear")}
    except Exception as e:
        return {"error": str(e)}


def get_session_list() -> list:
    """Get list of recent sessions."""
    try:
        response = requests.get(f"{API_BASE_URL}/session/list?limit=10", timeout=5)
        if response.status_code == 200:
            return response.json().get("sessions", [])
        return []
    except:
        return []


def get_session_stats() -> dict:
    """Get session statistics."""
    try:
        response = requests.get(f"{API_BASE_URL}/session", timeout=5)
        if response.status_code == 200:
            return response.json()
        return {}
    except:
        return {}


# ============================================================
# UI Components
# ============================================================

def render_sidebar():
    """Render the sidebar with polished UX."""
    with st.sidebar:
        st.title("📊 Analytics Hub")
        st.markdown("*Intelligent SQL Assistant*")
        
        # 🟢 Connection Status
        if st.session_state.backend_connected:
            st.success("🟢 System Online")
        else:
            st.error("🔴 System Offline")
            if st.button("🔄 Reconnect", use_container_width=True):
                if check_backend():
                    st.rerun()
            st.warning("Server is unreachable. Please check backend console.")
            return

        st.divider()

        # 💬 Chat Operations
        st.subheader("💬 Active Session")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ New", help="Start a new conversation", use_container_width=True):
                st.session_state.session_id = None
                st.session_state.messages = []
                get_or_create_session()
                st.rerun()
        with col2:
            if st.button("🗑️ Clear", help="Clear messages in current chat", use_container_width=True):
                st.session_state.messages = []
                st.rerun()

        # 📜 History Section
        with st.expander("🕰️ Session History", expanded=False):
            sessions = get_session_list()
            # Filter valid sessions
            valid_sessions = [s for s in sessions if s.get("id") and (s.get("message_count", 0) > 0 or s.get("id") == st.session_state.session_id)]
            
            if valid_sessions:
                for idx, sess in enumerate(valid_sessions):
                    sess_id = sess.get("id", "")
                    msg_count = sess.get("message_count", 0)
                    preview = sess.get("preview", "New Conversation")
                    is_current = sess_id == st.session_state.session_id
                    
                    # Truncate preview
                    if len(preview) > 35:
                        preview = preview[:32] + "..."
                    
                    label = f"{'🟢' if is_current else '📄'} {preview}"
                    
                    if st.button(label, key=f"hist_{idx}", use_container_width=True, help=f"Messages: {msg_count}"):
                        if not is_current:
                            if load_session(sess_id):
                                st.rerun()
            else:
                st.caption("No history found.")
                
            if st.button("⚠️ Delete All History", use_container_width=True, type="primary"):
                 with st.spinner("Deleting..."):
                     res = clear_all_sessions()
                     if "error" not in res:
                         st.session_state.session_id = None
                         st.session_state.messages = []
                         st.toast("History Cleared!")
                         st.rerun()

        st.divider()
        
        # 📁 Data Center
        st.subheader("📁 Data Center")
        
        # Upload
        with st.expander("📤 Upload Data", expanded=False):
            uploaded_files = st.file_uploader(
                "Choose CSVs", 
                type=["csv"], 
                accept_multiple_files=True,
                label_visibility="collapsed"
            )
            
            if uploaded_files:
                if st.button(f"Process {len(uploaded_files)} Files", use_container_width=True):
                    progress_bar = st.progress(0)
                    for idx, file_obj in enumerate(uploaded_files):
                        with st.spinner(f"Uploading {file_obj.name}..."):
                            result = upload_csv(file_obj)
                            if "error" not in result:
                                st.toast(f"✅ Loaded {result.get('table_name')}")
                            else:
                                st.error(f"❌ {file_obj.name}: {result['error']}")
                        progress_bar.progress((idx + 1) / len(uploaded_files))
                    st.success("Batch processing complete!")
                    st.rerun()

        # Tables
        with st.expander("🗃️ Database Tables", expanded=False):
            tables = get_tables()
            if tables:
                for table in tables:
                     # Handle if table is string (old API) or dict (new API)
                     table_name = table.get('name', 'Unknown') if isinstance(table, dict) else str(table)
                     
                     # Filter system tables
                     if table_name in ["conversation_sessions", "conversation_messages"]:
                         continue
                         
                     row_count = f"({table.get('row_count', '?')} rows)" if isinstance(table, dict) else ""
                     
                     # Beautify display name
                     display_name = table_name.replace("_", " ").title()
                     # Truncate if very long
                     if len(display_name) > 22:
                         display_name = display_name[:20] + "..."
                         
                     row_count = f"({table.get('row_count', '?')} rows)" if isinstance(table, dict) else ""
                     
                     # Sidebar column ratio - give more space to text
                     col_t1, col_t2 = st.columns([0.8, 0.2])
                     with col_t1:
                         st.markdown(f"{display_name}")
                         if row_count:
                             st.caption(row_count)
                     with col_t2:
                         # Use a smaller/simpler remove button
                         if st.button("🗑️", key=f"del_{table_name}", help=f"Delete {table_name}"):
                             delete_table(table_name)
                             st.rerun()
                     st.divider()
            else:
                st.info("No tables found.")

        st.divider()
        st.caption(f"v1.0.0 | Session: ...{str(st.session_state.session_id)[-6:] if st.session_state.session_id else 'None'}")



def render_chat():
    """Render the main chat interface."""
    st.markdown("## 💬 Ask about your data")
    st.markdown("Type natural language questions and get SQL-powered answers")
    
    # Display chat messages
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
            # 2. Hero Metrics (Premium Display in History)
            if msg.get("insights") and msg["insights"].get("top_values"):
                # Try to extract key metrics from insights
                stats = msg["insights"].get("numeric_stats", {})
                cols = st.columns(3)
                
                # Metric 1: Row Count
                with cols[0]:
                    st.metric("Total Records", msg.get("row_count", 0))
                
                # Metric 2 & 3: Dynamic
                idx = 1
                for col_name, col_stats in stats.items():
                    if idx >= 3: break
                    if "sum" in col_stats:
                        with cols[idx]:
                            st.metric(f"Total {col_name.title()}", f"{col_stats['sum']:,.0f}")
                        idx += 1
                    elif "avg" in col_stats:
                        with cols[idx]:
                            st.metric(f"Avg {col_name.title()}", f"{col_stats['avg']:,.2f}")
                        idx += 1

            # 3. Tabs for Details in history
            # Only show tabs if there is SQL or Data to show
            if msg.get("sql") or msg.get("data") or msg.get("sql_queries") or msg.get("token_usage"):
                tab_names = ["📄 SQL", "📊 Data", "📈 Charts"]
                if msg.get("token_usage"):
                    tab_names.append("🔢 Usage")
                
                tabs = st.tabs(tab_names)
                
                # Tab 1: SQL
                with tabs[0]:
                    sql_queries = msg.get("sql_queries", [])
                    if sql_queries:
                        for i, q in enumerate(sql_queries):
                            st.markdown(f"**Query {i+1}:**")
                            st.code(q, language="sql")
                    elif msg.get("sql"):
                        st.code(msg["sql"], language="sql")
                    else:
                        st.info("No SQL generated.")

                # Tab 2: Data
                with tabs[1]:
                    formatted_list = msg.get("formatted_data_list", [])
                    data_list = msg.get("data")
                    
                    if formatted_list:
                        for i, table in enumerate(formatted_list):
                            st.markdown(f"**Result {i+1}:**")
                            st.markdown(table)
                    elif data_list and len(data_list) > 0:
                        st.dataframe(data_list, use_container_width=True)
                        
                        # Data Download (Unique Key required)
                        import pandas as pd
                        df = pd.DataFrame(data_list)
                        csv = df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "📥 Download CSV",
                            csv,
                            "data_export.csv",
                            "text/csv",
                            key=f"dl_hist_{st.session_state.messages.index(msg)}"
                        )
                    else:
                        st.info("No data.")

                # Tab 3: Charts
                with tabs[2]:
                    data_list = msg.get("data")
                    if data_list and len(data_list) > 1:
                            from src.analytics.visualizer import Visualizer
                            fig = Visualizer.create_chart(data_list)
                            if fig:
                                st.plotly_chart(fig, use_container_width=True, key=f"hist_chart_{i}")
                            else:
                                st.info("No chart available.")
                    else:
                        st.info("Not enough data for chart.")

                # Tab 4: Usage
                if msg.get("token_usage") and len(tabs) > 3:
                     with tabs[3]:
                        usage = msg["token_usage"]
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Total Tokens", usage.get("total_tokens", 0))
                        c2.metric("Prompt Tokens", usage.get("prompt_tokens", 0))
                        c3.metric("Completion Tokens", usage.get("completion_tokens", 0))
            
            # Show insights if available
            if msg.get("insights") and msg["insights"].get("insight_text"):
                st.success(f"💡 Insight: {msg['insights']['insight_text']}")
    
    # Chat input and controls
    # FIX: Adjusted ratio to give the toggle more room (was [5,1], now [8,2] or similar)
    # The toggle needs about 120px to not wrap "Analysis"
    col_input, col_toggle = st.columns([0.80, 0.20])
    
    
    with col_toggle:
        # Pushes the toggle down to align with input
        st.write("") 
        st.write("")
        include_analysis = st.toggle("✨ Analysis", value=False, help="Enable deep AI analysis (slower)")
        
    with col_input:
        if prompt := st.chat_input("Ask a question about your data..."):
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Get response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response = send_message(prompt, include_analysis)
                    
                    if "error" in response:
                        st.error(f"❌ {response['error']}")
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": f"Error: {response['error']}"
                        })
                    else:
                        # Display response
                        # ============================================================
                        # Response Display (Tabs)
                        # ============================================================
                        
                        # 1. Main Answer
                        st.markdown(response.get("message", "No response"))
                        
                        # 1. Hero Metrics (Premium Dashboard)
                        if response.get("insights"):
                            # Create a container for metrics
                            with st.container():
                                cols = st.columns(3)
                                # Metric 1: Records found
                                with cols[0]:
                                    st.metric("Total Records", response.get("row_count", 0))
                                
                                # Dynamic Metrics from Statistics
                                stats = response["insights"].get("numeric_stats", {})
                                idx = 1
                                for col_name, col_stats in stats.items():
                                    if idx >= 3: break
                                    # Prioritize SUM (Sales) then AVG (Rating)
                                    if "sum" in col_stats and col_stats['sum'] > 0:
                                        with cols[idx]:
                                            st.metric(f"Total {col_name.title()}", f"{col_stats['sum']:,.0f}")
                                        idx += 1
                                    elif "avg" in col_stats:
                                        with cols[idx]:
                                            st.metric(f"Avg {col_name.title()}", f"{col_stats['avg']:,.2f}")
                                        idx += 1

                        # 2. Executive Brief (Strategy Deck) - ONLY IN DEEP ANALYSIS MODE
                        if response.get("insights") and response["insights"].get("insight_type") == "ai":
                            with st.expander("✨ Executive Brief (Strategy Officer)", expanded=True):
                                st.markdown(response["insights"].get("insights_text", ""))
                        
                        # Fallback for Simple Mode (Optional: Just show metrics or a small caption)
                        elif response.get("insights") and response["insights"].get("insights_text"):
                             # In fast mode, just show the summary as regular text, or not at all if redundant.
                             # User wanted a "better" experience when ON. So when OFF, we keep it simple.
                             st.caption(f"📝 Summary: {response['insights']['insights_text']}")

                        # 3. Tabs for Details
                        tab_names = ["📄 SQL", "📊 Data", "📈 Charts"]
                        if response.get("token_usage"):
                            tab_names.append("🔢 Usage")
                        tabs = st.tabs(tab_names)
                        
                        # Tab 1: SQL
                        with tabs[0]:
                            sql_queries = response.get("sql_queries", [])
                            if sql_queries:
                                for i, q in enumerate(sql_queries):
                                    st.markdown(f"**Query {i+1}:**")
                                    st.code(q, language="sql")
                            elif response.get("sql"):
                                st.code(response["sql"], language="sql")
                            else:
                                st.info("No SQL generated for this response.")

                        # Tab 2: Data
                        with tabs[1]:
                            formatted_list = response.get("formatted_data_list", [])
                            data_list = response.get("data")
                            
                            # Handle multi-data
                            if formatted_list:
                                for i, table in enumerate(formatted_list):
                                    st.markdown(f"**Result {i+1}:**")
                                    st.markdown(table)
                            # Handle single data
                            elif data_list and len(data_list) > 0:
                                st.dataframe(data_list, use_container_width=True)
                                
                                # CSV Download
                                import pandas as pd
                                df = pd.DataFrame(data_list)
                                csv = df.to_csv(index=False).encode('utf-8')
                                st.download_button(
                                    "📥 Download CSV",
                                    csv,
                                    "data_export.csv",
                                    "text/csv",
                                    key=f"dl_{len(st.session_state.messages)}"
                                )
                            else:
                                st.info("No data returned.")

                        # Tab 3: Charts (Plotly)
                        with tabs[2]:
                            data_list = response.get("data")
                            if data_list and len(data_list) > 1:
                                 from src.analytics.visualizer import Visualizer
                                 fig = Visualizer.create_chart(data_list)
                                 if fig:
                                     # Use a unique key for the new chart based on message count + timestamp/random
                                     import time
                                     st.plotly_chart(fig, use_container_width=True, key=f"new_chart_{int(time.time())}")
                                 else:
                                     st.info("No suitable chart could be generated for this data.")
                            else:
                                st.info("Not enough data to generate a chart (need >1 row).")
                        
                        # Tab 4: Usage
                        if response.get("token_usage") and len(tabs) > 3:
                             with tabs[3]:
                                usage = response["token_usage"]
                                c1, c2, c3 = st.columns(3)
                                c1.metric("Total Tokens", usage.get("total_tokens", 0))
                                c2.metric("Prompt Tokens", usage.get("prompt_tokens", 0))
                                c3.metric("Completion Tokens", usage.get("completion_tokens", 0))
                            

                    
                    # Save to session state
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response.get("message", ""),
                        "sql": response.get("sql"),
                        "sql_queries": response.get("sql_queries"),
                        "data": response.get("data"),
                        "formatted_data_list": response.get("formatted_data_list"),
                        "row_count": response.get("row_count"),
                        "formatted_data_list": response.get("formatted_data_list"),
                        "row_count": response.get("row_count"),
                        "insights": response.get("insights"),
                        "token_usage": response.get("token_usage")
                    })


# ============================================================
# Main App
# ============================================================

def main():
    """Main application entry point."""
    init_session_state()
    
    # Check backend connection
    if not st.session_state.backend_connected:
        check_backend()
    
    # Render sidebar first
    render_sidebar()
    
    # If not connected, show warning in main area
    if not st.session_state.backend_connected:
        st.warning("⚠️ Cannot connect to backend. Please start the server:")
        st.code("cd D:\\ChatBot\n.\\venv\\Scripts\\Activate.ps1\nuvicorn src.api.main:app --reload --port 8000", language="powershell")
        return
    
    # Get or create session
    if not get_or_create_session():
        st.error("Failed to create session")
        return
    
    # Render chat
    render_chat()


if __name__ == "__main__":
    main()
