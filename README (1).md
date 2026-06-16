# Dashboard de Rotación de Inventario + Matriz de Decisiones — CL · MX · PE

App en Streamlit que analiza rotación de inventario para Chile, México y Perú,
**agrupando productos por modelo** (junta colores y deja "iPhone 13 128GB"),
con una pestaña dedicada a **teléfonos** (iPhone/Samsung) y un módulo de
**Matriz de Decisiones de marketing** (CR × Visitas × Stock) que cruza datos de
GA4 con stock y ventas.

## Archivos del proyecto

| Archivo | Para qué sirve |
|---|---|
| `app.py` | La aplicación principal |
| `matriz_logic.py` | Lógica de modelos, fusión de variantes y matriz (lo usa `app.py`) |
| `requirements.txt` | Librerías a instalar |

> **Importante:** `app.py` y `matriz_logic.py` deben estar en la **misma carpeta**
> (o el mismo repo de GitHub). La app importa el segundo.

## Instalación (una sola vez)

```bash
pip install -r requirements.txt
```

## Ejecutar localmente

```bash
streamlit run app.py
```

## Flujo semanal

1. Exporta de tus sistemas, por país:
   - **Stock actual** (Bsale)
   - **Detalle de ventas** (Bsale)
   - **GA4 visitas/conversiones** (opcional — solo para la Matriz de Decisiones)
2. En la barra lateral ajusta **fecha inicio / fin** del período.
3. Sube los archivos en el panel de cada país.
4. Revisa las 8 secciones y descarga los Excel (consolidado y/o matriz).

## Secciones

1. **Resumen Ejecutivo** — KPIs por país
2. **Comparativo** — CL vs MX vs PE
3. **Por Categoría** — rotación por tipo de producto
4. **Por Producto** — tabla dinámica (productos ya fusionados por modelo)
5. **Rotación Teléfonos** — iPhone y Samsung por línea de modelo
6. **Matriz de Decisiones** — bubble chart CR × Visitas, semáforo DOI, decisiones
7. **Alertas** — semáforo de clasificación + alertas operativas
8. **Recomendaciones** — tabla priorizada + estancados / alta rotación / capital inmovilizado

## Fusión de variantes (cambio clave)

El análisis ya **no separa por color**. Todos los colores de un mismo modelo y
capacidad se suman en una sola fila:

APPLE IPHONE 13 128GB NEGRO + ... ROJO + ... AZUL  ->  IPHONE 13 128GB

Esto aplica a toda la app. La capacidad (128GB) sí se mantiene porque diferencia
precio y rotación.

## Matriz de Decisiones — lógica

- **Cruce:** GA4 con stock/ventas por **línea de modelo** (iPhone 13, Galaxy S23…),
  no por SKU, porque los SKU no calzan entre sistemas y GA4 trae solo el nombre.
- **Eje X — CR%:** compras / visitas de GA4 (misma ventana). Corte de mediana en 0.85%.
- **Eje Y — Visitas:** escala lineal, corte en la mediana de los modelos que califican.
- **Filtros:** >=10 ventas/30d para calificar; se excluye stock <=3 con <100 visitas.
- **DOI (Días de Inventario)** = Stock x 30 / Ventas 30d. Semáforo: rojo <10, amarillo 10-30, verde >30.
- **Cuadrantes:** Escalar tráfico · Invertir en CR · Activar tráfico · Revisar/Liquidar.
- **Prioridad:** Crítica / Alta / Media / Baja según cuadrante x nivel de stock.

> Nota: tu archivo de ventas es de 7 días, así que las ventas a 30d se **proyectan**
> (x4.35). El CR usa los datos de GA4 tal cual (misma ventana), que es lo correcto.
> Si más adelante exportas ventas reales de 30 días, el DOI será exacto.

## Formato del archivo GA4 esperado

Columnas que la app reconoce automáticamente (con paso de mapeo manual por si cambian):
`Producto`, `Visitas (vistas)`, `Compras`, `CR % (compra/visita)`. Acepta `.xlsx` y `.csv`.

## Compartir con el equipo

Sube `app.py`, `matriz_logic.py` y `requirements.txt` a un repo de GitHub y
conéctalo a Streamlit Community Cloud (https://share.streamlit.io). Obtienes un
link web para todo el equipo.
