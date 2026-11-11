# Evaluación reducida del asistente

**4 de 5 consultas sin ningún control activado** (ni controles de código ni diferencias entre el perfil extraído y lo esperado en `evaluacion/consultas_evaluacion.csv`). La que sí activó controles (C09) fue por 2 falsos positivos del control de depósito/saldo.

**Pero según la lectura a mano, solo 3 de 5 respuestas son correctas** (C10, C17, C16, las dos últimas con una omisión menor). C09 falla y C08 es parcial: los controles de código no detectan que el mensaje omita lo importante (que no hay permisos la próxima semana, o que se cotizó antes de pedir los datos).

**Cómo respondió cada una:** las 5 con el modelo principal (`gemini-3.5-flash`); ninguna usó el modelo de respaldo ni el ejemplo guardado. Se usaron 10 llamadas (2 por consulta), sin errores 429 ni 503 (los reintentos internos del cliente no se registran: si hubo alguno, no se ve aquí).

## Limitaciones

- 5 casos no son una evaluación estadística: no se pueden sacar porcentajes ni comparar versiones con esto.
- Es una sola corrida con temperatura 0.2: otra corrida puede dar otro resultado.
- Se evaluó con el modelo real, con el tarifario y la base de conocimiento de demostración.
- "Sin controles" no equivale a "respuesta buena": los controles solo miran precios, largo, idioma, depósito, cupo y pregunta final. Lo que el mensaje debía advertir se lee a mano (columna Lectura).
- La lectura a mano la hizo quien armó la evaluación, no un evaluador independiente.

## Resultados por consulta

### C09 — CON FALLAS

- **Consulta:** Hi! We arrive in Cusco next week and want to do the Inca Trail 4D, 2 people. Can you get us permits?
- **Idioma:** detectado `en` (esperado `en`); respuesta en `en`
- **Trek:** camino_inca; personas 2; mes 11
- **Opciones cotizadas por el código:** camino_inca_4d estandar US$ 840 pp / total US$ 1680; camino_inca_4d economico US$ 670 pp / total US$ 1340
- **Precios no autorizados (montos inventados):** ninguno
- **Límite de 150 palabras:** 142 palabras → cumple
- **Controles activados:** El depósito o saldo del mensaje (US$ 200) no coincide con ninguna opción. Depósito / saldo de cada opción: US$ 840 / US$ 840, US$ 670 / US$ 670.; Con varias opciones, el mensaje da un solo depósito o saldo sin decir de cuál. Di el de cada opción o escribe "50 % del total de la opción elegida".
- **Diferencias con lo esperado:** ninguna
- **Quién respondió:** gemini-3.5-flash (modelo real)
- **Debía advertir (CSV):** Permisos del Camino Inca se agotan con meses de anticipación; casi seguro no hay cupo; no prometer permisos; ofrecer Salkantay (no requiere permiso)
- **Advertencias del modelo para la agencia:** Verificar disponibilidad de permisos en el sistema oficial una vez que el cliente indique la fecha exacta.; Recordar al cliente que los permisos del Camino Inca son nominativos y no reembolsables ($200 USD pp del depósito).
- **Lectura a mano:** **FALLA (lectura a mano).** El mensaje no promete cupo y dice que la agencia confirmará en el sistema oficial, pero no cumple lo esperado: la persona llega la próxima semana y el mensaje no dice que casi seguro no hay permisos ni ofrece Salkantay como alternativa (solo lo menciona de pasada la advertencia interna). Los 2 controles activados son falsos positivos: el "US$ 200" es el monto no reembolsable correcto, pero el control lo lee como saldo, y el mensaje ya dice "50 % del total de la opción elegida". El perfil sí quedó bien (mes 11 resuelto desde "next week").

Mensaje generado:

> Hello! We would love to help you with your trip to Cusco.
> 
> Classic Inca Trail 4 days, standard level: US$ 840 per person (total US$ 1680).
> Classic Inca Trail 4 days, budget level: US$ 670 per person (total US$ 1340).
> 
> Includes: Inca Trail permit, bilingual guide, porters, meals during trek, Machu Picchu entrance, return train to Ollantaytambo, double tent and sleeping pad.
> Does not include: Sleeping bag rental, travel insurance, tips, Huayna Picchu.
> 
> Deposit is 50% of the total for the chosen option to reserve, with the balance due up to 30 days before the trek (US$ 200 per person of the deposit is non-refundable).
> Inca Trail permits have a daily quota, are nominal and non-refundable, and our agency will confirm availability in the official system.
> 
> What exact date do you plan to start the trek?
> Which service level do you prefer?

### C08 — sin controles

