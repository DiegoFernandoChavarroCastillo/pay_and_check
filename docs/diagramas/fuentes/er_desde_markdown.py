"""Genera datos.dot a partir del diagrama ER (mermaid) de docs/data-model.md, para que el PNG y el
documento no se separen. Uso: python3 er_desde_markdown.py && dot -Tpng -Gdpi=110 datos.dot -o ../diagramaDatos.png"""
import pathlib
import re

md = (pathlib.Path(__file__).parent / "../../data-model.md").read_text()
er = md.split("```mermaid", 1)[1].split("```", 1)[0]

rel = re.findall(r"^\s+(\w+) (\S+)--(\S+) (\w+) : \"([^\"]*)\"", er, re.M)
ent = re.findall(r"^\s+(\w+) \{\n(.*?)\n\s+\}", er, re.M | re.S)

out = [
    "// Generado por er_desde_markdown.py desde docs/data-model.md. No editar a mano.",
    "digraph datos {",
    '  graph [rankdir=LR, fontname="Helvetica", pad=0.3, nodesep=0.25, ranksep=0.9, bgcolor="white", concentrate=false];',
    '  node [shape=plain, fontname="Helvetica", fontsize=10];',
    '  edge [fontname="Helvetica", fontsize=8, color="#666666", arrowhead=crow, arrowtail=none, dir=both];',
]
for nombre, cuerpo in ent:
    filas = []
    for linea in cuerpo.strip().splitlines():
        partes = re.sub(r'"[^"]*"', "", linea).split()  # los comentarios entre comillas no van al PNG
        tipo, campo = partes[0], partes[1]
        claves = " ".join(p for p in partes[2:] if not p.startswith('"'))
        filas.append(
            f'<tr><td align="left">{campo}</td><td align="left"><font color="#777777">{tipo}</font></td>'
            + (f'<td align="left"><font color="#9370DB">{claves}</font></td></tr>' if claves else '<td> </td></tr>')
        )
    out.append(
        f'  {nombre} [label=<<table border="1" cellborder="0" cellspacing="0" cellpadding="3" color="#9370DB">'
        f'<tr><td colspan="3" bgcolor="#ECECFF"><b>{nombre}</b></td></tr>{"".join(filas)}</table>>];'
    )
for a, _, _, b, etiqueta in rel:
    out.append(f'  {a} -> {b} [label="{etiqueta}"];')
out.append("}")
(pathlib.Path(__file__).parent / "datos.dot").write_text("\n".join(out) + "\n")
print(len(ent), "tablas,", len(rel), "relaciones")
