import streamlit as st
import pandas as pd
from datetime import datetime

# --- CONFIGURATION & SETUP ---
st.set_page_config(page_title="Money Count Dashboard", layout="wide")

# Initialize data storage (In a real app, this would be a CSV or Database)
if 'transactions' not in st.session_state:
    st.session_state.transactions = pd.DataFrame(columns=[
        "Date", "Entity", "Category", "Sub Category", "Particulars", "TO/FROM", "Amount", "Type"
    ])

if 'opening_balances' not in st.session_state:
    st.session_state.opening_balances = {"Cash": 0.0, "Axis Bank": 10000.0}

# --- SIDEBAR: OPENING BALANCES ---
with st.sidebar:
    st.header("🏦 Opening Balances")
    for account in st.session_state.opening_balances:
        new_val = st.number_input(f"Opening {account}", value=st.session_state.opening_balances[account])
        st.session_state.opening_balances[account] = new_val

# --- MAIN INTERFACE ---
st.title("📊 February 2026 Money Tracker")

tab1, tab2 = st.tabs(["➕ Add Transaction", "📈 Dashboard"])

with tab1:
    with st.form("entry_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            date = st.date_input("Date", datetime(2026, 2, 1))
            entity = st.selectbox("Entity", ["CASH", "AXIS", "TGCCB", "CREDIT_CARD"])
            category = st.selectbox("Category", ["PER", "SCH", "VEGE", "FAMILY", "VEHICLE", "LOAN"])
        
        with col2:
            # Dynamic Sub-Category logic
            sub_cat_options = []
            if category == "FAMILY":
                sub_cat_options = ["Self", "Mother", "Baso", "Suborno"]
            elif category == "VEGE":
                sub_cat_options = ["Market Trip", "Daily Needs"]
            elif category == "LOAN":
                sub_cat_options = ["Deduction", "Interest", "Repayment"]
            else:
                sub_cat_options = ["General"]
                
            sub_category = st.selectbox("Sub Category", sub_cat_options)
            to_from = st.text_input("TO / FROM (e.g., Girishmore Market)")
            
        with col3:
            # Handle multiple items in particulars as you requested
            particulars = st.text_area("Particulars", help="Enter 'Mixed Veg' if items are too many to list.")
            amount = st.number_input("Amount", min_value=0.0)
            trans_type = st.radio("Type", ["Expense", "Income", "Transfer"])

        submit = st.form_submit_button("Add Record")
        
        if submit:
            new_data = {
                "Date": date, "Entity": entity, "Category": category, 
                "Sub Category": sub_category, "Particulars": particulars, 
                "TO/FROM": to_from, "Amount": amount, "Type": trans_type
            }
            st.session_state.transactions = pd.concat([st.session_state.transactions, pd.DataFrame([new_data])], ignore_index=True)
            st.success("Entry Saved!")

with tab2:
    # --- DASHBOARD LOGIC ---
    df = st.session_state.transactions
    
    # Calculate Balances
    total_expenses = df[df['Type'] == "Expense"]['Amount'].sum()
    total_income = df[df['Type'] == "Income"]['Amount'].sum()
    opening = sum(st.session_state.opening_balances.values())
    current_balance = opening + total_income - total_expenses

    # Top Metric Row
    m1, m2, m3 = st.columns(3)
    m1.metric("Opening Balance", f"₹{opening:,.2f}")
    m2.metric("Current Balance", f"₹{current_balance:,.2f}", delta=f"{total_income - total_expenses:,.2f}")
    m3.metric("Total Expenses", f"₹{total_expenses:,.2f}")

    st.divider()

    # --- ALTERNATING ROW COLOR DATASET ---
    def style_rows(df):
        # Logic to change color when date changes
        return df.style.apply(lambda x: ['background-color: #2e2e2e' if i % 2 == 0 else '' for i in range(len(x))], axis=0)

    st.subheader("Transaction Log")
    if not df.empty:
        st.dataframe(df.sort_values("Date", ascending=False), use_container_width=True)
    else:
        st.info("No transactions recorded yet.")