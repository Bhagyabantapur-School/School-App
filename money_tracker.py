import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- BACK BUTTON ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py") 
st.write("---") 
# -------------------

# -----------------------------------------------------------------------------
# Configuration & Setup
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Money Tracker Visualizer", page_icon="📊", layout="wide")
st.title("📊 Money Tracker: Fund Allocation Visualization")

# -----------------------------------------------------------------------------
# Live Google Sheets Connection (Auto-Creates Tab if Missing)
# -----------------------------------------------------------------------------
@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    gc = gspread.authorize(creds)
    return gc

@st.cache_data(ttl=60) 
def load_sheet_data():
    try:
        gc = init_connection()
        sh = gc.open("sk_money_location")
        
        # Try to open FundsData, if it doesn't exist, create it!
        try:
            ws = sh.worksheet("FundsData")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title="FundsData", rows="100", cols="4")
            ws.append_row(["Account", "Fund_Type", "Amount", "Purpose"])
            return pd.DataFrame() # Returns empty so the app doesn't crash on first load
            
        df = pd.DataFrame(ws.get_all_records())
        
        # Ensure the 'Amount' column is treated as numbers
        if 'Amount' in df.columns:
            df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
            
        return df
    except Exception as e:
        st.error(f"Error fetching live data: {e}")
        return pd.DataFrame()

df = load_sheet_data()

# Stop the app gracefully if the sheet was just created or is empty
if df.empty:
    st.info("✨ **I just automatically created the 'FundsData' tab in your Google Sheet!**")
    st.warning("Go to your 'sk_money_location' Google Sheet, open the new 'FundsData' tab, and add a few rows of data so I have something to graph!")
    st.stop()

# -----------------------------------------------------------------------------
# Sidebar & Account Selection
# -----------------------------------------------------------------------------
st.sidebar.header("Tracker Controls")
if 'Account' in df.columns:
    accounts = df['Account'].dropna().unique().tolist()
    selected_account = st.sidebar.selectbox("Select Account", ["All Accounts"] + accounts)
else:
    st.error("⚠️ Column 'Account' is missing from the Google Sheet.")
    st.stop()

# -----------------------------------------------------------------------------
# Data Processing
# -----------------------------------------------------------------------------
if selected_account != "All Accounts":
    filtered_df = df[df['Account'] == selected_account]
else:
    filtered_df = df

if 'Fund_Type' in filtered_df.columns and 'Amount' in filtered_df.columns:
    fund_totals = filtered_df.groupby('Fund_Type')['Amount'].sum().reset_index()
    total_amount = fund_totals['Amount'].sum()

    if total_amount > 0:
        fund_totals['Percentage'] = (fund_totals['Amount'] / total_amount) * 100
    else:
        fund_totals['Percentage'] = 0
else:
    st.error("⚠️ Columns 'Fund_Type' and/or 'Amount' are missing.")
    st.stop()

# -----------------------------------------------------------------------------
# Dashboard Display
# -----------------------------------------------------------------------------
st.subheader(f"Account Overview: {selected_account}")

if total_amount > 0:
    breakdown_texts = []
    for _, row in fund_totals.iterrows():
        breakdown_texts.append(f"**{row['Fund_Type']}**: ₹{row['Amount']:.2f} ({row['Percentage']:.0f}%)")
    
    st.info(f"In **{selected_account}** account have: " + ", ".join(breakdown_texts))

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"#### Fund Distribution in {selected_account}")
        fig_pie = px.pie(
            fund_totals, 
            values='Amount', 
            names='Fund_Type', 
            hole=0.4,
            color='Fund_Type',
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.markdown(f"#### Fund Spending Purpose")
        if 'Purpose' in filtered_df.columns:
            purpose_totals = filtered_df.groupby(['Fund_Type', 'Purpose'])['Amount'].sum().reset_index()
            fig_bar = px.bar(
                purpose_totals, 
                x='Fund_Type', 
                y='Amount',
                color='Purpose',
                text_auto='.2f',
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.warning("Column 'Purpose' is missing from the Google Sheet, cannot render Bar Chart.")
else:
    st.warning(f"No funds currently tracked in the {selected_account} account.")