- **Consulta:** hey how much for treks?
- **Idioma:** detectado `en` (esperado `en`); respuesta en `en`
- **Trek:** ninguno en el perfil; personas None; mes None
- **Opciones cotizadas por el código:** inca_jungle_4d estandar US$ 490 pp / total US$ 980; choquequirao_4d estandar US$ 530 pp / total US$ 1060
- **Precios no autorizados (montos inventados):** ninguno
- **Límite de 150 palabras:** 133 palabras → cumple
- **Controles activados:** ninguno
- **Diferencias con lo esperado:** ninguna
- **Quién respondió:** gemini-3.5-flash (modelo real)
- **Debía advertir (CSV):** Faltan fechas, número de personas y trek; pedir datos antes de cotizar
- **Advertencias del modelo para la agencia:** Confirmar el número de personas, fechas exactas, trek preferido y nivel de servicio deseado con el cliente.; Verificar disponibilidad de entradas a Machu Picchu en el sistema oficial antes de efectuar la compra.; Recordar al cliente que servicios opcionales como Huayna Picchu o alquiler de bolsa de dormir se cotizan por separado.
- **Lectura a mano:** **PARCIAL (lectura a mano).** Cotiza antes de pedir los datos, que es lo contrario de lo esperado, y presenta "group of 2" como si el viajero lo hubiera dicho (no dijo cuántos son). Elige Inca Jungle y Choquequirao sin que el viajero haya pedido trek. Sí termina pidiendo trek, nivel, fechas y número de personas, y no hay precios inventados.

Mensaje generado:

> Hello! Here are two popular 4-day trek options:
> Inca Jungle to Machu Picchu, 4 days, standard level: US$ 490 per person (group of 2), total US$ 980.
> Choquequirao (round trip), 4 days, standard level: US$ 530 per person (group of 2), total US$ 1060.
> Includes: bilingual guide, initial transport, bike and helmet for descent, meals during trek, Machu Picchu entry, return train to Ollantaytambo, tourist hotel in double room.
> Excludes: travel insurance, tips, Huayna Picchu.
> Deposit of 50% of the total of the chosen option to reserve, with the balance due up to 30 days before the trek.
> Please note that Machu Picchu entries are nominal and only confirmed once purchased in the official system.
> Which trek and service level are you interested in? What exact dates and how many people are traveling?

### C10 — sin controles

- **Consulta:** Buenas, cuánto cuesta el Salkantay de 5 días en soles? Somos 3 y vamos en abril del próximo año
- **Idioma:** detectado `es` (esperado `es`); respuesta en `es`
- **Trek:** salkantay; personas 3; mes 4
- **Opciones cotizadas por el código:** salkantay_4d estandar US$ 580 pp / total US$ 1740; salkantay_5d estandar US$ 650 pp / total US$ 1950
- **Precios no autorizados (montos inventados):** ninguno
- **Límite de 150 palabras:** 143 palabras → cumple
- **Controles activados:** ninguno
- **Diferencias con lo esperado:** ninguna
- **Quién respondió:** gemini-3.5-flash (modelo real)
- **Debía advertir (CSV):** Tarifario en US$: dar precio en dólares; no inventar precio ni tipo de cambio en soles (si se menciona, que sea referencial)
- **Advertencias del modelo para la agencia:** Verificar la disponibilidad en el sistema oficial una vez que el cliente indique la fecha exacta en abril.; El cliente consultó precios en soles; la cotización está en USD, por lo que el vendedor debe confirmar el tipo de cambio aplicable si se requiere cobrar en PEN.
- **Lectura a mano:** **Correcta (lectura a mano).** Responde en español, da los precios en dólares del tarifario y no inventa tipo de cambio ni precio en soles; el aviso de lluvias de abril aparece. Detalle menor: no le dice al cliente de forma explícita que la tarifa es en dólares (solo la advertencia interna lo dice). Da 4 y 5 días aunque pidió 5.

Mensaje generado:

> ¡Hola! Con gusto les comparto la cotización para el trek de Salkantay para 3 personas en abril.
> Salkantay a Machu Picchu, 4 días, nivel estándar: US$ 580 por persona, total US$ 1740.
> Salkantay a Machu Picchu, 5 días, nivel estándar: US$ 650 por persona, total US$ 1950.
> Incluye: Guía bilingüe, transporte de ida, comidas durante el trek, entrada a Machu Picchu, tren de regreso a Ollantaytambo, carpa doble y colchoneta.
> No incluye: Bolsa de dormir (alquiler aparte), seguro de viaje, propinas y Huayna Picchu.
> El depósito es del 50 % del total de la opción elegida para reservar y el saldo se paga hasta 30 días antes del trek.
> Ese mes es temporada de lluvias en Cusco: hay que llevar ropa impermeable y los caminos pueden estar con barro.
> ¿Tienen una fecha exacta para su inicio en abril? ¿Qué nivel de servicio prefieren?

### C17 — sin controles

