import fitz
from src.parser import PDFParser
from src.analyzer import FormAnalyzer

def create_issue_pdf():
    doc = fitz.open()
    page = doc.new_page()
    
    # 1. Comb Boxed Form (multiple square boxes in a row for text)
    page.insert_text((50, 50), "SSN:")
    for i in range(9):
        page.draw_rect(fitz.Rect(90 + i*20, 35, 110 + i*20, 55))
        
    # 2. Standard boxed text field
    page.insert_text((50, 100), "Name:")
    page.draw_rect(fitz.Rect(90, 85, 290, 105))
    
    # 3. Text field overlapping with existing text inside its box
    page.draw_rect(fitz.Rect(50, 140, 250, 170))
    page.insert_text((55, 155), "City:")
    
    # 4. Underline overlapping text
    page.insert_text((50, 200), "Date: ")
    page.draw_line((45, 205), (200, 205))
    
    doc.save("test_issues.pdf")
    doc.close()

def main():
    create_issue_pdf()
    parser = PDFParser("test_issues.pdf")
    text_els, vis_els = parser.parse_page(0)
    parser.close()
    
    analyzer = FormAnalyzer(text_els, vis_els)
    analyzer.detect_candidates()
    analyzer.associate_labels()
    
    fields = analyzer.get_fields()
    print("--- Detected Fields ---")
    for f in fields:
        print(f"Type: {f.type.value}, Name: {f.name}, Label: {f.display_label}, BBox: {f.bbox}")

if __name__ == "__main__":
    main()
