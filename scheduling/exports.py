from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from PIL import Image, ImageDraw, ImageFont

from .constants import DAYS, PT_SLOT_KEY


def _try_register_fonts():
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
        pdfmetrics.registerFont(TTFont("DejaVuBold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
        return True
    except Exception:
        return False


def _day_header_cells(schedule):
    cells = []
    for day_key, day_lbl in DAYS:
        d = schedule.date_for_day_key(day_key)
        cells.append(f"{day_lbl}\n{d.strftime('%d %b')}")
    return cells


def _slot_row_has_any(schedule, slot_key: str) -> bool:
    day_map = (schedule.cells or {}).get(slot_key, {}) or {}
    for day_key, _ in DAYS:
        cell = (day_map or {}).get(day_key, {}) or {}
        staff_ids = cell.get("staff") or []
        if staff_ids:
            return True
    return False


def build_pdf(*, schedule, slots, staff_map: dict[int, str], theme, style: int = 1) -> bytes:
    _try_register_fonts()
    buf = BytesIO()

    from reportlab.platypus import Flowable
    from reportlab.pdfbase import pdfmetrics
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm

    def _clamp(v: float, lo: float, hi: float) -> float:
        try:
            v = float(v)
        except Exception:
            v = lo
        if v < lo:
            return lo
        if v > hi:
            return hi
        return v

    def _hex_to_rgb01(h: str):
        h = (h or "").strip().lstrip("#")
        if len(h) == 3:
            h = "".join([c + c for c in h])
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        return r, g, b

    def _blend_hex(src_hex: str, dst_hex: str = "#FFFFFF", t: float = 0.10) -> str:
        t = max(0.0, min(float(t or 0.0), 1.0))
        sr, sg, sb = _hex_to_rgb01(src_hex)
        dr, dg, db = _hex_to_rgb01(dst_hex)
        r = sr + (dr - sr) * t
        g = sg + (dg - sg) * t
        b = sb + (db - sb) * t
        return "#%02X%02X%02X" % (int(r * 255), int(g * 255), int(b * 255))

    def _short_date(s: str) -> str:
        s = (s or "").strip()
        if not s:
            return ""
        parts = s.split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"
        return s

    def _draw_vertical_gradient(c, x: float, y: float, w: float, h: float, *, top_hex: str, bottom_hex: str, steps: int = 80):
        br, bg, bb = _hex_to_rgb01(bottom_hex)
        tr, tg, tb = _hex_to_rgb01(top_hex)

        step_h = h / float(max(steps, 1))
        for i in range(max(steps, 1)):
            t = i / float(max(steps - 1, 1))
            r = br + (tr - br) * t
            g = bg + (tg - bg) * t
            b = bb + (tb - bb) * t

            yy = y + (i * step_h)
            c.setFillColorRGB(r, g, b)
            c.rect(x, yy, w, step_h + 0.8, stroke=0, fill=1)

    class _RoundedCard(Flowable):
        def __init__(
            self,
            flowable,
            *,
            radius: float = 5,
            fill_color=None,
            stroke_color=None,
            stroke_width: float = 0.9,
            inset: float = 0.0,
            shadow: bool = False,
            shadow_dx: float = 2.2,
            shadow_dy: float = -2.2,
            shadow_color=None,
            shadow_alpha: float = 0.10,
        ):
            super().__init__()
            self.flowable = flowable
            self.radius = radius
            self.fill_color = fill_color
            self.stroke_color = stroke_color
            self.stroke_width = stroke_width
            self.inset = inset
            self.shadow = shadow
            self.shadow_dx = shadow_dx
            self.shadow_dy = shadow_dy
            self.shadow_color = shadow_color
            self.shadow_alpha = shadow_alpha
            self._w = 0
            self._h = 0

        def wrap(self, availWidth, availHeight):
            w, h = self.flowable.wrap(availWidth - (self.inset * 2), availHeight)
            self._w = w + (self.inset * 2)
            self._h = h + (self.inset * 2)
            return self._w, self._h

        def draw(self):
            c = self.canv
            c.saveState()

            # Soft shadow behind the table card
            if self.shadow:
                try:
                    c.saveState()
                    if self.shadow_color is not None:
                        c.setFillColor(self.shadow_color)
                    else:
                        c.setFillColor(colors.black)
                    try:
                        c.setFillAlpha(float(self.shadow_alpha or 0.0))
                    except Exception:
                        pass
                    c.roundRect(self.shadow_dx, self.shadow_dy, self._w, self._h, self.radius, stroke=0, fill=1)
                    try:
                        c.setFillAlpha(1)
                    except Exception:
                        pass
                    c.restoreState()
                except Exception:
                    pass

            if self.fill_color is not None:
                c.setFillColor(self.fill_color)
            if self.stroke_color is not None and self.stroke_width and self.stroke_width > 0:
                c.setStrokeColor(self.stroke_color)
                c.setLineWidth(self.stroke_width)
                stroke = 1
            else:
                stroke = 0

            fill = 1 if self.fill_color is not None else 0
            c.roundRect(0, 0, self._w, self._h, self.radius, stroke=stroke, fill=fill)
            self.flowable.drawOn(c, self.inset, self.inset)
            c.restoreState()

    class _GradientRoundedCard(Flowable):
        def __init__(
            self,
            flowable,
            *,
            radius: float = 5,
            top_hex: str = "#FFFFFF",
            bottom_hex: str = "#000000",
            stroke_color=None,
            stroke_width: float = 0.0,
            inset: float = 0.0,
            steps: int = 80,
        ):
            super().__init__()
            self.flowable = flowable
            self.radius = radius
            self.top_hex = top_hex
            self.bottom_hex = bottom_hex
            self.stroke_color = stroke_color
            self.stroke_width = stroke_width
            self.inset = inset
            self.steps = steps
            self._w = 0
            self._h = 0

        def wrap(self, availWidth, availHeight):
            w, h = self.flowable.wrap(availWidth - (self.inset * 2), availHeight)
            self._w = w + (self.inset * 2)
            self._h = h + (self.inset * 2)
            return self._w, self._h

        def draw(self):
            c = self.canv
            c.saveState()

            p = c.beginPath()
            p.roundRect(0, 0, self._w, self._h, self.radius)
            c.clipPath(p, stroke=0, fill=0)

            _draw_vertical_gradient(c, 0, 0, self._w, self._h, top_hex=self.top_hex, bottom_hex=self.bottom_hex, steps=self.steps)

            if self.stroke_color is not None and self.stroke_width and self.stroke_width > 0:
                c.setStrokeColor(self.stroke_color)
                c.setLineWidth(self.stroke_width)
                c.roundRect(0, 0, self._w, self._h, self.radius, stroke=1, fill=0)

            self.flowable.drawOn(c, self.inset, self.inset)
            c.restoreState()

    styles = getSampleStyleSheet()

    # ===== Fonts (nice + consistent, minimal bold) =====
    body_font = (getattr(theme, "pdf_font_body", "") or "").strip() or "Helvetica"
    bold_font = (getattr(theme, "pdf_font_bold", "") or "").strip() or "Helvetica-Bold"

    # ===== Font sizes (balanced) =====
    header_font_size = _clamp(getattr(theme, "pdf_header_font_size", 18.0) or 18.0, 15.5, 20.0)
    week_font_size = _clamp(getattr(theme, "pdf_week_font_size", 12.8) or 12.8, 11.2, 14.5)
    th_font_size = _clamp(getattr(theme, "pdf_table_header_font_size", 12.3) or 12.3, 11.2, 14.5)
    td_font_size = _clamp(getattr(theme, "pdf_table_font_size", 12.1) or 12.1, 10.8, 14.6)

    # IMPORTANT: keep same size feel as week range and PT time
    subtext_size = _clamp(getattr(theme, "pdf_subtext_size", week_font_size) or week_font_size, 11.2, 14.5)
    td_pt_font_size = _clamp(getattr(theme, "pdf_table_pt_font_size", week_font_size) or week_font_size, 11.2, 14.5)

    # Header row: slightly smaller so day/date never wrap (one-line guarantee)
    header_th_size = _clamp(th_font_size - 0.8, 10.6, th_font_size)
    header_sub_size = _clamp(subtext_size - 0.8, 10.4, subtext_size)

    # PT row: make text a little smaller (including "PT" label + names + time)
    pt_row_delta = 1.0
    td_pt_font_size_sm = _clamp(td_pt_font_size - pt_row_delta, 10.2, td_pt_font_size)
    pt_shift_font_size_sm = _clamp(header_th_size - pt_row_delta, 10.2, header_th_size)

    # ===== Page size + margins (centered layout) =====
    page_w, page_h = landscape(A4)

    # less wide overall: increase margins a bit
    margin = 16 * mm
    left_margin = margin
    right_margin = margin
    top_margin = margin
    bottom_margin = margin

    avail_w = page_w - left_margin - right_margin

    # ===== Colors (soft, but not too soft) =====
    base_header_hex = "#611B29"
    header_top_hex = _blend_hex(base_header_hex, "#FFFFFF", 0.20)
    header_bottom_hex = _blend_hex(base_header_hex, "#000000", 0.20)

    header_bg_hex = header_bottom_hex
    header_text_hex = "#F8FAFC"

    # New soft header row bg (different from other rows)
    header_row_bg_hex = "#FFF3E8"
    header_row_text_hex = "#0F172A"
    table_text_hex = "#0F172A"
    table_subtext_hex = "#64748B"

    border_hex = "#D7DEE8"
    divider_hex = "#C6CFDB"
    weekend_bg_hex = "#F3F6FB"

    stripe_a_hex = "#FFFFFF"
    stripe_b_hex = "#FAFCFF"

    offday_bg_hex = "#F2BFC4"
    leave_bg_hex  = "#EFCF86"
    pt_bg_hex     = "#CBE8D4"

    empty_cell_bg_hex = _blend_hex(base_header_hex, "#FFFFFF", 0.92)

    pt_empty_bg_hex = _blend_hex("#D14B57", "#FFFFFF", 0.72)

    header_row_bg_hex = _blend_hex(header_row_bg_hex, "#FFFFFF", 0.10)
    weekend_bg_hex = _blend_hex(weekend_bg_hex, "#FFFFFF", 0.08)
    stripe_b_hex = _blend_hex(stripe_b_hex, "#FFFFFF", 0.06)

    offday_bg_hex = _blend_hex(offday_bg_hex, "#FFFFFF", 0.05)
    leave_bg_hex = _blend_hex(leave_bg_hex, "#FFFFFF", 0.05)
    pt_bg_hex = _blend_hex(pt_bg_hex, "#FFFFFF", 0.05)

    header_bg = colors.HexColor(header_bg_hex)
    header_text = colors.HexColor(header_text_hex)

    header_row_bg = colors.HexColor(header_row_bg_hex)
    header_row_text = colors.HexColor(header_row_text_hex)
    table_text = colors.HexColor(table_text_hex)
    border_soft = colors.HexColor(border_hex)
    divider_color = colors.HexColor(divider_hex)
    weekend_bg = colors.HexColor(weekend_bg_hex)

    stripe_a = colors.HexColor(stripe_a_hex)
    stripe_b = colors.HexColor(stripe_b_hex)

    offday_row_bg = colors.HexColor(offday_bg_hex)
    leave_row_bg = colors.HexColor(leave_bg_hex)
    pt_row_bg = colors.HexColor(pt_bg_hex)

    empty_cell_bg = colors.HexColor(empty_cell_bg_hex)
    pt_empty_bg = colors.HexColor(pt_empty_bg_hex)

    # ===== Data helpers =====
    header_cells = _day_header_cells(schedule)

    visible_slots = []
    for s in slots:
        if _slot_row_has_any(schedule, s.key):
            visible_slots.append(s)

    def _slot_kind(slot) -> str:
        k = (getattr(slot, "key", "") or "").strip().lower()
        l = (getattr(slot, "label", "") or "").strip().lower()
        if k == PT_SLOT_KEY or "pt" == k or l == "pt" or l.startswith("pt "):
            return "pt"
        if "off" in k or "off" in l:
            return "off"
        if "ph" in k or "al" in k or "ph" in l or "al" in l:
            return "leave"
        return "work"

    def _label_clean(s: str) -> str:
        # PH*/AL@  -> PH/AL
        s = (s or "").strip()
        if s == "PH*/AL@":
            return "PH/AL"
        if s == "Off Day":
            return "Rest Day"
        return s

    def _format_names(names: list[str]) -> str:
        if not names:
            return ""
        return "<br/>".join([n for n in names if (n or "").strip()])

    def _format_pt_names(names: list[str], pt_time: str) -> str:
        if not names:
            return ""
        if not pt_time:
            return _format_names(names)

        tagged = [f"{n} ({pt_time})" for n in names if (n or "").strip()]
        return "<br/>".join(tagged)

    # ===== Dynamic column widths (snug but stable) =====
    # less wide: very small horizontal padding + slightly narrower clamps
    cell_pad_x = 2
    min_day_w = 82
    max_day_w = 135
    min_shift_w = 92
    max_shift_w = 160

    shift_max = pdfmetrics.stringWidth("Shift", bold_font, th_font_size)
    for slot in visible_slots:
        try:
            w = pdfmetrics.stringWidth(str(_label_clean(slot.label) or ""), bold_font, th_font_size)
            if w > shift_max:
                shift_max = w
        except Exception:
            pass
    shift_w = _clamp(shift_max + (cell_pad_x * 2) + 6, min_shift_w, max_shift_w)

    day_max = 0.0
    for h in header_cells:
        parts = [p.strip() for p in str(h).splitlines() if p.strip()]
        day = parts[0] if parts else ""
        date_txt = _short_date(parts[1]) if len(parts) >= 2 else ""
        try:
            wd = pdfmetrics.stringWidth(day, bold_font, th_font_size)
        except Exception:
            wd = 0.0
        try:
            wdt = pdfmetrics.stringWidth(date_txt, body_font, subtext_size)
        except Exception:
            wdt = 0.0
        need = wd + wdt + 12
        if need > day_max:
            day_max = need

    for slot in visible_slots:
        for day_key, _ in DAYS:
            cell = (schedule.cells.get(slot.key, {}) or {}).get(day_key, {}) or {}
            blocked = bool(cell.get("blocked"))
            if slot.allow_block and blocked:
                continue

            staff_ids = [int(x) for x in (cell.get("staff") or []) if str(x).isdigit()]
            names = [staff_map.get(i, "") for i in staff_ids if staff_map.get(i, "")]
            kind = _slot_kind(slot)

            if kind == "pt":
                pt_time = (cell.get("pt_time") or "").strip()
                preview = _format_pt_names([str(n) for n in names], pt_time) if names else ""
            else:
                preview = _format_names([str(n) for n in names]) if names else ""

            if preview:
                for line in [x for x in preview.split("<br/>") if x.strip()]:
                    try:
                        w = pdfmetrics.stringWidth(line, body_font, td_font_size)
                        if w > day_max:
                            day_max = w
                    except Exception:
                        pass

    day_w = _clamp(day_max + (cell_pad_x * 2) + 8, min_day_w, max_day_w)
    table_width = shift_w + (day_w * 7.0)

    # ===== Fit to page width (fix cutdown) =====
    if table_width > avail_w:
        day_w_fit = (avail_w - shift_w) / 7.0
        if day_w_fit < min_day_w:
            day_w = max(70.0, day_w_fit)
        else:
            day_w = min(day_w, day_w_fit)

        table_width = shift_w + (day_w * 7.0)
        if table_width > avail_w:
            scale = avail_w / float(max(table_width, 1.0))
            shift_w = max(78.0, shift_w * scale)
            day_w = max(70.0, day_w * scale)
            table_width = shift_w + (day_w * 7.0)

    # ===== Header band =====
    week_title = f"{schedule.week_start.strftime('%d %b %Y')} – {schedule.week_end().strftime('%d %b %Y')}"

    center_style = styles["Normal"].clone("pdf_header_center")
    center_style.fontName = bold_font
    center_style.fontSize = week_font_size
    center_style.leading = week_font_size + 2.2
    center_style.textColor = header_text
    center_style.alignment = 1

    right_style = styles["Normal"].clone("pdf_header_right")
    right_style.fontName = bold_font
    right_style.fontSize = week_font_size
    right_style.leading = week_font_size + 2.2
    right_style.textColor = header_text
    right_style.alignment = 2


    header_table = Table(
        [[
            Paragraph("", right_style),
            Paragraph("Sam's @ Batai Weekly Staff Schedule", center_style),
            Paragraph(week_title, right_style),
        ]],
        colWidths=[table_width * 0.18, table_width * 0.54, table_width * 0.28],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))

    # ===== Table styles =====
    th_day_style = styles["Normal"].clone("pdf_th_day")
    th_day_style.fontName = bold_font
    th_day_style.fontSize = header_th_size
    th_day_style.leading = header_th_size + 0.1
    th_day_style.textColor = header_row_text
    th_day_style.alignment = 0
    th_day_style.spaceBefore = 0
    th_day_style.spaceAfter = 0
    th_day_style.splitLongWords = 0

    th_date_style = styles["Normal"].clone("pdf_th_date")
    th_date_style.fontName = bold_font
    th_date_style.fontSize = header_sub_size
    th_date_style.leading = header_sub_size + 2.2
    th_date_style.textColor = colors.HexColor(table_subtext_hex)
    th_date_style.alignment = 2
    th_date_style.spaceBefore = 0
    th_date_style.spaceAfter = 0
    th_date_style.splitLongWords = 0

    # Shift column should be bold like day
    shift_style = styles["Normal"].clone("pdf_shift")
    shift_style.fontName = bold_font
    shift_style.fontSize = header_th_size
    shift_style.leading = header_th_size + 0.1
    shift_style.textColor = header_row_text
    shift_style.alignment = 0
    shift_style.spaceBefore = 0
    shift_style.spaceAfter = 0
    shift_style.splitLongWords = 0

    # PT shift label: slightly smaller
    pt_shift_style = styles["Normal"].clone("pdf_shift_pt")
    pt_shift_style.fontName = bold_font
    pt_shift_style.fontSize = pt_shift_font_size_sm
    pt_shift_style.leading = pt_shift_font_size_sm + 0.1
    pt_shift_style.textColor = header_row_text
    pt_shift_style.alignment = 0
    pt_shift_style.spaceBefore = 0
    pt_shift_style.spaceAfter = 0
    pt_shift_style.splitLongWords = 0

    # Tight line spacing in cells (padding controls height)
    td_style = styles["Normal"].clone("pdf_td")
    td_style.fontName = bold_font
    td_style.fontSize = td_font_size
    td_style.leading = td_font_size + 0.6
    td_style.textColor = table_text
    td_style.spaceBefore = 0
    td_style.spaceAfter = 0

    td_pt_style = styles["Normal"].clone("pdf_td_pt")
    td_pt_style.fontName = bold_font
    td_pt_style.fontSize = td_pt_font_size_sm
    td_pt_style.leading = td_pt_font_size_sm + 0.6
    td_pt_style.textColor = table_text
    td_pt_style.spaceBefore = 0
    td_pt_style.spaceAfter = 0

    # ---- Small, equal “breathing space” rules ----
    shift_left_pad = 5       # only left padding for Shift column
    header_lr_pad = 3        # small left+right padding for day/date header cells
    body_left_inset = 2      # tiny left inset for all body cell content (as space)

    body_inset = "&nbsp;" * max(1, int(body_left_inset))

    def _indent_each_line(html: str) -> str:
        html = (html or "")
        if not html.strip():
            return ""
        lines = html.split("<br/>")
        return "<br/>".join([f"{body_inset}{ln}" for ln in lines])

    header = [Paragraph("Shift", shift_style)]
    inner_day_w = max(10.0, day_w - (cell_pad_x * 2))
    for h in header_cells:
        parts = [p.strip() for p in str(h).splitlines() if p.strip()]
        day = parts[0] if parts else ""
        date_txt = _short_date(parts[1]) if len(parts) >= 2 else ""
        date_txt_nb = (date_txt or "").replace(" ", "&nbsp;")

        cell_tbl = Table(
            [[
                Paragraph(day, th_day_style),
                Paragraph(date_txt_nb, th_date_style),
            ]],
            colWidths=[inner_day_w * 0.48, inner_day_w * 0.52],
        )
        cell_tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), header_lr_pad),
            ("RIGHTPADDING", (0, 0), (-1, -1), header_lr_pad),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        header.append(cell_tbl)

    data = [header]

    # PT empty cells (no one assigned) -> reddish background
    pt_empty_cells: list[tuple[int, int]] = []

    # Empty cells (all kinds) -> soft background
    empty_cells: list[tuple[int, int]] = []
    row_kind_by_row: dict[int, str] = {}

    for slot in visible_slots:
        row_index = len(data)

        kind = _slot_kind(slot)
        row_kind_by_row[row_index] = kind

        # Shift labels: left breathing space (same for PT/Rest/PH/AL/etc.)
        if kind == "pt":
            row = [Paragraph(_label_clean(slot.label), pt_shift_style)]
        else:
            row = [Paragraph(_label_clean(slot.label), shift_style)]

        for col_index, (day_key, _) in enumerate(DAYS, start=1):
            cell = (schedule.cells.get(slot.key, {}) or {}).get(day_key, {}) or {}
            blocked = bool(cell.get("blocked"))

            if slot.allow_block and blocked:
                empty_cells.append((row_index, col_index))
                row.append("")
                continue

            staff_ids = [int(x) for x in (cell.get("staff") or []) if str(x).isdigit()]
            names = [staff_map.get(i, "") for i in staff_ids if staff_map.get(i, "")]
            names_list = [str(n) for n in names]

            if kind == "pt":
                pt_time = (cell.get("pt_time") or "").strip()

                # Empty -> use same empty cell color
                if not names_list:
                    empty_cells.append((row_index, col_index))
                    row.append("")
                    continue

                row.append(Paragraph(_indent_each_line(_format_pt_names(names_list, pt_time)), td_pt_style))
                continue

            if not names_list:
                empty_cells.append((row_index, col_index))
                row.append("")
                continue

            row.append(Paragraph(_indent_each_line(_format_names(names_list)), td_style))

        data.append(row)

    col_widths = [shift_w] + [day_w] * 7
    table = Table(data, colWidths=col_widths, repeatRows=1)

    st = TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("ALIGN", (1, 1), (-1, -1), "LEFT"),

        ("BACKGROUND", (0, 0), (-1, 0), header_row_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), header_row_text),

        # default: very tight table (less wide)
        ("LEFTPADDING", (0, 0), (-1, -1), cell_pad_x),
        ("RIGHTPADDING", (0, 0), (-1, -1), cell_pad_x),

        # Shift column: small LEFT padding only (right stays tight)
        ("LEFTPADDING", (0, 0), (0, -1), shift_left_pad),
        ("RIGHTPADDING", (0, 0), (0, -1), cell_pad_x),

        # Header row same height as body rows
        ("TOPPADDING", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),

        # Body rows
        ("TOPPADDING", (0, 1), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 10),

        ("INNERGRID", (0, 0), (-1, -1), 0.45, border_soft),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [stripe_a, stripe_b]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, divider_color),
    ])

    sat_col = 1 + 5
    sun_col = 1 + 6
    st.add("BACKGROUND", (sat_col, 1), (sat_col, -1), weekend_bg)
    st.add("BACKGROUND", (sun_col, 1), (sun_col, -1), weekend_bg)

    row_i = 1
    for slot in visible_slots:
        kind = _slot_kind(slot)

        if kind == "off":
            row_bg = offday_row_bg
            st.add("BACKGROUND", (0, row_i), (-1, row_i), row_bg)
        elif kind == "leave":
            row_bg = leave_row_bg
            st.add("BACKGROUND", (0, row_i), (-1, row_i), row_bg)
        elif kind == "pt":
            row_bg = pt_row_bg
            st.add("BACKGROUND", (0, row_i), (-1, row_i), row_bg)
        else:
            row_bg = None

        if slot.allow_block:
            for day_idx, (day_key, _) in enumerate(DAYS, start=1):
                cell = (schedule.cells.get(slot.key, {}) or {}).get(day_key, {}) or {}
                if bool(cell.get("blocked")) and row_bg is not None:
                    st.add("BACKGROUND", (day_idx, row_i), (day_idx, row_i), row_bg)

        row_i += 1

    # PT empty cells: reddish background
    for (r, c) in pt_empty_cells:
        st.add("BACKGROUND", (c, r), (c, r), pt_empty_bg)

    # Empty cells: soft background (also overrides weekend for empty sat/sun)
    for (r, c) in empty_cells:
        st.add("BACKGROUND", (c, r), (c, r), empty_cell_bg)

    table.setStyle(st)

    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
    )

    header_to_table_gap = 16
    gap = 6

    header_card = _GradientRoundedCard(header_table, radius=5, top_hex=header_top_hex, bottom_hex=header_bottom_hex, stroke_color=None, stroke_width=0.0, inset=0.0, steps=90)
    header_card.hAlign = "CENTER"

    table_card = _RoundedCard(
        table,
        radius=5,
        fill_color=colors.white,
        stroke_color=border_soft,
        stroke_width=0.9,
        inset=0.0,
        shadow=True,
        shadow_dx=2.2,
        shadow_dy=-2.2,
        shadow_color=colors.black,
        shadow_alpha=0.10,
    )
    table_card.hAlign = "CENTER"

    story = [
        header_card,
        Spacer(1, header_to_table_gap),
        table_card,
    ]

    if schedule.notes.strip():
        story.append(Spacer(1, gap))
        notes_title = styles["Normal"].clone("pdf_notes_title")
        notes_title.fontName = bold_font
        notes_title.fontSize = 10.5
        notes_title.leading = 12.5
        notes_title.textColor = table_text

        notes_body = styles["Normal"].clone("pdf_notes_body")
        notes_body.fontName = body_font
        notes_body.fontSize = 10.0
        notes_body.leading = 12.8
        notes_body.textColor = table_text

        story.append(Paragraph("Notes", notes_title))
        story.append(Paragraph(schedule.notes, notes_body))

    # ===== Vertical centering (equal empty space top/bottom when possible) =====
    avail_h = page_h - top_margin - bottom_margin
    total_h = 0.0
    for f in story:
        try:
            _, h = f.wrap(avail_w, avail_h)
        except Exception:
            try:
                h = float(getattr(f, "height", 0) or 0)
            except Exception:
                h = 0.0
        total_h += float(h or 0.0)

    remaining = avail_h - total_h
    if remaining > 2.0:
        story.insert(0, Spacer(1, remaining / 2.0))

    doc.build(story)
    return buf.getvalue()


