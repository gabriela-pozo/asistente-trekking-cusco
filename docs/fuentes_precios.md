# Fuentes y reglas de precios de "Andes Trek Demo"

"Andes Trek Demo" es una **agencia ficticia**. Su tarifario (`data/tarifario_demo.csv`) sirve para probar el asistente con precios realistas; no es la oferta de ninguna agencia real.

El tarifario no se escribe a mano: lo genera `scripts/analisis_precios.py` a partir de la investigación de mercado. Para regenerarlo:

```bash
python scripts/analisis_precios.py
```

La prueba `test_archivo_coincide_con_el_generador` falla si alguien edita el CSV a mano o cambia las reglas sin regenerarlo.

## De dónde vienen los datos

| Archivo | Qué contiene |
| --- | --- |
| `data/precios_mercado.csv` | 42 publicaciones de precios de grupo (Salkantay 4 y 5 días, Camino Inca clásico 4 días), consultadas el 2026-11-10. 39 se usan en el análisis: **13 por trek** |
| `data/extras_mercado.csv` | 7 precios de extras (Huayna Picchu y mejora a tren Vistadome) vistos en esas mismas páginas |

Hubo dos rondas de investigación el mismo día. La primera dejó 4 a 6 precios por trek; la segunda llevó la muestra a 13 por trek, sobre todo con webs propias de agencias de Cusco.

Solo se usan las filas con `incluir_en_analisis = si`. Se excluyeron:
- **Tierras Vivas, lista de precios del Camino Inca:** dice "2020". Su ficha vigente del tour sí está incluida.
- **Alpaca Expeditions en TourRadar:** la cabecera dice "desde US$ 595", pero las salidas reales muestran US$ 835.
- **Anywhere.com, Salkantay 4 días:** no dice la moneda, si el precio es por persona ni si es servicio de grupo.
- **Inkayni, Huayna Picchu:** el precio sale de una respuesta del operador de 2022.
- **CuscoPeru.com, Vistadome:** el precio no se leyó textualmente en la página.

Tampoco se registraron:
- **Nomades, Salkantay Express 4 días:** precios válidos "hasta el 31 de diciembre de 2024" y la actividad ya no se opera.
- **Bolivian Mountains:** el precio está solo en libras esterlinas.

### Criterios al anotar precios

- **Precio especial con fecha límite:** si la página muestra un precio especial con fecha límite (por ejemplo "US$ 695 hasta el 31/12/2026"), se anota el **precio regular**, porque el tarifario es para todo el año. Pasa con Salkantay Trekking (3 treks) y G Adventures.
- **Dos precios sin explicación:** si la página muestra dos precios juntos sin decir cuál es la oferta (por ejemplo "US$ 880 US$ 680"), se anota el destacado.
- **Precio por tamaño de grupo:** si la página da una tabla según el número de personas, se anota el precio "desde" que muestra la cabecera y la tabla queda en las notas.
- **Verificación en el texto original:** algunas páginas eran muy largas y en la primera lectura una parte (9 filas) se leyó a través de un resumen automático de la herramienta. El mismo día se volvieron a descargar esas 9 páginas (una vez cada una) y se buscó cada precio en el texto original: los 9 coinciden, así que siguen en el análisis. Esas filas dicen "verificado en el texto original" en `notas`. Se quitaron dos montos de alquiler de bolsa de dormir que no aparecían en el texto.

## Reglas para calcular el tarifario

| # | Regla | ¿Dato o supuesto? |
| --- | --- | --- |
| 1 | **Estándar** = mediana del mercado de cada trek, sin contar las filas premium, redondeada a la decena | Dato del mercado + decisión de método |
| 2 | **Salkantay 4 días:** si su mediana supera a la del de 5 días, se usa el estándar del de 5 días menos 10 % | Supuesto |
| 3 | **Económico** = estándar − 20 % | Supuesto |
| 4 | **Premium** = estándar + 60 % | Supuesto |
| 5 | **Descuento por grupo:** 4 % para 3 a 4 personas, 8 % para 5 o más. Una o dos personas pagan la tarifa base | Supuesto |
| 6 | **Camino Inca cerrado en febrero** (`meses_no_disponible = 2`) | Dato: cierre anual por mantenimiento (ver `data/knowledge/camino_inca.md`) |
| 7 | **Extras** = mediana de los precios encontrados, redondeada a múltiplos de 5 | Dato del mercado + decisión de método |
| 8 | **Tamaño máximo de grupo:** 16 en económico, 12 en estándar, 8 en premium | Supuesto, basado en rangos publicados (grupos de "hasta 8" a "hasta 20") |
| 9 | **Qué incluye cada nivel:** por ejemplo, la bolsa de dormir solo va incluida en premium | Supuesto: de 42 publicaciones solo 1 incluye la bolsa de dormir; 24 la excluyen y 17 no la mencionan |

