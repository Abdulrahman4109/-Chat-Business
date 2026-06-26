from xml.sax.saxutils import escape as xml_escape

from .models import CalculationResult, FinancialData


def generate_financial_roadmap(data: FinancialData, calc: CalculationResult) -> str:
    cells = []
    cid = 2
    Y1 = 45
    Y2 = 195

    def add_box(label, val, x, y, color, width=180, height=72, val_size=16, raw_val=False):
        nonlocal cid
        safe_label = xml_escape(label).upper()
        safe_val = val if raw_val else xml_escape(val)
        cells.append(
            f'    <mxCell id="{cid}" '
            f'value="&lt;font color=&quot;#C9A4FF&quot; style=&quot;font-size:11px&quot;&gt;{safe_label}&lt;/font&gt;&lt;br&gt;&lt;b&gt;&lt;font style=&quot;font-size:{val_size}px&quot;&gt;{safe_val}&lt;/font&gt;&lt;/b&gt;" '
            f'style="rounded=1;whiteSpace=wrap;fillColor={color};fontColor=#F3EEFF;fontSize=12;arcSize=10;html=1;verticalAlign=middle;align=center;overflow=hidden;" '
            f'vertex="1" parent="1">\n'
            f'      <mxGeometry x="{x}" y="{y}" width="{width}" height="{height}" as="geometry" />\n'
            f"    </mxCell>"
        )
        cid += 1
        return cid - 1

    def add_edge(src, dst, extra_style="", exit_x=1, exit_y=0.5, entry_x=0, entry_y=0.5):
        nonlocal cid
        cells.append(
            f'    <mxCell id="{cid}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;'
            f'exitX={exit_x};exitY={exit_y};exitDx=0;exitDy=0;'
            f'entryX={entry_x};entryY={entry_y};entryDx=0;entryDy=0;'
            f'strokeColor=#C9A4FF;strokeWidth=2;{extra_style}" '
            f'edge="1" parent="1" source="{src}" target="{dst}">\n'
            f'      <mxGeometry relative="1" as="geometry" />\n'
            f"    </mxCell>"
        )
        cid += 1

    def signed_pos(val):
        if val is None:
            return ""
        s = format_val(val)
        return f"+{s}" if val > 0 else s

    def signed_neg(val):
        if val is None:
            return ""
        s = format_val(val)
        return f"-{s}" if val > 0 else s

    def row_positions(count):
        gap = 60
        bw = min(180, (900 - (count - 1) * gap) // count)
        total = count * bw + (count - 1) * gap
        start = 40 + (900 - total) // 2
        return [start + i * (bw + gap) for i in range(count)], bw

    has_extra = data.extra_income is not None and data.extra_income > 0
    has_debts = data.current_debts is not None and data.current_debts > 0
    net = calc.net_monthly_savings
    has_net = net is not None

    ids = {}

    # === ROW 1: Income → Expenses → [Extra] → Net Savings ===
    r1_keys = []
    if data.monthly_income is not None:
        r1_keys.append("income")
    if data.monthly_expenses is not None:
        r1_keys.append("expenses")
    if has_extra:
        r1_keys.append("extra_income")
    if has_net:
        r1_keys.append("net_savings")

    if r1_keys:
        xs, bw = row_positions(len(r1_keys))
        for i, k in enumerate(r1_keys):
            if k == "income":
                ids[k] = add_box("Income", signed_pos(data.monthly_income), xs[i], Y1, "#8E3DFF", bw)
            elif k == "expenses":
                ids[k] = add_box("Expenses", signed_neg(data.monthly_expenses), xs[i], Y1, "#E35CFF", bw)
            elif k == "extra_income":
                ids[k] = add_box("Extra Income", signed_pos(data.extra_income), xs[i], Y1, "#8E3DFF", bw)
            elif k == "net_savings":
                net_color = "#E35CFF" if net < 0 else "#B56CFF"
                ids[k] = add_box("Net Savings", f"= {format_val(net)}", xs[i], Y1, net_color, bw)

    # === ROW 2: Savings → [Debts] → Goal → Still Needed → Timeline ===
    r2_keys = []
    if data.current_savings is not None:
        r2_keys.append("savings")
    if has_debts:
        r2_keys.append("debts")
    if data.goal_price is not None:
        r2_keys.append("goal")
    if data.current_savings is not None and data.goal_price is not None:
        r2_keys.append("needed")
    if calc.duration_display:
        r2_keys.append("timeline")

    if r2_keys:
        xs, bw = row_positions(len(r2_keys))
        for i, k in enumerate(r2_keys):
            if k == "savings":
                ids[k] = add_box("Current Savings", format_val(data.current_savings), xs[i], Y2, "#C9A4FF", bw)
            elif k == "debts":
                ids[k] = add_box("Debts", signed_neg(data.current_debts), xs[i], Y2, "#E35CFF", bw)
            elif k == "goal":
                ids[k] = add_box("Goal", format_val(data.goal_price), xs[i], Y2, "#8E3DFF", bw)
            elif k == "needed":
                needed = max(calc.remaining, 0)
                n_color = "#E35CFF" if needed > 0 else "#C9A4FF"
                n_val = format_val(needed) if needed > 0 else "$0"
                ids[k] = add_box("Still Needed", n_val, xs[i], Y2, n_color, bw)
            elif k == "timeline":
                status_symbol = "\u2713" if calc.is_achievable else "\u2717"
                status_word = "Achievable" if calc.is_achievable else "Not Achievable"
                tl_color = "#C9A4FF" if calc.is_achievable else "#E35CFF"
                tl_val = f"{calc.duration_display}&lt;br&gt;{status_symbol} {status_word}"
                ids[k] = add_box("Timeline", tl_val, xs[i], Y2, tl_color, bw, val_size=14, raw_val=True)

    # === EDGES ===
    for i in range(len(r1_keys) - 1):
        if r1_keys[i] in ids and r1_keys[i + 1] in ids:
            add_edge(ids[r1_keys[i]], ids[r1_keys[i + 1]])

    for i in range(len(r2_keys) - 1):
        if r2_keys[i] in ids and r2_keys[i + 1] in ids:
            add_edge(ids[r2_keys[i]], ids[r2_keys[i + 1]])

    if "net_savings" in ids and "needed" in ids:
        add_edge(
            ids["net_savings"], ids["needed"],
            exit_x=0.5, exit_y=1, entry_x=0.5, entry_y=0,
        )

    xml = f'''<mxGraphModel dx="0" dy="0" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="0" pageScale="1" pageWidth="1100" pageHeight="850" background="#070511">
  <root>
    <mxCell id="0" />
    <mxCell id="1" parent="0" />
{chr(10).join(cells)}
  </root>
</mxGraphModel>'''
    return xml


def format_val(value: float | None) -> str:
    if value is None:
        return ""
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.0f}"
