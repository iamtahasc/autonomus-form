from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

def create_non_fillable_form(filename):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(1 * inch, 10 * inch, "Employee Onboarding Form")

    # Section 1: Personal Information
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1 * inch, 9.5 * inch, "1. Personal Information")
    
    c.setFont("Helvetica", 10)
    
    # Field: Full Name (Underline style)
    c.drawString(1 * inch, 9 * inch, "Full Name:")
    c.line(2 * inch, 9 * inch - 2, 5 * inch, 9 * inch - 2)
    
    # Field: Date of Birth (Box style)
    c.drawString(5.5 * inch, 9 * inch, "Date of Birth:")
    c.rect(6.5 * inch, 8.85 * inch, 1.5 * inch, 20, fill=0)

    # Field: Address (Multi-line / large gap)
    c.drawString(1 * inch, 8.5 * inch, "Current Address:")
    c.line(2.2 * inch, 8.5 * inch - 2, 7.5 * inch, 8.5 * inch - 2)
    # Duplicate label to test unique naming
    c.drawString(1 * inch, 8.2 * inch, "Current Address:")
    c.line(2.2 * inch, 8.2 * inch - 2, 7.5 * inch, 8.2 * inch - 2)

    # Section 2: Preferences (Checkboxes and Radios)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1 * inch, 7.5 * inch, "2. Preferences")
    c.setFont("Helvetica", 10)

    # Checkboxes: Department
    c.drawString(1 * inch, 7.0 * inch, "Department:")
    
    c.rect(2 * inch, 7.0 * inch, 12, 12, fill=0)
    c.drawString(2.3 * inch, 7.0 * inch + 2, "Engineering")
    
    c.rect(3.5 * inch, 7.0 * inch, 12, 12, fill=0)
    c.drawString(3.8 * inch, 7.0 * inch + 2, "Marketing")
    
    c.rect(5.0 * inch, 7.0 * inch, 12, 12, fill=0)
    c.drawString(5.3 * inch, 7.0 * inch + 2, "Sales")

    # Radio-like (Circles): Employment Type
    c.drawString(1 * inch, 6.5 * inch, "Type:")
    
    c.circle(2 * inch + 6, 6.5 * inch + 6, 6, fill=0)
    c.drawString(2.3 * inch, 6.5 * inch + 2, "Full-time")
    
    c.circle(3.5 * inch + 6, 6.5 * inch + 6, 6, fill=0)
    c.drawString(3.8 * inch, 6.5 * inch + 2, "Part-time")

    # Manually drawn checkbox (4 lines)
    c.drawString(1 * inch, 6.0 * inch, "Terms:")
    x, y, s = 2 * inch, 6.0 * inch, 12
    c.line(x, y, x+s, y) # bottom
    c.line(x+s, y, x+s, y+s) # right
    c.line(x+s, y+s, x, y+s) # top
    c.line(x, y+s, x, y) # left
    c.drawString(2.3 * inch, 6.0 * inch + 2, "I agree")

    # Test Case: Overlap (Rect + Lines) to verify Deduplication
    # Some PDFs draw a box AND lines.
    c.drawString(4.0 * inch, 6.0 * inch, "Overlap Check:")
    ox, oy = 5.5 * inch, 6.0 * inch
    c.rect(ox, oy, 12, 12, fill=0) # Rect
    c.line(ox, oy, ox+12, oy) # Lines on top
    c.line(ox, oy, ox, oy+12)
    
    # Test Case: Orphan Field (Should be ignored)
    c.line(1 * inch, 2 * inch, 3 * inch, 2 * inch) # Random line at bottom
    
    # Test Case: Right-side Label
    c.line(6.0 * inch, 6.0 * inch, 6.5 * inch, 6.0 * inch)
    c.drawString(6.6 * inch, 6.0 * inch + 2, "(Initials)")
    
    # Test Case: Radio Group (Gender)
    # Group Label: Gender
    # Options: Male, Female
    c.drawString(1 * inch, 3.0 * inch, "Gender:")
    c.circle(2 * inch, 3.0 * inch + 4, 6, fill=0)
    c.drawString(2.3 * inch, 3.0 * inch, "Male")
    
    c.circle(3.5 * inch, 3.0 * inch + 4, 6, fill=0)
    c.drawString(3.8 * inch, 3.0 * inch, "Female")

    # Test Case: Dotted Line (Email)
    c.drawString(1 * inch, 2.5 * inch, "Email:")
    # Draw dotted line (segments)
    dx = 2 * inch
    dy = 2.5 * inch
    for _ in range(20):
        c.line(dx, dy, dx+3, dy)
        dx += 6
    # Label on right too? No, detected by left.
    
    # Test Case: Box Text Field (Notes)
    c.drawString(1 * inch, 2.0 * inch, "Notes:")
    c.rect(2 * inch, 1.9 * inch, 100, 20, fill=0)

    # Section 3: Signature
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1 * inch, 5.0 * inch, "3. Authorization")
    
    c.setFont("Helvetica", 10)
    c.drawString(1 * inch, 4.5 * inch, "Signature:")
    c.line(2 * inch, 4.5 * inch - 2, 5 * inch, 4.5 * inch - 2)
    
    c.drawString(5.5 * inch, 4.5 * inch, "Date:")
    c.line(6.0 * inch, 4.5 * inch - 2, 7.5 * inch, 4.5 * inch - 2) # line for date

    # 9. Small Text Box (Potential False Positive for Checkbox)
    c.drawString(72, 600, "Age:")
    c.rect(100, 595, 30, 15) # 30x15 box - might be confused with checkbox if logic is loose
    
    # 10. Image Placeholder
    c.drawString(72, 550, "Photo:")
    # 6. Comb Field (Series of small boxes)
    c.drawString(72, 400, "Account ID:")
    x_comb = 150
    for i in range(5):
        c.rect(x_comb + (i * 25), 390, 20, 20) # 5 boxes, 20x20, 5gap
        
    # 7. Multi-line Text Field (Tall box)
    c.drawString(72, 100, "Comments:")
    c.rect(144, 50, 200, 60) # 200x60 (tall)

    # 8. Grid / Table (Label Above)
    c.drawString(400, 400, "Item")
    c.drawString(450, 400, "Qty")
    c.drawString(500, 400, "Price")
    
    # Row 1
    c.rect(400, 380, 15, 15) # Checkbox without label
    c.rect(450, 380, 40, 15)
    c.rect(500, 380, 40, 15)
    
    # Row 2
    c.rect(400, 360, 15, 15) # Checkbox without label
    c.rect(450, 360, 40, 15)
    c.rect(500, 360, 40, 15)
    c.rect(72, 440, 100, 100) # 100x100 box
    
    # 11. Signature Box
    c.drawString(300, 550, "Authorized Signature:")
    c.rect(300, 500, 200, 40) # Box processing for signature
    
    c.save()
    print(f"Created {filename}")

if __name__ == "__main__":
    create_non_fillable_form("dummy_form.pdf")
