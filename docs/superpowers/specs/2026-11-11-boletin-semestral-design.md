# Diseño — Boletín semestral "Proyección Social EN ACCIÓN"

**Programa 3 de 3** · Área de Proyección Social, Facultad de Ingenierías y Ciencias Básicas
Corporación Universitaria Empresarial Alexander von Humboldt · Armenia, Quindío

**Fecha:** 11 de noviembre de 2026
**Estado:** aprobado en brainstorming (cuatro partes), pendiente de revisión de este documento y de plan
de implementación

---

## 1. Propósito

Un programa que arma cada semestre el boletín de proyección social de la Facultad, en dos formatos
salidos del mismo diseño: una **página web** dentro del sitio que ya publica el boletín de empleos, y un
**PDF** que se sube a Heyzine como hasta ahora.

**Problema que resuelve.** El boletín se rehace a mano cada semestre en una herramienta de diseño a partir
del correo de actividades de la Coordinación. El Vol. 7 (junio de 2026) es la versión diseñada del correo
*"📢 Actividades de proyección social"* del 19 de junio: las cifras coinciden una a una. Con el programa,
la estructura y el diseño quedan fijos y cada semestre solo cambia el contenido.

**Primera edición:** el Vol. 8 (semestre 2026-2), que sale del correo de la Coordinación del 6 de
noviembre de 2026 y debe publicarse en **diciembre de 2026**.

Referencias: análisis del Vol. 7 en `docs/02-analisis-boletin-anterior.md`; PDF en
`docs/referencias/boletin-semestre-anterior.pdf`.

## 2. Lo acordado y lo supuesto

**Dicho por el usuario**

| Tema | Decisión |
|---|---|
| Qué se entrega | Un programa reusable; el Vol. 8 es su primera edición |
| Quién lo usa | Ambos: la Coordinación entrega la información y los monitores corren el programa |
| Formato | Web + PDF; el PDF se sube a Heyzine |
| Fecha del Vol. 8 | Diciembre de 2026 |
| Quién aprueba | Mónica Vásquez, docente que supervisa la monitoría |
| Enfoque | A: un archivo de contenido por edición, del que salen web y PDF |
| Dirección visual | B: "Vol. 7 refinado" |
| Manual | Un manual de uso para monitores y Coordinación es entregable del proyecto |

**Supuesto (corregir si no es así)**

- Se conservan las secciones del Vol. 7 y los colores del escudo.
- El programa vive en este repositorio y se publica en el mismo sitio.
- Subir el PDF a Heyzine lo hace una persona.

**Éxito:** en diciembre Mónica aprueba la vista previa y el Vol. 8 queda en la web y en PDF; en junio de
2027 el Vol. 9 se arma llenando un archivo nuevo, sin tocar el diseño ni el código.

## 3. Alcance

### Dentro

- Paquete `src/boletin_semestral/` con tres comandos: `nueva`, `borrador` y `armar`.
- Archivo de contenido por edición (TOML) con seis tipos de sección.
- Página web y PDF generados del mismo HTML.
- Vista previa marcada como BORRADOR, con las secciones pendientes a la vista.
- Sección `/semestral/` del sitio: última edición, PDF descargable y archivo de volúmenes anteriores.
- Borrador opcional de textos a partir del correo de la Coordinación, con Claude.
- Manual de uso en `docs/manual-boletin-semestral.md`.
- El Vol. 8 como primera edición real.

### Fuera

- **Publicar en Heyzine automáticamente.** Se sube a mano.
- **Leer Gmail directamente.** El monitor copia el texto del correo y descarga las fotos; no hay OAuth.
- **Formulario para la Coordinación** (enfoque B, descartado): pide credenciales de Google
  institucionales y sirve mal para textos largos y fotos.
- **Enviar el boletín por correo.**
- **Editor visual.** El contenido se edita en el archivo TOML.
- **Rehacer los Vol. 1 a 7 en el programa.** El Vol. 7 aparece en el archivo como enlace a Heyzine.

## 4. Decisiones y su razón

