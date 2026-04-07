import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ==========================================
# 1. SETUP & DATABASE CONNECTION
# ==========================================
st.set_page_config(page_title="BPS Supply Distribution", layout="centered")
today_date = datetime.now().strftime("%a, %d.%m.%y").upper()

# Cache the connection so it doesn't re-authenticate on every click
@st.cache_resource
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    # Pull credentials directly from your [gcp_service_account] secret block
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    return gspread.authorize(credentials)

gc = get_gspread_client()

# Try to open the Google Sheet
try:
    # Make sure the document name in Google Sheets is exactly "BPS_Distribution_Log"
    sh = gc.open("BPS_Distribution_Log")
    worksheet = sh.sheet1 # This grabs the very first tab at the bottom
except gspread.exceptions.SpreadsheetNotFound:
    st.error("Google Sheet 'BPS_Distribution_Log' not found. Make sure it is shared with your client_email as an Editor.")
    st.stop()

# Initialize the distribution database from Google Sheets
if 'supply_df' not in st.session_state:
    records = worksheet.get_all_records()
    
    if not records:
        # Fallback if the sheet is completely empty
        data = {
            'Class': ['PP', 'PP', 'LPP', 'LPP'],
            'Roll': [1, 2, 1, 2],
            'Name': ['MIMMA PARVIN', 'SK AIYUB ALI', 'AMIRA KHATUN', 'RAHUL DAS'],
            'Mobile': ['9999999991', '9999999992', '8888888881', '8888888882'],
            'Books_Given': [False, False, False, False],
            'Uniform_Given': [False, False, False, False],
            'Bag_Given': [False, False, False, False]
        }
        st.session_state.supply_df = pd.DataFrame(data)
        # Push this default data to Google Sheets
        worksheet.update(values=[st.session_state.supply_df.columns.values.tolist()] + st.session_state.supply_df.values.tolist())
    else:
        # Load existing data from Google Sheets
        st.session_state.supply_df = pd.DataFrame(records)
        # Ensure 'True'/'False' strings from Sheets are treated as actual booleans in Python
        for col in ['Books_Given', 'Uniform_Given', 'Bag_Given']:
            st.session_state.supply_df[col] = st.session_state.supply_df[col].map({'TRUE': True, 'FALSE': False, True: True, False: False}).fillna(False)

if 'distribution_submitted' not in st.session_state:
    st.session_state.distribution_submitted = False

df = st.session_state.supply_df

st.title("Bhagyabantapur Primary School")
st.markdown(f"**Supply Distribution Log | Date:** {today_date}")

# ==========================================
# 2. APP TABS (TEACHER & ADMIN)
# ==========================================
tab_entry, tab_summary = st.tabs(["Distribute Items", "Head Teacher Summary"])

# --- TEACHER ENTRY TAB ---
with tab_entry:
    st.header("Issue Supplies to Students")
    st.info("Select the items distributed to each student today.")

    distribution_type = st.radio("Select Item Category:", ["Books", "Uniform", "Bag"], horizontal=True)
    column_map = {"Books": "Books_Given", "Uniform": "Uniform_Given", "Bag": "Bag_Given"}
    active_column = column_map[distribution_type]

    st.markdown("---")
    
    # Class PP Section
    st.subheader("CLASS PP")
    df_pp = df[df['Class'] == 'PP']
    for index, row in df_pp.iterrows():
        widget_key = f"supply_{active_column}_PP_{row['Roll']}_{row['Name']}"
        
        if widget_key not in st.session_state:
            st.session_state[widget_key] = bool(row[active_column])
            
        if st.checkbox(f"Roll {row['Roll']}: {row['Name']}", key=widget_key):
            df.loc[(df['Class'] == 'PP') & (df['Roll'] == row['Roll']), active_column] = True
        else:
            df.loc[(df['Class'] == 'PP') & (df['Roll'] == row['Roll']), active_column] = False

    st.markdown("---")

    # Class LPP Section
    st.subheader("CLASS LPP")
    df_lpp = df[df['Class'] == 'LPP']
    for index, row in df_lpp.iterrows():
        widget_key = f"supply_{active_column}_LPP_{row['Roll']}_{row['Name']}"
        
        if widget_key not in st.session_state:
            st.session_state[widget_key] = bool(row[active_column])
            
        if st.checkbox(f"Roll {row['Roll']}: {row['Name']}", key=widget_key):
            df.loc[(df['Class'] == 'LPP') & (df['Roll'] == row['Roll']), active_column] = True
        else:
            df.loc[(df['Class'] == 'LPP') & (df['Roll'] == row['Roll']), active_column] = False

    st.markdown("<br>", unsafe_allow_html=True)
    
    # Write to Google Sheets on Submit using pure gspread
    if st.button(f"Submit {distribution_type} Distribution", type="primary"):
        try:
            # Clear old data and push the entirely updated dataframe
            worksheet.clear()
            worksheet.update(values=[df.columns.values.tolist()] + df.values.tolist())
            
            st.session_state.distribution_submitted = True
            st.success("Distribution log saved successfully to Google Sheets!")
        except Exception as e:
            st.error(f"Failed to update Google Sheets: {e}")

# --- HEAD TEACHER SUMMARY TAB ---
with tab_summary:
    st.header("Distribution Summary")
    
    # Adding a hard refresh button so the Head Teacher can pull live updates
    if st.button("Refresh Live Data from Sheets"):
        # Delete the dataframe from session state so it is forced to redownload on rerun
        del st.session_state['supply_df'] 
        st.rerun()

    if st.session_state.distribution_submitted:
        st.subheader("Items Distributed")
        
        books_total = len(df[df['Books_Given'] == True])
        uniforms_total = len(df[df['Uniform_Given'] == True])
        bags_total = len(df[df['Bag_Given'] == True])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Books Issued", books_total)
        col2.metric("Uniforms Issued", uniforms_total)
        col3.metric("Bags Issued", bags_total)
        
        st.write("### Detailed Distribution Record")
        received_items = df[(df['Books_Given'] == True) | (df['Uniform_Given'] == True) | (df['Bag_Given'] == True)]
        st.dataframe(received_items[['Class', 'Roll', 'Name', 'Books_Given', 'Uniform_Given', 'Bag_Given']], hide_index=True)
    else:
        st.info("Waiting for teachers to log today's distributions. (Or click 'Refresh' above to check for updates).")