Todos los precios se redondean a la decena (las mitades hacia arriba). Por eso el descuento por grupo efectivo puede quedar a menos de un punto del 4 % o del 8 %: en el Camino Inca estándar, 840 × 0,96 = 806,4, que queda en 810.

### Resultado

| Trek | Mediana del mercado (sin premium) | Estándar | Económico | Premium |
| --- | --- | --- | --- | --- |
| Salkantay 4 días | 595 (n = 13) | **600** | 480 | 960 |
| Salkantay 5 días | 674,5 (n = 12) | **670** | 540 | 1 070 |
| Camino Inca clásico 4 días | 835 (n = 13) | **840** | 670 | 1 340 |

| Extra | Precios encontrados | Precio en el tarifario |
| --- | --- | --- |
| Ingreso a Huayna Picchu | 70, 75, 75 | **US$ 75** por persona |
| Mejora a tren Vistadome en el regreso | 67, 80 | **US$ 75** por persona (no aplica a premium, que ya lo incluye) |

### Cambio respecto a la primera ronda

| Trek | Mediana con 4 a 6 precios | Mediana con 13 precios | Cambio | Estándar antes → ahora |
| --- | --- | --- | --- | --- |
| Salkantay 4 días | 690 | 595 | **−13,8 %** | 600 → 600 |
| Salkantay 5 días (sin premium) | 669 | 674,5 | +0,8 % | 670 → 670 |
| Camino Inca clásico 4 días | 812,5 | 835 | +2,8 % | 810 → 840 |

### La regla del Salkantay 4 días

En la primera ronda, con 5 precios, la mediana del de 4 días (US$ 690) salía más alta que la del de 5 días (US$ 669). Una agencia real no cobraría más por un día menos de guía, comida y campamento. La diferencia venía de qué publicaciones cayeron en la muestra: la de 4 días incluía ofertas con domos y un precio de Viator con comisión. Por eso se agregó la regla 2: tomar el de 5 días como ancla y fijar el de 4 días un 10 % más barato (670 − 10 % = 600).

Con 13 precios, la mediana del de 4 días bajó a US$ 595, ya por debajo de la del de 5 días. La regla **ya no se activa**, y el estándar sale directamente de la mediana (US$ 600). Que la regla antigua y los datos nuevos den el mismo número indica que la regla corregía bien el sesgo de una muestra chica.

La regla se mantiene en el código como protección si una muestra futura vuelve a dar ese resultado, y la prueba `test_regla_salkantay_4d_con_datos_de_prueba` la sigue comprobando con datos inventados.

### Comparación con el mercado

- El **premium** calculado (Salkantay 5 días: US$ 1 070) queda por debajo del único premium real encontrado: el Premium de Salkantay Trekking en TourRadar, a US$ 1 270, con comisión de plataforma incluida. Es razonable para una agencia pequeña que vende directo.
- El **económico** (Salkantay 5 días: US$ 540) queda por encima de las ofertas más baratas, como la versión "para mochileros" de Quechuas Expeditions a US$ 310 o SAP Adventures a US$ 420. Esas ofertas existen, pero el económico de la agencia demo no intenta competir con ellas.
- El **Camino Inca** es el trek con menos dispersión: de US$ 760 a 990. Todas las agencias cargan el mismo permiso, entrada y tren.

## Límites de estos datos

- **Las muestras siguen siendo chicas: 13 precios por trek** (12 en el Salkantay 5 días sin la fila premium). Ahora son más estables que con 4 a 6, pero no son una muestra aleatoria: salen de lo que aparece en buscadores, que favorece a las agencias con más presencia en internet.
- **Algunas agencias aparecen más de una vez:** Salkantay Trekking (4 filas, en su web y en TourRadar) y Quechuas Expeditions (4 filas). Son productos distintos, pero pesan más en la mediana.
- **9 de los 39 precios vienen de TourRadar.** Esos precios incluyen la comisión de la plataforma, así que la agencia recibe menos.
- **Tres precios vienen de fuentes secundarias.** Los dos de Viator no se leyeron en Viator, sino en reseñas de welcomeperutravel.com que enlazan a Viator: Bamba Travel (Salkantay 4 días, US$ 810) e Incredible Peru Tours (Camino Inca, US$ 860; Huayna Picchu, US$ 70). Uno de GetYourGuide se leyó en un blog (theabroadguide.com, Salkantay 4 días, US$ 410). Pueden estar desactualizados respecto al precio vigente en esas plataformas, y no siempre dicen "USD", solo "$".
- **Casi todos son precios "desde".** El precio real depende de la fecha, el tipo de habitación y el tamaño del grupo.
- **El nivel de servicio casi nunca está indicado.** Solo se marcó "premium", "superior", "estándar" o "mochilero" cuando lo decía la página; el resto quedó como `no_indicado`.
- **Los precios cambian.** Esta investigación es del 2026-11-10. Hay que repetirla al menos una vez por temporada.
