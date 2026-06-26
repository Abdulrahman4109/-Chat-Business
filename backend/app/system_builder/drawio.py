from xml.sax.saxutils import escape as xml_escape
from .models import SystemUnderstanding, RoiResult


def generate_system_diagram(understanding: SystemUnderstanding, roi: RoiResult | None = None) -> str:
    cells = []
    cid = 2

    def add_box(label, detail, x, y, w, h, color, font_color="#F3EEFF"):
        nonlocal cid
        safe_label = xml_escape(label)
        safe_detail = xml_escape(detail)
        value = f"<b>{safe_label}</b><br><font style='font-size:10px' color='#C9A4FF'>{safe_detail}</font>"
        cells.append(
            f'    <mxCell id="{cid}" '
            f'value="{value}" '
            f'style="rounded=1;whiteSpace=wrap;fillColor={color};fontColor={font_color};fontSize=12;arcSize=10;html=1;verticalAlign=middle;align=center;overflow=hidden;" '
            f'vertex="1" parent="1">\n'
            f'      <mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry" />\n'
            f"    </mxCell>"
        )
        cid += 1
        return cid - 1

    def add_edge(src, dst, label="", style=""):
        nonlocal cid
        safe_label = xml_escape(label)
        val_attr = f'value="{safe_label}" ' if label else ""
        cells.append(
            f'    <mxCell id="{cid}" '
            f'{val_attr}style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;'
            f'strokeColor=#B56CFF;strokeWidth=2;fontColor=#C9A4FF;fontSize=10;{style}" '
            f'edge="1" parent="1" source="{src}" target="{dst}">\n'
            f'      <mxGeometry relative="1" as="geometry" />\n'
            f"    </mxCell>"
        )
        cid += 1

    entities = understanding.entities
    users = understanding.users
    workflows = understanding.workflows

    start_x = 60
    start_y = 60
    box_w = 170
    box_h = 60
    gap_x = 220
    gap_y = 120

    entity_ids = {}

    for i, ent in enumerate(entities):
        col = i % 4
        row = i // 4
        x = start_x + col * gap_x
        y = start_y + row * gap_y
        attrs_summary = ", ".join(a.name for a in ent.attributes[:4])
        if len(ent.attributes) > 4:
            attrs_summary += "..."
        detail = attrs_summary if attrs_summary else ent.description[:40]
        entity_ids[ent.name] = add_box(ent.name, detail, x, y, box_w, box_h, "#8E3DFF")

    user_y = start_y + max(len(entities), 1) * gap_y + 40
    user_ids = {}
    for i, role in enumerate(users):
        x = start_x + i * gap_x
        perms = ", ".join(role.permissions[:3]) if role.permissions else role.description[:40]
        user_ids[role.name] = add_box(role.name, perms, x, user_y, box_w, box_h, "#E35CFF")

    wf_y = user_y + 120
    wf_ids = {}
    for i, wf in enumerate(workflows):
        x = start_x + i * gap_x
        steps_summary = f"{len(wf.steps)} steps" if wf.steps else wf.description[:40]
        wf_ids[wf.name] = add_box(wf.name, steps_summary, x, wf_y, box_w, box_h, "#B56CFF")

    for ent in entities:
        src = entity_ids.get(ent.name)
        if src is None:
            continue
        for rel in ent.relationships:
            dst = entity_ids.get(rel.target_entity)
            if dst:
                add_edge(src, dst, rel.type)

    for role in users:
        src = user_ids.get(role.name)
        if src is None:
            continue
        for ent_name in entity_ids:
            dst = entity_ids[ent_name]
            add_edge(src, dst, "access")

    for wf in workflows:
        src = wf_ids.get(wf.name)
        if src is None:
            continue
        for ent_name in wf.entities_involved:
            dst = entity_ids.get(ent_name)
            if dst:
                add_edge(src, dst, "uses")

    roi_ids = {}
    if roi and roi.is_profitable:
        roi_y = wf_y + 140
        cost_str = f"${roi.development_cost:,.0f}"
        ret_str = f"${roi.expected_monthly_return:,.0f}/mo"
        time_str = roi.duration_display
        roi_ids["cost"] = add_box("Development Cost", cost_str, start_x, roi_y, box_w, box_h, "#E35CFF")
        roi_ids["return"] = add_box("Monthly Return", ret_str, start_x + gap_x, roi_y, box_w, box_h, "#8E3DFF")
        roi_ids["timeline"] = add_box("ROI Timeline", time_str, start_x + 2 * gap_x, roi_y, box_w, box_h, "#B56CFF")
        if "cost" in roi_ids and "return" in roi_ids:
            add_edge(roi_ids["cost"], roi_ids["return"], "funds")
        if "return" in roi_ids and "timeline" in roi_ids:
            add_edge(roi_ids["return"], roi_ids["timeline"], "recoup")

    xml = f'''<mxGraphModel dx="0" dy="0" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="0" pageScale="1" pageWidth="1200" pageHeight="900" background="#070511">
  <root>
    <mxCell id="0" />
    <mxCell id="1" parent="0" />
{chr(10).join(cells)}
  </root>
</mxGraphModel>'''
    return xml


def generate_erd_diagram(understanding: SystemUnderstanding) -> str:
    return generate_system_diagram(understanding)


def generate_flowchart_diagram(understanding: SystemUnderstanding) -> str:
    cells = []
    cid = 2

    def add_box(label, x, y, w, h, color):
        nonlocal cid
        value = xml_escape(label)
        cells.append(
            f'    <mxCell id="{cid}" '
            f'value="{value}" '
            f'style="rounded=1;whiteSpace=wrap;fillColor={color};fontColor=#F3EEFF;fontSize=12;arcSize=10;html=1;verticalAlign=middle;align=center;overflow=hidden;" '
            f'vertex="1" parent="1">\n'
            f'      <mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry" />\n'
            f"    </mxCell>"
        )
        cid += 1
        return cid - 1

    def add_edge(src, dst, label=""):
        nonlocal cid
        safe = xml_escape(label)
        val = f'value="{safe}" ' if label else ""
        cells.append(
            f'    <mxCell id="{cid}" '
            f'{val}style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;'
            f'strokeColor=#B56CFF;strokeWidth=2;fontColor=#C9A4FF;fontSize=10;" '
            f'edge="1" parent="1" source="{src}" target="{dst}">\n'
            f'      <mxGeometry relative="1" as="geometry" />\n'
            f"    </mxCell>"
        )
        cid += 1

    ids = {}
    y = 60
    for i, wf in enumerate(understanding.workflows):
        x = 60 + i * 300
        ids[wf.name] = add_box(wf.name, x, y, 220, 50, "#8E3DFF")
        for j, step in enumerate(wf.steps):
            sy = y + 80 + j * 70
            sid = add_box(f"{j+1}. {step.name}", x + 25, sy, 170, 50, "#B56CFF")
            if j > 0:
                prev_id = ids.get(f"{wf.name}_step_{j-1}")
                if prev_id:
                    add_edge(prev_id, sid)
            ids[f"{wf.name}_step_{j}"] = sid

    xml = f'''<mxGraphModel dx="0" dy="0" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="0" pageScale="1" pageWidth="1200" pageHeight="900" background="#070511">
  <root>
    <mxCell id="0" />
    <mxCell id="1" parent="0" />
{chr(10).join(cells)}
  </root>
</mxGraphModel>'''
    return xml
