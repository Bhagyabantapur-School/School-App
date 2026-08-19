import streamlit as st
# --- BACK BUTTON ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py") 
st.write("---") 
# -------------------
import pandas as pd
from datetime import datetime, timedelta, timezone
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. SETUP & HELPER FUNCTIONS
# ==========================================
st.set_page_config(page_title="SK Income Nexus", page_icon="💸", layout="centered")

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

if 'locked_date' not in st.session_state: 
    st.session_state.locked_date = get_ist_now().date()

@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    return client.open("sk_money_location")

try:
    sh = init_connection()
except Exception as e:
    st.error(f"Could not connect to Google Sheets. Error: {e}")
    st.stop()

# --- SMART CACHING ENGINE ---
@st.cache_data(ttl=600)
def load_config():
    try: return pd.DataFrame(sh.worksheet("CONFIG").get_all_records())
    except: return pd.DataFrame()

# We only need to clear money data when investments auto-sync
@st.cache_data(ttl=60)
def load_money_data():
    try: return pd.DataFrame(sh.worksheet("MONEY_DATA").get_all_records())
    except: return pd.DataFrame()

config_df = load_config()

def get_list(column_name):
    if column_name in config_df.columns:
        raw_list = [str(val).strip() for val in config_df[column_name].dropna().tolist() if str(val).strip() != ""]
        return list(dict.fromkeys(raw_list))
    return []

# ==========================================
# APP LAYOUT & TABS
# ==========================================
st.title("💸 SK Income Nexus")
st.caption("Your command center for all active and passive revenue streams.")

tab_yt, tab_aff, tab_spon, tab_ai, tab_inv = st.tabs([
    "🎥 YouTube", "🛒 Affiliate", "🤝 Sponsorship", "🤖 AI Projects", "📈 Stock Market"
])

# ==========================================
# TAB 1: YOUTUBE
# ==========================================
with tab_yt:
    st.subheader("▶️ YouTube Analytics & Revenue")
    
    channel_opts = get_list("YouTube_Channels") 
    if not channel_opts: channel_opts = ["techfeatureslife9451", "-- Type New --"]
    
    yt_channel_sel = st.selectbox("Select Channel", channel_opts, key="yt_chan")
    yt_channel = st.text_input("Type New Channel") if yt_channel_sel == "-- Type New --" else yt_channel_sel
    
    yt_c1, yt_c2 = st.columns(2)
    with yt_c1:
        yt_date = st.date_input("Analytics Date", value=st.session_state.locked_date, key="yt_date")
        yt_views = st.number_input("Views", min_value=0, step=100)
        yt_subs = st.number_input("Subscribers Gained", min_value=0, step=1)
    
    with yt_c2:
        yt_title = st.text_input("Video Title (Optional)")
        yt_hours = st.number_input("Watch Hours", min_value=0.0, step=1.0)
        yt_revenue = st.number_input("Estimated Revenue (₹)", min_value=0.0, step=10.0)

    if st.button("💾 Save YouTube Log", use_container_width=True, type="primary"):
        if yt_channel:
            try:
                date_str = yt_date.strftime("%d-%m-%Y")
                try: yt_ws = sh.worksheet("YOUTUBE_LOG")
                except gspread.exceptions.WorksheetNotFound:
                    yt_ws = sh.add_worksheet(title="YOUTUBE_LOG", rows="100", cols="7")
                    yt_ws.append_row(["Date", "Channel_Name", "Video_Title", "Views", "Watch_Hours", "Subscribers_Gained", "Estimated_Revenue"])
                
                yt_ws.append_row([date_str, yt_channel, yt_title, yt_views, yt_hours, yt_subs, yt_revenue])
                st.success(f"✅ Logged stats for {yt_channel}!")
                st.balloons()
            except Exception as e: st.error(f"Error: {e}")
        else: st.warning("⚠️ Please provide a channel name.")

