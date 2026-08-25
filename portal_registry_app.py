import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. SETUP & HELPER FUNCTIONS
# ==========================================
st.set_page_config(page_title="Portal & Credential Manager", page_icon="🔐", layout="centered")

# --- BACK BUTTON ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py") 
st.write("---") 
# -------------------

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    gc = gspread.authorize(creds)
    return gc

try:
    gc = init_connection()
    # Now explicitly connecting to your dedicated PORTAL_LOG file
    sh = gc.open("PORTAL_LOG") 
except Exception as e:
    st.error(f"Could not connect to Google APIs. Please ensure 'PORTAL_LOG' is shared with your service account email! Error: {e}")
    st.stop()

@st.cache_data(ttl=60)
def load_portals():
    try: return pd.DataFrame(sh.worksheet("PORTAL_REGISTRY").get_all_records())
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def load_activity():
    try: return pd.DataFrame(sh.worksheet("PORTAL_ACTIVITY").get_all_records())
    except: return pd.DataFrame()

# ==========================================
# APP LAYOUT
# ==========================================
st.title("🔐 Portal & Credential Manager")
st.write("Securely track your personal and school portal logins, and log ongoing activities.")

# Organized into three neat tabs
tab1, tab2, tab3 = st.tabs(["➕ Add Portal", "📝 Log Activity", "🗂️ My Portals Dashboard"])

# ------------------------------------------
# TAB 1: REGISTER NEW PORTAL
# ------------------------------------------
with tab1:
    with st.form("portal_form"):
        p_name = st.text_input("Portal / App Name", placeholder="e.g., SHVR 2026-27, Income Tax e-Filing, UDISE+")
        
        c_type, c_url = st.columns([1, 2])
        with c_type:
            p_type = st.radio("Type", ["School", "Personal"])
        with c_url:
            p_url = st.text_input("Access Link / Platform", placeholder="e.g., Android App, https://eportal.incometax.gov.in")

        st.divider()
        st.caption("🔑 **Credential Details**")
        c1, c2 = st.columns(2)
        with c1:
            p_user = st.text_input("Username / ID", placeholder="e.g., UDISE+ Code, PAN, Email")
            p_mobile = st.text_input("Registered Mobile Number")
        with c2:
            # Masked on screen, but saves as plain text to Google Sheets so you can read it later
            p_pass = st.text_input("Password / PIN", type="password") 
            p_email = st.text_input("Registered Email")

        p_notes = st.text_area("Additional Notes", placeholder="e.g., Security questions, or registration context...")

        if st.form_submit_button("💾 Save Credentials", type="primary", use_container_width=True):
            if p_name and p_user:
                try:
                    try: 
                        ws_reg = sh.worksheet("PORTAL_REGISTRY")
                    except gspread.exceptions.WorksheetNotFound:
                        ws_reg = sh.add_worksheet(title="PORTAL_REGISTRY", rows="100", cols="9")
                        ws_reg.append_row(["Date_Added", "Portal_Name", "Type", "Access_Link", "Username", "Password", "Mobile", "Email", "Notes"])

                    date_added = get_ist_now().strftime("%d-%m-%Y")
                    ws_reg.append_row([date_added, p_name, p_type, p_url, p_user, p_pass, p_mobile, p_email, p_notes])
                    
                    load_portals.clear()
                    st.success(f"✅ Credentials for {p_name} saved securely to PORTAL_LOG!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error saving data: {e}")
            else:
                st.warning("⚠️ Portal Name and Username are required.")

# ------------------------------------------
# TAB 2: LOG ONGOING ACTIVITY
# ------------------------------------------
with tab2:
    df_portals = load_portals()
    
    if df_portals.empty:
        st.info("No portals registered yet. Add one in the first tab to start logging activity!")
    else:
        portal_list = df_portals["Portal_Name"].tolist()
        
        with st.form("activity_form"):
            act_portal = st.selectbox("Select Portal / App", portal_list)
            act_date = st.date_input("Activity Date", value=get_ist_now().date())
            act_desc = st.text_area("Activity Description", placeholder="e.g., Registered for 2026-27 cycle, uploaded photos, submitted survey...")

            if st.form_submit_button("💾 Log Activity", type="primary", use_container_width=True):
                if act_desc:
                    try:
                        try: 
                            ws_act = sh.worksheet("PORTAL_ACTIVITY")
                        except gspread.exceptions.WorksheetNotFound:
                            ws_act = sh.add_worksheet(title="PORTAL_ACTIVITY", rows="100", cols="4")
                            ws_act.append_row(["Date", "Time", "Portal_Name", "Activity"])

                        ws_act.append_row([
                            act_date.strftime("%d-%m-%Y"), 
                            get_ist_now().strftime("%H:%M"), 
                            act_portal, 
                            act_desc
                        ])
                        
                        load_activity.clear()
                        st.success(f"✅ Activity logged under {act_portal}!")
                    except Exception as e:
                        st.error(f"Error saving activity: {e}")
                else:
                    st.warning("⚠️ Please provide a description of the activity.")

# ------------------------------------------
# TAB 3: DASHBOARD & LOOKUP
# ------------------------------------------
with tab3:
    if df_portals.empty:
        st.info("Your portal library is empty.")
    else:
        df_activity = load_activity()
        
        # Search bar to quickly find a portal
        search_query = st.text_input("🔍 Search Portals...", placeholder="Type name, username, or type...")
        
        if search_query:
            mask = df_portals.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
            df_display = df_portals[mask]
        else:
            df_display = df_portals

        for _, row in df_display.iterrows():
            p_n = row.get("Portal_Name", "Unknown")
            p_type = row.get("Type", "-")
            
            # Add a visual icon based on the type
            icon = "🏫" if p_type == "School" else "👤"

            with st.expander(f"{icon} {p_n}"):
                st.caption(f"🔗 **Platform:** {row.get('Access_Link', 'Not specified')}")
                
                # Highlighted Credentials Box
                st.info(f"""
                **Username / ID:** `{row.get('Username', '-')}`  
                **Password / PIN:** `{row.get('Password', '-')}`
                """)

                st.markdown(f"**📱 Linked Mobile:** {row.get('Mobile', '-')} | **📧 Linked Email:** {row.get('Email', '-')}")
                
                notes = str(row.get("Notes", "")).strip()
                if notes:
                    st.markdown(f"**📝 Notes:** {notes}")

                # Pull corresponding activity logs for this specific portal
                st.divider()
                st.markdown("**🔄 Activity History:**")
                if not df_activity.empty and "Portal_Name" in df_activity.columns:
                    history = df_activity[df_activity["Portal_Name"] == p_n]
                    if history.empty:
                        st.write("No activity logged yet.")
                    else:
                        # Display newest activity first
                        for _, h_row in history.iloc[::-1].iterrows():
                            st.caption(f"🕒 {h_row.get('Date', '-')} at {h_row.get('Time', '-')}")
                            st.write(f"▪️ {h_row.get('Activity', '-')}")
                else:
                    st.write("No activity logged yet.")
