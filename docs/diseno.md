# Sistema de diseño de Abra Travel

**Usuario:** el dueño o vendedor de una agencia de trekking en Cusco, que responde a viajeros desde la laptop o el celular, muchas veces de noche.
**Momento clave:** pega la consulta y en segundos tiene una respuesta lista para enviar. El borrador y el botón "Abrir en WhatsApp" son la pantalla. El perfil, las opciones y los avisos son el respaldo que le da confianza para enviarlo.
**Marca:** "Abra" es el punto más alto de un trek (abra Salkantay, 4 600 m). Tono confiable, local, sereno y preciso.

Dónde vive cada cosa: el tema en `.streamlit/config.toml`, el CSS que el tema no cubre en `app/estilo.css`, el formato de datos en `app/presentacion.py` y el logo en `assets/`.

## Color: "Abra: del glaciar al amanecer"

Paleta de viaje y trekking pensada para proyector: bloques oscuros (Cumbre) contra bloques claros (Arena y Nieve), con un solo destello cálido (Amanecer). Sirve para cualquier destino: Cusco, Huaraz, Arequipa, Puno o el resto de Latam. Cada color es una variable CSS en `app/estilo.css` y el tema de `.streamlit/config.toml` usa los mismos valores. En el CSS solo se usan estos tokens.

| Token CSS | Color | Uso |
| --- | --- | --- |
| `--cumbre` / `--cumbre-texto` | `#0B2E3A` / `#E6F1F3` | Barra lateral y cabecera, y su texto |
| `--laguna` / `--laguna-hover` | `#0B6E7F` / `#095866` | Botón principal (texto blanco) y enlaces |
| `--amanecer` | `#F59E2E` | Destello **solo sobre fondos oscuros**: ítem activo del menú, indicadores, ícono destacado |
| `--sendero` | `#0E7C58` | Éxito y "reservada" |
| `--arena` | `#F5F1E8` | Fondo de página y de las fichas |
| `--nieve` / `--borde` | `#FFFFFF` / `#DDD6C8` | Tarjetas (esquinas de 12 a 16 px, sombra muy suave) y su borde |
| `--tinta` | `#12303A` | Texto |
| `--secundario` / `--tenue` | `#4A5F66` / `#5C6E74` | Texto secundario / texto tenue |
| `--tierra` / `--tierra-barra` | `#B45F06` / `#C8660A` | `--tierra`: precios en texto pequeño. `--tierra-barra`: solo barras y números de 24 px o más |
| `--aviso-fondo` / `--aviso-texto` | `#FFF1D6` / `#7A4B00` | Avisos |
| `--borde-campo` | `#7F9096` | Borde de los campos de entrada (blancos, con borde visible) |
| `--acento-destino` | `var(--laguna)` | Acento por destino: cada destino puede redefinirlo sin tocar el resto |

Estados de los gráficos, sin cambios: reservada `#0E7C58`, cotizada `#3A78C2`, sin respuesta `#C8660A`, perdida `#5B6F6A`.

### Contraste (WCAG AA: 4,5:1 en texto; 3:1 en texto grande y componentes)

