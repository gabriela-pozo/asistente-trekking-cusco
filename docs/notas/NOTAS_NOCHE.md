# Notas de la noche (2026-11-10)

Trabajé solo, sin preguntarte, en las 6 partes y en orden. Todo quedó en commits locales; **no hice push**. Ningún archivo tiene claves de API (lo revisé al final).

| Parte | Commit |
| --- | --- |
| 1. Ampliar precios | `824b932` Más precios del mercado |
| 2. Evidencia sobre atención | `d85f5d8` Evidencia pública sobre atención de agencias |
| 3. Entorno | `c9b1fb2` Dependencias de la app |
| 4. Datos para el mapa | `69218d2` Datos de rutas para el mapa |
| 5. Huaraz | `7938faf` Base de conocimiento de Huaraz |
| 6. Seguimiento | `fc584b4` Plantillas de mensajes de seguimiento |

No escribí código de la app.

---

## 1. Qué hice en cada parte

### Parte 1: Más precios del mercado
- **Muestra ampliada:** `data/precios_mercado.csv` pasó de 17 a **42 publicaciones**, y quedaron **13 precios válidos por trek**. Los nuevos son sobre todo webs propias de agencias de Cusco (Quechuas Expeditions, SAP Adventures, Turismo Liberty, Terra Quechua, AB Expeditions, Happy Gringo, etc.), para depender menos de TourRadar.
- **Cómo los leí:** abrí cada página una vez, anoté la URL y la fecha, marqué los precios "desde" y no puse nada que no estuviera en la página.
- **Tarifario:** corrí `scripts/analisis_precios.py` y se regeneró solo.
- **Pruebas:** fallaron 3, todas por el nuevo precio del Camino Inca (ver la sección 3). Cambié solo los valores esperados y sus comentarios.
- **Prueba nueva:** la regla del "Salkantay 4 días = 5 días − 10 %" ya no se activa con los datos reales. Para que no quede sin probar, agregué una prueba con datos inventados que sí la activa. Ahora son **34 pruebas, todas pasan**.
- **Documentación:** actualicé `docs/fuentes_precios.md` con las cifras nuevas, los criterios de anotación y una tabla de antes y después.

### Parte 2: Evidencia pública
- **Archivo:** `docs/research/evidencia_publica.md`, con 14 fuentes. Cada una tiene URL, fecha, tema y un resumen de una línea con mis palabras, sin nombres de personas.
- **Rapidez de respuesta:** el hallazgo más útil es que **TourRadar publica la tasa y el tiempo de respuesta de cada operador**. Una agencia de Cusco con 5 estrellas responde solo el 50 % de los mensajes.
- **Cobros no incluidos:** aparecen en blogs independientes (el turista creía que algo estaba incluido) y en las propias webs de agencias, que listan extras: bolsa de dormir, bastones y recargo por tarjeta.
- **Páginas que no se abrieron:** anoté las que fallaron y por qué.

### Parte 3: Entorno
- **Entorno creado:** `conda` no estaba en el PATH, pero Anaconda sí está instalada en `C:\Users\Asus\anaconda3`. La usé por su ruta completa y creé el entorno **`trekking` con Python 3.12.16**.
- **Dependencias:** a `requirements.txt` le agregué `folium>=0.17` y `streamlit-folium>=0.22`; las otras 6 ya estaban. Todo se instaló con pip dentro del entorno.
- **Comprobación:** las 8 librerías se importan bien. Versiones: streamlit 1.67.0, anthropic 2.7.0, pandas 3.1.1, scikit-learn 1.9.1, pydantic 2.14.3, python-dotenv 1.2.4, folium 0.20.0, streamlit-folium 0.27.4. Las 34 pruebas también pasan dentro del entorno.
- **Para activarlo mañana** (en Anaconda Prompt, o después de `conda init`): `conda activate trekking`. Sin activarlo: `C:\Users\Asus\anaconda3\envs\trekking\python.exe`.