| Decisión | Elección | Razón |
|---|---|---|
| Fuente del contenido | Archivo TOML por edición, en el repositorio | Mismo formato que `programas/*.toml`; queda versionado y comparable entre semestres |
| Estructura | Lista ordenada de secciones con un `tipo` | Las secciones nuevas (Emprendimiento, reconocimientos) se agregan sin tocar código |
| Web y PDF | Un solo HTML; el PDF se imprime con Chromium (Playwright) | Las dos versiones no se separan con el tiempo; WeasyPrint exige GTK en Windows |
| Dónde se genera la edición aprobada | En el computador del monitor; se guarda en el repositorio con su HTML, su PDF y sus fotos | Ver §9: el flujo quincenal de empleos republica el sitio entero. Lo aprobado es exactamente lo publicado |
| Dirección visual | B, "Vol. 7 refinado" (§8) | Se reconoce como el mismo boletín y aguanta contenido de cualquier largo |
| Borrador con IA | Opcional, escribe en un archivo aparte | Nunca pisa lo que escribió una persona; sin clave de API el programa funciona igual |
| Ediciones anteriores | Se publican todas (archivo) | A diferencia de las vacantes, los boletines no vencen: son memoria de la Facultad |
| Pendientes | Visibles en el borrador; impiden aprobar | Nunca se inventa un dato para llenar un hueco |
| Fuentes tipográficas | Fredoka, Kaushan Script e Inter, guardadas en el repositorio | Licencia OFL; el PDF no depende de internet |

## 5. Flujo de trabajo de cada semestre

| Paso | Quién | Qué |
|---|---|---|
| 1 | Coordinación | Manda su correo de actividades con fotos, como siempre, más las cifras que el boletín necesita (§12) |
| 2 | Monitor | `uv run semestral nueva 2026-2`: crea `datos/semestral/2026-2/` con el orden de secciones de la edición anterior (o, si no hay ninguna, con el esqueleto base que reproduce la estructura del Vol. 7), todo marcado como pendiente |
| 3 | Monitor | Llena `edicion.toml` y copia las fotos en `fotos/`. Opcional: `uv run semestral borrador 2026-2 --correo correo.txt` |
| 4 | Monitor | `uv run semestral armar 2026-2`: vista previa en `salida/semestral/2026-2/` (web + PDF con marca BORRADOR) y lista de pendientes |
| 5 | Mónica | Revisa el PDF de la vista previa y pide cambios o aprueba |
| 6 | Monitor | Cambia `estado = "aprobada"` y corre `armar` otra vez: genera la edición final en `datos/semestral/2026-2/publicada/` |
| 7 | Monitor | Sube el cambio a `main`: GitHub publica la edición en `/semestral/` |
| 8 | Monitor | Descarga el PDF publicado y lo sube a Heyzine |

El programa no verifica quién aprobó: el monitor cambia el estado solo después del visto bueno de Mónica,
y el historial de git deja constancia de quién lo hizo y cuándo.

## 6. El archivo de la edición

### 6.1 Carpeta

```
datos/semestral/
  anteriores.toml                 volúmenes previos al programa (Vol. 7 → Heyzine)
  2026-2/
    edicion.toml                  el contenido, lo único que se edita a mano
    fotos/                        las fotos que nombra edicion.toml
    borrador-sugerido.toml        lo que propuso `borrador` (opcional, no se publica)
    publicada/                    solo existe cuando la edición está aprobada
      index.html
      boletin-vol-8.pdf
      fotos/ · estilo.css · fuentes/
```

`salida/` (la vista previa) se ignora en git.

### 6.2 Campos generales

```toml
volumen = 8
semestre = "2026-2"          # AAAA-1 o AAAA-2
fecha = "Diciembre 2026"     # texto que se imprime
estado = "borrador"          # borrador | aprobada

[portada]
titular = "Ecohumboldt, entre las 20 experiencias del país en acción climática"
foto = "portada.jpg"

[editorial]
titulo = "Construyendo *impacto* desde la academia"
cuerpo = """Párrafos separados por una línea en blanco. Se permite **negrita**."""
firma = "Coordinación de Proyección Social"
```

