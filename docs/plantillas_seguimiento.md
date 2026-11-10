# Plantillas de mensajes de seguimiento

Para un turista que recibió una cotización y no respondió. Son tres mensajes, uno por momento; si después del tercero no hay respuesta, no se escribe más.

**Reglas de las plantillas**
- **Cortas:** se leen en el celular sin abrir el mensaje completo.
- **Sin presión:** nada de "últimos cupos" ni "la oferta vence hoy", salvo que sea verdad. En el Camino Inca, avisar que los permisos se agotan sí es información útil, no presión.
- **Cada mensaje aporta algo:** una respuesta, un dato útil o una salida fácil, no solo "¿y?".
- **Se puede responder fácil:** con una palabra o un número.
- **Datos reales:** reemplazar lo que está entre `{llaves}` con datos de la cotización. Nunca poner un precio que no esté en el tarifario.

| Campo | Ejemplo |
| --- | --- |
| `{nombre}` | Emma |
| `{trek}` | Salkantay de 5 días |
| `{fecha}` | 14 de marzo |
| `{vendedor}` | Rosa, de Andes Trek Demo |

---

## 1. A las 24 horas: ¿llegó bien?

**Para qué:** confirmar que vio la cotización y ofrecer resolver dudas.

**Español**
> Hola {nombre}, soy {vendedor}. Te escribo solo para confirmar que te llegó la cotización del {trek} para el {fecha}. Si tienes alguna duda sobre el itinerario, la altura o qué incluye, con gusto te respondo por aquí. 🙂

**English**
> Hi {nombre}, this is {vendedor}. Just checking that you received the quote for the {trek} on {fecha}. If you have any questions about the itinerary, the altitude or what's included, I'm happy to help here. 🙂

---

## 2. A los 3 días: un dato útil

**Para qué:** aportar algo de valor sin repetir la cotización. Elegir **un** dato que encaje con el turista.

**Español**
> Hola {nombre}, un dato por si te sirve para decidir: {dato_util}. Si quieres, te ajusto la cotización (otras fechas, otro nivel o más personas). Sin compromiso.

**English**
> Hi {nombre}, one tip in case it helps you decide: {dato_util}. If you'd like, I can adjust the quote (different dates, another service level or more people). No obligation.

**Ejemplos de `{dato_util}`**, tomados de `data/knowledge/`:

| Situación | Español | English |
| --- | --- | --- |
| Viaja en temporada de lluvias | en marzo el Salkantay se hace bien, solo conviene llevar ropa impermeable y calzado ya usado | the Salkantay is very doable in March, just bring rain gear and broken-in boots |
| Pidió el Camino Inca | los permisos del Camino Inca son nominales y se agotan con meses de anticipación, así que conviene asegurar la fecha con tiempo | Inca Trail permits are issued by name and sell out months ahead, so it's worth securing the date early |
| Preguntó por equipo | la bolsa de dormir no está incluida, pero se puede alquilar con nosotros | the sleeping bag isn't included, but you can rent one from us |
| Viene de otra ciudad baja | conviene llegar a Cusco dos días antes para aclimatarse a la altura | it's best to arrive in Cusco two days early to adjust to the altitude |

---

## 3. A la semana: cierre amable

**Para qué:** dar una salida fácil y dejar la puerta abierta. Es el último mensaje.

**Español**
> Hola {nombre}, no quiero llenarte de mensajes, así que este es el último. Si ya organizaste tu trek, ¡que lo disfrutes mucho! Y si todavía lo estás pensando, aquí estoy para cuando quieras: solo responde este chat.

**English**
> Hi {nombre}, I don't want to fill up your inbox, so this is my last message. If you've already sorted out your trek, enjoy it! And if you're still deciding, I'm here whenever you're ready: just reply to this chat.

---

## Cuándo no enviar

- **Ya respondió**, aunque sea para decir que no.
- **Pidió que no le escriban más.**
- **La fecha del trek ya pasó**, o falta tan poco que no se puede organizar (en el Camino Inca, si ya no hay permisos para su fecha).
- **El tercer mensaje ya se envió.**