### Parte 4: Datos para el mapa
- **Archivos:** `data/rutas/` tiene `salkantay_5d.csv` (11 puntos), `camino_inca_4d.csv` (10) y `lares_4d.csv` (6).
- **De dónde salen los puntos:** el itinerario de una agencia por trek dice qué puntos hay y en qué orden.
- **Coordenadas:** de Wikipedia o de OpenStreetMap, una consulta por lugar.
- **Altitud:** la del itinerario; si no la da, la de OpenStreetMap o Wikipedia.
- **README:** `data/rutas/README.md` explica todo, lista los puntos que faltan y menciona la licencia **ODbL** de OpenStreetMap.

### Parte 5: Huaraz
- **Archivos:** `data/knowledge_huaraz/santa_cruz.md` (8 secciones) y `laguna_69.md` (7 secciones), en el mismo formato de cabecera y "## " que `data/knowledge`. Comprobé que `ai/knowledge.py` los lee sin cambios: salen 15 fragmentos, todos con fecha y fuentes.
- **Contenido:** duración, altura máxima, entrada al parque, temporada y precios de 2 agencias por trek.
- **Santa Cruz:** Nomades (S/ 660) y Tierras de los Andes (desde US$ 535).
- **Laguna 69:** Nomades (S/ 67) e Iziperu en GetYourGuide (desde US$ 29, visto en una fuente secundaria).
- **Dato importante:** desde el **9 de febrero de 2026**, la Laguna 69 solo se puede visitar con agencias autorizadas por SERNANP (noticia de Gestión).

### Parte 6: Mensajes de seguimiento
- **Archivo:** `docs/plantillas_seguimiento.md`, con 3 mensajes (24 horas, 3 días, una semana) en español e inglés.
- **Uso:** campos entre `{llaves}` y una tabla de "datos útiles" sacados de la base de conocimiento para el segundo mensaje.
- **Reglas:** cuándo **no** enviar. El tercer mensaje dice explícitamente que es el último.

---

## 2. Qué no pude hacer y por qué

### Parte 1
- **Páginas que no abrieron:** GetYourGuide y TripAdvisor (error 403, bloquean la lectura automática), dos páginas de Magpie y dos de TourRadar (404), Lokalee (en mantenimiento) y machupicchureservations.org (error de DNS dos veces).
- **Páginas sin precio usable:**
  - x-tremetourbulencia.com: un artículo sin precio propio.
  - Bolivian Mountains: precio solo en libras.
  - Nomades Salkantay Express: precios de 2024 y la actividad ya no opera.
  - Anywhere.com: no dice la moneda ni si es por persona; está registrada pero excluida.
- **9 filas leídas del resumen automático:** algunas páginas eran muy largas y una parte se leyó del resumen de la herramienta, no del texto original. Están marcadas en `notas`. **Conviene verificarlas a mano** (sobre todo las 3 de Salkantay Trekking, G Adventures, AB Expeditions, Andean Spirit y Okidoki).

### Parte 2
- **No pude leer** TripAdvisor (403), las reseñas de Google (no se pueden abrir sin navegador), dos foros de Fodor's (403), TravelStride (403) ni una queja pública en Test-Aankoop (410, eliminada).
- **Sesgo hacia lo positivo:** las reseñas que sí se leyeron son casi todas de 5 estrellas.
- **Relatos antiguos:** los relatos independientes de cobros sorpresa son de 2009 y 2014.
- **Falta evidencia reciente de quejas.** Para eso sirve más la prueba de cliente misterioso.

### Parte 4
- **Puntos que no encontré, así que no los puse:**
  - **Camino Inca:** los campamentos Ayapata y Chaquicocha (solo hay lugares homónimos en otras regiones) y Pacaymayu (resultado dudoso).
  - **Salkantay:** Huayracmachay y el pueblo de Mollepata.
  - **Lares:** todo el tramo alto (Quishuarani, laguna Azul, abra Cóndor, Cancha Cancha) y los baños termales.
- **`lares_4d.csv` está incompleto:** le faltan los días 1 y 2 de caminata. Conviene completarlo a mano con el mapa de OpenStreetMap antes de mostrarlo.
- **Los puntos no son el sendero:** unirlos con líneas rectas no muestra el sendero real. No descargué el trazo (track) de OpenStreetMap.
- **Itinerarios del resumen automático:** los del Camino Inca (Alpaca) y de Lares (días 2 a 4) se leyeron del resumen automático.