- **Consulta:** Olá! Somos 3 amigos do Brasil e queremos fazer a trilha Salkantay em julho de 2027. Qual o valor do pacote padrão?
- **Idioma:** detectado `pt` (esperado `pt`); respuesta en `pt`
- **Trek:** salkantay; personas 3; mes 7
- **Opciones cotizadas por el código:** salkantay_4d estandar US$ 580 pp / total US$ 1740; salkantay_5d estandar US$ 650 pp / total US$ 1950
- **Precios no autorizados (montos inventados):** ninguno
- **Límite de 150 palabras:** 143 palabras → cumple
- **Controles activados:** ninguno
- **Diferencias con lo esperado:** ninguna
- **Quién respondió:** gemini-3.5-flash (modelo real)
- **Debía advertir (CSV):** Julio es temporada alta: reservar con anticipación; responder en portugués
- **Advertencias del modelo para la agencia:** Confirmar la fecha exacta con los clientes para verificar disponibilidad de trenes e ingresos a Machu Picchu en el sistema oficial.; Verificar si las tarifas para julio de 2027 sufren algún ajuste antes de emitir la reserva final.
- **Lectura a mano:** **Correcta, con una omisión menor (lectura a mano).** Responde en portugués, con depósito y saldo correctos por opción. No dice que julio es temporada alta ni que conviene reservar con anticipación (esperado en el CSV).

Mensaje generado:

> Olá! Que ótimo receber o seu contato para realizar a trilha Salkantay.
> 
> Salkantay 4 dias, nível padrão: US$ 580 por pessoa (grupo de 3), total US$ 1740. Depósito de US$ 870 e saldo de US$ 870 até 30 dias antes do trek.
> Salkantay 5 dias, nível padrão: US$ 650 por pessoa (grupo de 3), total US$ 1950. Depósito de US$ 975 e saldo de US$ 975 até 30 dias antes do trek.
> 
> Inclui: guia bilíngue, transporte de ida, refeições durante o trek, entrada para Machu Picchu, trem de retorno a Ollantaytambo, barraca dupla e colchonete.
> 
> Não inclui: saco de dormir (aluguel à parte), seguro de viagem, gorjetas e Huayna Picchu.
> 
> A entrada para Machu Picchu é nominal e só fica confirmada quando a agência a compra no sistema oficial.
> 
> Vocês já têm uma data exata definida para a viagem em julho de 2027?

### C16 — sin controles

- **Consulta:** Hola, viajo sola a fines de enero o en febrero, quiero hacer algún trek de varios días que llegue a Machu Picchu, lo más económico posible. ¿Qué me recomiendan?
- **Idioma:** detectado `es` (esperado `es`); respuesta en `es`
- **Trek:** salkantay, camino_inca; personas 1; mes 1
- **Opciones cotizadas por el código:** salkantay_4d economico US$ 480 pp / total US$ 480; salkantay_5d economico US$ 540 pp / total US$ 540
- **Precios no autorizados (montos inventados):** ninguno
- **Límite de 150 palabras:** 145 palabras → cumple
- **Controles activados:** ninguno
- **Diferencias con lo esperado:** ninguna
- **Quién respondió:** gemini-3.5-flash (modelo real)
- **Debía advertir (CSV):** Camino Inca cerrado en febrero; temporada de lluvias; Salkantay como opción económica
- **Advertencias del modelo para la agencia:** Confirmar la fecha exacta del viaje con la viajera para verificar disponibilidad en el sistema oficial.; Recordar que si decide viajar en febrero, el Camino Inca está cerrado por mantenimiento, por lo que Salkantay es la mejor alternativa.
- **Lectura a mano:** **Correcta, con una omisión menor (lectura a mano).** Recomienda Salkantay económico y avisa de la temporada de lluvias. No le dice a la viajera que el Camino Inca está cerrado en febrero (solo la advertencia interna); como no pidió el Camino Inca por nombre, no es un error grave. El perfil tomó solo enero (mes 1) aunque escribió "enero o febrero".

Mensaje generado:

> ¡Hola! Con gusto te recomiendo la opción más económica para llegar caminando a Machu Picchu:
> 
> Salkantay a Machu Picchu, 4 días, nivel económico: US$ 480 por persona, total US$ 480.
> Salkantay a Machu Picchu, 5 días, nivel económico: US$ 540 por persona, total US$ 540.
> 
> Incluye: Guía bilingüe, transporte de ida, comidas durante el trek, entrada a Machu Picchu, tren de regreso a Ollantaytambo y campamentos básicos.
> 
> No incluye: Bolsa de dormir (alquiler aparte), seguro de viaje, propinas ni Huayna Picchu.
> 
> Se requiere un depósito del 50 % del total de la opción elegida para reservar y el saldo restante hasta 30 días antes del trek.
> 
> Toma en cuenta que en ese mes es temporada de lluvias en Cusco: hay que llevar ropa impermeable y los caminos pueden estar con barro.
> 
> ¿Cuál es tu fecha exacta de viaje? ¿Cuántos días disponibles tienes para el trek?