# ==========================================
# TAB 2: AFFILIATE
# ==========================================
with tab_aff:
    st.subheader("🛒 Affiliate Sales & Commissions")
    
    aff_opts = get_list("Affiliate_Programs")
    if not aff_opts: aff_opts = ["Amazon Associates", "Flipkart Affiliate", "Hostinger", "-- Type New --"]
    if "-- Type New --" not in aff_opts: aff_opts.append("-- Type New --")
        
    aff_prog_sel = st.selectbox("Select Affiliate Program", aff_opts, key="aff_prog")
    aff_program = st.text_input("Type New Program Name") if aff_prog_sel == "-- Type New --" else aff_prog_sel

    aff_product = st.text_input("Product or Campaign Promoted (e.g., DJI Mic Mini)")
    
    aff_c1, aff_c2, aff_c3 = st.columns(3)
    with aff_c1: aff_date = st.date_input("Date", value=st.session_state.locked_date, key="aff_date")
    with aff_c2: aff_clicks = st.number_input("Link Clicks", min_value=0, step=10, key="aff_clicks")
    with aff_c3: aff_conversions = st.number_input("Conversions (Sales)", min_value=0, step=1, key="aff_conv")
        
    aff_commission = st.number_input("Estimated Commission Earned (₹)", min_value=0.0, step=50.0, key="aff_comm")

    if st.button("💾 Save Affiliate Log", use_container_width=True, type="primary"):
        if aff_program and aff_product:
            try:
                date_str = aff_date.strftime("%d-%m-%Y")
                try: aff_ws = sh.worksheet("AFFILIATE_LOG")
                except gspread.exceptions.WorksheetNotFound:
                    aff_ws = sh.add_worksheet(title="AFFILIATE_LOG", rows="100", cols="6")
                    aff_ws.append_row(["Date", "Program", "Product_or_Campaign", "Clicks", "Conversions", "Estimated_Commission"])
                
                aff_ws.append_row([date_str, aff_program, aff_product, aff_clicks, aff_conversions, aff_commission])
                st.success(f"✅ Logged {aff_conversions} sales for {aff_program}!")
            except Exception as e: st.error(f"Error: {e}")
        else: st.warning("⚠️ Please provide both the Program and the Product name.")

# ==========================================
# TAB 3: SPONSORSHIP
# ==========================================
with tab_spon:
    st.subheader("🤝 Sponsorship & Brand Deals")
    
    sponsor_opts = get_list("Sponsors")
    if not sponsor_opts: sponsor_opts = ["-- Type New --"]
    elif "-- Type New --" not in sponsor_opts: sponsor_opts.append("-- Type New --")
        
    sp_brand_sel = st.selectbox("Sponsor / Brand Name", sponsor_opts, key="sp_brand_sel")
    sp_brand = st.text_input("Type New Brand Name", key="sp_new_brand") if sp_brand_sel == "-- Type New --" else sp_brand_sel

    sp_campaign = st.text_input("Campaign or Video Title")
    
    sp_c1, sp_c2 = st.columns(2)
    with sp_c1:
        sp_type = st.selectbox("Deliverable Type", ["Integrated (60-90s)", "Dedicated Video", "YouTube Shorts", "Community Post", "Bundle"])
        sp_status = st.selectbox("Current Status", ["Pitching / Outreach", "Negotiating", "Contract Signed", "Content Submitted for Approval", "Content Live", "Invoice Sent", "✅ Paid"])
    
    with sp_c2:
        sp_publish_date = st.date_input("Target Publish Date", value=st.session_state.locked_date, key="sp_pub_date")
        sp_fee = st.number_input("Agreed Fee (₹)", min_value=0.0, step=1000.0, key="sp_fee")

    if st.button("💾 Save Sponsorship Log", use_container_width=True, type="primary"):
        if sp_brand and sp_campaign:
            try:
                today_str = get_ist_now().strftime("%d-%m-%Y")
                publish_str = sp_publish_date.strftime("%d-%m-%Y")
                
                try: sp_ws = sh.worksheet("SPONSORSHIP_LOG")
                except gspread.exceptions.WorksheetNotFound:
                    sp_ws = sh.add_worksheet(title="SPONSORSHIP_LOG", rows="100", cols="7")
                    sp_ws.append_row(["Date_Logged", "Brand_Name", "Campaign_or_Video", "Deliverable_Type", "Status", "Target_Publish_Date", "Agreed_Fee"])
                
                sp_ws.append_row([today_str, sp_brand, sp_campaign, sp_type, sp_status, publish_str, sp_fee])
                st.success(f"✅ Logged deal with {sp_brand} as '{sp_status}'!")
                if sp_status == "✅ Paid": st.info("Remember to log the actual cash received in the main Money app!")
            except Exception as e: st.error(f"Error: {e}")
        else: st.warning("⚠️ Please provide the Brand Name and Campaign Title.")