### Parte 5
- **Tarifa del parque sin verificar en la fuente oficial:** no pude confirmarla directamente en SERNANP. La tabla de 2026 sale de una guía informativa que dice no ser oficial, y las fuentes no coinciden en la tarifa para nacionales en la Laguna 69 (S/ 10, 12 o 15). Lo dejé escrito así.
- **Perunorth no se leyó:** redirigía a otra URL y no la seguí.

### Partes 3 y 6
Nada pendiente.

---

## 3. Medianas nuevas comparadas con las anteriores

En USD por persona, sin la fila premium:

| Trek | Antes (n) | Ahora (n) | Cambio | Estándar antes → ahora |
| --- | --- | --- | --- | --- |
| Salkantay 4 días | 690 (5) | 595 (13) | **−13,8 % ⚠️ más de 10 %** | 600 → 600 |
| Salkantay 5 días | 669 (5) | 674,5 (12) | +0,8 % | 670 → 670 |
| Camino Inca clásico 4 días | 812,5 (4) | 835 (13) | +2,8 % | 810 → **840** |

- **Salkantay 4 días: es la única mediana que cambió más de 10 %.** Con 5 precios salía más cara que la del de 5 días por cómo cayó la muestra. Con 13 bajó a 595, ya por debajo de la del de 5 días, así que la regla del −10 % ya no se activa. El precio estándar quedó igual (600) porque ahora sale directamente de la mediana. Que la regla antigua y los datos nuevos den lo mismo sugiere que la regla corregía bien.
- **Camino Inca:** sube US$ 30 en estándar (810 → 840), y con eso todo su tarifario. Económico pasa de 650 a 670 y premium de 1 300 a 1 340.
- **Salkantay 5 días:** sin cambios en el tarifario.

---

## 4. Decisiones que tomé sin preguntarte

### Precios (parte 1)
1. **13 precios válidos por trek, no "12 incluyendo excluidos":** conté solo las filas con `incluir_en_analisis = si`.
2. **Precio especial con fecha límite:** si una página mostraba un precio regular y uno especial con fecha límite (por ejemplo "US$ 695 hasta el 31/12/2026"), anoté el regular, porque el tarifario es para todo el año. Pasa con 3 filas de Salkantay Trekking y con G Adventures (regular US$ 699, en promoción a US$ 489).
3. **Dos precios juntos sin explicación** (por ejemplo "US$ 880 US$ 680"): anoté el destacado, el más bajo.
4. **Precios con regreso en bus o en tren:** anoté el que la página trata como principal y el otro quedó en `notas`. SAP: tren US$ 420, auto US$ 380. Okidoki: bus US$ 420, tren US$ 500.
5. **Nivel "mochilero":** creé ese valor en `nivel_aprox` para la versión "para mochileros" de Quechuas (US$ 310), porque la página lo dice. Entra en la mediana; solo se excluye "premium".
6. **Agencias repetidas:** Salkantay Trekking y Quechuas aparecen 4 veces cada una (productos o plataformas distintos). Las dejé todas y lo anoté como límite en la documentación.
7. **Eco Tour Cusco:** cambié su URL de un artículo de blog a la ficha del tour, que confirma el mismo precio (US$ 595). No agregué una fila duplicada.
8. **Fila de Anywhere.com:** la registré pero la excluí, porque no dice moneda ni si el precio es por persona.
9. **Documentación y prueba extra:** actualicé `docs/fuentes_precios.md` (no estaba pedido, pero tenía cifras viejas) y agregué la prueba de la regla del 10 %.
10. **Corregí mi propio commit:** después del commit de la parte 1 vi dos conteos mal escritos en la documentación (TourRadar: 9, no "unos 10"; filas del resumen automático: 9, no 7). Corregí el mismo commit con `--amend`, porque no estaba subido.

### Evidencia (parte 2)
11. **Tema extra:** agregué el tema "(d) el turista compara varias agencias" porque apareció varias veces y apoya la idea del proyecto.
12. **Nombres:** las agencias se nombran solo cuando la página es suya o trata de ellas. No hay nombres de personas.
13. **Métricas de TourRadar:** busqué perfiles de operadores en TourRadar porque publican tasa y tiempo de respuesta. Es la evidencia más objetiva que encontré.

