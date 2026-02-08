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
        ):
            super().__init__()
            self.flowable = flowable
            self.radius = radius
            self.fill_color = fill_color
            self.stroke_color = stroke_color
            self.stroke_width = stroke_width
            self.inset = inset
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
    header_font_size = _clamp(getattr(theme, "pdf_header_font_size", 15.0) or 15.0, 13.5, 17.0)
    week_font_size = _clamp(getattr(theme, "pdf_week_font_size", 10.5) or 10.5, 9.5, 12.0)
    th_font_size = _clamp(getattr(theme, "pdf_table_header_font_size", 10.3) or 10.3, 9.5, 12.0)
    td_font_size = _clamp(getattr(theme, "pdf_table_font_size", 10.0) or 10.0, 9.0, 11.5)

    # IMPORTANT: keep same size feel as week range and PT time
    subtext_size = _clamp(getattr(theme, "pdf_subtext_size", week_font_size) or week_font_size, 9.5, 12.0)
    td_pt_font_size = _clamp(getattr(theme, "pdf_table_pt_font_size", week_font_size) or week_font_size, 9.5, 12.0)

    # ===== Page size + margins (centered layout) =====
    page_w, page_h = landscape(A4)

    # wider + equal margins (gives same empty space around)
    margin = 12 * mm
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

    header_row_bg_hex = "#EEF2F7"
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

    header_row_bg_hex = _blend_hex(header_row_bg_hex, "#FFFFFF", 0.06)
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
        if len(names) == 1:
            return names[0]
        if len(names) == 2:
            return f"{names[0]} / {names[1]}"
        first_line = f"{names[0]} / {names[1]}"
        rest = "<br/>".join(names[2:])
        return first_line + "<br/>" + rest

    def _format_pt_names(names: list[str], pt_time: str) -> str:
        if not names:
            return ""
        if not pt_time:
            return _format_names(names)

        tagged = [f"{n} ({pt_time})" for n in names]
        if len(tagged) == 1:
            return tagged[0]
        if len(tagged) == 2:
            return f"{tagged[0]} / {tagged[1]}"
        first_line = f"{tagged[0]} / {tagged[1]}"
        rest = "<br/>".join(tagged[2:])
        return first_line + "<br/>" + rest

    # ===== Dynamic column widths (snug but stable) =====
    cell_pad_x = 8
    min_day_w = 90
    max_day_w = 150
    min_shift_w = 100
    max_shift_w = 180

    shift_max = pdfmetrics.stringWidth("Shift", bold_font, th_font_size)
    for slot in visible_slots:
        try:
            w = pdfmetrics.stringWidth(str(_label_clean(slot.label) or ""), bold_font, th_font_size)
            if w > shift_max:
                shift_max = w
        except Exception:
            pass
    shift_w = _clamp(shift_max + (cell_pad_x * 2) + 8, min_shift_w, max_shift_w)

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
        need = wd + wdt + 14
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
                first_line = preview.split("<br/>")[0]
                try:
                    w = pdfmetrics.stringWidth(first_line, body_font, td_font_size)
                    if w > day_max:
                        day_max = w
                except Exception:
                    pass

    day_w = _clamp(day_max + (cell_pad_x * 2) + 12, min_day_w, max_day_w)
    table_width = shift_w + (day_w * 7.0)

    # ===== Fit to page width (fix cutdown) =====
    if table_width > avail_w:
        day_w_fit = (avail_w - shift_w) / 7.0
        if day_w_fit < min_day_w:
            day_w = max(72.0, day_w_fit)
        else:
            day_w = min(day_w, day_w_fit)

        table_width = shift_w + (day_w * 7.0)
        if table_width > avail_w:
            scale = avail_w / float(max(table_width, 1.0))
            shift_w = max(80.0, shift_w * scale)
            day_w = max(72.0, day_w * scale)
            table_width = shift_w + (day_w * 7.0)

    # ===== Header band =====
    week_title = f"{schedule.week_start.strftime('%d %b %Y')} – {schedule.week_end().strftime('%d %b %Y')}"

    center_style = styles["Normal"].clone("pdf_header_center")
    center_style.fontName = bold_font
    center_style.fontSize = week_font_size
    center_style.leading = week_font_size + 1.8
    center_style.textColor = header_text
    center_style.alignment = 1

    right_style = styles["Normal"].clone("pdf_header_right")
    right_style.fontName = body_font
    right_style.fontSize = week_font_size
    right_style.leading = week_font_size + 1.8
    right_style.textColor = header_text
    right_style.alignment = 2

    header_table = Table(
        [[
            Paragraph("", right_style),
            Paragraph("Sam's Weekly Staff Schedule", center_style),
            Paragraph(week_title, right_style),
        ]],
        colWidths=[table_width * 0.18, table_width * 0.54, table_width * 0.28],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    # ===== Table styles =====
    th_day_style = styles["Normal"].clone("pdf_th_day")
    th_day_style.fontName = bold_font
    th_day_style.fontSize = th_font_size
    th_day_style.leading = th_font_size + 1.8
    th_day_style.textColor = header_row_text
    th_day_style.alignment = 0

    th_date_style = styles["Normal"].clone("pdf_th_date")
    th_date_style.fontName = body_font
    th_date_style.fontSize = subtext_size
    th_date_style.leading = subtext_size + 1.6
    th_date_style.textColor = colors.HexColor(table_subtext_hex)
    th_date_style.alignment = 2

    # Shift column should be bold like day
    shift_style = styles["Normal"].clone("pdf_shift")
    shift_style.fontName = bold_font
    shift_style.fontSize = th_font_size
    shift_style.leading = th_font_size + 2.0
    shift_style.textColor = header_row_text
    shift_style.alignment = 0

    td_style = styles["Normal"].clone("pdf_td")
    td_style.fontName = body_font
    td_style.fontSize = td_font_size
    td_style.leading = td_font_size + 2.4
    td_style.textColor = table_text

    td_pt_style = styles["Normal"].clone("pdf_td_pt")
    td_pt_style.fontName = body_font
    td_pt_style.fontSize = td_pt_font_size
    td_pt_style.leading = td_pt_font_size + 2.2
    td_pt_style.textColor = table_text

    header = [Paragraph("Shift", shift_style)]
    inner_day_w = max(10.0, day_w - (cell_pad_x * 2))
    for h in header_cells:
        parts = [p.strip() for p in str(h).splitlines() if p.strip()]
        day = parts[0] if parts else ""
        date_txt = _short_date(parts[1]) if len(parts) >= 2 else ""

        cell_tbl = Table(
            [[
                Paragraph(day, th_day_style),
                Paragraph(date_txt, th_date_style),
            ]],
            colWidths=[inner_day_w * 0.34, inner_day_w * 0.66],
        )
        cell_tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
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
        row = [Paragraph(_label_clean(slot.label), shift_style)]
        kind = _slot_kind(slot)
        row_kind_by_row[row_index] = kind

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

                row.append(Paragraph(_format_pt_names(names_list, pt_time), td_pt_style))
                continue

            if not names_list:
                empty_cells.append((row_index, col_index))
                row.append("")
                continue

            row.append(Paragraph(_format_names(names_list), td_style))

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

        ("LEFTPADDING", (0, 0), (-1, -1), cell_pad_x),
        ("RIGHTPADDING", (0, 0), (-1, -1), cell_pad_x),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),

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

    header_to_table_gap = 10
    gap = 4

    header_card = _GradientRoundedCard(header_table, radius=5, top_hex=header_top_hex, bottom_hex=header_bottom_hex, stroke_color=None, stroke_width=0.0, inset=0.0, steps=90)
    header_card.hAlign = "CENTER"

    table_card = _RoundedCard(table, radius=5, fill_color=colors.white, stroke_color=border_soft, stroke_width=0.9, inset=0.0)
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
