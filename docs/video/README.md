# Video de respaldo (Plan B)

**Estado:** Pendiente: se graba el 11 de noviembre antes de la presentación; irá en Google Drive (acceso: cualquier persona con el enlace, rol lector).

Todavía no hay enlace.

## Qué muestra

De 60 a 90 segundos de grabación de pantalla del software real, con la voz de la autora:

1. **README** del repositorio: el problema y la idea en una pantalla.
2. **Demo con "Usar mensaje de ejemplo"**: el perfil del viajero, las opciones con precios del tarifario y el borrador listo para WhatsApp.
3. **Modo nocturno a las 00:07**: con la hora de llegada en 00:07, fuera del horario de atención, la app muestra la respuesta segura que se enviaría sola (simulación).
4. **Tablero**: Mi semana arriba y, debajo, consultas, tasa de cierre y monto reservado.

## Dónde está el código que lo produce

| Parte | Rutas |
|---|---|
| App (páginas Nueva consulta, Mi agencia y Tablero) | `app/app.py`, `app/estilo.css` |
| Modelo y control del borrador | `ai/pipeline.py`, `ai/llm.py`, `ai/prompts.py`, `ai/schemas.py`, `ai/knowledge.py` |
| Ejemplo guardado ("Usar mensaje de ejemplo") | `ai/ejemplo.py` |
| Tarifario, paquete y enlace de WhatsApp | `core/cotizacion.py`, `core/paquete.py`, `core/whatsapp.py` |
| Modo nocturno | `core/respuesta_nocturna.py` |
| Tablero y Mi semana | `core/tablero.py`, `core/mi_semana.py` |
| Webhook de WhatsApp (escrito y probado, no conectado en vivo) | `server/webhook.py` |

## Guion

| Tiempo | Pantalla | Qué se dice |
|---|---|---|
| 0:00 – 0:10 | README en GitHub | "Las agencias de trekking en Cusco tardan horas en responder por WhatsApp. Este asistente arma la respuesta en segundos." |
| 0:10 – 0:35 | Nueva consulta → "Usar mensaje de ejemplo" | "Uso el mensaje de ejemplo. Sale el perfil del viajero, las opciones con precios del tarifario de la agencia y el borrador listo para WhatsApp. El modelo no inventa precios: el código los revisa." |
| 0:35 – 0:55 | Hora de llegada 00:07, modo nocturno | "Si la consulta llega a las 00:07, fuera de horario, el asistente muestra la respuesta segura que se enviaría sola. Aquí es una simulación." |
| 0:55 – 1:20 | Tablero | "En el Tablero, Mi semana muestra la meta, el monto reservado y las cotizaciones por seguir. Debajo, consultas y tasa de cierre con datos sintéticos." |
| 1:20 – 1:30 | App completa | "Es el software real, funcionando. Gracias." |
