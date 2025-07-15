import streamlit as st
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
import google.generativeai as genai
import json
import re

# === CONFIG ===
SERVICE_ACCOUNT_JSON = r"C:\Users\s.megavarnan\OneDrive - Perficient, Inc\Python\AI POC\ai_poc\reflecting-ivy-434006-f4-135e5b8e8f67.json"  # 🔁 Replace this
GEMINI_API_KEY = "AIzaSyB3IC4cCbtYqbED4FPeVJ8Y_zMFKKbKic8"  # 🔁 Replace this

# === AUTH ===
service_account_info = json.loads(st.secrets["gcp_service_account"])
credentials = service_account.Credentials.from_service_account_info(service_account_info)
client = bigquery.Client(credentials=credentials, project=credentials.project_id)

# === GEMINI ===
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# === CONSTANTS ===
PUBLIC_PROJECT = "bigquery-public-data"
DATASET = "ga4_obfuscated_sample_ecommerce"
TABLE_PATTERN = f"{PUBLIC_PROJECT}.{DATASET}.events_*"

# === UI ===
st.set_page_config(page_title="Chat with your Data", layout="wide")
st.title("Chat with your data - Your Conversational Analytics Assistant")

st.markdown("Ask questions about Google Analytics 4 ecommerce events data from the public dataset.")

suggestions = [
    "",
    "What are the top 5 events in January 2021?",
    "How many purchases were made in the first week of January?",
    "Which traffic sources brought the most users?",
    "Show daily event count trends for January 2021.",
    "What are the top item categories added to cart?"
]



if "user_question" not in st.session_state:
    st.session_state.user_question = ""

# Dropdown suggestions
# If a suggestion is picked and input is empty or different, update it
if selected_suggestion and st.session_state.user_question != selected_suggestion:
    st.session_state.user_question = selected_suggestion

# Single editable input field
user_question = st.text_input("💬 Ask your question:", value=st.session_state.user_question, key="user_question")

# === Run on Button Click ===
# Button to ask AI
if st.button("🚀 Ask AI"):
    try:
        
        final_question = st.session_state.user_question.strip()
        if not final_question:
            st.warning("Please enter or select a question to proceed.")
        else:
            st.success(f"Processing: {final_question}")

        # Prompt Gemini to generate SQL
            with st.spinner("🧠 Generating SQL..."):
            prompt = f"""
You are a data analyst. Generate a BigQuery SQL query for the following question:

Question: {final_question}

Dataset: {TABLE_PATTERN}
Schema: {schema_str}

Important:
- The table is date-sharded: events_YYYYMMDD.
- Use _TABLE_SUFFIX to query between dates.
- Return only SQL, no explanation.
"""
            response = model.generate_content(prompt)
            raw_sql = response.text

        # Extract SQL only (remove "SQL:", markdown, explanation, etc.)
        sql_lines = raw_sql.splitlines()
        sql_only = "\n".join(line for line in sql_lines if not line.strip().lower().startswith(("sql", "--", "#", "explanation")) and line.strip() != "")
        sql_clean = re.sub(r"^```sql|```$", "", sql_only).strip()

        # Run SQL
        with st.spinner("📡 Querying BigQuery..."):
            df = client.query(sql_clean).to_dataframe()
            st.dataframe(df)

        # Get Insights
        with st.spinner("📊 Generating insights..."):
            insight_prompt = f"Give a brief summary and insight on this table:\n{df.head(10).to_csv(index=False)}"
            insight = model.generate_content(insight_prompt)
            st.markdown("### 📌 AI-Powered Insights")
            st.markdown(insight.text)
        
        with st.spinner("📈 Generating chart..."):
            chart_prompt = f"""
You are a Streamlit expert. Based on the following table, generate Python code to render the most suitable chart using Streamlit (preferably with Altair or st.bar_chart).

Requirements:
- Use 'df' as the DataFrame (assume it's already defined)
- Do not define df again.
- Do not include imports or explanations — only the plotting code.
- Assume df.head(10) looks like this:
{df.head(10).to_csv(index=False)}
"""
            chart_response = model.generate_content(chart_prompt)
            chart_code = chart_response.text.strip()

            chart_code = re.sub(r"^```(?:python)?", "", chart_code, flags=re.IGNORECASE).strip()
            chart_code = re.sub(r"```$", "", chart_code).strip()
            chart_code = chart_code.replace("python", "").strip()

            # Try to execute chart code
            try:
                exec(chart_code)
            except Exception as chart_error:
                st.error(f"⚠️ Error running chart code: {chart_error}")

    except Exception as e:
        st.error(f"❌ Error: {e}")
