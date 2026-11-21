# Diagramas

PNG para documentos y presentaciones. Cada uno tiene su versión en el documento donde se explica (en Mermaid, que
GitHub dibuja solo) y su fuente para regenerar la imagen en [`fuentes/`](fuentes/).

| Imagen | Qué muestra | Dónde se explica | Fuente |
|---|---|---|---|
| [contextoGeneral.png](contextoGeneral.png) | El sistema, quién lo usa (APK y web) y los servicios externos | [use-cases.md](../use-cases.md) | `fuentes/contexto.dot` |
| [diagramaDespliegue.png](diagramaDespliegue.png) | Producción: AWS EC2 + Caddy, Vercel, Neon, Render de respaldo y GitHub Actions | [despliegue.md](../despliegue.md), [architecture.md](../architecture.md) | `fuentes/despliegue.dot` |
| [diagramaComponentes.png](diagramaComponentes.png) | Capas del cliente Flutter y del backend | [architecture.md](../architecture.md) | `fuentes/componentes.dot` |
| [casosUso.png](casosUso.png) | 33 casos de uso con sus actores | [use-cases.md](../use-cases.md) | `fuentes/casos_uso.dot` |
| [diagramaDatos.png](diagramaDatos.png) | Modelo entidad-relación (23 tablas) | [data-model.md](../data-model.md) | Se genera desde el Mermaid de `data-model.md` |
| [diagramaSecuencia.png](diagramaSecuencia.png) | Registrar un gasto por texto, voz, recibo o SMS | [architecture.md](../architecture.md) | Mermaid de `architecture.md` (no cambió) |

## Regenerar

Necesita Graphviz (`dot`).

```bash
cd docs/diagramas/fuentes
dot -Tpng -Gdpi=150 contexto.dot    -o ../contextoGeneral.png
dot -Tpng -Gdpi=150 despliegue.dot  -o ../diagramaDespliegue.png
dot -Tpng -Gdpi=150 componentes.dot -o ../diagramaComponentes.png
dot -Tpng -Gdpi=110 casos_uso.dot   -o ../casosUso.png
python3 er_desde_markdown.py && dot -Tpng -Gdpi=110 datos.dot -o ../diagramaDatos.png
```

Al cambiar un diagrama, cambiar también su versión Mermaid en el documento, para que no se separen. El de datos
se genera del Mermaid de `data-model.md`, así que basta con editar ese.

Actualizados el 21 nov 2026, con la versión web, el despliegue en AWS y las tablas de planes, previstos, vacas,
apoyos y uso de IA.
