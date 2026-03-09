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
        super().__init__(orientation='P', unit='mm', format='A4')
        self.add_font('Bengali', '', 'Bengali.ttf')
        self.set_text_shaping(True) # HarfBuzz engine for correct conjuncts

    def draw_digit_boxes(self, x, y):
        """Draws 10 consecutive 6x6mm boxes for 10-digit phone numbers"""
        box_size = 6 
        for i in range(10):
            self.rect(x + (i * box_size), y, box_size, box_size)

    def draw_single_form(self, x, y, row):
        """Draws exactly one survey form at the given x, y coordinates"""
        self.set_xy(x, y)
        
        # --- School Logo ---
        try:
            self.image('logo.png', x, y, 14) 
        except:
            self.rect(x, y, 14, 14)
            self.set_font('Helvetica', 'B', 6)
            self.text(x + 2, y + 7, "LOGO")

        # --- Header ---
        self.set_font('Helvetica', 'B', 11)
        self.set_xy(x + 16, y)
        self.cell(80, 6, "Bhagyabantapur Primary School (BPS)", ln=True)
        
        self.set_font('Bengali', '', 10)
        self.set_x(x + 16)
        self.cell(80, 6, u"অভিভাবক তথ্য যাচাই ফর্ম", ln=True)
        
        # --- Student Info Table ---
        curr_y = y + 16
        self.rect(x, curr_y, 96, 22)
        
        mobile_val = str(row['Mobile']).split('.')[0] if pd.notna(row['Mobile']) and str(row['Mobile']).strip() != "" else "N/A"
        
        # Left Column Data (English uses Helvetica)
        self.set_font('Helvetica', '', 9)
        self.text(x + 2, curr_y + 6, f"Student: {row['Name']}")
        self.text(x + 2, curr_y + 13, f"Father: {row['Father']}")
        self.text(x + 2, curr_y + 20, f"Mother: {row['Mother']}")
        
        # Right Column Data
        self.text(x + 55, curr_y + 6, f"Class: {row['Class']}")
        self.text(x + 55, curr_y + 13, f"Section: {row['Section']}")
        self.text(x + 55, curr_y + 20, f"Mobile: {mobile_val}")
        
        # --- Questions Section ---
        curr_y += 24
        self.set_xy(x, curr_y)
        self.set_font('Bengali', '', 9)
        
        # INSTRUCTION: Tick the correct box
        self.cell(0, 5, u"সঠিক ঘরে টিক (\u2713) দিন:", ln=True)
        
        # --- MOBILE QUESTION ---
        curr_y = self.get_y()
        self.set_xy(x, curr_y)
        self.cell(44, 6, u"এই মোবাইল নম্বরটি কি সঠিক?")
        
        # Draw "Yes" and Box
        self.set_x(x + 45)
        self.cell(8, 6, u"হ্যাঁ")
        self.rect(x + 52, curr_y + 1.5, 3.5, 3.5) # Drawn Square Box
        
        # Draw "No" and Box
        self.set_x(x + 58)
        self.cell(8, 6, u"না")
        self.rect(x + 64, curr_y + 1.5, 3.5, 3.5) # Drawn Square Box
        
        self.set_xy(x, curr_y + 6)
        self.cell(0, 6, u"সঠিক না হলে, সঠিক নম্বরটি দিন:", ln=True)
        self.draw_digit_boxes(x, self.get_y() + 1)
        
        # --- WHATSAPP QUESTION ---
        curr_y = self.get_y() + 9
        self.set_xy(x, curr_y)
        self.cell(48, 6, u"এটি কি আপনার হোয়াটসঅ্যাপ নম্বর?")
        
        # Draw "Yes" and Box
        self.set_x(x + 49)
        self.cell(8, 6, u"হ্যাঁ")
        self.rect(x + 56, curr_y + 1.5, 3.5, 3.5) # Drawn Square Box
        
        # Draw "No" and Box
        self.set_x(x + 62)
        self.cell(8, 6, u"না")
        self.rect(x + 68, curr_y + 1.5, 3.5, 3.5) # Drawn Square Box
        
        self.set_xy(x, curr_y + 6)
        self.cell(0, 6, u"হোয়াটসঅ্যাপ নম্বর না হলে সেটি দিন:", ln=True)
        self.draw_digit_boxes(x, self.get_y() + 1)
        
        # --- Signature Line ---
        curr_y = self.get_y() + 14
        self.set_font('Helvetica', '', 7)
        self.text(x, curr_y, "______________________")
        self.text(x + 60, curr_y, "______________________")
        
        self.set_font('Bengali', '', 8)
        self.set_xy(x, curr_y + 1)
        self.cell(40, 5, u"অভিভাবকের স্বাক্ষর")
        self.set_xy(x + 60, curr_y + 1)
        self.cell(30, 5, u"তারিখ")

# --- 3. Streamlit UI ---
st.set_page_config(page_title="BPS Survey Generator", layout="wide") # Changed to wide layout for 3 columns
st.title("📋 BPS Guardian Update Form")

if df.empty:
    st.error("⚠️ 'students.csv' not found or is empty.")
    st.stop()

# Ensure missing sections don't break the dropdown
if 'Section' not in df.columns:
    df['Section'] = "A" # Default fallback
df['Section'] = df['Section'].fillna("N/A").astype(str)

# --- Class & Section Selection Logic ---
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    available_classes = sorted(df['Class'].dropna().unique())
    selected_class = st.selectbox("1. Select Class:", available_classes)

# Filter dataframe by selected class
class_df = df[df['Class'] == selected_class]

with col2:
    available_sections = sorted(class_df['Section'].unique())
    selected_section = st.selectbox("2. Select Section:", available_sections)

# Filter dataframe further by selected section
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
if st.button("Generate PDF Forms", type="primary"):
    if not selected_indices:
        st.warning("Please select at least one student.")
    else:
        with st.spinner(f"Generating PDF for {selected_class} - {selected_section}..."):
            pdf = BPS_Survey()
            
            for i in range(0, len(selected_indices), 4):
                pdf.add_page()
                quadrant_coords = [(7, 7), (107, 7), (7, 150), (107, 150)]
                
                for j in range(4):
                    if i + j < len(selected_indices):
                        student_data = df.loc[selected_indices[i + j]]
                        current_coords = quadrant_coords[j]
                        pdf.draw_single_form(current_coords[0], current_coords[1], student_data)
            
            pdf_bytes = bytes(pdf.output())
            
        st.success(f"Successfully generated {len(selected_indices)} forms!")
        
        st.download_button(
            label="⬇️ Download Survey Forms (PDF)", 
            data=pdf_bytes, 
            file_name=f"BPS_Surveys_Class_{selected_class}_Sec_{selected_section}.pdf",
            mime="application/pdf"
        )