# ==========================================
# TAB 4: AI PROJECTS
# ==========================================
with tab_ai:
    st.subheader("🤖 AI Generation & Projects")
    
    ai_opts = get_list("AI_Platforms")
    if not ai_opts: ai_opts = ["Direct Client", "Upwork", "Fiverr", "Gumroad", "-- Type New --"]
    elif "-- Type New --" not in ai_opts: ai_opts.append("-- Type New --")
        
    ai_plat_sel = st.selectbox("Platform / Source", ai_opts, key="ai_plat_sel")
    ai_platform = st.text_input("Type New Platform Name", key="ai_new_plat") if ai_plat_sel == "-- Type New --" else ai_plat_sel

    ai_project = st.text_input("Project or Task Name (e.g., 'Streamlit App Build')")
    
    ai_c1, ai_c2, ai_c3 = st.columns([1.5, 1, 1.5])
    with ai_c1: ai_date = st.date_input("Date Logged", value=st.session_state.locked_date, key="ai_date")
    with ai_c2: ai_hours = st.number_input("Hours Spent", min_value=0.0, step=0.5, key="ai_hrs")
    with ai_c3: ai_revenue = st.number_input("Estimated Revenue (₹)", min_value=0.0, step=100.0, key="ai_rev")
        
    ai_status = st.selectbox("Payment Status", ["Pending / Unbilled", "Invoice Sent", "✅ Paid"], key="ai_status")

    if st.button("💾 Save AI Income Log", use_container_width=True, type="primary"):
        if ai_platform and ai_project:
            try:
                date_str = ai_date.strftime("%d-%m-%Y")
                try: ai_ws = sh.worksheet("AI_INCOME_LOG")
                except gspread.exceptions.WorksheetNotFound:
                    ai_ws = sh.add_worksheet(title="AI_INCOME_LOG", rows="100", cols="6")
                    ai_ws.append_row(["Date", "Platform", "Project_Name", "Hours_Spent", "Estimated_Revenue", "Status"])
                
                ai_ws.append_row([date_str, ai_platform, ai_project, ai_hours, ai_revenue, ai_status])
                st.success(f"✅ Logged AI project: {ai_project}!")
                if ai_status == "✅ Paid": st.info("Remember to log the actual cash received in the main Money app!")
            except Exception as e: st.error(f"Error: {e}")
        else: st.warning("⚠️ Please provide both the Platform and the Project Name.")

# ==========================================
# TAB 5: STOCK MARKET
# ==========================================
with tab_inv:
    st.subheader("📈 Stock Market & Mutual Funds")
    
    asset_opts = get_list("Investment_Assets")
    if not asset_opts: asset_opts = ["Mahindra Manulife Mutual Fund", "UTI Mutual Fund", "Index Fund", "Direct Equity", "-- Type New --"]
    elif "-- Type New --" not in asset_opts: asset_opts.append("-- Type New --")
        
    asset_sel = st.selectbox("Asset / Fund Name", asset_opts, key="inv_asset_sel")
    asset_name = st.text_input("Type New Asset Name", key="inv_new_asset") if asset_sel == "-- Type New --" else asset_sel

    inv_c1, inv_c2 = st.columns(2)
    with inv_c1:
        inv_type = st.selectbox("Transaction Type", ["Buy (SIP)", "Buy (Lumpsum)", "Sell (Redemption)", "Dividend / Yield Payout"], key="inv_type")
        inv_date = st.date_input("Transaction Date", value=st.session_state.locked_date, key="inv_date")
        
    with inv_c2:
        inv_amount = st.number_input("Total Amount (₹)", min_value=0.0, step=500.0, key="inv_amt")
        inv_units = st.number_input("Units / Qty (Optional)", min_value=0.0, step=0.001, format="%.3f", key="inv_units")

    nav_calc = (inv_amount / inv_units) if inv_units > 0 else 0.0
    if nav_calc > 0: st.caption(f"🧮 *Calculated NAV/Price: ₹{nav_calc:.2f}*")

    if st.button("💾 Save & Sync Investment Log", use_container_width=True, type="primary"):
        if asset_name and inv_amount > 0:
            try:
                date_str = inv_date.strftime("%d-%m-%Y")
                time_str = get_ist_now().strftime("%H:%M")
                
                # 1. Log to the Portfolio Tracker
                try: inv_ws = sh.worksheet("INVESTMENT_LOG")
                except gspread.exceptions.WorksheetNotFound:
                    inv_ws = sh.add_worksheet(title="INVESTMENT_LOG", rows="100", cols="6")
                    inv_ws.append_row(["Date", "Asset_Name", "Transaction_Type", "Amount_INR", "Units_Qty", "NAV_or_Price"])
                
                inv_ws.append_row([date_str, asset_name, inv_type, inv_amount, inv_units, round(nav_calc, 2)])
                
                # 2. Automatically sync with Main MONEY_DATA
                money_ws = sh.worksheet("MONEY_DATA")
                if "Buy" in inv_type:
                    money_row = [date_str, time_str, "", inv_amount, "MB", "Salary", "ASSETS", "INVESTMENT", "MUTUAL FUND / STOCK", asset_name, "", "", f"Auto-logged {inv_type}"]
                else:
                    money_row = [date_str, time_str, inv_amount, "", "MB", "", "ASSETS", "INCOME", "MARKET YIELD", asset_name, "", "", f"Auto-logged {inv_type}"]
                
                money_ws.append_row(money_row)
                load_money_data.clear() # Clears cache in the other app
                
                st.success(f"✅ Logged {inv_type} for {asset_name} and synced with Main Money Ledger!")
                st.balloons()
            except Exception as e: st.error(f"Error: {e}")
        else: st.warning("⚠️ Please provide the Asset Name and an Amount greater than zero.")