### Entorno (parte 3)
14. **Canal de Python:** instalé Python desde el canal `conda-forge`, para no depender de aceptar los términos de servicio de los canales de Anaconda. Las librerías se instalaron con pip desde `requirements.txt`.
15. **Versiones mínimas nuevas:** `folium>=0.17` y `streamlit-folium>=0.22`, el mismo estilo de `>=` que el resto.

### Mapa (parte 4)
16. **Un itinerario por trek:** SAP Adventures (Salkantay), Alpaca Expeditions (Camino Inca) y TreXperience (Lares).
17. **Columna `fuente`:** lleva dos URLs, `coord:` y `alt:`. Separé la fuente de la coordenada y la de la altitud porque suelen ser distintas.
18. **Pueblos:** la coordenada es el centro del pueblo, no el hotel o campamento exacto.
19. **Orden en el Camino Inca:** puse las ruinas de Runkuraqay antes que el abra, por su posición en el mapa (Alpaca las nombra al revés).
20. **Altitudes que no coinciden:** usé la del itinerario elegido, salvo Wiñay Wayna, donde Alpaca se contradecía (2 680 y 2 600) y usé Wikipedia (2 650).
21. **URL con coma:** la de Wikipedia de Aguas Calientes rompía el CSV, así que la escribí con `%2C`.

### Huaraz (parte 5)
22. **Precios en soles:** los de Nomades están en soles y los dejé así, sin convertir.
23. **Regla de 2026 primero:** si una fuente vieja contradice la regla de 2026 de agencias autorizadas, puse primero la regla nueva y mencioné la contradicción.
24. **Boleto de 4 a 30 días:** para el Santa Cruz (4 días) expliqué que corresponde ese boleto (S/ 150 extranjeros). La cifra de S/ 60 que dan algunas fuentes es la del boleto de 2 a 3 días.

### Seguimiento (parte 6)
25. **Variables:** usé `{llaves}` para que luego se llenen con datos de la cotización.
26. **Regla en el documento:** escribí que nunca se ponga un precio que no esté en el tarifario, igual que en el resto del proyecto.

---

## Para revisar mañana

1. Verificar a mano las 9 filas de precios marcadas "resumen automático".
2. Completar `data/rutas/lares_4d.csv` con el tramo alto, o mostrar en el mapa solo Salkantay y Camino Inca.
3. Confirmar en https://visitaareasnaturales.sernanp.gob.pe la tarifa vigente del Parque Nacional Huascarán.
4. Si quieres mostrar el mapa con el sendero real, hay que bajar el trazo de OpenStreetMap (es otro paso).
5. Activar el entorno: `conda activate trekking`.

---

# Tablero para la presentación (2026-11-11, rama `mejoras-diseno`)

Trabajé solo en `mejoras-diseno`: sin merge ni push a `main`. No toqué `ai/` ni `server/`. En `core/tablero.py` solo agregué funciones y textos nuevos; ninguna métrica existente cambió su cálculo. No leí ni imprimí `.env`.

## Antes de empezar: traje `main` a la rama

El Tablero con embudo, mapa de calor y frases (`360228d`) estaba en `main`, no en `mejoras-diseno`. Además, `main` había movido este archivo a `docs/notas/`. Para trabajar sobre ese Tablero hice un merge **de `main` hacia `mejoras-diseno`** (`27b48f9`). Hubo un solo conflicto, en `app/estilo.css` (los dos lados agregaban estilos al final), y quedaron los dos. Con esto, el merge final a `main` debería ser más simple.

## Pruebas

