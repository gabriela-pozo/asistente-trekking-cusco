# Prueba de cliente misterioso

> **Advertencia:** es una prueba **pequeña e ilustrativa**, con 6 agencias, un solo mensaje y una sola noche. No es una muestra representativa de las agencias de trekking del Cusco, y sus cifras no se pueden generalizar. Sirve para ver cómo es en la práctica la primera respuesta a un turista, no para medir al mercado.

Datos: [`cliente_misterioso.csv`](cliente_misterioso.csv). Hay una fila por agencia, identificada solo con un código (A, B, D, E, J, L) y su tamaño aproximado (2 grandes, 2 medianas, 2 pequeñas).

## Método

- **Canal:** WhatsApp, el canal donde los turistas consultan a las agencias.
- **Cuándo:** la noche del 9 al 10 de noviembre de 2026, entre las 11:55 p. m. y las 12:07 a. m. (hora de Lima).
- **Mensaje:** el mismo para todas las agencias, en inglés:

  > Hi! We are 2 friends planning to visit Cusco in late March. Is the Salkantay trek to Machu Picchu possible in 4 or 5 days? How much would it cost per person and what is included? Thanks!

  El mensaje deja datos sin decir a propósito (fechas exactas, nivel de servicio, condición física, si tienen equipo), para ver si la agencia pregunta.
- **Qué se midió:**
  - minutos hasta la primera respuesta humana (sin contar respuestas automáticas);
  - idioma de la respuesta;
  - si dio el precio en el mismo chat;
  - si explicó qué incluye;
  - si hizo preguntas al turista;
  - si ofreció alternativas;
  - si mandó PDF o enlaces;
  - qué depósito pidió.
- **Ética:** después de la primera respuesta se envió a cada agencia un mensaje de cierre explicando que era una investigación universitaria y que no se haría una reserva. En el repositorio no hay nombres, teléfonos ni datos que identifiquen a las agencias.

## Hallazgos

| Qué | Resultado |
| --- | --- |
| Agencias que respondieron | **6 de 6** |
| Primera respuesta humana | **entre 8 y 10,5 horas** después del mensaje (de 496 a 629 minutos; mediana de unas 9,4 horas) |
| Hora de esa respuesta | entre las 8:23 y las 10:33 de la mañana siguiente |
| Respuesta automática al instante | 1 de 6, y fue en español a un mensaje en inglés |
| Respondieron en otro idioma | **2 de 6** contestaron en español a un mensaje escrito en inglés |
| Precio en el chat | 3 de 6 (US$ 695 a 755 por persona). **Las otras 3 no lo dieron en el chat**: lo mandaron solo en un PDF o un enlace |
| Explicaron qué incluye en el chat | 1 de 6 con una lista completa, 1 de forma parcial; el resto, solo en PDF o enlace, o nada |
| Hicieron preguntas al turista | **casi ninguna**: 1 de 6, y solo pidió un correo. Ninguna preguntó fechas exactas, condición física, nivel de servicio ni equipo |
| Mandaron PDF o enlaces | 5 de 6. Tres PDF pesaban entre 3 y 13 MB, y dos tenían 11 y 12 páginas |
| Ofrecieron alternativas | 3 de 6. Una ofreció un descuento por reservar ese año, otra un grupo privado o pequeño, y otra una fecha distinta (4 de abril, cuando se pidió fines de marzo) sin preguntar si servía |
| Precio del mismo trek | **de US$ 499 a 755** por persona, contando el chat y los PDF (5 de 6 dieron precio: A 750, B 695, D 499, E 755, L 580) |
| Qué no incluye | **Distinto en cada agencia** (ver la tabla de abajo) |
| Dijeron el depósito en el chat | 2 de 6 (US$ 200 y US$ 350 por persona; el de US$ 350 no reembolsable) |

### Qué no incluye cada cotización