def build_png(*, schedule, slots, staff_map: dict[int, str], theme, dpi: int = 600, style: int = 1) -> bytes:
    # target DPI (what you want to return)
    dpi = max(200, min(int(dpi or 600), 900))

    # 1) Always generate the PDF first (so PNG can be identical to PDF)
    pdf_bytes = build_pdf(schedule=schedule, slots=slots, staff_map=staff_map, theme=theme, style=style)

    from io import BytesIO
    import math
    import os
    import shutil
    import subprocess
    import tempfile

    def _tighten_png_height(png_bytes: bytes, *, pad_dpi: int) -> bytes:
        # Crop ONLY vertical whitespace (top/bottom) based on non-white content
        from PIL import Image, ImageChops

        img = Image.open(BytesIO(png_bytes)).convert("RGB")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        diff = ImageChops.difference(img, bg).convert("L")

        mask = diff.point(lambda p: 255 if p > 10 else 0)
        bbox = mask.getbbox()
        if not bbox:
            return png_bytes

        _, top, _, bottom = bbox

        scale = pad_dpi / 150.0
        pad = int(max(8, 16 * scale))

        top = max(0, top - pad)
        bottom = min(img.size[1], bottom + pad)

        img = img.crop((0, top, img.size[0], bottom))

        out = BytesIO()
        img.save(out, format="PNG", dpi=(pad_dpi, pad_dpi), optimize=True)
        return out.getvalue()

    def _downsample_png(png_bytes: bytes, *, src_dpi: int, dst_dpi: int) -> bytes:
        if src_dpi <= dst_dpi:
            return png_bytes

        from PIL import Image

        img = Image.open(BytesIO(png_bytes)).convert("RGB")
        scale = dst_dpi / float(src_dpi)
        new_w = max(1, int(img.size[0] * scale))
        new_h = max(1, int(img.size[1] * scale))

        try:
            resample = Image.Resampling.LANCZOS
        except Exception:
            resample = Image.LANCZOS

        img = img.resize((new_w, new_h), resample=resample)

        out = BytesIO()
        img.save(out, format="PNG", dpi=(dst_dpi, dst_dpi), optimize=True)
        return out.getvalue()

    # ---- Safe render cap (NO ENV needed) ----
    # Free tier safe defaults (prevents 502/OOM). Tune here only.
    max_pixels = 26000000        # safer than 32M on free tier
    supersample = 1.25           # 1.0–1.5
    if supersample < 1.0:
        supersample = 1.0
    if supersample > 1.5:
        supersample = 1.5

    def _cap_render_dpi(*, w_pt: float, h_pt: float, render_dpi: int) -> int:
        zoom = render_dpi / 72.0
        px_w = int(w_pt * zoom)
        px_h = int(h_pt * zoom)
        pixels = int(px_w) * int(px_h)

        if pixels <= max_pixels:
            return render_dpi

        max_zoom = math.sqrt(max_pixels / float(max(w_pt * h_pt, 1.0)))
        capped = int(max(200, min(render_dpi, int(max_zoom * 72.0))))
        return capped

    # Mild supersample for sharper text
    render_dpi = int(min(1200, max(200, int(dpi * supersample))))

    last_error = None

    # --- A) PyMuPDF (fitz): best for Railway/Render ---
    try:
        import fitz  # type: ignore

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            page = doc.load_page(0)

            w_pt = float(page.rect.width)
            h_pt = float(page.rect.height)

            render_dpi2 = _cap_render_dpi(w_pt=w_pt, h_pt=h_pt, render_dpi=render_dpi)

            zoom = render_dpi2 / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            png = _tighten_png_height(pix.tobytes("png"), pad_dpi=render_dpi2)

            if render_dpi2 != dpi:
                png = _downsample_png(png, src_dpi=render_dpi2, dst_dpi=dpi)

            return png
        finally:
            try:
                doc.close()
            except Exception:
                pass
    except Exception as e:
        last_error = e

    # --- B) Ghostscript (if available) ---
    gs = shutil.which("gs")
    if gs:
        # A4 landscape is 842 x 595 points
        w_pt = 842.0
        h_pt = 595.0
        render_dpi2 = _cap_render_dpi(w_pt=w_pt, h_pt=h_pt, render_dpi=render_dpi)

        pdf_path = None
        out_tpl = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(pdf_bytes)
                f.flush()
                pdf_path = f.name

            out_tpl = os.path.join(tempfile.gettempdir(), f"schedule_{os.getpid()}_%03d.png")
            cmd = [
                gs,
                "-q",
                "-dSAFER",
                "-dBATCH",
                "-dNOPAUSE",
                "-sDEVICE=png16m",
                f"-r{render_dpi2}",
                "-dTextAlphaBits=4",
                "-dGraphicsAlphaBits=4",
                "-dFirstPage=1",
                "-dLastPage=1",
                f"-sOutputFile={out_tpl}",
                pdf_path,
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            page1 = out_tpl.replace("%03d", "001")
            with open(page1, "rb") as imgf:
                png = _tighten_png_height(imgf.read(), pad_dpi=render_dpi2)
                if render_dpi2 != dpi:
                    png = _downsample_png(png, src_dpi=render_dpi2, dst_dpi=dpi)
                return png
        except Exception as e:
            last_error = e
        finally:
            try:
                if pdf_path and os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except Exception:
                pass
            try:
                if out_tpl:
                    page1 = out_tpl.replace("%03d", "001")
                    if os.path.exists(page1):
                        os.remove(page1)
            except Exception:
                pass

    # --- C) pdf2image + poppler (if available) ---
    try:
        from pdf2image import convert_from_bytes  # type: ignore

        # A4 landscape is 842 x 595 points
        render_dpi2 = _cap_render_dpi(w_pt=842.0, h_pt=595.0, render_dpi=render_dpi)

        images = convert_from_bytes(
            pdf_bytes,
            dpi=render_dpi2,
            fmt="png",
            first_page=1,
            last_page=1,
            single_file=True,
        )
        out = BytesIO()
        images[0].save(out, format="PNG", dpi=(render_dpi2, render_dpi2), optimize=True)
        png = _tighten_png_height(out.getvalue(), pad_dpi=render_dpi2)
        if render_dpi2 != dpi:
            png = _downsample_png(png, src_dpi=render_dpi2, dst_dpi=dpi)
        return png
    except Exception as e:
        last_error = e

    raise RuntimeError(
        "PNG rendering failed.\n"
        "Fix options:\n"
        "  1) Recommended (works on Railway/Render): pip install PyMuPDF  (module name: fitz)\n"
        "  2) Or install Ghostscript (gs) on the server\n"
        "  3) Or install poppler-utils + pdf2image\n"
        "Tip: free tier usually works best with ?dpi=350–450. 600/800 may be auto-capped for safety.\n"
        f"Original error: {type(last_error).__name__}: {last_error}"
        if last_error
        else ""
    )
