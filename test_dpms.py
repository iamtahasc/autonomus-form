import sys
import fitz

def main():
    doc = fitz.open('uploads/2c1d8422-166a-4752-8d3c-f5daa99ed217_DPMS_INDIVIDUAL_BOOK__Final_17-03-2026_low-2.pdf')
    page = doc.load_page(5)
    blocks = page.get_text("dict")["blocks"]
    
    print(f"Total blocks on page 5: {len(blocks)}")
    for i, b in enumerate(blocks):
        print(f"Block {i}: type={b.get('type')}, bbox={b.get('bbox')}")
        
    drawings = page.get_drawings()
    print(f"Total drawings: {len(drawings)}")

if __name__ == "__main__":
    main()
