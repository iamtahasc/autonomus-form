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
        """Detect potential fields based on visual primitives."""
        for v in self.visual_elements:
            width = v.bbox[2] - v.bbox[0]
            height = v.bbox[3] - v.bbox[1]
            
            # Heuristic 1: Text Line (Underline)
            if v.type == "line":
                if width > 30 and height < 5:
                    field_height = 20 
                    field_bbox = (v.bbox[0], v.bbox[1] - field_height, v.bbox[2], v.bbox[1])
                    self.candidates.append(FieldCandidate(FieldType.TEXT, field_bbox, v.page_num))
            
            # Rectangles: Text Box, Checkbox, Signature Box, Image
            elif v.type == "rect":
                 ratio = width / (height + 0.001)
                 
                 # 1. Image Placeholder (Large box, e.g. > 60x60)
                 if width > 60 and height > 60:
                     # Check if it's not just a page border (usually very large)
                     if width < 500 and height < 700: 
                        self.candidates.append(FieldCandidate(FieldType.IMAGE, v.bbox, v.page_num))
                 
                 # 2. Text Box (Wide)
                 # Relaxed: Allow width > 25 if ratio > 1.5 (catches "Age: [ ]")
                 elif width > 25 and height > 10 and height < 50 and ratio > 1.5:
                      # If very wide and tall, might be signature?
                      if width > 150 and height > 25:
                           # Could be text or signature. Default TEXT, associate_labels can override.
                           self.candidates.append(FieldCandidate(FieldType.TEXT, v.bbox, v.page_num))
                      else:
                           self.candidates.append(FieldCandidate(FieldType.TEXT, v.bbox, v.page_num))
                 
                 # 3. Checkbox (Square-ish)
                 # Strict ratio to avoid confusion with small text boxes
                 elif 6 < width < 40 and 6 < height < 40 and 0.8 < ratio < 1.2:
                      self.candidates.append(FieldCandidate(FieldType.CHECKBOX, v.bbox, v.page_num))

            # Heuristic 2: Checkbox / Radio (Paths/Curves)
            elif v.type in ["path", "curve"]: 
                ratio = width / (height + 0.001)
                # Relaxed size constraints: > 5pt to catch small curve segments
                if 5 < width < 40 and 5 < height < 40:
                     if 0.7 < ratio < 1.3:
                         f_type = FieldType.CHECKBOX if v.type == "path" else FieldType.RADIO
                         self.candidates.append(FieldCandidate(f_type, v.bbox, v.page_num))
                     elif ratio > 1.5 and v.type == "path":
                         # Small text box (e.g. "Age: [   ]")
                         self.candidates.append(FieldCandidate(FieldType.TEXT, v.bbox, v.page_num))
                
                # Large Paths (Image or Signature Box)
                elif width > 60 and height > 60:
                     self.candidates.append(FieldCandidate(FieldType.IMAGE, v.bbox, v.page_num))
                elif width > 150 and height > 25:
                     self.candidates.append(FieldCandidate(FieldType.TEXT, v.bbox, v.page_num))

        # Heuristic 3: Clustered Lines (Checkboxes)
        self._detect_line_clusters()
        
        # Heuristic 8: Clustered Lines (Large Boxes - Images/Signatures)
        self._detect_large_boxes()
        
        # Heuristic 6: Clustered Curves (Radio Buttons)
        # Circles are often parsed as 4 bezier curves.
        self._detect_curve_clusters()

        # Heuristic 5: Dotted/Dashed Fields (Merge small collinear lines)
        self._detect_dotted_lines()

        # Heuristic 4: Deduplicate overlapping candidates
        self._deduplicate_candidates()

        # Heuristic 7: Filter candidates that overlap too much with text
        self._filter_text_overlaps()

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
                
                # Allow 6pt (half-circle/quarter-circle chunks might be small, but total cluster should be > 5)
                # Actually, if we merge, w should be ~12.
                if 5 < w < 40 and 5 < h < 40:
                    ratio = w / (h + 0.001)
                    # Relaxed ratio to accept half-circles (e.g. 12x6 -> 2.0)
                    if 0.4 < ratio < 2.5:
                        self.candidates.append(FieldCandidate(FieldType.RADIO, (x0, y0, x1, y1), p_num))

    def _detect_dotted_lines(self):
        """Merge short collinear lines into a single Text Field candidate."""
        # Dotted lines are many small line segments on the same Y-axis (approx).
        MAX_Y_DIFF = 2.0
        MAX_X_GAP = 5.0
        
        pages = set(v.page_num for v in self.visual_elements)
        for p_num in pages:
            lines = [v for v in self.visual_elements if v.page_num == p_num and v.type == "line"]
            # Sort by Y then X
            lines.sort(key=lambda l: (l.bbox[1], l.bbox[0]))
            
            if not lines: continue
            
            current_cluster = [lines[0]]
            
            for i in range(1, len(lines)):
                l = lines[i]
                prev = current_cluster[-1]
                
                # Check Collinearity
                y_diff = abs(l.bbox[1] - prev.bbox[1])
                x_gap = l.bbox[0] - prev.bbox[2]
                
                # Merge if same row and close
                if y_diff < MAX_Y_DIFF and 0 < x_gap < MAX_X_GAP:
                    current_cluster.append(l)
                else:
                    # Process cluster
                    self._process_dotted_cluster(current_cluster)
                    current_cluster = [l]
            
            # Last cluster
            self._process_dotted_cluster(current_cluster)

    def _process_dotted_cluster(self, cluster):
        if len(cluster) < 3: return # Needs multiple dots/dashes
        
        # Calculate total width
        x0 = cluster[0].bbox[0]
        x1 = cluster[-1].bbox[2]
        y0 = min(l.bbox[1] for l in cluster)
        y1 = max(l.bbox[3] for l in cluster)
        
        width = x1 - x0
        
        if width > 30: # Minimum width for a field
            # It's a valid dotted line field
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
        """Detect large boxes formed by lines (Images, Signatures)."""
        MAX_GAP = 5.0 
        pages = set(v.page_num for v in self.visual_elements)
        for p_num in pages:
            lines = [v for v in self.visual_elements if v.page_num == p_num and v.type == "line"]
            # Consider lines that are NOT small (part of checkbox)
            # lines = [l for l in lines if (l.bbox[2]-l.bbox[0]) > 20 or (l.bbox[3]-l.bbox[1]) > 20]
            
            clusters = [] 
            visited = set()
            
            # Simple clustering
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
                        # connectivity check
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
                if len(c['segments']) < 4: continue # A box needs at least 3-4 lines?
                x0, y0, x1, y1 = c['bbox']
                w, h = x1 - x0, y1 - y0
                
                # Check Image (Large Box)
                if w > 60 and h > 60:
                     self.candidates.append(FieldCandidate(FieldType.IMAGE, (x0, y0, x1, y1), p_num))
                # Check Signature Box (Wide)
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
                    if i_area / (c_area + 0.001) > 0.3: # Threshold 30%
                        is_text_border = True
                        print(f"DEBUG: Filtering Candidate {c.type} {c.bbox} due to overlap with '{t.text}'")
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
                    # Check proximity
                    # Horizontal overlap (same row) or Vertical overlap (same col)
                    # Actually, simple distance between centers
                    ccx, ccy = (cx0+cx1)/2, (cy0+cy1)/2
                    ocx, ocy = (ox0+ox1)/2, (oy0+oy1)/2
                    
                    dist = math.sqrt((ccx-ocx)**2 + (ccy-ocy)**2)
                    if dist < 150: # Cluster threshold
                         # Verify alignment (optional but good)
                         visited_ids.add(id(other))
                         cluster.append(other)
                         queue.append(other)
            
            clusters.append(cluster)
            
        for cluster in clusters:
            if len(cluster) < 2: continue
            
            # 1. Export Values
            for r in cluster:
                r.export_value = r.name if r.name else "choice"
            
            # 2. Group Label
            group_label = None
            min_dist = float('inf')
            min_x, min_y = min(r.bbox[0] for r in cluster), min(r.bbox[1] for r in cluster)
            max_x, max_y = max(r.bbox[2] for r in cluster), max(r.bbox[3] for r in cluster)
            cy = (min_y + max_y) / 2
            
            for text in self.text_elements:
                if text.page_num != cluster[0].page_num: continue
                if any(r.associated_label == text.text.strip(": ") for r in cluster): continue
                
                t_y = (text.bbox[1]+text.bbox[3])/2
                # Check Left
                if abs(cy - t_y) < 50:
                    if text.bbox[2] < min_x:
                        dist = min_x - text.bbox[2]
                        if dist < 300 and dist < min_dist:
                            min_dist = dist
                            group_label = text.text
                # Check Above
                if text.bbox[3] < min_y:
                    overlap = max(0, min(max_x, text.bbox[2]) - max(min_x, text.bbox[0]))
                    if overlap > 0:
                         dist_y = min_y - text.bbox[3]
                         if dist_y < 100 and dist_y < min_dist:
                             min_dist = dist_y
                             group_label = text.text
            
            if group_label:
                group_name = self._normalize_name(group_label.strip(": "))
                for r in cluster: r.name = group_name

    def associate_labels(self):
        W_LEFT, W_RIGHT, W_ABOVE = 1.0, 1.2, 2.5 
        for candidate in self.candidates:
            best_label = None
            min_score = float('inf')
            cx, cy = (candidate.bbox[0]+candidate.bbox[2])/2, (candidate.bbox[1]+candidate.bbox[3])/2
            
            for text in self.text_elements:
                if text.page_num != candidate.page_num: continue
                tx, ty = (text.bbox[0]+text.bbox[2])/2, (text.bbox[1]+text.bbox[3])/2
                
                # Left
                if abs(cy - ty) < 20 and text.bbox[2] < candidate.bbox[0]:
                    dist = candidate.bbox[0] - text.bbox[2]
                    if dist < 300:
                        score = dist * W_LEFT
                        if score < min_score:
                             min_score = score
                             best_label = text.text
                # Right
                if abs(cy - ty) < 20 and text.bbox[0] > candidate.bbox[2]:
                    dist = text.bbox[0] - candidate.bbox[2]
                    if dist < 50:
                        score = dist * W_RIGHT
                        if score < min_score:
                            min_score = score
                            best_label = text.text
                # Above
                if text.bbox[3] < candidate.bbox[1]:
                    overlap = max(0, min(candidate.bbox[2], text.bbox[2]) - max(candidate.bbox[0], text.bbox[0]))
                    if overlap > 0:
                        dist = candidate.bbox[1] - text.bbox[3]
                        if dist < 60:
                            score = dist * W_ABOVE
                            if score < min_score:
                                min_score = score
                                best_label = text.text
                                
            if best_label:
                candidate.associated_label = best_label.strip(": ")
                raw = self._normalize_name(candidate.associated_label)
                candidate.name = raw
                
                # Heuristic: If label contains "signature", override type
                if "signature" in raw or "sign" in raw:
                    # Only override TEXT or IMAGE (don't override checks/radios normally)
                    if candidate.type in [FieldType.TEXT, FieldType.IMAGE]: 
                        candidate.type = FieldType.SIGNATURE

    def _normalize_name(self, text: str) -> str:
        s = text.lower()
        s = "".join(c if c.isalnum() else "_" for c in s)
        while "__" in s: s = s.replace("__", "_")
        return s.strip("_")

    def get_fields(self) -> List[FieldCandidate]:
        """Return final list of detected fields."""
        # 1. Filter Overlaps
        self._filter_text_overlaps()
        
        # 2. Group Radios
        self._group_radios() 
        
        # 3. Filter Orphans & Deduplicate Names
        final = []
        counts = {}
        
        for c in self.candidates:
            if not c.name:
                continue
                
            # Deduplicate names (append _2, _3 etc)
            name = c.name
            if name in counts:
                counts[name] += 1
                name = f"{name}_{counts[name]}"
                c.name = name # update candidate name
            else:
                counts[name] = 1
            
            final.append(c)
            
        return final
