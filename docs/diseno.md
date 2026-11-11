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

- **Montserrat** 600–700 para títulos y el precio. **Nunito** 400–600 para el texto. Ambas desde Google Fonts, con la sintaxis `"Nombre:URL"` del tema.
- Escala fija: **32 / 24 / 18 / 15 / 13** px.
  - 24: título de página y precio.
  - 18: borrador y nombre de cada opción.
  - 15: texto base.
  - 13: rótulos y notas.
- Cifras tabulares en toda la app (`font-variant-numeric: tabular-nums`), para que los montos se alineen.
- El borrador tiene un ancho máximo de 70 caracteres e interlineado de 1,6. En el celular baja a 15 px.

## Espacio, forma y profundidad

- Espaciado en múltiplos de 8. Radio de 12 a 16 px en tarjetas y de 12 px en botones y campos.
- La sombra es casi imperceptible y va **solo en la tarjeta del borrador**: es lo único que "flota".
- Iconos: Material Symbols de Streamlit, solo en acciones y avisos. Sin emojis decorativos.

## Orden de la pantalla "Nueva consulta"

1. Encabezado de una línea y la tarjeta de entrada: mensaje, teléfono, "Preparar respuesta".
2. **Tarjeta del borrador**: texto editable, contador de palabras, "Respondió: modelo · tokens" y el botón "Abrir en WhatsApp" a todo el ancho de la tarjeta.
3. Avisos del control agrupados: lo grave en rojo y arriba.
4. Opciones como filas comparables: trek, días, nivel, el **precio por persona destacado en ocre**, total y depósito, y la etiqueta "Alternativa" cuando corresponde.
5. Perfil del viajero en fichas legibles ("Inglés", "Salkantay", "marzo"). Lo que falta va como etiqueta.

En la laptop, el borrador y las opciones van lado a lado (7:5). En el celular todo va en una columna, con el borrador primero. A 1440 × 900, el botón de WhatsApp queda en la primera pantalla.

## Navegación y páginas de respaldo

La barra lateral lista las páginas en este orden, cada una con una línea que dice para qué sirve: **Nueva consulta**, **Tablero**, **Fuentes y verificación**, **Mi agencia**, **Estado del sistema** y **Acerca del piloto**. Arriba va el trabajo diario; abajo, lo que da confianza para enviar.

- **Fuentes y verificación:** los fragmentos de la base de conocimiento que se usaron en la última consulta (título, archivo, fecha y enlaces a la fuente; las del Estado peruano llevan la etiqueta "Oficial"). Lo que tiene más de 90 días, o no tiene fecha, lleva la etiqueta ámbar "Verificar antes de enviar". Debajo, la base completa en una tabla con buscador; en el celular cada fila se apila.
- **Estado del sistema:** seis cifras en dos filas de tres: modelo que respondió, consultas que quedan (solo se afirma el 0; si no se sabe, dice "No se conoce"), si se usó el ejemplo guardado, versión (huella del contenido) y fecha de la base, hora en Lima con el modo nocturno, y el número de pruebas (contadas, no ejecutadas). Las cifras van a 24 px, porque algunas son nombres de modelo.
- **Acerca del piloto:** arriba, "El vendedor siempre revisa" en una franja verde suave; debajo, "Alcance" y "Lo que no hace" lado a lado (en el celular, una debajo de otra). Los límites llevan borde ámbar.

La lógica de estas páginas está en `ai/trazabilidad.py`: solo lee archivos locales, nunca llama a la API.

## Tablero

- **Arriba, una banda** con la pregunta que responde ("¿Qué consultas se pierden y cuándo?") y el origen de los datos, contado del archivo: "300 consultas sintéticas de demostración" y, si las hay, cuántas registradas en la app.
- **Orden de lectura:** Tu semana → filtros → KPIs → embudo y por trek (lado a lado) → cuándo llegan → meses → países. Cada gráfico lleva la pregunta como rótulo y **la conclusión como título** (las frases de `core/tablero.py`).
- **Un color fijo por estado** en todos los gráficos, con la paleta validada: reservada `#0E7C58`, cotizada `#3A78C2`, sin respuesta `#C8660A` (la pérdida que el Tablero quiere mostrar), perdida `#5B6F6A`. Leyenda siempre visible, rejilla `#EDF2EF` y texto de 14 px para el proyector.
- **Por trek:** barras apiladas por estado, con "x % cierre · n=respondidas". Con menos de 10 respondidas, la barra va al 35 % de opacidad y el texto en gris.
- **Cuándo llegan:** por defecto 7 días × 4 franjas alineadas con el horario (madrugada 0–8 y noche 20–24 son fuera de horario), con el número en cada celda. "Hora por hora" muestra el 7 × 24.
- **Bajo cada gráfico,** "Ver los datos en una tabla" (accesible, sin depender del color). Si un filtro no deja consultas, un aviso dice qué combinación no existe y un botón "Quitar filtros".

## Estados

- **Sin clave:** aviso con qué falta y dónde ponerla; "Preparar respuesta" queda deshabilitado.
- **Cargando:** dice qué está pasando: "Leyendo el mensaje, cotizando con tu tarifario y redactando la respuesta…".
- **Sin cuota:** muestra el ejemplo guardado con un aviso que dice que no corresponde al mensaje pegado.
- **Error:** mensaje claro (clave inválida, o "intenta de nuevo en un minuto") con el detalle técnico plegado.
- **Vacío:** antes de la primera consulta, una tarjeta explica qué va a aparecer.

## Microcopia

Verbos y español claro: "Preparar respuesta", "Abrir en WhatsApp", "Descargar tarifario", "Revisa antes de enviar", "Corrige antes de enviar". Para el vendedor no hay jerga técnica, salvo la línea de modelo y tokens, que es para la demo.

## Límites de Streamlit 1.67

- **El botón de subir archivos dice "Upload" y "5MB per file", en inglés.** `st.file_uploader` no tiene parámetro para ese texto, y cambiarlo exigiría CSS sobre clases internas. La etiqueta del campo sí está en español.
- **Las fuentes se cargan desde Google Fonts.** Sin internet, la app usa las fuentes del sistema. El logo no depende de eso: lleva incrustadas las letras de "Abra Travel" en Montserrat (licencia OFL).
