import streamlit as st
# --- BACK BUTTON ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py") 
st.write("---") 
# -------------------
import pandas as pd
import plotly.express as px

# -----------------------------------------------------------------------------
# Configuration & Setup
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Money Tracker Visualizer", page_icon="📊", layout="wide")
st.title("📊 Money Tracker: Fund Allocation Visualization")

# -----------------------------------------------------------------------------
# Data Loading (Connects to the same Google Sheet as money_location.py)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_sheet_data():
    # Example using Streamlit's official GSheets connection
    # conn = st.connection("gsheets", type=GSheetsConnection)
    # df = conn.read(spreadsheet="sk_money_location", worksheet="FundsData")
    
    # This is a sample structure replacing the live fetch for demonstration
    # Replace this block with your actual Google Sheet fetch logic
    data = {
        'Account': ['MB', 'MB', 'SBI', 'SBI', 'Cash', 'MB'],
        'Fund_Type': ['Salary Fund', 'SCH MDM Fund', 'Salary Fund', 'SCH Essential', 'Salary Fund', 'SCH Essential'],
        'Amount': [80.00, 20.00, 150.00, 50.00, 30.00, 15.00],
        'Purpose': ['Personal', 'School Veg', 'Personal', 'School Supplies', 'Groceries', 'Stationery']
    }
    return pd.DataFrame(data)

try:
    df = load_sheet_data()
except Exception as e:
    st.error(f"Error loading data from Google Sheets: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# Sidebar & Account Selection
# -----------------------------------------------------------------------------
st.sidebar.header("Tracker Controls")
accounts = df['Account'].dropna().unique().tolist()
selected_account = st.sidebar.selectbox("Select Account", ["All Accounts"] + accounts)

# -----------------------------------------------------------------------------
# Data Processing
# -----------------------------------------------------------------------------
if selected_account != "All Accounts":
    filtered_df = df[df['Account'] == selected_account]
else:
    filtered_df = df

# Group amounts by Fund Type to calculate percentages
fund_totals = filtered_df.groupby('Fund_Type')['Amount'].sum().reset_index()
total_amount = fund_totals['Amount'].sum()

# Calculate the exact percentages required (e.g., 80%)
if total_amount > 0:
    fund_totals['Percentage'] = (fund_totals['Amount'] / total_amount) * 100
else:
    fund_totals['Percentage'] = 0

# -----------------------------------------------------------------------------
# Dashboard Display
# -----------------------------------------------------------------------------
st.subheader(f"Account Overview: {selected_account}")

if total_amount > 0:
    # 1. Text-based breakdown (e.g., "in MB account have Salary Fund ₹80.00 (80%), SCH MDM Fund ₹20.00 (20%)")
    breakdown_texts = []
    for _, row in fund_totals.iterrows():
        breakdown_texts.append(f"**{row['Fund_Type']}**: ₹{row['Amount']:.2f} ({row['Percentage']:.0f}%)")
    
    st.info(f"In **{selected_account}** account have: " + ", ".join(breakdown_texts))

    st.divider()

    # Layout for visualizations
    col1, col2 = st.columns(2)

    # 2. Color-coded Pie Chart for visual breakdown
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

    # 3. Bar Chart to show what the funds are used for
    with col2:
        st.markdown(f"#### Fund Spending Purpose")
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
    st.warning(f"No funds currently tracked in the {selected_account} account.")
