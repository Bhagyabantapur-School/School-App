import streamlit as st
import pandas as pd
from fpdf import FPDF # Requires fpdf2 (pip install fpdf2)

# --- 1. Load Data ---
@st.cache_data
def load_data():
    try:
        return pd.read_csv("students.csv")
    except FileNotFoundError:
        return pd.DataFrame() # Return empty if not found

df = load_data()

# --- 2. PDF Generation Class ---
class BPS_Survey(FPDF):
    def __init__(self):
        # CHANGED: format='A5' instead of 'A4'
        super().__init__(orientation='P', unit='mm', format='A5')
        self.add_font('Bengali', '', 'Bengali.ttf')
        self.set_text_shaping(True) # HarfBuzz engine for correct conjuncts

    def draw_digit_boxes(self, x, y, box_size=8):
        """Draws 10 consecutive boxes for 10-digit phone numbers"""
        for i in range(10):
            self.rect(x + (i * box_size), y, box_size, box_size)

    def draw_single_form(self, row):
        """Draws exactly one survey form taking up the entire A5 page"""
        # We start at standard margins (10, 10)
        x = 10 
        y = 10
        self.set_xy(x, y)
        
        # --- School Logo ---
        try:
            self.image('logo.png', x, y, 20) # Scaled up to 20mm
        except:
            self.rect(x, y, 20, 20)
            self.set_font('Helvetica', 'B', 8)
            self.text(x + 3, y + 10, "LOGO")

        # --- Header ---
        self.set_font('Helvetica', 'B', 14) # Scaled up
        self.set_xy(x + 24, y + 2)
        self.cell(100, 8, "Bhagyabantapur Primary School (BPS)", ln=True)
        
        self.set_font('Bengali', '', 12) # Scaled up
        self.set_x(x + 24)
        self.cell(100, 8, u"অভিভাবক তথ্য যাচাই ফর্ম", ln=True)
        
        # --- Student Info Table ---
        curr_y = 35 # Moved down to account for larger header
        self.rect(x, curr_y, 128, 30) # Wider and taller table
        
        mobile_val = str(row['Mobile']).split('.')[0] if pd.notna(row['Mobile']) and str(row['Mobile']).strip() != "" else "N/A"
        
        # Left Column Data
        self.set_font('Helvetica', '', 11)
        self.text(x + 3, curr_y + 8, f"Student: {row['Name']}")
        self.text(x + 3, curr_y + 18, f"Father: {row['Father']}")
        self.text(x + 3, curr_y + 28, f"Mother: {row['Mother']}")
        
        # Right Column Data
        self.text(x + 70, curr_y + 8, f"Class: {row['Class']}")
        self.text(x + 70, curr_y + 18, f"Section: {row['Section']}")
        self.text(x + 70, curr_y + 28, f"Mobile: {mobile_val}")
        
        # --- Questions Section ---
        curr_y = 75
        self.set_xy(x, curr_y)
        
        # INSTRUCTION: Tick the correct box
        self.set_font('Bengali', '', 11)
        self.cell(26, 6, u"সঠিক ঘরে টিক (")
        self.set_font('ZapfDingbats', '', 10) 
        self.cell(4, 6, "4") # Checkmark
        self.set_font('Bengali', '', 11)
        self.cell(15, 6, u") দিন:")
        self.ln(10)
        
        # --- MOBILE QUESTION ---
        curr_y = self.get_y()
        self.set_xy(x, curr_y)
        self.cell(60, 8, u"এই মোবাইল নম্বরটি কি সঠিক?")
        
        # Draw "Yes" and Box
        self.set_x(x + 65)
        self.cell(10, 8, u"হ্যাঁ")
        self.rect(x + 75, curr_y + 1.5, 5, 5) # 5mm checkbox
        
        # Draw "No" and Box
        self.set_x(x + 85)
        self.cell(10, 8, u"না")
        self.rect(x + 95, curr_y + 1.5, 5, 5) # 5mm checkbox
        
        self.set_xy(x, curr_y + 10)
        self.cell(0, 8, u"সঠিক না হলে, সঠিক নম্বরটি দিন:", ln=True)
        self.draw_digit_boxes(x, self.get_y() + 2, box_size=8) # 8mm writing boxes!
        self.ln(15)
        
        # --- WHATSAPP QUESTION ---
        curr_y = self.get_y()
        self.set_xy(x, curr_y)
        self.cell(65, 8, u"এটি কি আপনার হোয়াটসঅ্যাপ নম্বর?")
        
        # Draw "Yes" and Box
        self.set_x(x + 70)
        self.cell(10, 8, u"হ্যাঁ")
        self.rect(x + 80, curr_y + 1.5, 5, 5) # 5mm checkbox
        
        # Draw "No" and Box
        self.set_x(x + 90)
        self.cell(10, 8, u"না")
        self.rect(x + 100, curr_y + 1.5, 5, 5) # 5mm checkbox
        
        self.set_xy(x, curr_y + 10)
        self.cell(0, 8, u"হোয়াটসঅ্যাপ নম্বর না হলে সেটি দিন:", ln=True)
        self.draw_digit_boxes(x, self.get_y() + 2, box_size=8) # 8mm writing boxes
        
        # --- Signature Line ---
        # Positioned near the bottom of the A5 page
        curr_y = 180 
        self.set_font('Helvetica', '', 10)
        self.text(x, curr_y, "__________________________")
        self.text(x + 75, curr_y, "__________________________")
        
        self.set_font('Bengali', '', 10)
        self.set_xy(x, curr_y + 2)
        self.cell(40, 6, u"অভিভাবকের স্বাক্ষর")
        self.set_xy(x + 75, curr_y + 2)
        self.cell(40, 6, u"তারিখ")

