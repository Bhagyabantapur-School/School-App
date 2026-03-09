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
        # A5 Format (148mm x 210mm), 1 form per page
        super().__init__(orientation='P', unit='mm', format='A5')
        self.add_font('Bengali', '', 'Bengali.ttf')
        self.set_text_shaping(True) # HarfBuzz engine for correct conjuncts
        
        # Prevent FPDF from secretly pushing text to a second page
        self.set_auto_page_break(auto=False)

    def draw_digit_boxes(self, x, y, box_size=8):
        """Draws 10 consecutive boxes for 10-digit phone numbers"""
        for i in range(10):
            self.rect(x + (i * box_size), y, box_size, box_size)

    def draw_single_form(self, row):
        """Draws exactly one survey form taking up the entire A5 page"""
        x = 10 
        y = 10
        self.set_xy(x, y)
        
        # --- School Logo ---
        try:
            self.image('logo.png', x, y, 20) 
        except:
            self.rect(x, y, 20, 20)
            self.set_font('Helvetica', 'B', 8)
            self.text(x + 3, y + 10, "LOGO")

        # --- Header ---
        self.set_font('Helvetica', 'B', 14) 
        self.set_xy(x + 24, y + 2)
        self.cell(100, 8, "Bhagyabantapur Primary School (BPS)", ln=True)
        
        self.set_font('Bengali', '', 12) 
        self.set_x(x + 24)
        self.cell(100, 8, u"অভিভাবক তথ্য যাচাই ফর্ম", ln=True)
        
        # --- Student Info Table ---
        curr_y = 35 
        self.rect(x, curr_y, 128, 36) 
        
        # Safe fetch for Mobile
        mobile_val = str(row['Mobile']).split('.')[0] if pd.notna(row['Mobile']) and str(row['Mobile']).strip() != "" else "N/A"
        
        # THE FIX: Format DOB to DD-MM-YYYY safely
        dob_val = "N/A"
        if 'DOB' in row and pd.notna(row['DOB']) and str(row['DOB']).strip() != "":
            try:
                # Parses the date and converts it to the requested format
                parsed_date = pd.to_datetime(row['DOB'], dayfirst=True)
                dob_val = parsed_date.strftime('%d-%m-%Y')
            except:
                # Fallback if the date format in the CSV is completely unrecognizable
                dob_val = str(row['DOB'])
        
        self.set_font('Helvetica', '', 11)
        
        # Row 1
        self.text(x + 3, curr_y + 7, f"Student: {row['Name']}")
        self.text(x + 70, curr_y + 7, f"Class: {row['Class']}")
        # Row 2
        self.text(x + 3, curr_y + 15, f"Father: {row['Father']}")
        self.text(x + 70, curr_y + 15, f"Section: {row['Section']}")
        # Row 3
        self.text(x + 3, curr_y + 23, f"Mother: {row['Mother']}")
        self.text(x + 70, curr_y + 23, f"DOB: {dob_val}")
        # Row 4
        self.text(x + 3, curr_y + 31, f"Mobile: {mobile_val}")
        
        # --- Questions Section ---
        curr_y = 78
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
        self.rect(x + 75, curr_y + 1.5, 5, 5) 
        
        # Draw "No" and Box
        self.set_x(x + 85)
        self.cell(10, 8, u"না")
        self.rect(x + 95, curr_y + 1.5, 5, 5) 
        
        self.set_xy(x, curr_y + 10)
        self.cell(0, 8, u"সঠিক না হলে, সঠিক নম্বরটি দিন:", ln=True)
        self.draw_digit_boxes(x, self.get_y() + 2, box_size=8)
        self.ln(15)
        
        # --- WHATSAPP QUESTION ---
        curr_y = self.get_y()
        self.set_xy(x, curr_y)
        self.cell(65, 8, u"এটি কি আপনার হোয়াটসঅ্যাপ নম্বর?")
        
        # Draw "Yes" and Box
        self.set_x(x + 70)
        self.cell(10, 8, u"হ্যাঁ")
        self.rect(x + 80, curr_y + 1.5, 5, 5) 
        
        # Draw "No" and Box
        self.set_x(x + 90)
        self.cell(10, 8, u"না")
        self.rect(x + 100, curr_y + 1.5, 5, 5) 
        
        self.set_xy(x, curr_y + 10)
        self.cell(0, 8, u"হোয়াটসঅ্যাপ নম্বর না হলে সেটি দিন:", ln=True)
        self.draw_digit_boxes(x, self.get_y() + 2, box_size=8)
        self.ln(15)
        
        # --- SC/ST/OBC QUESTION ---
        curr_y = self.get_y()
        self.set_xy(x, curr_y)
        self.cell(82, 8, u"ছাত্র/ছাত্রীর কি SC / ST / OBC সার্টিফিকেট আছে?")
        
        # Draw "Yes" and Box
        self.set_x(x + 85)
        self.cell(10, 8, u"হ্যাঁ")
        self.rect(x + 95, curr_y + 1.5, 5, 5) 
        
        # Draw "No" and Box
        self.set_x(x + 105)
        self.cell(10, 8, u"না")
        self.rect(x + 115, curr_y + 1.5, 5, 5) 
        
        self.set_xy(x, curr_y + 10)
        self.cell(0, 8, u"হ্যাঁ হলে, সার্টিফিকেটের জেরক্স (Xerox) কপি জমা দিন।", ln=True)
        
        # --- Signature Line ---
        curr_y = self.get_y() + 15 
        
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
if st.button("Generate PDF Forms (A5)", type="primary"):
    if not selected_indices:
        st.warning("Please select at least one student.")
    else:
        with st.spinner(f"Generating PDF for {selected_class} - {selected_section}..."):
            pdf = BPS_Survey()
            
            # 1 Form per A5 Page
            for idx in selected_indices:
                pdf.add_page()
                student_data = df.loc[idx]
                pdf.draw_single_form(student_data)
            
            pdf_bytes = bytes(pdf.output())
            
        st.success(f"Successfully generated {len(selected_indices)} A5 pages!")
        
        st.download_button(
            label="⬇️ Download Survey Forms (PDF)", 
            data=pdf_bytes, 
            file_name=f"BPS_Surveys_Class_{selected_class}_Sec_{selected_section}.pdf",
            mime="application/pdf"
        )