| Par | Contraste | |
| --- | --- | --- |
| Tinta sobre Arena / Nieve | 12,3 / 13,9 | cumple |
| Secundario sobre Nieve / Arena | 6,7 / 6,0 | cumple |
| Tenue sobre Nieve / Arena | 5,3 / 4,7 | cumple |
| Blanco sobre Laguna / Laguna hover | 5,9 / 8,1 | cumple |
| Laguna (enlace) sobre Nieve / Arena | 5,9 / 5,3 | cumple |
| Texto de Cumbre sobre Cumbre | 12,4 | cumple |
| Amanecer sobre Cumbre | 6,7 | cumple |
| Tinta de Cumbre sobre Amanecer | 6,7 | cumple |
| Aviso: `#7A4B00` sobre `#FFF1D6` | 6,6 | cumple |
| Tierra `#B45F06` sobre Nieve | 4,6 | cumple, **solo sobre Nieve** |
| Sendero sobre Nieve / blanco sobre Sendero | 5,2 | cumple |
| Cotizada `#3A78C2` sobre Nieve | 4,5 | cumple justo |
| Borde de campo `#7F9096` sobre Nieve | 3,3 | cumple (componente, 3:1) |
| **Tierra `#B45F06` sobre Arena** | **4,1** | **no cumple en texto pequeño**: el precio va siempre dentro de una tarjeta Nieve |
| **`#C8660A` sobre Nieve** | **3,9** | solo en barras y números de 24 px o más (3:1) |
| **Borde `#DDD6C8` sobre Nieve** | **1,5** | decorativo: separa tarjetas; nada depende de él para entender |
| **Sin respuesta `#C8660A` en texto pequeño** | **3,9** | solo en barras; en el texto va la etiqueta, no el color |

Los avisos se separan por gravedad:
- **Error (rojo), arriba:** montos que no están en la cotización, depósito que no cuadra, trek sin precio, mensaje sin precio.
- **Aviso (ámbar):** lo demás que hay que revisar.
- **Informativo (Laguna suave):** el ejemplo guardado.

## Tipografía

- **Montserrat** 600–700 para títulos, precios y cifras. **Nunito** 400–700 para el texto. Ambas desde Google Fonts, con la sintaxis `"Nombre:URL"` del tema.
- Escala: **40 / 36–38 / 32 / 24 / 18 / 16 / 14** px. Texto mínimo 14 px (etiquetas y notas); cuerpo 16 px.
  - 36–40: número de cada KPI y total del paquete.
  - 24: título de página y precio por persona.
  - 18: pregunta del Tablero y títulos de gráfico.
- Cifras tabulares en toda la app (`font-variant-numeric: tabular-nums`), para que los montos se alineen.

## Espacio, forma y profundidad

- Retícula de 12 columnas: 4 KPIs de 3 columnas y 2 gráficos de 6. Relleno de tarjetas de 16 a 20 px.
- Campos y botones de 44 px de alto. Campos blancos con borde `--borde-campo`.
- Radio de 12 a 16 px; sombra muy suave en las tarjetas, un poco más al pasar el cursor.
- Animaciones sobrias (transición al pasar el cursor, entrada suave de la respuesta), solo si el usuario no pide menos movimiento (`prefers-reduced-motion`).
- Íconos: Material Symbols de Streamlit (en el menú, los chips y los avisos las pone el CSS) y el logo SVG propio: un paso de montaña con el sol saliendo, en Cumbre y Amanecer.
- Contraste fuerte entre bloques oscuros (barra lateral, cabecera, banda del Tablero) y claros (tarjetas). Un solo botón principal por pantalla. Los avisos legales van al pie, en gris y con ícono.

## Cabecera y navegación

- **Barra superior** siempre visible (pegada arriba al bajar): nombre de la agencia, **una sola** insignia "Datos de demostración", el estado del sistema en una insignia pequeña (modelo activo o "Ejemplo guardado") y el botón **¿Cómo se usa?** (ventana con `st.dialog`).
- **Menú lateral** con nombres cortos e íconos, sin descripciones: Consulta, Tablero, Fuentes, Mi agencia, Sistema, Piloto. El ítem activo, en Amanecer sobre Cumbre.

## Pantalla "Consulta": tres pasos

