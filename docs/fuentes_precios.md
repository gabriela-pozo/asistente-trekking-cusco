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
| `data/precios_mercado.csv` | 17 publicaciones de precios de grupo (Salkantay 4 y 5 días, Camino Inca clásico 4 días), consultadas el 2026-11-10 |
| `data/extras_mercado.csv` | 7 precios de extras (Huayna Picchu y mejora a tren Vistadome) vistos en esas mismas páginas |

Solo se usan las filas con `incluir_en_analisis = si`. Se excluyeron:
- **Tierras Vivas, Camino Inca:** la lista de precios dice "2020".
- **Alpaca Expeditions en TourRadar:** la cabecera dice "desde US$ 595", pero las salidas reales muestran US$ 835.
- **Inkayni, Huayna Picchu:** el precio sale de una respuesta del operador de 2022.
- **CuscoPeru.com, Vistadome:** el precio no se leyó textualmente en la página, solo en un resumen automático.

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
| 9 | **Qué incluye cada nivel:** por ejemplo, la bolsa de dormir solo va incluida en premium | Supuesto, basado en que ninguna publicación la incluye en el servicio de grupo |

Todos los precios se redondean a la decena (las mitades hacia arriba). Por eso el descuento por grupo efectivo puede quedar a menos de un punto del 4 % o del 8 %: en el Camino Inca estándar, 810 × 0,96 = 777,6, que queda en 780.

### Resultado

| Trek | Mediana del mercado (sin premium) | Estándar | Económico | Premium |
| --- | --- | --- | --- | --- |
| Salkantay 4 días | 690 (n = 5) | **600** (regla 2) | 480 | 960 |
| Salkantay 5 días | 669 (n = 5) | **670** | 540 | 1 070 |
| Camino Inca clásico 4 días | 812,5 (n = 4) | **810** | 650 | 1 300 |

| Extra | Precios encontrados | Precio en el tarifario |
| --- | --- | --- |
| Ingreso a Huayna Picchu | 70, 75, 75 | **US$ 75** por persona |
| Mejora a tren Vistadome en el regreso | 67, 80 | **US$ 75** por persona (no aplica a premium, que ya lo incluye) |

### Por qué el Salkantay de 4 días cuesta menos que el de 5

En la muestra, la mediana del de 4 días (US$ 690) sale más alta que la del de 5 días (US$ 669). Una agencia real no cobraría más por un día menos de guía, comida y campamento. La diferencia viene de **qué publicaciones cayeron en cada muestra**, no de un costo real:
- La muestra de 4 días incluye ofertas con extras, como domos o un precio en Viator con comisión (US$ 810).
- La de 5 días tiene sobre todo ofertas básicas.

Con 5 precios por trek, una sola publicación mueve la mediana. Por eso se toma el de 5 días como ancla y el de 4 días se fija un 10 % más barato.

### Comparación con el mercado

- El **premium** calculado (Salkantay 5 días: US$ 1 070) queda por debajo del único premium real encontrado: el Premium de Salkantay Trekking en TourRadar, a US$ 1 270, con comisión de plataforma incluida. Es razonable para una agencia pequeña que vende directo.
- El **económico** (Salkantay 4 días: US$ 480) es cercano al precio más bajo del mercado (US$ 450, CondeTravel en TourRadar).

## Límites de estos datos

- **Las muestras son chicas: de 4 a 6 precios por trek.** La mediana es una referencia razonable, no una estadística confiable. Con un precio más o uno menos puede moverse US$ 20 a 50. Conviene ampliar la muestra antes de usar estos precios con una agencia real.
- **La mitad de los precios viene de TourRadar.** Esos precios incluyen la comisión de la plataforma, así que la agencia recibe menos.
- **Los precios de Viator vienen de una fuente secundaria.** No se leyeron en Viator, sino en reseñas de welcomeperutravel.com que enlazan a Viator: Bamba Travel (Salkantay 4 días, US$ 810), Incredible Peru Tours (Camino Inca, US$ 860; Huayna Picchu, US$ 70). La reseña puede estar desactualizada respecto al precio vigente en Viator, y además no dice "USD", solo "$".
- **Casi todos son precios "desde"** (13 de 17). El precio real depende de la fecha, el tipo de habitación y el tamaño del grupo.
- **El nivel de servicio casi nunca está indicado.** Solo se marcó "premium" o "superior" cuando lo decía el título; el resto quedó como `no_indicado`.
- **Los precios cambian.** Esta investigación es del 2026-11-10. Hay que repetirla al menos una vez por temporada.
