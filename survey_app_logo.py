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
        # Set format to A4, unit to millimeters, orientation to Portrait
        super().__init__(orientation='P', unit='mm', format='A4')
        
        # Load the Bengali font. 
        # Make sure 'Bengali.ttf' is in the same folder as this script.
        # NOTE: There is NO add_font('Helvetica') here, to prevent the ValueError.
        self.add_font('Bengali', '', 'Bengali.ttf')

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
            # Assumes logo.png is in the same directory
            self.image('logo.png', x, y, 14) 
        except:
            # Fallback square if logo.png is missing
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
        self.rect(x, curr_y, 96, 22) # Outer border for the details box
        
        self.set_font('Bengali', '', 9)
        
        # Clean mobile number (removes decimals, handles blanks)
        mobile_val = str(row['Mobile']).split('.')[0] if pd.notna(row['Mobile']) and str(row['Mobile']).strip() != "" else "N/A"
        
        # Left Column Data
        self.text(x + 2, curr_y + 6, f"Student: {row['Name']}")
        self.text(x + 2, curr_y + 13, f"Father: {row['Father']}")
        self.text(x + 2, curr_y + 20, f"Mother: {row['Mother']}")
        
        # Right Column Data
        self.text(x + 55, curr_y + 6, f"Class: {row['Class']}")
        self.text(x + 55, curr_y + 13, f"Section: {row['Section']}")
        self.text(x + 55, curr_y + 20, f"Mobile: {mobile_val}")
        
        # --- Questions Section ---
        curr_y += 26
        self.set_xy(x, curr_y)
        self.set_font('Bengali', '', 9)
        
        # Mobile Question
        self.cell(0, 6, u"এই মোবাইল নম্বরটি কি সঠিক?  হ্যাঁ [   ]  না [   ]", ln=True)
        self.set_x(x)
        self.cell(0, 6, u"সঠিক না হলে, সঠিক নম্বরটি দিন:", ln=True)
        self.draw_digit_boxes(x, self.get_y() + 1)
        
        # WhatsApp Question
        curr_y = self.get_y() + 10
        self.set_xy(x, curr_y)
        self.cell(0, 6, u"এটি কি আপনার হোয়াটসঅ্যাপ নম্বর?  হ্যাঁ [   ]  না [   ]", ln=True)
        self.set_x(x)
        self.cell(0, 6, u"হোয়াটসঅ্যাপ নম্বর না হলে সেটি দিন:", ln=True)
        self.draw_digit_boxes(x, self.get_y() + 1)
        
        # --- Signature Line ---
        curr_y = self.get_y() + 14
        self.set_font('Helvetica', '', 7)
        self.text(x, curr_y, "______________________")
        self.text(x + 60, curr_y, "______________________")
        
        self.set_font('Bengali', '', 8)
        self.text(x, curr_y + 4, u"অভিভাবকের স্বাক্ষর")
        self.text(x + 60, curr_y + 4, u"তারিখ")

# --- 3. Streamlit UI ---
st.set_page_config(page_title="BPS Survey Generator", layout="centered")
st.title("📋 BPS Guardian Update Form (4-in-1)")

if df.empty:
    st.error("⚠️ 'students.csv' not found or is empty. Please ensure it is in the same folder.")
    st.stop()

# Select All functionality
select_all = st.checkbox("Select All Students")

if select_all:
    selected_indices = df.index.tolist()
else:
    selected_indices = st.multiselect(
        "Select Students manually:", 
        df.index, 
        format_func=lambda i: f"{df.iloc[i]['Name']} (Class {df.iloc[i]['Class']})"
    )

if st.button("Generate PDF Forms", type="primary"):
    if not selected_indices:
        st.warning("Please select at least one student from the list.")
    else:
        with st.spinner("Generating PDF..."):
            pdf = BPS_Survey()
            
            # Process in chunks of 4 to fit 4 quadrants on an A4 sheet
            for i in range(0, len(selected_indices), 4):
                pdf.add_page()
                
                # Coordinates for Top-Left, Top-Right, Bottom-Left, Bottom-Right
                quadrant_coords = [(7, 7), (107, 7), (7, 150), (107, 150)]
                
                for j in range(4):
                    if i + j < len(selected_indices):
                        student_data = df.iloc[selected_indices[i + j]]
                        current_coords = quadrant_coords[j]
                        pdf.draw_single_form(current_coords[0], current_coords[1], student_data)
            
            # Convert to pure bytes to prevent Streamlit download error
            pdf_bytes = bytes(pdf.output())
            
        st.success("PDF generated successfully!")
        
        st.download_button(
            label="⬇️ Download Survey Forms (PDF)", 
            data=pdf_bytes, 
            file_name="BPS_Guardian_Surveys.pdf",
            mime="application/pdf"
        )
