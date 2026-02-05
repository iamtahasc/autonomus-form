from src.parser import PDFParser

def debug_print():
    parser = PDFParser("dummy_form.pdf")
    text_elements, visual_elements = parser.parse_page(0)
    
    print(f"--- Text Elements ({len(text_elements)}) ---")
    for t in text_elements[:10]: # Print first 10
        print(f"'{t.text}' @ {t.bbox} Font: {t.font}")
        
    print(f"\n--- Visual Elements ({len(visual_elements)}) ---")
    for v in visual_elements[:10]:
        print(f"{v.type} @ {v.bbox} Color: {v.stroke_color}")

    parser.close()

if __name__ == "__main__":
    debug_print()
