# Abra Travel

> Abra Travel responde en segundos las consultas de viajeros a las agencias de turismo, empezando por Cusco, con sus propios precios y en el idioma de cada viajero.

**El nombre:** el abra es el punto más alto de un trek (como el abra Salkantay) y viene de "abrir": abre cada conversación con el viajero.

Proyecto final de la Diplomatura de Ciencia de Datos para las Ciencias Sociales y la Gestión Pública (Q-Lab PUCP, 2026).

## Qué hace

1. La agencia pega el mensaje del viajero, en cualquier idioma.
2. El modelo extrae su perfil (personas, mes, días, trek, nivel, presupuesto) como salida estructurada.
3. El código elige opciones del **tarifario de la agencia** y calcula precios, total y depósito. El modelo nunca calcula precios.
4. Se buscan en la base de conocimiento (`data/knowledge/`, con fuentes y fechas) los fragmentos del trek y de las condiciones de reserva.
5. El modelo redacta un borrador corto en el idioma del viajero, y un control revisa en código que no haya precios inventados, que esté en el idioma correcto y que tenga menos de 150 palabras.
6. El vendedor revisa, edita y lo abre en WhatsApp con un clic.

Las reglas de la respuesta salen de una prueba de cliente misterioso con 6 agencias de Cusco (`docs/research/cliente_misterioso.md`).

## Cómo correrlo

```bash
pip install -r requirements.txt
cp .env.example .env      # pon tu GEMINI_API_KEY (https://aistudio.google.com/apikey)
streamlit run app/app.py  # y abre http://localhost:8501
```

- Proveedor: Gemini por defecto. Para usar Claude, pon `LLM_PROVIDER=claude` y `ANTHROPIC_API_KEY` en `.env`.
- Pruebas (no llaman a la API): `python -m unittest discover tests`
- Probar con el modelo real desde la terminal: `python scripts/probar_consultas.py`

## Estructura

| Carpeta | Qué contiene |
| --- | --- |
| `app/` | App web en Streamlit: "Nueva consulta" y "Mi agencia" |
| `ai/` | Esquemas (pydantic), conexión con el modelo, instrucciones, búsqueda y flujo principal |
| `core/` | Cotización con el tarifario y enlace de WhatsApp |
| `data/` | Tarifario demo, precios de mercado, base de conocimiento de Cusco y de Huaraz |
| `docs/` | Fuentes de precios e investigación (evidencia pública, cliente misterioso, verificación oficial) |
| `evaluacion/` | 20 consultas sintéticas para evaluar las respuestas |
| `scripts/` | Análisis de precios (genera el tarifario) y prueba con el modelo real |
| `tests/` | Pruebas automáticas |

## Qué sigue

1. **Cusco**: trekking (Salkantay, Camino Inca, Lares, Choquequirao, Inca Jungle).
2. **Huaraz, Arequipa y Puno**: otros destinos de aventura y naturaleza del Perú.
3. **Departamentos con boleto turístico (Ley 32586)**.
4. **Latinoamérica**.

Un destino nuevo es solo una carpeta nueva de conocimiento más el tarifario de la agencia: `data/knowledge_huaraz/` (Santa Cruz y Laguna 69) ya tiene el mismo formato que la de Cusco, sin cambiar el código.

## Riesgos

- **El modelo puede equivocarse.** Por eso los precios los calcula el código, un control revisa el borrador y el vendedor siempre lo revisa antes de enviarlo.
- **Las reglas cambian** (permisos, entradas a Machu Picchu, horarios). Cada archivo de conocimiento tiene fecha y fuentes, y hay que revisarlo cada temporada.
- **Límites de la capa gratuita de Gemini**: 20 solicitudes por día y por modelo. Cada consulta usa 2.
- **Marca:** Abra ya se usa en otros rubros de software (criptomonedas, gestión empresarial); antes de lanzar habría que registrar la marca en Indecopi.

Licencia: [MIT](LICENSE).