1. **Pegar:** mensaje de 4 líneas, un solo botón grande "Preparar respuesta" y el enlace "Usar mensaje de ejemplo". El WhatsApp del viajero y la hora de llegada, en el expander "Opciones". Mientras carga: "Leyendo el mensaje → Buscando tu tarifa → Redactando" (`st.status`).
2. **Revisar:** "Resultado guardado" como insignia pequeña; la respuesta en una burbuja tipo WhatsApp (idioma y hora arriba, "Copiar" y "Abrir en WhatsApp" abajo); a la derecha, "Lo que entendimos del viajero" en chips con ícono, las advertencias para la agencia en un panel de máximo 3 viñetas y las opciones en dos líneas. "Registrar como cotizada/reservada" lleva la frase "Alimenta el Tablero".
3. **Ajustar:** el resumen (total grande, por persona y depósito) siempre visible; el expander cerrado "Ajustar paquete y extras" tiene el trek base, los extras, "Más opciones" (noches, hotel y forma de pago) y el desglose, en pestañas.

"Información consultada" es un enlace pequeño a Fuentes. El mapa sigue en su expander. Con la consulta llegada fuera de horario, la respuesta automática simulada aparece debajo.

## Páginas de respaldo

- **Fuentes:** arriba el buscador y lo usado en la última respuesta; la tabla completa de la base, plegada.
- **Sistema:** una línea de estado (sin consulta todavía no se conoce el modelo ni la cuota); la versión de la base y las pruebas, al pie.
- **Mi agencia:** el tarifario a la vista solo con el nivel estándar; "Editar todos los niveles" en un expander.
- **Piloto:** "El vendedor siempre revisa" y dos bloques de 3 viñetas con ícono; el texto completo, en "Más detalle".

## Tablero

- Banda oscura con la pregunta y el origen de los datos en una línea. "Tu semana" como barra de progreso compacta.
- Período como control segmentado (3, 6 o 12 meses); trek e idioma en selectores compactos, en una sola fila.
- 4 KPIs grandes con ícono y variación (las definiciones están en el "i"). Debajo: embudo y por trek (con `n=`), "Cuándo llegan" más pequeño con el % fuera de horario, y las pestañas **Más análisis** (por mes del viaje y países) y **Tablas** (los mismos datos de cada gráfico, accesibles y descargables).
- El título de cada gráfico tiene 8 palabras o menos y dice la conclusión; la frase larga queda debajo en gris.
- Sin resultados con los filtros: el aviso dice qué filtros chocan y "Quitar filtros" los limpia.

## Estados

- **Sin clave:** aviso con qué falta y dónde ponerla; "Preparar respuesta" queda deshabilitado.
- **Cargando:** dice qué está pasando: "Leyendo el mensaje, cotizando con tu tarifario y redactando la respuesta…".
- **Sin cuota:** muestra el ejemplo guardado con un aviso que dice que no corresponde al mensaje pegado.
- **Error:** mensaje claro (clave inválida, o "intenta de nuevo en un minuto") con el detalle técnico plegado.
- **Vacío:** antes de la primera consulta, una tarjeta explica qué va a aparecer.

## Microcopia

Verbos y español claro: "Preparar respuesta", "Abrir en WhatsApp", "Descargar tarifario", "Revisa antes de enviar", "Corrige antes de enviar". Para el vendedor no hay jerga técnica, salvo la línea de modelo y tokens, que es para la demo.

## Límites de Streamlit

- **El botón de subir archivos dice "Upload" y "5MB per file", en inglés.** `st.file_uploader` no tiene parámetro para ese texto, y cambiarlo exigiría CSS sobre clases internas. La etiqueta del campo sí está en español.
- **Las fuentes se cargan desde Google Fonts.** Sin internet, la app usa las fuentes del sistema. El logo no depende de eso: lleva incrustadas las letras de "Abra Travel" en Montserrat (licencia OFL).

- **Compatibilidad:** la app declara `streamlit>=1.40`. Solo usa funciones que existen en esa versión (`st.dialog`, `st.status`, `st.segmented_control`, `st.tabs`, íconos `:material/…:`). Los íconos del menú y de los KPI salen de CSS sobre la fuente Material de Streamlit.
- **Portapapeles:** "Copiar" usa un componente mínimo (`st.components.v1.html`, sin red); si Streamlit lo quita, cae a un botón que abre el texto con el ícono de copiar de `st.code`.
