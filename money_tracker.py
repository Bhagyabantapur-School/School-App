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
st.title("📊 Money Tracker & Analytics")

# -----------------------------------------------------------------------------
# Live Google Sheets Connections
# -----------------------------------------------------------------------------
@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    gc = gspread.authorize(creds)
    return gc

@st.cache_data(ttl=60) 
def load_funds_data():
    try:
        gc = init_connection()
        sh = gc.open("sk_money_location")
        try:
            ws = sh.worksheet("FundsData")
        except gspread.exceptions.WorksheetNotFound:
            return pd.DataFrame() # Return empty if it doesn't exist yet
            
        df = pd.DataFrame(ws.get_all_records())
        if 'Amount' in df.columns:
            df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_money_data():
    try:
        gc = init_connection()
        sh = gc.open("sk_money_location")
        df = pd.DataFrame(sh.worksheet("MONEY_DATA").get_all_records())
        
        # Clean numeric columns to ensure they graph properly
        for col in ['In', 'Out']:
            if col in df.columns:
                # Replaces empty strings or spaces with 0, converts to float
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Error fetching MONEY_DATA: {e}")
        return pd.DataFrame()

df_funds = load_funds_data()
df_money = load_money_data()

# -----------------------------------------------------------------------------
# Sidebar & Global Filters
# -----------------------------------------------------------------------------
st.sidebar.header("Tracker Controls")

# Combine all unique accounts from both sheets so the dropdown is complete
accounts_set = set()
if not df_funds.empty and 'Account' in df_funds.columns:
    accounts_set.update(df_funds['Account'].dropna().unique().tolist())
if not df_money.empty and 'Account' in df_money.columns:
    accounts_set.update(df_money['Account'].dropna().unique().tolist())

# Clean up empty strings from the account list
accounts_list = [acc for acc in list(accounts_set) if str(acc).strip() != ""]

selected_account = st.sidebar.selectbox("Filter by Account", ["All Accounts"] + sorted(accounts_list))

# -----------------------------------------------------------------------------
# Apply Global Filters to Data
# -----------------------------------------------------------------------------
if selected_account != "All Accounts":
    if not df_funds.empty:
        df_funds = df_funds[df_funds['Account'] == selected_account]
    if not df_money.empty:
        df_money = df_money[df_money['Account'] == selected_account]

# -----------------------------------------------------------------------------
# Dashboard Layout (Tabs)
# -----------------------------------------------------------------------------
tab1, tab2 = st.tabs(["💼 Fund Allocation", "📈 Category Breakdown"])

# ==========================================
# TAB 1: FUND ALLOCATION
# ==========================================
with tab1:
    if df_funds.empty:
        st.info("✨ **No fund data found.** Ensure you have added rows to your 'FundsData' tab in Google Sheets.")
    else:
        if 'Fund_Type' in df_funds.columns and 'Amount' in df_funds.columns:
            fund_totals = df_funds.groupby('Fund_Type')['Amount'].sum().reset_index()
            total_amount = fund_totals['Amount'].sum()

            if total_amount > 0:
                fund_totals['Percentage'] = (fund_totals['Amount'] / total_amount) * 100
                
                breakdown_texts = []
                for _, row in fund_totals.iterrows():
                    breakdown_texts.append(f"**{row['Fund_Type']}**: ₹{row['Amount']:.2f} ({row['Percentage']:.0f}%)")
                
                st.info(f"**Account Selection:** {selected_account}  \n**Total:** ₹{total_amount:.2f}  \n" + " | ".join(breakdown_texts))

                st.divider()
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("#### Fund Distribution")
                    fig_pie = px.pie(
                        fund_totals, values='Amount', names='Fund_Type', hole=0.4,
                        color_discrete_sequence=px.colors.qualitative.Pastel
                    )
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_pie, use_container_width=True)

                with col2:
                    st.markdown("#### Fund Spending Purpose")
                    if 'Purpose' in df_funds.columns:
                        purpose_totals = df_funds.groupby(['Fund_Type', 'Purpose'])['Amount'].sum().reset_index()
                        fig_bar = px.bar(
                            purpose_totals, x='Fund_Type', y='Amount', color='Purpose',
                            text_auto='.2f', color_discrete_sequence=px.colors.qualitative.Set2
                        )
                        st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.warning(f"No funds currently tracked for: {selected_account}.")

# ==========================================
# TAB 2: CATEGORY BREAKDOWN
# ==========================================
with tab2:
    if df_money.empty:
        st.info("No transaction history found in your MONEY_DATA tab.")
    else:
        st.subheader(f"Expense Analytics: {selected_account}")
        
        # Filter to only show outgoing money (Expenses)
        if 'Out' in df_money.columns and 'Category' in df_money.columns:
            expenses = df_money[df_money['Out'] > 0].copy()
            
            if not expenses.empty:
                # Clean up empty categories to display as "Uncategorized"
                expenses['Category'] = expenses['Category'].replace(r'^\s*$', 'Uncategorized', regex=True).fillna('Uncategorized')
                
                if 'Sub Category' in expenses.columns:
                    expenses['Sub Category'] = expenses['Sub Category'].replace(r'^\s*$', 'Uncategorized', regex=True).fillna('Uncategorized')
                else:
                    expenses['Sub Category'] = 'Uncategorized'
                
                # Group the data
                cat_sub_totals = expenses.groupby(['Category', 'Sub Category'])['Out'].sum().reset_index()
                
                # Create the interactive Sunburst chart
                st.markdown("#### Expense Hierarchy (Click on a Category to Zoom In!)")
                fig_sunburst = px.sunburst(
                    cat_sub_totals,
                    path=['Category', 'Sub Category'],
                    values='Out',
                    color='Category',
                    color_discrete_sequence=px.colors.qualitative.Prism
                )
                fig_sunburst.update_traces(textinfo="label+percent parent+value")
                st.plotly_chart(fig_sunburst, use_container_width=True)
                
                # Show the clean data table
                st.divider()
                st.markdown("#### Detailed Category Summary")
                
                # Format the table nicely
                display_table = cat_sub_totals.sort_values(by='Out', ascending=False)
                display_table = display_table.rename(columns={"Out": "Total Spent (₹)"})
                st.dataframe(
                    display_table, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={"Total Spent (₹)": st.column_config.NumberColumn(format="₹%.2f")}
                )
            else:
                st.info(f"No outgoing expenses recorded for: {selected_account}.")
        else:
            st.error("Missing required columns ('Out' or 'Category') in MONEY_DATA tab.")