- **`pytest` no estaba instalado** en el Python del sistema (3.14). Lo instalé solo en la carpeta temporal de la sesión y lo corrí con `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` (un plugin de `platformdirs` lo rompía). Nada se instaló en el entorno del proyecto.
- **Antes (en la rama, sin el merge):** 228 pasan, 1 falla, 1 se salta.
- **Después del merge:** 245 pasan, 1 falla, 1 se salta.
- **Al final:** 258 pasan, 1 falla, 1 se salta, más 231 subpruebas.
- **La que falla** es `test_proveedor_claude_pide_su_clave`, porque el paquete `anthropic` no está instalado en este Python. Ya fallaba antes y no tiene que ver con el Tablero. En el entorno `trekking` debería pasar.
- **`python -c "import app.app"`:** termina bien (código 0) después de cada commit.
- **Pruebas nuevas:** `tests/test_tablero_demo.py`, con 13 pruebas. Además, cambié una etiqueta esperada en `tests/test_tablero.py` ("Sin respuesta" pasó a "Sin respuesta de la agencia").

## Commits (uno por cambio)

| Tarea | Commit | Qué cambió |
| --- | --- | --- |
| — | `27b48f9` | Merge de `main` hacia la rama |
| 1 | `bd64a5e` | Banda arriba: "¿Qué consultas se pierden y cuándo?" y "Datos: 300 consultas sintéticas de demostración" (si hay registradas, dice cuántas). La cuenta sale del archivo con `texto_origen()`, que es nuevo |
| 2 | `b71b632` | Bajo "Tasa de cierre": "Reservadas ÷ respondidas: 20 ÷ 111". El KPI ahora se llama "Sin respuesta de la agencia" y abajo dice "15,3 % de las consultas: la agencia no contestó" |
| 3 | `2db0972` | Orden: KPIs → embudo y por trek (lado a lado; en el celular, uno debajo del otro) → cuándo llegan → meses → países. El título de cada gráfico es la frase de `core/tablero.py`, con la pregunta encima como rótulo |
| Regla 5 | `e435c33` | Un color fijo por estado: reservada `#0E7C58`, cotizada `#3A78C2`, sin respuesta `#C8660A`, perdida `#5B6F6A`. Texto de los gráficos a 14 px y leyendas a 14 px |
| 4 | `775d559` | Prueba de cuadre con todos los filtros, y un aviso cuando hay consultas sin mes de viaje (solo texto) |
| 5 | `c920a9a` | "Cuándo llegan": 7 días × 4 franjas con el número en cada celda. Las franjas siguen el horario: madrugada (0–8) y noche (20–24) son justo las horas fuera de horario. El título conserva el % fuera de horario. "Hora por hora" muestra el 7 × 24 de antes |
| 6 | `579ee61` | Por trek: barras apiladas por estado y "21 % cierre · n=42" (n = respondidas). Con menos de 10 respondidas se atenúan; es el mismo umbral que ya usaba `hallazgo_treks()` |
| 7 | `920e112` | Países: ya venían en barras horizontales ordenadas, top 7 + "Otros", desde `main`. Solo puse "Otros" en gris y agregué una nota de cómo se ordenan |
| 8 | `9b503a2` | "Ver los datos en una tabla" bajo cada gráfico (una tabla por gráfico, con CSV). Si un filtro no deja consultas: "Ninguna consulta cumple a la vez: Choquequirao + Francés…" y un botón "Quitar filtros" |
| 9 | `5b61bf9` | "Tu semana": sin registros muestra "0 de 3 consultas registradas esta semana" y "Primera meta: 3". El 3 es una sugerencia, no un dato. Con registros sigue el bloque de antes (meta editable en Mi agencia) |
| Arreglo | `d5879e3` | "Quitar filtros" generaba una advertencia de Streamlit en el log (selector con `index=` y valor por `session_state`). Ahora el período inicial va por `session_state` |
| Arreglo | `dd37973` | El atenuado de la tarea 6 no se veía: el eje usaba `sum(n)` y esa agregación descartaba el campo `poca_base`. Además, en el celular los rótulos de franja se encimaban; ahora van en dos líneas debajo |
| Docs | `baf187f` | Capturas en `docs/capturas_diseno/` (`tablero_1440.png`, `tablero_390.png`, `tablero_vacio_1440.png`) y una sección "Tablero" en `docs/diseno.md` |

## Inconsistencias numéricas (no cambié ningún cálculo)

