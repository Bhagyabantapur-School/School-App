import streamlit as st
import pandas as pd
import gspread
import os
import base64
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# 1. Page Configuration
st.set_page_config(page_title="BPS Presentation", page_icon="🏫", layout="wide", initial_sidebar_state="collapsed")

# 2. Sync Logic (Allows Presenter Device and Projector to stay on the same slide)
SYNC_FILE = "sync_slide.txt"

def get_synced_slide():
    if os.path.exists(SYNC_FILE):
        with open(SYNC_FILE, "r") as f:
            try: return int(f.read().strip())
            except: return 0
    return 0

def set_synced_slide(slide_index):
    with open(SYNC_FILE, "w") as f:
        f.write(str(slide_index))

if not os.path.exists(SYNC_FILE):
    set_synced_slide(0)

# Check URL to see if this is the Projector (Audience) or Phone (Presenter)
role = st.query_params.get("role", "presenter")
current_slide = get_synced_slide()

# 3. CSS for Projector vs Presenter
if role == "audience":
    st.markdown("""
    <style>
        #MainMenu, footer, header, [data-testid="stSidebar"] {visibility: hidden; display: none;}
        .block-container {padding-top: 1rem; max-width: 95%;}
        .school-title {font-size: 55px; font-weight: 900; color: #007bff; text-align: center; margin-top: 20px;}
        .subject-title {font-size: 45px; font-weight: bold; color: #333; text-align: center; margin-top: 10px;}
        .slide-topic {font-size: 60px; font-weight: bold; color: #007bff; border-bottom: 4px solid #007bff; padding-bottom: 10px; margin-bottom: 30px;}
        .slide-content {font-size: 40px; line-height: 1.6; color: #222;}
        ul {font-size: 40px; line-height: 1.6;} li {margin-bottom: 15px;}
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
        .notes-box {background-color: #fff3cd; border-left: 5px solid #ffc107; padding: 15px; border-radius: 5px; margin-top: 20px; font-size: 18px;}
        .school-title {font-size: 24px; font-weight: bold; color: #007bff; text-align: center;}
        .slide-topic {font-size: 28px; font-weight: bold; color: #007bff;}
        .slide-content {font-size: 18px; color: #444;}
    </style>
    """, unsafe_allow_html=True)

# 4. Google Sheets Connection
@st.cache_resource
def get_gspread_client():
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), 
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds)

@st.cache_data(ttl=30) 
def load_slides():
    try:
        client = get_gspread_client()
        sheet = client.open("BPS_Database").worksheet("Slides")
        return pd.DataFrame(sheet.get_all_records())
    except gspread.exceptions.WorksheetNotFound:
        st.error("❌ Error: Could not find a worksheet named 'Slides' in BPS_Database.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Google Sheets API Error: {e}")
        return pd.DataFrame()

# Navigation Functions
def next_slide(total):
    if current_slide < total - 1: set_synced_slide(current_slide + 1)

def prev_slide():
    if current_slide > 0: set_synced_slide(current_slide - 1)

# 5. Fetch and Render Data
slides_df = load_slides()

if slides_df.empty:
    st.warning("⚠️ No slide data is loading. Please check the error messages above or ensure your 'Slides' worksheet has data.")
else:
    total_slides = len(slides_df)
    
    if current_slide >= total_slides:
        current_slide = 0
        set_synced_slide(0)
        
    slide_data = slides_df.iloc[current_slide]
    slide_type = str(slide_data.get('Slide_Type', '')).strip()
    subject = str(slide_data.get('Subject', '')).strip()
    topic = str(slide_data.get('Topic', '')).strip()
    content = str(slide_data.get('Content', '')).strip()
    notes = str(slide_data.get('Speaker_Notes', '')).strip()

    main_container = st.container(height=650 if role == "audience" else None, border=False)
    
    with main_container:
        if slide_type.lower() == 'title' or current_slide == 0:
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                # Local Base64 Logo Rendering Logic
                if os.path.exists("logo.png"):
                    with open("logo.png", "rb") as f:
                        img_b64 = base64.b64encode(f.read()).decode()
                    st.markdown(f"""
                    <div style="text-align: center; margin-bottom: 20px;">
                        <img src="data:image/png;base64,{img_b64}" style="max-width: 250px; max-height: 250px; object-fit: contain;">
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown('<div class="school-title">BHAGYABANTAPUR PRIMARY SCHOOL</div>', unsafe_allow_html=True)
                if subject: st.markdown(f'<div class="subject-title">{subject}</div>', unsafe_allow_html=True)
                if topic: st.markdown(f'<div class="subject-title" style="color: #666;">{topic}</div>', unsafe_allow_html=True)
        else:
            if topic: st.markdown(f'<div class="slide-topic">{topic}</div>', unsafe_allow_html=True)
            if content: st.markdown(f'<div class="slide-content">{content}</div>', unsafe_allow_html=True)

    # --- PRESENTER MODE: CONTROLS & NOTES ---
    if role == "presenter":
        st.divider()
        if notes:
            st.markdown(f"**📝 Speaker Notes:**<br><div class='notes-box'>{notes}</div>", unsafe_allow_html=True)
        else:
            st.info("No notes for this slide.")
            
        st.write("") 
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1: st.button("◀️ Prev", on_click=prev_slide, disabled=(current_slide == 0), use_container_width=True)
        with col2: st.markdown(f"<div style='text-align: center; font-weight: bold;'>Slide {current_slide + 1} of {total_slides}</div>", unsafe_allow_html=True)
        with col3: st.button("Next ▶️", on_click=next_slide, args=(total_slides,), disabled=(current_slide == total_slides - 1), use_container_width=True)
        
        with st.sidebar:
            st.success("👨‍🏫 Presenter Mode Active")
            host = st.context.headers.get("Host", "localhost:8501")
            st.markdown("🔗 **Projector Link (Audience View):**")
            st.code(f"http://{host}/?role=audience")

    # --- AUDIENCE MODE: AUTO REFRESH LOOP ---
    if role == "audience":
        st_autorefresh(interval=1000, limit=None, key="audience_sync_refresh")
