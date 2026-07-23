import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# 1. Page Configuration (Wide layout is best for projectors)
st.set_page_config(page_title="BPS Presentation Deck", page_icon="🏫", layout="wide", initial_sidebar_state="collapsed")

# 2. Inject CSS for Projector Optimization
# This hides the Streamlit top menu and footer, and makes the text massive for the projector.
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {padding-top: 1rem; max-width: 95%;}
    
    .school-title {font-size: 55px; font-weight: 900; color: #007bff; text-align: center; margin-top: 20px;}
    .subject-title {font-size: 45px; font-weight: bold; color: #333; text-align: center; margin-top: 10px;}
    
    .slide-topic {font-size: 60px; font-weight: bold; color: #007bff; border-bottom: 4px solid #007bff; padding-bottom: 10px; margin-bottom: 30px;}
    .slide-content {font-size: 40px; line-height: 1.6; color: #222;}
    
    /* Make standard Streamlit markdown lists larger */
    ul {font-size: 40px; line-height: 1.6;}
    li {margin-bottom: 15px;}
</style>
""", unsafe_allow_html=True)

# 3. Google Sheets Connection (Re-using your existing BPS database logic)
@st.cache_resource
def get_gspread_client():
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), 
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds)

@st.cache_data(ttl=60) # Caches data for 60 seconds so you can update slides on the fly
def load_slides():
    try:
        client = get_gspread_client()
        sheet = client.open("BPS_Database").worksheet("Slides")
        df = pd.DataFrame(sheet.get_all_records())
        return df
    except Exception as e:
        st.error(f"⚠️ Could not load slides from Google Sheets: {e}")
        return pd.DataFrame()

# 4. Initialize Session State for Navigation
if 'current_slide' not in st.session_state:
    st.session_state.current_slide = 0

def next_slide(total):
    if st.session_state.current_slide < total - 1:
        st.session_state.current_slide += 1

def prev_slide():
    if st.session_state.current_slide > 0:
        st.session_state.current_slide -= 1

# 5. Fetch Data and Render
slides_df = load_slides()

if slides_df.empty:
    st.warning("No slide data found. Please add data to the 'Slides' worksheet.")
else:
    total_slides = len(slides_df)
    slide_data = slides_df.iloc[st.session_state.current_slide]
    
    slide_type = str(slide_data.get('Slide_Type', '')).strip()
    subject = str(slide_data.get('Subject', '')).strip()
    topic = str(slide_data.get('Topic', '')).strip()
    content = str(slide_data.get('Content', '')).strip()

    # Create a tall empty container to push content to the center of the projector screen
    main_container = st.container(height=650, border=False)
    
    with main_container:
        if slide_type.lower() == 'title' or st.session_state.current_slide == 0:
            # --- RENDER TITLE SLIDE ---
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                # IMPORTANT: Replace this URL with the RAW GitHub link to your logo
                # Example: "https://raw.githubusercontent.com/YourUser/YourRepo/main/logo.png"
                github_logo_url = "https://raw.githubusercontent.com/replace-this-with-your-raw-github-logo-link.png" 
                
                try:
                    st.image(github_logo_url, use_column_width=True)
                except:
                    st.info("ℹ️ Replace `github_logo_url` in the code with your actual GitHub Raw image link.")
                
                st.markdown('<div class="school-title">BHAGYABANTAPUR PRIMARY SCHOOL</div>', unsafe_allow_html=True)
                if subject:
                    st.markdown(f'<div class="subject-title">{subject}</div>', unsafe_allow_html=True)
                if topic:
                    st.markdown(f'<div class="subject-title" style="color: #666; font-size: 35px;">{topic}</div>', unsafe_allow_html=True)
                    
        else:
            # --- RENDER CONTENT SLIDE ---
            if topic:
                st.markdown(f'<div class="slide-topic">{topic}</div>', unsafe_allow_html=True)
            if content:
                # Using standard markdown so you can use bold (**text**) or bullets (-) in your Google Sheet
                st.markdown(f'<div class="slide-content">{content}</div>', unsafe_allow_html=True)

    st.markdown("<hr style='margin-top: 50px; margin-bottom: 20px;'>", unsafe_allow_html=True)

    # 6. Navigation Controls at the Bottom
    nav_col1, nav_col2, nav_col3 = st.columns([1, 6, 1])
    
    with nav_col1:
        st.button("◀️ Previous", on_click=prev_slide, disabled=(st.session_state.current_slide == 0), use_container_width=True)
        
    with nav_col2:
        st.markdown(f"<div style='text-align: center; font-size: 24px; color: gray; margin-top: 5px;'>Slide {st.session_state.current_slide + 1} of {total_slides}</div>", unsafe_allow_html=True)
        
    with nav_col3:
        st.button("Next ▶️", on_click=next_slide, args=(total_slides,), disabled=(st.session_state.current_slide == total_slides - 1), use_container_width=True)