La contraportada se arma sola con el volumen, la fecha y los logos. Puede llevar una `foto` opcional.

### 6.3 Secciones

Cada `[[secciones]]` tiene estos campos comunes:

- `tipo`: uno de los seis de abajo.
- `etiqueta`: palabra corta; con el número de la sección forma el antetítulo, por ejemplo "04 · Planeta".
- `titulo`: la palabra entre asteriscos sale en la letra manuscrita roja: `"Proyectos que *transforman*"`.
- `pendiente`: opcional. Dice qué falta y a quién pedirlo, por ejemplo "Falta el número de egresados de
  Team Teaching. Pedir a: Coordinación".

| `tipo` | Campos propios | Uso en el Vol. 7 / Vol. 8 |
|---|---|---|
| `texto` | `cuerpo`; `fotos = [{ archivo, pie }]` (la primera va grande; hasta tres) | Planeta, Monitores, Emprendimiento, Egresados, Docentes |
| `cifras` | `cifras = [{ valor, texto }]` (de 2 a 6) | Proyección social en cifras |
| `proyectos` | `proyectos = [{ nombre, docentes, programas, descripcion, foto }]` | Proyectos que transforman, Proyectos nucleares, Propuestas 2027 |
| `comparativo` | `periodo_anterior`, `periodo_actual`, `meta`; `grupos = [{ nombre, indicadores = [{ nombre, anterior, actual }] }]` | Indicadores de prácticas empresariales |
| `videos` | `videos = [{ titulo, enlace, miniatura }]` | Videos de la proyección social |
| `imagen` | `archivo`, `descripcion` (texto alternativo obligatorio) | Sistema de Proyección Social (infografía) |

El tipo `imagen` se agregó al escribir este documento: la página 7 del Vol. 7 es una infografía, y
ninguno de los otros cinco tipos la cubría.

**Reglas de validación** (modelo con pydantic, unión discriminada por `tipo`):

- Los porcentajes del comparativo van de 0 a 100.
- `enlace` de un video es una URL https.
- Toda foto nombrada existe en `fotos/`.
- `semestre` cumple `AAAA-1|2`.
- Una sección está **pendiente** si tiene `pendiente` o si le falta su contenido mínimo: cuerpo, al menos
  una cifra, un proyecto, un indicador, un video o el archivo de la imagen. La portada sin titular o sin
  foto y el editorial sin cuerpo también cuentan como pendientes.
- El texto se escapa siempre: el archivo no admite HTML, solo párrafos, `**negrita**` y `*manuscrita*` en
  los títulos.

## 7. Arquitectura

```
src/boletin_semestral/
  modelo.py        Edicion, Portada, Editorial y una clase por tipo de sección (pydantic)
  edicion.py       cargar(carpeta) -> Edicion · nueva(semestre) copia el esqueleto de la anterior
  esqueleto.toml   estructura base del Vol. 7 (portada, editorial, 10 secciones), para la primera edición
  fotos.py         verifica que existan y reduce en el lugar las de más de 1800 px o 1,5 MB
  borrador.py      texto del correo -> borrador-sugerido.toml (Claude; nunca toca edicion.toml)
  render.py        Edicion -> HTML (Jinja2, autoescape) en modo "borrador" o "final"
  pdf.py           HTML -> PDF A4 con Chromium (Playwright); mide si alguna sección pasa de una página
  sitio.py         copia las ediciones publicadas a sitio/semestral/ y arma su portada
  cli.py           semestral nueva | borrador | armar
  plantillas/      boletin.html.j2 y una plantilla parcial por tipo de sección
  estaticos/       estilo.css (pantalla + impresión), movimiento.js, fuentes/ (woff2)
```

- **Entrada de consola:** `semestral = "boletin_semestral.cli:main"` en `pyproject.toml`.
- **Dependencias nuevas:** `jinja2` (hoy solo llega de forma indirecta), `pillow`, `playwright` y
  `segno`, que genera los códigos QR de los videos en Python puro.
