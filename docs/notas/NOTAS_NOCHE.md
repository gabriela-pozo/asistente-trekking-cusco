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

## Informe de la rama mejoras-mapas (mapa de rutas)

**Commits** (todos en `mejoras-mapas`; nada en main):
1. `c33a00e` Módulo `core/mapa.py` + `tests/test_mapa.py` (9 pruebas con datos reales de `data/rutas/`).
2. `d3c2cba` `app/mapa_ui.py` con `mostrar_mapa(trek)`, atribución ODbL y try/except general + `tests/test_mapa_ui.py`.
3. `8ef75f1` `app/app.py`: una import y una llamada (`mostrar_mapa_del_resultado(resultado)`) después de `mostrar_perfil`.
4. `4f87b9a` Perfil de altitud.
5. `d41e5d6` Enlace "Abrir punto de inicio en Google Maps".
6. `28ab1ce` README: punto 4 de "Qué sigue" actualizado, con atribución ODbL.

**Qué treks tienen mapa:** Salkantay (11 puntos, 8 con altitud), Camino Inca clásico (10 puntos, 7 con altitud) y Lares (6 puntos, **incompleto**: faltan campamentos y el tramo alto de los días 1 y 2; la app lo avisa). Sin mapa: Choquequirao, Inca Jungle y Camino Inca corto; muestran "Mapa no disponible todavía para este trek." y la atribución.
- El trek que se mapea es el primero de `perfil.treks_de_interes` (lo que pidió el viajero). Si no hay trek detectado, no se muestra nada.
- El archivo de datos es un itinerario de referencia (Salkantay 5 días, Camino Inca 4, Lares 4); la app lo dice debajo del mapa, porque un trek de 4 días de Salkantay usa el mismo trazado de 5.

**Pytest:**
- Antes: 232 pasan, 1 skipped, **1 falla** (`tests/test_pipeline.py::PruebasLLM::test_proveedor_claude_pide_su_clave`).
- Después: 244 pasan, 1 skipped, la misma 1 falla. Las 12 nuevas son de esta rama. No investigué esa falla (ya fallaba antes de mi primer cambio; parece depender de las claves del entorno).
- `python -c "import app.app"` y `tests/test_importa_app.py` pasan tras cada commit.

**Verificación de la app:** `streamlit run app/app.py` arrancó 25 s sin excepciones. Con la prueba de sesión de Streamlit (AppTest) y el ejemplo guardado: el expander "Ver la ruta en el mapa" aparece con Salkantay (mapa, perfil, enlace y atribución); al forzar Choquequirao muestra "Mapa no disponible" y la atribución; sin trek no aparece el expander. **No lo vi en un navegador real**, así que el aspecto del mapa pydeck (teselas y tooltip) no está confirmado visualmente.

**Dependencias:** ninguna nueva en `requirements.txt`. Se usa `pydeck` y `altair` (vienen con Streamlit) y `pandas`. Para correr las pruebas en esta máquina instalé `pytest` en el Python local (no en el proyecto) y hay que correrlo con `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` por un conflicto de plugins local (`platformdirs`). `folium` y `streamlit-folium` ya están en requirements.txt pero no los usé.

**Riesgos:**
- El mapa base de pydeck lo sirve un proveedor externo de teselas; sin internet el mapa se vería sin fondo (los puntos y la línea siguen). El resto de la app no se afecta.
- La distancia entre puntos (`distancia_recta_km`) existe en `core/mapa.py` pero **no se muestra**: es en línea recta e incluye tramos en vehículo, y podría engañar. El perfil usa km en línea recta como eje y lo rotula así.
- El desnivel se calcula solo con los puntos que tienen altitud (parcial); la nota lo indica ("8 de 11 puntos").
- Altitudes en conflicto y datos leídos por resumen automático (ver `data/rutas/README.md`): conviene revisarlos antes de afirmar cifras ante un cliente.
- Si `mejoras-diseno` también toca el final de `pagina_consulta` o el bloque de imports de `app/app.py`, puede haber un conflicto de 2 líneas al unir.

**Sin hacer:**
- El mapa no está en el texto de la respuesta por WhatsApp, solo en la pantalla de la agencia.
- Completar Lares y agregar Choquequirao, Inca Jungle y Camino Inca corto (requiere datos reales de OSM).
- Revisión visual en navegador y en celular.