# --- 3. Streamlit UI ---
st.set_page_config(page_title="BPS Survey Generator", layout="wide") 
st.title("📋 BPS Guardian Update Form (A5 Format)")

if df.empty:
    st.error("⚠️ 'students.csv' not found or is empty.")
    st.stop()

# Ensure missing sections don't break the dropdown
if 'Section' not in df.columns:
    df['Section'] = "A" 
df['Section'] = df['Section'].fillna("N/A").astype(str)

# --- Class & Section Selection Logic ---
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    available_classes = sorted(df['Class'].dropna().unique())
    selected_class = st.selectbox("1. Select Class:", available_classes)

class_df = df[df['Class'] == selected_class]

with col2:
    available_sections = sorted(class_df['Section'].unique())
    selected_section = st.selectbox("2. Select Section:", available_sections)

final_df = class_df[class_df['Section'] == selected_section]

with col3:
    st.write(f"**3. Students in {selected_class} - {selected_section}:**")
    select_all = st.checkbox(f"Select All {len(final_df)} Students", value=True)
    
    if select_all:
        selected_indices = final_df.index.tolist()
    else:
        selected_indices = st.multiselect(
            "Choose specific students:", 
            final_df.index, 
            format_func=lambda i: f"{final_df.loc[i]['Name']} (Roll: {final_df.loc[i].get('Roll', 'N/A')})"
        )

# --- Generation Button ---
if st.button("Generate A5 PDF Forms", type="primary"):
    if not selected_indices:
        st.warning("Please select at least one student.")
    else:
        with st.spinner(f"Generating A5 PDF for {selected_class} - {selected_section}..."):
            pdf = BPS_Survey()
            
            # CHANGED: 1 Form = 1 Page
            for idx in selected_indices:
                pdf.add_page()
                student_data = df.loc[idx]
                # We no longer need coordinate arrays; it uses standard margins inside the class
                pdf.draw_single_form(student_data)
            
            pdf_bytes = bytes(pdf.output())
            
        st.success(f"Successfully generated {len(selected_indices)} A5 pages!")
        
        st.download_button(
            label="⬇️ Download Survey Forms (PDF)", 
            data=pdf_bytes, 
            file_name=f"BPS_Surveys_A5_Class_{selected_class}_Sec_{selected_section}.pdf",
            mime="application/pdf"
        )
