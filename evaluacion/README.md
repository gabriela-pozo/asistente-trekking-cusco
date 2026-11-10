# Conjunto de evaluación: consultas de turistas (WhatsApp)

Este conjunto sirve para medir la calidad del asistente para agencias de trekking en Cusco
(consulta de WhatsApp → perfil estructurado del turista → opciones del tarifario → borrador de respuesta).

- Archivo: `consultas_evaluacion.csv` (20 consultas, UTF-8).
- Todas las consultas son **sintéticas**: no corresponden a personas reales.
- Fecha de referencia: noviembre de 2026 (por eso la mayoría de los viajes son en 2027).
- Hechos de contexto usados para las respuestas esperadas: el Camino Inca cierra todos los febreros;
  sus permisos son limitados y se agotan con meses de anticipación; Salkantay no necesita permiso;
  mediana de mercado ≈ US$ 670 (Salkantay 5 días) y ≈ US$ 810 (Camino Inca 4 días).

Distribución: 12 en inglés, 4 en español, 2 en portugués, 1 en francés, 1 en alemán.
Incluye casos difíciles: Camino Inca en febrero, grupo de 9, presupuesto de US$ 300,
"Machu Picchu walking", familia con niños y adultos mayores, mal de altura, mensajes vagos sin fecha,
permisos para la semana siguiente, precio en soles y un mensaje con errores y emojis.

## Columnas

| Columna | Significado |
|---|---|
| `id` | Identificador de la consulta (C01…C20). |
| `consulta` | Texto del mensaje tal como llegaría por WhatsApp. |
| `idioma_esperado` | Código ISO 639-1 del idioma del turista (`en`, `es`, `pt`, `fr`, `de`). La respuesta debe estar en este idioma. |
| `num_personas_esperado` | Número de viajeros (entero). Vacío si el mensaje no lo dice. |
| `mes_viaje_esperado` | Mes del viaje (1–12). Vacío si no se menciona o es ambiguo (p. ej. "enero o febrero"). |
| `treks_esperados` | Treks pedidos, separados por `;`, de: `salkantay`, `camino_inca`, `otro`. Vacío si no se menciona ninguno. |
| `nivel_esperado` | `economico`, `estandar` o `premium`. Vacío si el turista no da pistas claras. |
| `debe_advertir` | Nota breve de lo que una respuesta correcta **debe** advertir o aclarar. |
| `dificultad` | Dificultad del caso para el sistema: `facil`, `media` o `dificil`. |

Regla para los vacíos: si el valor esperado está vacío, lo correcto es que el sistema **tampoco** invente
un valor (debe dejarlo vacío / nulo). Extraer "2 personas" cuando el mensaje no lo dice cuenta como error.

## Método de puntuación (4 métricas)

1. **Extracción del perfil (%)**: para cada consulta se comparan 5 campos
   (idioma, num_personas, mes_viaje, treks, nivel) con lo esperado. `treks` se compara como conjunto
   (el orden no importa). Métrica = campos correctos / (20 × 5) × 100. Se puede reportar también por campo.
2. **Respuesta en el idioma del turista (%)**: % de borradores escritos en `idioma_esperado`
   (verificable con un detector de idioma o a mano).
3. **Precios inventados (conteo, meta = 0)**: número total de precios en los borradores que no
   están en el tarifario. La app ya marca estos precios; basta con sumar las marcas. Cualquier valor > 0 es un fallo grave.
4. **Advertencia requerida (%)**: un evaluador humano lee cada borrador y llena una columna
   `advierte_ok` con `si`/`no` según cumpla lo indicado en `debe_advertir`. Métrica = % de `si`.

Conviene desglosar las métricas por `dificultad` e `idioma_esperado` para ver dónde falla el sistema.

## Plan de ejecución (script a escribir)

1. Leer `consultas_evaluacion.csv` y cargar el `tarifario`, la `base` y el cliente `llm` igual que en la app.
2. Para cada fila, llamar `procesar_consulta(consulta, llm, base, tarifario)` capturando errores (una consulta fallida no debe detener la corrida).
3. Guardar por fila: el perfil extraído (5 campos), el borrador de respuesta y los precios marcados como no presentes en el tarifario.
4. Calcular automáticamente aciertos por campo, idioma detectado del borrador y número de precios inventados.
5. Escribir `resultados_evaluacion.csv` con `id`, valores esperados, valores obtenidos, aciertos, borrador y una columna vacía `advierte_ok`.
6. Llenar `advierte_ok` a mano (sí/no) y luego calcular las 4 métricas en un resumen final.
7. Fijar el modelo y la temperatura (idealmente 0) y anotarlos, para poder comparar corridas.