**Solo con las 300 sintéticas, todo cuadra.** Probé los 3 períodos × 7 opciones de trek × 6 de idioma. En cada combinación coinciden:
- consultas, respondidas y reservadas de los KPIs con las del embudo;
- el total y las "sin respuesta" del gráfico por mes y estado;
- el total y las reservadas del gráfico por trek.

Quedó como prueba automática (`PruebasCuadre`). Por defecto (6 meses): 131 consultas, 111 respondidas, 20 sin respuesta y 20 reservadas en los cuatro lugares.

**Lo que no cuadra o se presta a confusión:**

1. **"Cotizadas" significa dos cosas distintas.** En el embudo, "Cotizadas" = respondidas con precio, e incluye las reservadas: 111. En el gráfico por mes, "cotizada" es el estado sin reservar: 91. Con los mismos filtros, la misma palabra muestra 111 y 91. No es un error de cálculo, pero alguien del público puede preguntarlo.
2. **El paso Respondidas → Cotizadas siempre da 100 %** con las sintéticas, porque todas las respondidas tienen monto. Ese paso no aporta información en el demo.
3. **Una sola consulta registrada hoy corre el período de las sintéticas.** `periodo()` toma como fin la consulta más reciente. Ejemplo: sin registradas, "6 meses" va del 01/05 al 31/10/2026 y tiene 131 sintéticas. Con una registrada el 11/11/2026 va del 12/05 al 11/11 y quedan 122 sintéticas, porque salen 9. **Si registras una consulta durante la presentación, todos los KPIs del Tablero cambian, y no solo en 1.**
4. **Las registradas sin mes de viaje no entran al gráfico por mes.** Ejemplo con 2 registradas de prueba: KPI 124 y gráfico por mes 123. Ahora aparece un aviso con cuántas faltan, pero el cálculo es el mismo.
5. **Una registrada como "cotizada" sin opción del tarifario tiene monto 0.** Cuenta como respondida pero no como cotizada en el embudo. Ejemplo: respondidas 107 y cotizadas 106.
6. **Las "perdidas" de "Mi semana" cuentan como respondidas** en la tasa de cierre y en el embudo. Es coherente con la definición (reservadas ÷ respondidas), pero conviene saberlo.

## Comprobación final con `streamlit run`

Levanté la app en el puerto 8577 y la recorrí con Chrome headless (Playwright).
- **Filtros por defecto:** el Tablero abre con 5 gráficos.
- **Filtro sin resultados (Choquequirao + Francés):** aparece el aviso; con "Quitar filtros" vuelven los 5 gráficos.
- **Errores:** 0 excepciones en pantalla y 0 errores de JavaScript.
- **Log del servidor:** solo dos cosas que no son de la app: `"theme.paddingTop" is not a valid config option` (ya estaba) y un `ConnectionResetError` de Windows cuando se cierra el navegador automatizado.
- **Ancho a 390 px:** 390, sin desplazamiento horizontal.

## Lo que quedó sin hacer

- **Tarea 7:** casi todo ya estaba en `main`; solo agregué el gris de "Otros".
- **Tarea 9:** el bloque con registros sigue siendo el "Mi semana" anterior, ahora con el rótulo "Tu semana". Lo único corto y nuevo es el estado sin registros.
- **El embudo no usa los colores de estado.** Sus etapas son acumulativas (una reservada también es respondida), así que pintarlas por estado confundiría. Van en el verde primario.
- **No probé la app publicada en Streamlit Cloud,** solo en local.

## Riesgos para la presentación

- **No registres consultas en vivo justo antes de mostrar el Tablero** (ver el punto 3): las cifras cambian de forma visible. Si lo haces, explica que el período termina en la consulta más reciente.
- **En el celular, la etiqueta del Salkantay** ("21 % cierre · n=42") queda un poco cortada en el borde a 390 px. En la laptop y en el proyector se ve completa.
- **La rama ya trae `main` adentro.** Si en `main` hay commits después de `fd55093`, el merge final puede tener conflictos en `app/app.py`.
- **Archivos que cambié desde el merge:** `app/app.py`, `app/estilo.css`, `core/tablero.py` (solo agregados), `tests/test_tablero.py`, `tests/test_tablero_demo.py`, `docs/diseno.md`, `docs/capturas_diseno/` y este archivo.
