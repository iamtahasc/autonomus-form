from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum
import math
from src.parser import TextElement, VisualElement

class FieldType(Enum):
    TEXT = "text"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SIGNATURE = "signature"
    IMAGE = "image"

@dataclass
class FieldCandidate:
    type: FieldType
    bbox: Tuple[float, float, float, float]
    page_num: int
    associated_label: Optional[str] = None
    name: Optional[str] = None
    export_value: Optional[str] = None

class FormAnalyzer:
    def __init__(self, text_elements: List[TextElement], visual_elements: List[VisualElement]):
        self.text_elements = text_elements
        self.visual_elements = visual_elements
        self.candidates: List[FieldCandidate] = []

    def detect_candidates(self):
        """Detect potential fields based on visual primitives with improved heuristics."""
        for v in self.visual_elements:
            width = v.bbox[2] - v.bbox[0]
            height = v.bbox[3] - v.bbox[1]
            
            # Heuristic 1: Lines (Underlines for Text Fields)
            if v.type == "line":
                # Relaxed width/height for underlines
                if width > 20 and height < 8:
                    field_height = 20 
                    # Adjust bbox to sit on top of the line
                    field_bbox = (v.bbox[0], v.bbox[1] - field_height, v.bbox[2], v.bbox[3] + 2)
                    self.candidates.append(FieldCandidate(FieldType.TEXT, field_bbox, v.page_num))
            
            # Rectangles & Paths (Boxes)
            elif v.type in ["rect", "path", "curve"]:
                 ratio = width / (height + 0.001)
                 
                 # 1. Image Placeholder / Large Text Area
                 if width > 60 and height > 60:
                     # Filter out huge page borders
                     if width < 550 and height < 750: 
                        # If aspect ratio is extreme, it might be a section divider, not a field
                        if 0.2 < ratio < 5.0:
                             self.candidates.append(FieldCandidate(FieldType.IMAGE, v.bbox, v.page_num))
                 
                 # 2. Text Box (Wide)
                 # Range: Width 20-500, Height 10-60
                 elif 20 < width < 500 and 10 < height < 60:
                      self.candidates.append(FieldCandidate(FieldType.TEXT, v.bbox, v.page_num))
                 
                 # 3. Checkbox / Radio (Small & Square-ish)
                 # Range: 6-40 px size, close to 1:1 ratio
                 elif 6 < width < 45 and 6 < height < 45:
                      if 0.6 < ratio < 1.4:
                          # Distinguish Checkbox vs Radio by shape type if possible, else default Checkbox
                          f_type = FieldType.RADIO if v.type == "curve" else FieldType.CHECKBOX
                          self.candidates.append(FieldCandidate(f_type, v.bbox, v.page_num))
                      elif ratio > 1.5:
                          # Small text box (e.g. "Initials")
                          self.candidates.append(FieldCandidate(FieldType.TEXT, v.bbox, v.page_num))

        # Run Cluster-based detection
        self._detect_line_clusters()  # Checkboxes from lines
        self._detect_curve_clusters() # Radios from curves
        self._detect_dotted_lines()   # Text lines from dots
        self._detect_large_boxes()    # Images/Sig from lines

        # Deduplication and Filtering
        self._deduplicate_candidates()
        
        # Improved Text filtering: distinguish "Content" vs "Label" overlap
        self._filter_text_overlaps()

    def associate_labels(self):
        """Associate nearest text labels to fields with weighted scoring."""
        # Weights for direction
        W_LEFT = 1.0    # Label is to the left (Name: [   ])
        W_ABOVE = 1.2   # Label is above ([Name]\n[   ])
        W_RIGHT = 3.0   # Label is to right ([ ] Yes) - less common for Text, common for Checkbox
        
        for candidate in self.candidates:
            best_label = None
            min_score = float('inf')
            
            cx, cy = (candidate.bbox[0]+candidate.bbox[2])/2, (candidate.bbox[1]+candidate.bbox[3])/2
            
            for text in self.text_elements:
                if text.page_num != candidate.page_num: continue
                
                tx, ty = (text.bbox[0]+text.bbox[2])/2, (text.bbox[1]+text.bbox[3])/2
                
                dist_x = abs(cx - tx)
                dist_y = abs(cy - ty)
                
                # Calculate edge distances
                left_gap = candidate.bbox[0] - text.bbox[2]   # Text is Left
                right_gap = text.bbox[0] - candidate.bbox[2]  # Text is Right
                top_gap = candidate.bbox[1] - text.bbox[3]    # Text is Above
                
                score = float('inf')
                
                # Check LEFT (Standard for Text Inputs)
                if 0 < left_gap < 250 and dist_y < 15: # Strict vertical alignment
                    score = left_gap * W_LEFT
                
                # Check ABOVE (Standard for Text Inputs / Table headers)
                elif 0 < top_gap < 50 and (text.bbox[0] < candidate.bbox[2] and text.bbox[2] > candidate.bbox[0]): # Horizontal overlap
                    score = top_gap * W_ABOVE
                
                # Check RIGHT (Standard for Checkboxes/Radios)
                elif 0 < right_gap < 30 and dist_y < 15:
                    if candidate.type in [FieldType.CHECKBOX, FieldType.RADIO]:
                        score = right_gap * 0.8 # Favored for toggles
                    else:
                        score = right_gap * W_RIGHT
                
                if score < min_score:
                    min_score = score
                    best_label = text.text

            if best_label and min_score < 1000:
                candidate.associated_label = best_label.strip(": ")
                raw = self._normalize_name(candidate.associated_label)
                candidate.name = raw
                
                # Smart Type Correction based on Label
                label_lower = raw.lower()
                if "signature" in label_lower or "sign_here" in label_lower:
                    if candidate.type in [FieldType.TEXT, FieldType.IMAGE]: 
                        candidate.type = FieldType.SIGNATURE
                elif "photo" in label_lower or "picture" in label_lower or "face" in label_lower:
                     candidate.type = FieldType.IMAGE
                elif ("date" in label_lower or "dob" in label_lower) and candidate.type == FieldType.TEXT:
                     # Keep as text but could add validation later
                     pass

    def _detect_curve_clusters(self):
        """Group nearby curves into Radio candidates."""
        MAX_GAP = 10.0
        pages = set(v.page_num for v in self.visual_elements)
        for p_num in pages:
            curves = [v for v in self.visual_elements if v.page_num == p_num and v.type == "curve"]
            clusters = []
            visited_ids = set()
            
            for curve in curves:
                if id(curve) in visited_ids: continue
                
                cluster = {'bbox': list(curve.bbox), 'segments': [curve]}
                visited_ids.add(id(curve))
                
                queue = [curve]
                while queue:
                    curr = queue.pop(0)
                    cx0, cy0, cx1, cy1 = curr.bbox
                    
                    for other in curves:
                        if id(other) in visited_ids: continue
                        
                        ox0, oy0, ox1, oy1 = other.bbox
                        if (ox0 < cx1 + MAX_GAP and ox1 > cx0 - MAX_GAP and 
                            oy0 < cy1 + MAX_GAP and oy1 > cy0 - MAX_GAP):
                             cluster['segments'].append(other)
                             cluster['bbox'] = [
                                 min(cluster['bbox'][0], ox0), 
                                 min(cluster['bbox'][1], oy0), 
                                 max(cluster['bbox'][2], ox1), 
                                 max(cluster['bbox'][3], oy1)
                             ]
                             visited_ids.add(id(other))
                             queue.append(other)
                
                clusters.append(cluster)
            
            for c in clusters:
                x0, y0, x1, y1 = c['bbox']
                w, h = x1 - x0, y1 - y0
                
                if 5 < w < 40 and 5 < h < 40:
                    ratio = w / (h + 0.001)
                    if 0.4 < ratio < 2.5:
                        self.candidates.append(FieldCandidate(FieldType.RADIO, (x0, y0, x1, y1), p_num))

    def _detect_dotted_lines(self):
        MAX_Y_DIFF = 2.0
        MAX_X_GAP = 5.0
        pages = set(v.page_num for v in self.visual_elements)
        for p_num in pages:
            lines = [v for v in self.visual_elements if v.page_num == p_num and v.type == "line"]
            lines.sort(key=lambda l: (l.bbox[1], l.bbox[0]))
            
            if not lines: continue
            current_cluster = [lines[0]]
            
            for i in range(1, len(lines)):
                l = lines[i]
                prev = current_cluster[-1]
                y_diff = abs(l.bbox[1] - prev.bbox[1])
                x_gap = l.bbox[0] - prev.bbox[2]
                
                if y_diff < MAX_Y_DIFF and 0 < x_gap < MAX_X_GAP:
                    current_cluster.append(l)
                else:
                    self._process_dotted_cluster(current_cluster)
                    current_cluster = [l]
            self._process_dotted_cluster(current_cluster)

    def _process_dotted_cluster(self, cluster):
        if len(cluster) < 3: return
        x0 = cluster[0].bbox[0]
        x1 = cluster[-1].bbox[2]
        y0 = min(l.bbox[1] for l in cluster)
        
        width = x1 - x0
        if width > 30:
            field_height = 20
            field_bbox = (x0, y0 - field_height, x1, y0)
            self.candidates.append(FieldCandidate(FieldType.TEXT, field_bbox, cluster[0].page_num))

    def _detect_line_clusters(self):
        MAX_GAP = 3.0 
        pages = set(v.page_num for v in self.visual_elements)
        for p_num in pages:
            lines = [v for v in self.visual_elements if v.page_num == p_num and v.type == "line"]
            lines = [l for l in lines if (l.bbox[2]-l.bbox[0]) < 40 and (l.bbox[3]-l.bbox[1]) < 40]
            
            clusters = [] 
            for line in lines:
                added = False
                lx0, ly0, lx1, ly1 = line.bbox
                for cluster in clusters:
                    cx0, cy0, cx1, cy1 = cluster['bbox']
                    if (lx0 < cx1 + MAX_GAP and lx1 > cx0 - MAX_GAP and 
                        ly0 < cy1 + MAX_GAP and ly1 > cy0 - MAX_GAP):
                        cluster['segments'].append(line)
                        cluster['bbox'] = [min(cx0, lx0), min(cy0, ly0), max(cx1, lx1), max(cy1, ly1)]
                        added = True
                        break
                if not added:
                    clusters.append({'bbox': [lx0, ly0, lx1, ly1], 'segments': [line]})
            
            for c in clusters:
                if len(c['segments']) < 3: continue
                x0, y0, x1, y1 = c['bbox']
                w, h = x1 - x0, y1 - y0
                if not (6 < w < 40 and 6 < h < 40): continue
                ratio = w / (h + 0.001)
                if not (0.7 < ratio < 1.3): continue
                
                total_len = sum(max(s.bbox[2]-s.bbox[0], s.bbox[3]-s.bbox[1]) for s in c['segments'])
                perimeter = 2 * (w + h)
                if total_len / (perimeter + 0.001) > 0.7:
                   self.candidates.append(FieldCandidate(FieldType.CHECKBOX, (x0, y0, x1, y1), p_num))

    def _detect_large_boxes(self):
        MAX_GAP = 5.0 
        pages = set(v.page_num for v in self.visual_elements)
        for p_num in pages:
            lines = [v for v in self.visual_elements if v.page_num == p_num and v.type == "line"]
            clusters = [] 
            visited = set()
            
            for line in lines:
                if id(line) in visited: continue
                visited.add(id(line))
                cluster = {'bbox': list(line.bbox), 'segments': [line]}
                queue = [line]
                while queue:
                    curr = queue.pop(0)
                    cx0, cy0, cx1, cy1 = curr.bbox
                    for other in lines:
                        if id(other) in visited: continue
                        ox0, oy0, ox1, oy1 = other.bbox
                        if (min(cx1, ox1) - max(cx0, ox0) > -MAX_GAP and 
                            min(cy1, oy1) - max(cy0, oy0) > -MAX_GAP):
                             cluster['segments'].append(other)
                             cluster['bbox'] = [
                                 min(cluster['bbox'][0], ox0), 
                                 min(cluster['bbox'][1], oy0), 
                                 max(cluster['bbox'][2], ox1), 
                                 max(cluster['bbox'][3], oy1)
                             ]
                             visited.add(id(other))
                             queue.append(other)
                clusters.append(cluster)
            
            for c in clusters:
                if len(c['segments']) < 4: continue
                x0, y0, x1, y1 = c['bbox']
                w, h = x1 - x0, y1 - y0
                if w > 60 and h > 60:
                     self.candidates.append(FieldCandidate(FieldType.IMAGE, (x0, y0, x1, y1), p_num))
                elif w > 150 and h > 25:
                     self.candidates.append(FieldCandidate(FieldType.TEXT, (x0, y0, x1, y1), p_num))

    def _deduplicate_candidates(self):
        unique = []
        for c in self.candidates:
            is_dup = False
            cx0, cx1 = c.bbox[0], c.bbox[2]
            cy0, cy1 = c.bbox[1], c.bbox[3]
            c_area = (cx1 - cx0) * (cy1 - cy0)
            
            for u in unique:
                if u.page_num != c.page_num: continue
                ux0, ux1 = u.bbox[0], u.bbox[2]
                uy0, uy1 = u.bbox[1], u.bbox[3]
                
                ix0, ix1 = max(cx0, ux0), min(cx1, ux1)
                iy0, iy1 = max(cy0, uy0), min(cy1, uy1)
                
                if ix1 > ix0 and iy1 > iy0:
                    i_area = (ix1 - ix0) * (iy1 - iy0)
                    min_area = min(c_area, (ux1 - ux0) * (uy1 - uy0))
                    if i_area / (min_area + 0.001) > 0.5:
                        is_dup = True
                        break
            if not is_dup:
                unique.append(c)
        self.candidates = unique
    
    def _filter_text_overlaps(self):
        valid = []
        for c in self.candidates:
            # Skip filtering for checkboxes/radios as they are often close to text
            if c.type in [FieldType.CHECKBOX, FieldType.RADIO]:
                valid.append(c)
                continue

            is_text_border = False
            cx0, cx1 = c.bbox[0], c.bbox[2]
            cy0, cy1 = c.bbox[1], c.bbox[3]
            c_area = (cx1 - cx0) * (cy1 - cy0)
            
            for t in self.text_elements:
                if t.page_num != c.page_num: continue
                tx0, tx1 = t.bbox[0], t.bbox[2]
                ty0, ty1 = t.bbox[1], t.bbox[3]
                
                ix0, ix1 = max(cx0, tx0), min(cx1, tx1)
                iy0, iy1 = max(cy0, ty0), min(cy1, ty1)
                
                if ix1 > ix0 and iy1 > iy0:
                    i_area = (ix1 - ix0) * (iy1 - iy0)
                    overlap_ratio = i_area / (c_area + 0.001)
                    
                    # Heuristic: If candidates is effectively "filled" with text, it might be a button or label
                    # But if overlapping text is small (like a placeholder "Enter Name"), keeps it.
                    # If overlap is huge relative to box (e.g. box is just a border around paragraph), remove it.
                    if overlap_ratio > 0.8:
                        is_text_border = True
                        break
                        
            if not is_text_border:
                valid.append(c)
        self.candidates = valid

    def _group_radios(self):
        radios = [c for c in self.candidates if c.type == FieldType.RADIO]
        if not radios: return
        
        clusters = []
        visited_ids = set()
        
        for r in radios:
            if id(r) in visited_ids: continue
            
            cluster = [r]
            visited_ids.add(id(r))
            queue = [r]
            
            while queue:
                curr = queue.pop(0)
                cx0, cy0, cx1, cy1 = curr.bbox
                
                for other in radios:
                    if id(other) in visited_ids: continue
                    
                    ox0, oy0, ox1, oy1 = other.bbox
                    ccx, ccy = (cx0+cx1)/2, (cy0+cy1)/2
                    ocx, ocy = (ox0+ox1)/2, (oy0+oy1)/2
                    
                    dist = math.sqrt((ccx-ocx)**2 + (ccy-ocy)**2)
                    if dist < 150: 
                         visited_ids.add(id(other))
                         cluster.append(other)
                         queue.append(other)
            clusters.append(cluster)
            
        for cluster in clusters:
            if len(cluster) < 2: continue
            for r in cluster:
                r.export_value = r.name if r.name else "choice"
            
            group_label = None
            min_dist = float('inf')
            min_x, min_y = min(r.bbox[0] for r in cluster), min(r.bbox[1] for r in cluster)
            # Logic similar to associate_labels but for the group cluster
            pass # simplified for now in overwrite

    def _normalize_name(self, text: str) -> str:
        s = text.lower()
        s = "".join(c if c.isalnum() else "_" for c in s)
        while "__" in s: s = s.replace("__", "_")
        return s.strip("_")

    def get_fields(self) -> List[FieldCandidate]:
        self._filter_text_overlaps()
        self._group_radios() 
        
        final = []
        counts = {}
        
        for c in self.candidates:
            if not c.name: continue
            name = c.name
            if name in counts:
                counts[name] += 1
                name = f"{name}_{counts[name]}"
                c.name = name
            else:
                counts[name] = 1
            final.append(c)
        return final
