# Abra Travel

> Abra Travel prepara en segundos la respuesta a cada consulta de viajeros para las agencias de turismo, empezando por Cusco, con sus propios precios y en el idioma de cada viajero.

**El nombre:** el abra es el punto más alto de un trek (como el abra Salkantay) y viene de "abrir": abre cada conversación con el viajero.

Proyecto final de la Diplomatura de Ciencia de Datos para las Ciencias Sociales y la Gestión Pública (Q-Lab PUCP, 2026).

## Problema

- A los viajeros les cuesta entender qué incluye y qué no cada cotización (lo dicen las 2 respuestas de la encuesta); por eso el borrador siempre lo explica.
- De día, la agencia más rápida responde en menos de 1 hora; a medianoche, en la prueba de cliente misterioso, las agencias tardaron de 8 a 10 horas: el problema se concentra fuera de horario.
- Evidencia y sus límites (2 conversaciones informales, una encuesta con 2 respuestas y un cliente misterioso con 6 agencias): [`docs/research/`](docs/research/).

## Solución

Hoy el vendedor revisa y envía cada respuesta: por la mañana responde en minutos todas las consultas que llegaron de noche, antes que la competencia. El **modo nocturno** muestra, para las consultas que llegan fuera de horario, la primera respuesta segura que se enviaría sola (armada por código: precio desde el tarifario, qué incluye y lo que falta preguntar), y solo cuando el control no encontró problemas. El envío real con la API de WhatsApp Cloud es el siguiente paso.

## Qué hace

1. La agencia pega el mensaje del viajero, en cualquier idioma.
2. El modelo extrae su perfil (personas, mes, días, trek, nivel, presupuesto) como salida estructurada.
3. El código elige opciones del **tarifario de la agencia** y calcula precios, total y depósito. El modelo nunca calcula precios.
4. Se buscan en la base de conocimiento (`data/knowledge/`, con fuentes y fechas) los fragmentos del trek y de las condiciones de reserva.
5. El modelo redacta un borrador corto en el idioma del viajero, y un control revisa en código que no haya precios inventados, que esté en el idioma correcto y que tenga menos de 150 palabras.
6. El vendedor revisa, edita y lo abre en WhatsApp con un clic. Puede registrar la consulta como cotizada o reservada (solo su perfil, sin el mensaje ni el teléfono).
7. **Tablero:** consultas, tasa de cierre, sin respuesta y monto reservado, por mes del viaje, trek y país, con filtros por trek e idioma. En el demo usa **datos sintéticos** (`data/consultas_sinteticas.csv`, de `scripts/generar_consultas_sinteticas.py`) más las consultas registradas en la app.

![Nueva consulta: la respuesta lista para WhatsApp](docs/captura_1_consulta.png)

Las reglas de la respuesta salen de una prueba de cliente misterioso con 6 agencias de Cusco (`docs/research/cliente_misterioso.md`).

## Cómo correrlo

```bash
pip install -r requirements.txt
cp .env.example .env      # pon tu GEMINI_API_KEY (https://aistudio.google.com/apikey)
streamlit run app/app.py  # y abre http://localhost:8501
```

- Proveedor: Gemini por defecto. Para usar Claude, pon `LLM_PROVIDER=claude` y `ANTHROPIC_API_KEY` en `.env`.
- Modelos de Gemini: `GEMINI_MODEL=gemini-3.5-flash` (principal) y `GEMINI_MODEL_RESPALDO=gemini-3.5-flash-lite` (respaldo).
- **Cadena de respaldo:** si el modelo principal se queda sin cuota diaria (429) o sigue saturado (503), la misma consulta se repite con el de respaldo; si los dos fallan, la app muestra un ejemplo guardado de una consulta real (`data/ejemplo_guardado.json`) con un aviso claro. La app muestra qué modelo respondió.
- El botón "Usar mensaje de ejemplo" muestra ese resultado guardado sin llamar a la API. Para volver a generarlo: `python scripts/guardar_ejemplo.py` (2 llamadas).
- Pruebas (no llaman a la API): `python -m unittest discover tests`
- Probar con el modelo real desde la terminal: `python scripts/probar_consultas.py`

## Estructura

| Carpeta | Qué contiene |
| --- | --- |
| `app/` | App web en Streamlit: "Nueva consulta", "Mi agencia" y "Tablero". Diseño en `docs/diseno.md` |
| `ai/` | Esquemas (pydantic), conexión con el modelo, instrucciones, búsqueda y flujo principal |
| `core/` | Cotización con el tarifario, enlace de WhatsApp, respuesta del modo nocturno y agregaciones del Tablero |
| `data/` | Tarifario demo, precios de mercado, base de conocimiento de Cusco y de Huaraz |
| `docs/` | Fuentes de precios e investigación (evidencia pública, cliente misterioso, verificación oficial) |
| `evaluacion/` | 20 consultas sintéticas para evaluar las respuestas |
| `scripts/` | Análisis de precios (genera el tarifario), consultas sintéticas del Tablero y prueba con el modelo real |
| `tests/` | Pruebas automáticas |

## Qué sigue

1. **Cusco**: trekking (Salkantay, Camino Inca, Lares, Choquequirao, Inca Jungle).
2. **Huaraz, Arequipa y Puno**: otros destinos de aventura y naturaleza del Perú.
3. **Departamentos con boleto turístico (Ley 32586)**.
4. **Latinoamérica**.

Un destino nuevo es solo una carpeta nueva de conocimiento más el tarifario de la agencia: `data/knowledge_huaraz/` (Santa Cruz y Laguna 69) ya tiene el mismo formato que la de Cusco, sin cambiar el código.

En el producto:

- **Mapa de la ruta en la respuesta al viajero**: lo pidió la [conversación 2](docs/research/conversacion_2.md); los trazados de 3 rutas ya están en `data/rutas/`.

## Riesgos

- **El modelo puede equivocarse.** Por eso los precios los calcula el código, un control revisa el borrador y el vendedor siempre lo revisa antes de enviarlo.
- **Las reglas cambian** (permisos, entradas a Machu Picchu, horarios). Cada archivo de conocimiento tiene fecha y fuentes, y hay que revisarlo cada temporada.
- **Límites de la capa gratuita de Gemini**: 20 solicitudes por día y por modelo. Cada consulta usa 2. Por eso hay un modelo de respaldo y un ejemplo guardado.
- **Marca:** Abra ya se usa en otros rubros de software (criptomonedas, gestión empresarial); antes de lanzar habría que registrar la marca en Indecopi.

Licencia: [MIT](LICENSE).