Datos de los PDF y la web que mandaron las agencias. También están en `notas` de `data/precios_mercado.csv`.

| Agencia | Precio | No incluye |
| --- | --- | --- |
| A | US$ 750 | Bolsa de dormir (alquiler US$ 25), bastones (US$ 25), tren desde Hidroeléctrica (opcional, US$ 41); recargo de 5 % con tarjeta y 8 % con PayPal |
| B | US$ 695 (US$ 720 si se reserva en 2027) | No lo indicó en el chat |
| D | US$ 499 | Entrada a Mollepata y laguna Humantay (S/ 20), bolsa de dormir (alquiler US$ 30), bastones (US$ 20), primer desayuno y último almuerzo, Huayna Picchu |
| E | US$ 755 | Según su web: Huayna Picchu, primer desayuno y último almuerzo, seguro, propinas |
| L | US$ 580 | Bolsa de dormir, bastones, bus Consettur, Huayna Picchu (US$ 60), último almuerzo, seguro |

### Qué muestran

1. **Nadie respondió de noche.** El mensaje llegó cerca de la medianoche y la primera respuesta humana llegó a la mañana siguiente. Contando desde las 8:00, las agencias tardaron entre unos 20 minutos y 2,5 horas en responder. Un turista que escribe a varias agencias de noche, desde otro huso horario, espera toda la noche, y gana la que responda primero en la mañana.
2. **El idioma no siempre coincide.** 2 de 6 respondieron en español a un turista que escribió en inglés, y la única respuesta automática también fue en español.
3. **El precio cuesta encontrarlo.** La mitad no dio el precio en el chat. El turista tenía que abrir un PDF pesado o un enlace para saber cuánto cuesta, que era una de las dos preguntas del mensaje.
4. **Casi nadie pregunta.** El mensaje no decía fechas exactas, nivel de servicio ni condición física, y ninguna agencia preguntó por eso. Las cotizaciones se mandaron sin saber si encajaban con el turista.
5. **Comparar es difícil.** El mismo trek cuesta entre US$ 499 y 755, una diferencia de US$ 256 por persona, y cada agencia deja fuera cosas distintas: una cobra aparte la bolsa de dormir y los bastones, otra el bus Consettur, otra las entradas en Mollepata, otra el recargo por pagar con tarjeta. El precio más bajo no es necesariamente el más barato al final, y el turista no puede saberlo sin abrir y comparar varios PDF.
6. **Qué incluye queda poco claro en el chat.** Solo una agencia lo listó en el mensaje. Esto coincide con lo que se vio en [`evidencia_publica.md`](evidencia_publica.md) sobre cobros que el turista creía incluidos.

### Relación con el producto

Cada hallazgo corresponde a una parte del asistente:
- **Respuesta en minutos:** un borrador listo para que el vendedor solo revise y envíe.
- **Respuesta en el idioma del turista.**
- **Precio en el chat:** calculado por el código desde el tarifario.
- **Lista de lo que incluye y lo que no**, con el precio de cada adicional, para que el turista compare precios completos.
- **Datos que faltan:** se detectan y se proponen como preguntas.

## Límites

- **Solo 6 agencias**, elegidas por conveniencia, no al azar.
- **Un solo mensaje**, enviado a medianoche: mide la respuesta fuera de horario, no la respuesta en horario de oficina.
- **Una sola noche**, la del 9 al 10 de noviembre de 2026, en temporada baja.
- **Una sola consulta:** Salkantay para 2 personas, en inglés.
- **Horas aproximadas en dos agencias:**
  - En una, el chat solo dice "ayer", así que la hora de envío es aproximada.
  - En otra, el mensaje figura como editado y no se ve la hora original de la respuesta: se registró la hora de edición como límite superior.
- **Precios no comparables entre sí:** los precios dados no siempre dicen si son del Salkantay de 4 o de 5 días.
- **Solo la primera respuesta:** no se midió el resto de la conversación.