- **Lo que reutiliza del boletín de empleos:** el logo (`render/estaticos/logo-humboldt.png`) y los
  nombres institucionales (`INSTITUCION` y `UNIDAD` de `render/web.py`), importados, no copiados.

**`armar`, paso a paso**

1. Carga y valida `edicion.toml`. Ante un error se detiene sin generar nada.
2. Verifica y reduce las fotos.
3. Calcula la lista de pendientes.
4. Si `estado = "borrador"`:
   - genera HTML y PDF en `salida/semestral/<semestre>/`, con la marca BORRADOR y los recuadros de
     pendientes;
   - imprime la lista de pendientes y avisa de las secciones que ocupan más de una página.
5. Si `estado = "aprobada"`:
   - si hay pendientes, error con la lista;
   - si no, genera en `datos/semestral/<semestre>/publicada/` el HTML final, el PDF `boletin-vol-N.pdf`,
     las fotos y los estáticos. Cada edición publicada es autosuficiente: si el diseño cambia después,
     las ediciones viejas se ven como el día en que se aprobaron.

## 8. Diseño visual — dirección B, "Vol. 7 refinado"

Las maquetas aprobadas quedaron en `.superpowers/brainstorm/` (pantallas `direccion-visual.html` y
`tipos-de-seccion.html`).

**Identidad que se conserva del Vol. 7**

- El título en dos tonos: palabra gruesa en azul (Fredoka 700) y palabra manuscrita en rojo
  (Kaushan Script).
- Los colores del escudo y el pie "Proyección Social | Boletín Semestral" con el número de página.

**Lo que cambia**

- Retícula fija: foto arriba, texto abajo, márgenes constantes.
- Texto en Inter, alineado a la izquierda y no justificado.
- Antetítulo numerado en rojo ("04 · Planeta").
- Línea roja corta bajo los títulos.
- Se quitan los adornos tipo collage.

**Colores**

| Nombre | Valor | Uso |
|---|---|---|
| Azul | `#143D68` | Títulos, cifras, barras del año actual |
| Azul claro | `#9DB7D6` | Barras del año anterior |
| Rojo | `#BD1822` | Palabra manuscrita, antetítulos, línea de la meta, pendientes |
| Línea | `#DDE3EA` | Divisiones de tablas y fichas |

**Cómo se ve cada tipo** (como en las maquetas):

| Tipo | Disposición |
|---|---|
| Portada | Foto arriba (57 %), marca en dos tonos, línea roja, titular y pie con escudo |
| Cifras | Cuadrícula de 2 × N con número grande y texto, y una franja de foto abajo |
| Texto | Foto grande, una columna de texto y hasta dos fotos con pie |
| Proyectos | Fichas con foto cuadrada, nombre, docentes y programas en rojo, y descripción |
| Comparativo | Por grupo, dos barras por indicador (anterior y actual) y la meta como línea roja |
| Videos | Web: reproductor en la página (`youtube-nocookie` o Drive). PDF: miniatura, QR y enlace corto |
| Imagen | La imagen a página completa, con márgenes |

**PDF:** A4 vertical; cada sección empieza en página nueva. Una sección más larga que una página sigue en la siguiente,
con pie y numeración continuos. El encabezado no se repite, y `armar` avisa para que se recorte si hace
falta. Esto ajusta lo dicho en la parte 3 ("sigue con el mismo encabezado"): repetir el encabezado
exige trocear el texto a mano, y no vale la complejidad.

**Web:**

- Las mismas secciones, una debajo de otra, en una columna de ancho máximo cercano a 760 px.
- Las cifras aparecen con una animación suave al bajar; se desactiva con `prefers-reduced-motion`.
- Funciona en celular.

**Borrador:** marca "BORRADOR" en diagonal muy tenue y recuadro rojo punteado por cada pendiente,
tanto en la web como en el PDF.

## 9. Publicación

**El riesgo que define el diseño.** Hay dos flujos de GitHub que publican el sitio:

