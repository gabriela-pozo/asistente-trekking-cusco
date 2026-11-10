# Sistema de diseño de Abra Travel

**Usuario:** el dueño o vendedor de una agencia de trekking en Cusco, que responde a viajeros desde la laptop o el celular, muchas veces de noche.
**Momento clave:** pega la consulta y en segundos tiene una respuesta lista para enviar. El borrador y el botón "Abrir en WhatsApp" son la pantalla. El perfil, las opciones y los avisos son el respaldo que le da confianza para enviarlo.
**Marca:** "Abra" es el punto más alto de un trek (abra Salkantay, 4 600 m). Tono confiable, local, sereno y preciso.

Dónde vive cada cosa: el tema en `.streamlit/config.toml`, el CSS que el tema no cubre en `app/estilo.css`, el formato de datos en `app/presentacion.py` y el logo en `assets/`.

## Color

| Rol | Color | Contraste sobre blanco | Uso |
| --- | --- | --- | --- |
| Primario | `#1E6B52` | 6,4:1 | Acciones, marca, enlaces |
| Tinta | `#15302B` | 14,1:1 | Texto |
| Secundario | `#5B6F6A` | 5,4:1 | Texto de apoyo, rótulos |
| Fondo / superficie / suave | `#F7F9F8` / `#FFFFFF` / `#E8F0EC` | — | Página / tarjetas / barra lateral, campos y fichas |
| Bordes | `#D6E0DD` | — | Tarjetas y tablas |
| Acento ocre | `#C9741D` | 3,5:1 | **Solo** el dato que más importa: barra de cada opción |
| Ocre para texto | `#9A5512` | 5,7:1 | El precio por persona |
| Éxito / aviso / error | `#2F7A4F` / `#B7791F` / `#B4471F` | 5,2 / 3,6 / 5,4 | Mensajes del control |
| Aviso para texto | `#7A4E0F` | 7,2:1 | Texto de los avisos |

El ocre y el amarillo de aviso no llegan a 4,5:1 sobre blanco. Por eso se usan en barras y bordes, y su texto va en el tono oscurecido de la misma familia. Todo el texto cumple WCAG AA (4,5:1), también sobre los fondos de los avisos.

Los avisos se separan por gravedad:
- **Error (rojo), arriba:** montos que no están en la cotización, depósito que no cuadra, trek sin precio, mensaje sin precio.
- **Aviso (amarillo):** lo demás que hay que revisar.
- **Informativo (verde grisáceo):** el ejemplo guardado y el aviso para el viajero.

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

- Espaciado en múltiplos de 8. Radio de 10 px en tarjetas, botones y fichas.
- La sombra es casi imperceptible y va **solo en la tarjeta del borrador**: es lo único que "flota".
- Iconos: Material Symbols de Streamlit, solo en acciones y avisos. Sin emojis decorativos.

## Orden de la pantalla "Nueva consulta"

1. Encabezado de una línea y la tarjeta de entrada: mensaje, teléfono, "Preparar respuesta".
2. **Tarjeta del borrador**: texto editable, contador de palabras, "Respondió: modelo · tokens" y el botón "Abrir en WhatsApp" a todo el ancho de la tarjeta.
3. Avisos del control agrupados: lo grave en rojo y arriba.
4. Opciones como filas comparables: trek, días, nivel, el **precio por persona destacado en ocre**, total y depósito, y la etiqueta "Alternativa" cuando corresponde.
5. Perfil del viajero en fichas legibles ("Inglés", "Salkantay", "marzo"). Lo que falta va como etiqueta.

En la laptop, el borrador y las opciones van lado a lado (7:5). En el celular todo va en una columna, con el borrador primero. A 1440 × 900, el botón de WhatsApp queda en la primera pantalla.

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
