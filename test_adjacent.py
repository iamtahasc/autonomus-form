import fitz
from src.parser import PDFParser
from src.analyzer import FormAnalyzer

def create_issue_pdf():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 200), "Date: ")
    page.draw_line((90, 205), (150, 205))
    
    page.insert_text((160, 200), "Place: ")
    page.draw_line((200, 205), (300, 205))

    doc.save("test_adjacent.pdf")
    doc.close()

def main():
    create_issue_pdf()
    parser = PDFParser("test_adjacent.pdf")
    text_els, vis_els = parser.parse_page(0)
    for t in text_els: print("TEXT:", t.text, t.bbox)
    for v in vis_els:  print("VIS:", v.type, v.bbox)
    parser.close()
    
    analyzer = FormAnalyzer(text_els, vis_els)
    from src.analyzer import FieldType
    print("Label for Date line:", analyzer._find_label((90, 185, 150, 207), 0, FieldType.TEXT))

if __name__ == "__main__":
    main()