- `boletin.yml`, cada quince días;
- `sitio.yml`, cuando cambia el diseño.

Los dos suben a GitHub Pages el sitio **entero**, armado por `boletin_empleos.sitio`. Si la sección
semestral se armara en uno solo, el otro la borraría al publicar.

**Solución:**

- La edición aprobada ya está generada y guardada en `datos/semestral/*/publicada/`.
- `boletin_empleos.sitio`, que usan los dos flujos, llama a `boletin_semestral.sitio.publicar(destino)`.
  Esa función solo copia carpetas y arma la portada de la sección, sin navegador ni red.
- Ningún flujo instala Chromium.
- `sitio.yml` también se activa con cambios en `datos/semestral/**`.

**Estructura publicada**

```
sitio/
  index.html                       portada del sitio + tarjeta "Boletín semestral"
  semestral/
    index.html                     última edición destacada + archivo de volúmenes
    vol-8/  index.html · boletin-vol-8.pdf · fotos/ · estilo.css · fuentes/
    (vol-9/, …)
```

El archivo lista las ediciones publicadas del programa y las de `anteriores.toml`:

```toml
[[anteriores]]
volumen = 7
fecha = "Junio 2026"
enlace = "https://heyzine.com/flip-book/df92099d87.html"
```

**Solo se publican ediciones aprobadas.** Un borrador no tiene carpeta `publicada/`, así que no hay nada
que copiar.

## 10. Errores

| Situación | Comportamiento |
|---|---|
| Campo faltante, tipo desconocido o valor inválido en `edicion.toml` | `armar` se detiene; mensaje con sección (número y título), campo y lo esperado |
| Foto nombrada que no existe | Error con el nombre del archivo |
| Foto de menos de 1000 px de ancho | Aviso: se verá borrosa en el PDF |
| Sección pendiente en borrador | Recuadro rojo; lista al final de `armar` |
| `estado = "aprobada"` con pendientes | Error con la lista; no se genera `publicada/` |
| Enlace de video no https | Error con el título del video |
| Sección de más de una página | Aviso con el título y el número de páginas |
| `borrador` sin clave `ANTHROPIC_API_KEY`, o con un fallo de red | Aviso; no escribe nada; el resto del programa no depende de él |
| Chromium no instalado | Error con el comando exacto: `uv run playwright install chromium` |
| `nueva` sobre un semestre que ya existe | Error; no sobrescribe |
| Falla la publicación en GitHub | Pages conserva el despliegue anterior; nunca queda una versión rota |

## 11. Pruebas

Corren con `pytest`, sin red, igual que las del boletín de empleos.

- **Modelo**
  - Una edición válida carga.
  - Cada error común da su mensaje: tipo desconocido, porcentaje fuera de rango, foto inexistente,
    semestre mal escrito, HTML en el texto (se escapa).
- **`nueva`:** copia el orden y los títulos de las secciones de la edición anterior, vacía el contenido,
  las marca pendientes y se niega a sobrescribir.
- **Render**
  - El borrador lleva la marca y los recuadros.
  - La edición final no lleva ninguna de las dos cosas.
  - Una edición aprobada con pendientes falla.
  - `*palabra*` sale como manuscrita.
  - El ancho de cada barra del comparativo es igual a su porcentaje.
  - Los videos llevan reproductor en la web y QR en el PDF.
- **Fotos:** reduce las grandes en el lugar y no toca las pequeñas.
- **Sitio**
  - Copia solo las ediciones con `publicada/`.
  - La portada de `/semestral/` destaca la última y lista las anteriores, incluidas las de
    `anteriores.toml`.
  - La portada del sitio lleva la tarjeta.
  - Las secciones de empleos no cambian.
- **`borrador`:** con un Claude simulado, igual que el enriquecimiento del boletín de empleos. Escribe
  `borrador-sugerido.toml` válido y nunca toca `edicion.toml`.
- **PDF:** una prueba de humo que genera el PDF de una edición mínima y comprueba que exista y tenga
  páginas. Se salta si Chromium no está instalado.
