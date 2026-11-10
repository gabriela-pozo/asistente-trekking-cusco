# Datos de rutas para el mapa

Un CSV por trek, con los puntos principales del recorrido en orden, para dibujarlos en un mapa. Datos reunidos el **2026-11-10**.

| Archivo | Trek | Itinerario usado | Puntos |
| --- | --- | --- | --- |
| `salkantay_5d.csv` | Salkantay 5 días | [SAP Adventures](https://sapadventures.org/tour/salkantay-trek-5-days/) | 11 |
| `camino_inca_4d.csv` | Camino Inca clásico 4 días | [Alpaca Expeditions](https://www.alpacaexpeditions.com/classic-inca-trail-trek-4d3n-group-service/) | 10 |
| `lares_4d.csv` | Lares 4 días | [TreXperience](https://trexperienceperu.com/lares-trek) | 6 (incompleto) |

## Columnas

| Columna | Qué es |
| --- | --- |
| `dia` | Día del itinerario en que se pasa por el punto |
| `orden` | Orden del punto en todo el recorrido (1, 2, 3…) |
| `lugar` | Nombre del lugar |
| `latitud`, `longitud` | Grados decimales (sur y oeste en negativo) |
| `altitud_m` | Metros sobre el nivel del mar; vacío si ninguna fuente la da |
| `tipo` | `inicio` (donde se empieza a caminar), `campamento` (donde se duerme), `paso` (abra o paso de montaña), `sitio` (ruina, laguna, pueblo), `fin` |
| `fuente` | URL de donde salió la coordenada (`coord:`) y la altitud (`alt:`) |

## Cómo se armaron

1. **Qué puntos y en qué orden:** salen de un itinerario público de una agencia por trek, abierto el 2026-11-10. Las rutas varían entre agencias (sobre todo en Lares), así que estos puntos representan *un* itinerario, no "el" único recorrido.
2. **Coordenadas:** de Wikipedia cuando el artículo trata del sitio exacto, y si no, de **OpenStreetMap** (búsqueda en Nominatim, una consulta por lugar, sin descarga masiva). No se inventó ni estimó ninguna coordenada.
3. **Altitud:** primero la que imprime el itinerario de la agencia; si no la da, la de OpenStreetMap (etiqueta `ele`) o Wikipedia; si nadie la da, queda vacía.
4. **Puntos de pueblos:** en pueblos (Aguas Calientes, Ollantaytambo, Lares, Chaullay) la coordenada es el centro del pueblo, no el campamento u hotel exacto.

**Importante para el mapa:** unir los puntos con líneas rectas **no** es el sendero real, sino una aproximación. Para dibujar el sendero real haría falta el trazo (track) de OpenStreetMap, que no se descargó.

## Puntos que quedaron fuera

| Trek | Lugar | Motivo |
| --- | --- | --- |
| Salkantay | Mollepata | Wikipedia solo da la coordenada del distrito, no del pueblo; además se pasa en vehículo |
| Salkantay | Huayracmachay (almuerzo del día 2) | No aparece en OpenStreetMap ni en Wikipedia |
| Camino Inca | Ayapata (campamento noche 1) | Las búsquedas solo devuelven lugares homónimos en Puno y Apurímac |
| Camino Inca | Pacaymayu (almuerzo del día 2) | OpenStreetMap da un sitio arqueológico con ese nombre, pero no está claro que sea el campamento; se dejó fuera por dudoso |
| Camino Inca | Chaquicocha (campamento noche 2) | Solo homónimos en Junín y Arequipa |
| Camino Inca | Intipata | No se buscó: el itinerario no da altitud y no tenía fuente de coordenadas |
| Lares | Quishuarani, laguna Azul (campamento noche 1), abra Cóndor (punto más alto, ~4 700 m), Cancha Cancha (campamento noche 2) | Solo homónimos en otras regiones, o no se encontraron |
| Lares | Baños termales de Lares | No aparecen en OpenStreetMap; se usa el pueblo de Lares |

Por eso **`lares_4d.csv` está incompleto**: tiene el inicio (Pampacorral) y el final (Huarán, Ollantaytambo, Aguas Calientes, Machu Picchu), pero le falta todo el tramo alto de los días 1 y 2. Conviene completarlo a mano con el mapa de OpenStreetMap antes de mostrarlo.

## Otras notas

- **Datos del resumen automático:** en el Camino Inca (Alpaca) y en los días 2 a 4 de Lares (TreXperience), el itinerario se leyó a través de un resumen automático de la página, no del texto original. Conviene verificar los nombres y las altitudes en la página.
- **Altitudes en conflicto entre fuentes:**
  - Abra Salkantay: 4 630 m en el día 2 de SAP, 4 650 m en el resumen de SAP y 4 629 m en OpenStreetMap. Se usa 4 630.
  - Wiñay Wayna: Alpaca da 2 680 y 2 600; se usa Wikipedia (2 650).
  - Aguas Calientes: SAP y Wikipedia dicen 2 040; TreXperience dice 2 000. Cada archivo usa su itinerario.
- **Orden en el Camino Inca:** las ruinas de Runkuraqay van antes que el abra del mismo nombre, por su posición en el mapa. El itinerario de Alpaca las nombra al revés.
- **Lugares visitados en vehículo:** en Lares, el pueblo de Lares se visita en vehículo antes de empezar a caminar en Pampacorral. En el día 3, de Huarán a Ollantaytambo y Aguas Calientes se va en vehículo y tren.

## Licencias

- **OpenStreetMap:** las coordenadas y altitudes tomadas de OpenStreetMap son © colaboradores de OpenStreetMap y están disponibles bajo la **Open Database License (ODbL) 1.0**: https://www.openstreetmap.org/copyright. Si se publican estos datos o un mapa hecho con ellos, hay que dar esa atribución y compartir las modificaciones de los datos bajo la misma licencia.
- **Wikipedia:** las coordenadas de Wikipedia se citan con su URL. El texto de Wikipedia está bajo CC BY-SA 4.0; aquí solo se usan los datos de ubicación, no texto.
- **Mapa base:** si el mapa usa teselas de OpenStreetMap (lo normal en folium), también debe mostrar "© OpenStreetMap contributors".
