import fitz  # PyMuPDF
from dataclasses import dataclass
from typing import List, Optional, Tuple

@dataclass
class TextElement:
    text: str
    bbox: Tuple[float, float, float, float]  # x0, y0, x1, y1
    size: float
    font: str
    page_num: int

@dataclass
class VisualElement:
    type: str  # 'line', 'rect', 'curve'
    bbox: Tuple[float, float, float, float]
    stroke_color: Tuple
    fill_color: Optional[Tuple]
    line_width: float
    page_num: int

class PDFParser:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)

    def parse_page(self, page_num: int) -> Tuple[List[TextElement], List[VisualElement]]:
        page = self.doc.load_page(page_num)
        
        # 1. Extract Text
        text_elements = []
        # get_text("dict") provides detailed font info
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block["type"] == 0:  # Text block
                for line in block["lines"]:
                    for span in line["spans"]:
                        # span: size, flags, font, color, ascender, descender, text, origin, bbox
                        text = span["text"].strip()
                        if text:
                            text_elements.append(TextElement(
                                text=text,
                                bbox=tuple(span["bbox"]),
                                size=span["size"],
                                font=span["font"],
                                page_num=page_num
                            ))

        # 2. Extract Drawings (Lines, Rects)
        visual_elements = []
        drawings = page.get_drawings()
        for draw in drawings:
            # draw keys: items, rect, type, color, fill, width, etc.
            # items list of (type, p1, p2, ...)
            
            # Simple heuristic: treat the bounding box of the drawing as the significant element
            # But specific lines matter (e.g. underline).
            # "items": [("l", p1, p2), ("re", rect), ...]
            
            # We want to flatten this into usable primitives
            # For this simple implementation, let's look at the drawing rect, 
            has_lines = any(x[0] == "l" for x in draw["items"])
            has_curves = any(x[0] == "c" for x in draw["items"])
            
            # Always emit the outer bbox as a "path" candidate (covers Checkboxes, Radios, Images, Boxes)
            # Determine type for proper Analyzer classification
            v_type = "path"
            if has_curves: v_type = "curve"
            
            if has_lines or has_curves:
                visual_elements.append(VisualElement(
                    type=v_type,
                    bbox=(draw["rect"].x0, draw["rect"].y0, draw["rect"].x1, draw["rect"].y1),
                    stroke_color=draw["color"],
                    fill_color=draw["fill"],
                    line_width=draw["width"] or 1.0,
                    page_num=page_num
                ))
                
            # Also emit individual items (lines, rects) for detailed analysis (e.g. underlines)
            for item in draw["items"]:
                if item[0] == "l": # line
                    p1, p2 = item[1], item[2]
                    # Create a bbox for the line
                    x0 = min(p1.x, p2.x)
                    y0 = min(p1.y, p2.y)
                    x1 = max(p1.x, p2.x)
                    y1 = max(p1.y, p2.y)

                    if abs(x1 - x0) < 0.1: x1 += draw["width"] or 1
                    if abs(y1 - y0) < 0.1: y1 += draw["width"] or 1
                    
                    visual_elements.append(VisualElement(
                        type="line",
                        bbox=(x0, y0, x1, y1),
                        stroke_color=draw["color"],
                        fill_color=None,
                        line_width=draw["width"],
                        page_num=page_num
                    ))
                elif item[0] in ["re", "q"]: # rect or quad
                    # item[1] is the rect
                    r = item[1]
                    visual_elements.append(VisualElement(
                        type="rect",
                        bbox=(r.x0, r.y0, r.x1, r.y1),
                        stroke_color=draw["color"],
                        fill_color=draw["fill"],
                        line_width=draw["width"],
                        page_num=page_num
                    ))
                elif item[0] == "c": # curve (bezier)
                    # ... (existing bezier code)
                    xs = [p.x for p in item[1:]]
                    ys = [p.y for p in item[1:]]
                    visual_elements.append(VisualElement(
                        type="curve",
                        bbox=(min(xs), min(ys), max(xs), max(ys)),
                        stroke_color=draw["color"],
                        fill_color=draw["fill"],
                        line_width=draw["width"],
                        page_num=page_num
                    ))
                    
        return text_elements, visual_elements

    def close(self):
        self.doc.close()
