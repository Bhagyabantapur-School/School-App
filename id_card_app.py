def generate_pdf(students_list):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    
    x_start, y_start = 10, 10
    card_w, card_h = 86, 54
    gap = 8  # Reduced gap slightly to fit better on A4
    
    col, row = 0, 0
    
    for student in students_list:
        x = x_start + (col * (card_w + gap))
        y = y_start + (row * (card_h + gap))
        
        # 1. Card Border
        pdf.set_draw_color(0, 0, 0)
        pdf.rect(x, y, card_w, card_h)
        
        # 2. Header
        pdf.set_fill_color(0, 123, 255)
        pdf.rect(x, y, card_w, 11, 'F')
        pdf.set_font("Arial", 'B', 10)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(x, y + 1.5)
        pdf.cell(card_w, 5, "BHAGYABANTAPUR PRIMARY SCHOOL", 0, 1, 'C')
        pdf.set_font("Arial", '', 6)
        pdf.set_xy(x, y + 6.5)
        pdf.cell(card_w, 3, "ID CARD - SESSION 2026", 0, 1, 'C')
        
        # 3. Photo Placeholder
        pdf.set_draw_color(200, 200, 200)
        pdf.rect(x + 3, y + 14, 18, 22) 
        pdf.set_text_color(150, 150, 150)
        pdf.set_font("Arial", '', 5)
        pdf.set_xy(x + 3, y + 22)
        pdf.cell(18, 5, "PHOTO", 0, 0, 'C')
        
        # 4. Student Details
        pdf.set_text_color(0, 0, 0)
        detail_x = x + 24
        curr_y = y + 14
        line_h = 4
        
        # Name (Bold & Slightly Larger)
        pdf.set_font("Arial", 'B', 9)
        pdf.set_xy(detail_x, curr_y)
        pdf.cell(50, line_h, f"{student['Name']}".upper()[:25], 0, 1)
        curr_y += 4.5

        # Small font for the rest of the details
        pdf.set_font("Arial", '', 7)
        
        # Row 1: Father
        pdf.set_xy(detail_x, curr_y)
        pdf.cell(50, line_h, f"Father: {student.get('Father', '')}", 0, 1)
        curr_y += line_h
        
        # Row 2: Class & Section
        pdf.set_xy(detail_x, curr_y)
        pdf.cell(50, line_h, f"Class: {student['Class']} | Sec: {student.get('Section', 'A')}", 0, 1)
        curr_y += line_h
        
        # Row 3: Roll & Gender
        pdf.set_xy(detail_x, curr_y)
        pdf.cell(50, line_h, f"Roll: {student['Roll']} | Sex: {student.get('Gender', '')}", 0, 1)
        curr_y += line_h
        
        # Row 4: DOB & Blood Group
        pdf.set_xy(detail_x, curr_y)
        pdf.cell(50, line_h, f"DOB: {student.get('DOB', '')} | Blood: {student.get('BloodGroup', 'N/A')}", 0, 1)
        curr_y += line_h
        
        # Row 5: Mobile
        pdf.set_xy(detail_x, curr_y)
        pdf.set_font("Arial", 'B', 7)
        pdf.cell(50, line_h, f"Mob: {student.get('Mobile', '')}", 0, 1)

        # 5. QR Code (Repositioned to bottom right)
        qr_data = f"Name:{student['Name']}|Roll:{student['Roll']}|Mob:{student.get('Mobile', '')}"
        qr = qrcode.make(qr_data)
        qr_path = tempfile.mktemp(suffix=".png")
        qr.save(qr_path)
        pdf.image(qr_path, x=x + 68, y=y + 35, w=15, h=15)
        
        # 6. Signature Area
        pdf.set_font("Arial", 'I', 5)
        pdf.set_xy(x, y + 50)
        pdf.cell(card_w - 5, 3, "Head Teacher Signature", 0, 0, 'R')
        
        # Grid Logic
        col += 1
        if col >= 2:
            col = 0
            row += 1
        if row >= 5:
            pdf.add_page()
            row = 0
            col = 0
            
    return pdf.output(dest='S').encode('latin-1')
