import streamlit as st
import pandas as pd
from fpdf import FPDF 

# 1. Load Data
df = pd.read_csv("students.csv")

class BPS_Survey(FPDF):
    def __init__(self):
        # Use 'P' for Portrait, 'mm' for millimeters, 'A4' size
        super().__init__(orientation='P', unit='mm', format='A4')
        
        # STEP 1: Load Noto Serif Bengali (Static version preferred)
        # Ensure the .ttf file is named 'Bengali.ttf' in your folder
        self.add_font('Bengali', '', 'Bengali.ttf')
        self.set_font('Bengali', '', 10)

    def draw_digit_boxes(self, x, y):
        box_size = 6 
        for i in range(10):
            self.rect(x + (i * box_size), y, box_size, box_size)

    def draw_single_form(self, x, y, row):
        # fpdf2 uses a slightly different positioning system for Unicode
        self.set_xy(x, y)
        
        # --- Logo ---
        try:
            self.image('logo.png', x, y, 14) 
        except:
            self.rect(x, y, 14, 14)

        # --- Header ---
        self.set_font('Helvetica', 'B', 11) # Use standard font for English
        self.set_xy(x + 16, y)
        self.cell(80, 6, "Bhagyabantapur Primary School (BPS)", ln=True)
        
        self.set_font('Bengali', '', 10)
        self.set_x(x + 16)
        # Real Bengali Script
        self.cell(80, 6, u"অভিভাবক তথ্য যাচাই ফর্ম", ln=True)
        
        # --- Student Info Table ---
        curr_y = y + 18
        self.rect(x, curr_y, 96, 22) 
        
        # Table Content
        self.set_font('Bengali', '', 9)
        # We use text() for precise quadrant placement
        self.text(x + 2, curr_y + 6, f"Student: {row['Name']}")
        self.text(x + 55, curr_y + 6, f"Class: {row['Class']}")
        self.text(x + 2, curr_y + 12, f"Father: {row['Father']}")
        self.text(x + 55, curr_y + 12, f"Section: {row['Section']}")
        self.text(x + 2, curr_y + 18, f"Mother: {row['Mother']}")
        self.text(x + 55, curr_y + 18, f"Mobile: {str(row['Mobile']).split('.')[0]}")
        
        # --- Questions Section ---
        self.set_y(curr_y + 26)
        
        # Mobile Question
        self.cell(0, 6, u"এই মোবাইল নম্বরটি কি সঠিক?  হ্যাঁ [   ]  না [   ]", ln=True)
        self.ln(2)
        self.cell(0, 6, u"সঠিক না হলে, সঠিক নম্বরটি দিন:", ln=True)
        self.draw_digit_boxes(x, self.get_y() + 1)
        
        # WhatsApp Question
        self.set_y(self.get_y() + 12)
        self.cell(0, 6, u"এটি কি আপনার হোয়াটসঅ্যাপ নম্বর?  হ্যাঁ [   ]  না [   ]", ln=True)
        self.ln(2)
        self.cell(0, 6, u"হোয়াটসঅ্যাপ নম্বর না হলে সেটি দিন:", ln=True)
        self.draw_digit_boxes(x, self.get_y() + 1)
        
        # --- Signatures ---
        self.set_y(self.get_y() + 15)
        self.set_font('Helvetica', '', 7)
        self.text(x, self.get_y(), "______________________")
        self.text(x + 60, self.get_y(), "______________________")
        self.set_font('Bengali', '', 8)
        self.text(x, self.get_y() + 4, u"অভিভাবকের স্বাক্ষর")
        self.text(x + 60, self.get_y() + 4, u"তারিখ")

# --- Streamlit UI ---
st.title("📋 BPS Guardian Update Form (4-per-page)")

selected_indices = st.multiselect("Select Students:", df.index, format_func=lambda x: f"{df.iloc[x]['Name']}")

if st.button("Generate PDF"):
    if not selected_indices:
        st.error("Select students first!")
    else:
        # fpdf2 handles the context better
        pdf = BPS_Survey()
        for i in range(0, len(selected_indices), 4):
            pdf.add_page()
            # 4 Corners of A4: Top-Left, Top-Right, Bottom-Left, Bottom-Right
            coords = [(7, 7), (107, 7), (7, 150), (107, 150)]
            for j, pos in enumerate(coords):
                if i + j < len(selected_indices):
                    pdf.draw_single_form(pos[0], pos[1], df.iloc[selected_indices[i+j]])
        
        # fpdf2 output is slightly different
        pdf_output = pdf.output()
        st.download_button("⬇️ Download PDF", pdf_output, "BPS_Update_Forms.pdf")