- **Aceptación:** el Vol. 8 real, aprobado por Mónica.

## 12. Manual de uso

`docs/manual-boletin-semestral.md`, en lenguaje sencillo, con dos partes:

**Para los monitores**

1. Instalar una sola vez: `uv sync` y `uv run playwright install chromium`.
2. Crear la edición con `nueva`.
3. Llenar `edicion.toml`, con un ejemplo de cada tipo de sección.
4. Copiar el texto del correo y descargar las fotos.
5. Usar `borrador` (opcional) y revisar lo que propone.
6. Generar la vista previa con `armar` y leer la lista de pendientes.
7. Pedir la aprobación a Mónica.
8. Aprobar: cambiar el estado, correr `armar` y subir a `main`.
9. Subir el PDF a Heyzine.
10. Qué hacer ante cada error de la tabla del §10.

**Para la Coordinación:** qué mandar cada semestre y para cuándo, porque sin esto la sección queda
pendiente:

- el correo de actividades;
- las fotos en tamaño original;
- las cifras del semestre;
- los datos de prácticas del año actual y del anterior;
- los egresados vinculados con Team Teaching;
- los docentes vinculados por programa;
- los enlaces de los videos.

Y que el repositorio es público: solo deben mandarse fotos que se puedan publicar.

El README del repositorio enlaza el manual.

## 13. Privacidad y repositorio público

- El repositorio y el sitio son públicos, como ya lo es el boletín en Heyzine. Solo entran las fotos
  que la Coordinación entrega para el boletín.
- Las fotos con menores, como las de los colegios del proyecto PRAE, tienen la misma condición que en
  el Vol. 7: la Coordinación responde por la autorización de uso.
- Las fotos se guardan reducidas (máximo 1800 px), no los originales de WhatsApp.
- Cada semestre suma unos 10 a 15 MB al repositorio (fotos y PDF). Es aceptable durante varios años;
  si deja de serlo, las ediciones viejas pueden pasar a Git LFS.

## 14. Riesgos y preguntas abiertas

| Tema | Estado al 11/11/2026 |
|---|---|
| Datos faltantes del Vol. 8 | No están en el correo del 6 de noviembre: cifras destacadas, comparativo de prácticas 2026-2 frente a 2025-2, proyectos nucleares, egresados de Team Teaching, docentes vinculados y videos. Pedirlos a la Coordinación ya |
| Terremoto del 10 de agosto | El correo no lo menciona. Decidir con Mónica si el Vol. 8 lo cubre |
| Diseño ante Mónica | Mónica no ha visto la dirección B. Conviene mostrarle las maquetas antes de construir |
| Fotos del Vol. 8 | Las 10 del correo del 6 de noviembre vienen de WhatsApp. Pedir originales si alguna sale borrosa |
| Migración del repositorio | El equipo de cuatro planea migrar el repositorio. Este programa debe moverse con él sin cambios: no depende de nada fuera del repositorio |
| Cuenta de Heyzine | No se sabe quién la administra; anotarlo en el manual cuando se sepa |

## 15. Criterios de aceptación

1. `uv run semestral nueva 2026-2`, sin ediciones anteriores, crea la carpeta con el esqueleto del
   Vol. 7: portada, editorial y sus 10 secciones en orden, todas pendientes. La contraportada se arma sola.
2. Con el contenido del correo del 6 de noviembre, `armar` produce web y PDF de vista previa con la
   marca BORRADOR y la lista exacta de lo que falta.
3. Una edición aprobada con pendientes no se puede publicar.
4. La edición aprobada aparece en `/semestral/` con su PDF descargable, y sigue ahí después de una
   corrida quincenal del boletín de empleos.
5. El PDF abre en Heyzine sin perder fuentes ni fotos.
6. El manual permite a un monitor que no participó en este diseño armar una edición sin ayuda.
7. Todas las pruebas pasan en GitHub sin red; la prueba de PDF puede saltarse en GitHub.
8. Mónica aprueba el Vol. 8 en diciembre de 2026.
