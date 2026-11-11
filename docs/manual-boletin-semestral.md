# Manual del boletín semestral "Proyección Social EN ACCIÓN"

Este manual explica cómo se arma, cada semestre, el boletín de proyección social de la Facultad de
Ingenierías y Ciencias Básicas. Tiene dos partes:

- **Para los monitores**, que corren el programa.
- **Para la Coordinación de Proyección Social**, que entrega la información.

El programa toma un archivo de texto con el contenido del semestre y produce dos cosas con el mismo
diseño: una **página web**, que se publica en el sitio de Proyección Social, y un **PDF**, que se sube
a Heyzine como siempre.

---

## Parte 1 — Para los monitores

### Antes de empezar (una sola vez por computador)

Necesitas tener instalado [uv](https://docs.astral.sh/uv/) y una copia del repositorio. Desde la
carpeta del repositorio, corre:

```bash
uv sync
```

```bash
uv run playwright install chromium
```

El segundo comando descarga el navegador con el que se genera el PDF. Solo hace falta una vez.

### El ciclo de cada semestre

| Paso | Quién | Qué hacer |
|---|---|---|
| 1 | Coordinación | Manda su correo de actividades, las fotos y los datos de la Parte 2 |
| 2 | Monitor | Crea la edición con `nueva` |
| 3 | Monitor | Llena `edicion.toml` y copia las fotos en `fotos/` |
| 4 | Monitor | Genera la vista previa con `armar` y revisa los pendientes |
| 5 | Mónica Vásquez | Revisa el PDF de la vista previa y aprueba o pide cambios |
| 6 | Monitor | Cambia el estado a `aprobada` y vuelve a correr `armar` |
| 7 | Monitor | Sube el cambio a `main`: GitHub publica la edición en el sitio |
| 8 | Monitor | Sube el PDF a Heyzine |

#### Paso 2: crear la edición

```bash
uv run semestral nueva 2026-2
```

El semestre se escribe como `AAAA-1` (primer semestre) o `AAAA-2` (segundo semestre). Verás:

```
Edición creada en datos\semestral\2026-2.
Llena datos\semestral\2026-2\edicion.toml y copia las fotos en datos\semestral\2026-2\fotos.
```

La edición nueva copia las secciones de la anterior, en el mismo orden y con los mismos títulos, pero
vacías y marcadas como pendientes. La primera edición del programa, el Vol. 8, parte de la estructura
del Vol. 7. El número de volumen se calcula solo.

#### Paso 3: llenar `edicion.toml`

Abre `datos/semestral/2026-2/edicion.toml` con cualquier editor de texto (VS Code, PyCharm, Bloc de
notas). Arriba van los datos generales:

```toml
volumen = 8
semestre = "2026-2"
fecha = "Diciembre 2026"     # el texto que se imprime en la portada
estado = "borrador"          # cámbialo a "aprobada" solo cuando Mónica apruebe

[portada]
titular = "Ecohumboldt, entre las 20 experiencias del país en acción climática"
foto = "portada.jpg"

[editorial]
titulo = "Construyendo *impacto* desde la academia"
cuerpo = """
Primer párrafo del editorial.

Segundo párrafo. Los párrafos se separan con una línea en blanco.
"""
firma = "Coordinación de Proyección Social"
```

Debajo va una sección `[[secciones]]` por cada página del boletín, en el orden en que aparecen. Todas
tienen estos campos:

- `tipo`: qué clase de página es (ver abajo).
- `etiqueta`: una palabra corta. El programa le pone el número de la sección y la muestra en rojo
  arriba del título, por ejemplo "04 · Planeta".
- `titulo`: el título de la página.
- `pendiente`: lo que falta y a quién pedirlo. **Borra esta línea cuando la sección esté completa.**

**Dos marcas de formato:**

- En un **título**, la palabra entre asteriscos sale en la letra manuscrita roja del boletín:
  `titulo = "Proyectos que *transforman*"`.
- En un **cuerpo**, el texto entre dos asteriscos sale en negrita: `**VII jornada de siembra**`.

No se puede escribir HTML: el programa lo muestra tal cual, como texto.

**Los seis tipos de sección**, cada uno con un ejemplo:

`texto`: un texto con fotos. La primera foto va grande arriba; las otras dos, abajo, con su pie.

```toml
[[secciones]]
tipo = "texto"
etiqueta = "Planeta"
titulo = "Nuestro compromiso con el *planeta*"
cuerpo = """
Estudiantes de Ingeniería Industrial y de Software participaron en la **VII jornada
institucional de siembra de árboles**.
"""
fotos = [
  { archivo = "siembra.jpg", pie = "VII jornada de siembra" },
  { archivo = "taller.jpg", pie = "Taller de huella de carbono" },
]
```

`cifras`: de 2 a 6 números grandes con su explicación, y una foto opcional abajo.

```toml
[[secciones]]
tipo = "cifras"
etiqueta = "Cifras"
titulo = "Proyección social en *cifras*"
foto = "siembra.jpg"
cifras = [
  { valor = "158", texto = "personas sensibilizadas en los talleres de huella de carbono" },
  { valor = "21", texto = "emprendedores vinculados a la ruta de emprendimiento" },
]
```

`proyectos`: una ficha por proyecto, con foto, docentes, programas y una o dos líneas.

```toml
[[secciones]]
tipo = "proyectos"
etiqueta = "Comunidades"
titulo = "Proyectos que *transforman*"

[[secciones.proyectos]]
nombre = "Huellas con Bienestar"
docentes = ["Diana María Melo Taborda"]
programas = ["Ingeniería de Software", "Medicina Veterinaria"]
descripcion = "Bienestar animal y relación entre la universidad y la comunidad."
foto = "huellas.jpg"
```

Para agregar otro proyecto, repite el bloque `[[secciones.proyectos]]` debajo del anterior.

`comparativo`: barras del semestre actual frente al mismo semestre del año anterior, con la meta en
rojo. Los valores van de 0 a 100.

```toml
[[secciones]]
tipo = "comparativo"
etiqueta = "Prácticas empresariales"
titulo = "Indicadores de *prácticas*"
periodo_anterior = "2025-2"
periodo_actual = "2026-2"
meta = 80

[[secciones.grupos]]
nombre = "Ingeniería Industrial"
indicadores = [
  { nombre = "Satisfacción de estudiantes con los escenarios de práctica", anterior = 87.2, actual = 90.0 },
  { nombre = "Impacto de la empresa", anterior = 90.0, actual = 100.0 },
]
```

Repite el bloque `[[secciones.grupos]]` para cada programa (Ingeniería de Software, etc.).

`videos`: en la web se ven ahí mismo; en el PDF salen como foto, código QR y enlace. El enlace debe
empezar con `https://`.

```toml
[[secciones]]
tipo = "videos"
etiqueta = "Videos"
titulo = "Videos de la *proyección social*"

[[secciones.videos]]
titulo = "Jornada de siembra 2026"
enlace = "https://www.youtube.com/watch?v=XXXXXXXXXXX"
miniatura = "siembra.jpg"
```

`imagen`: una imagen a página completa, como la infografía del sistema de proyección social. La
`descripcion` es obligatoria: es lo que leen las personas que usan lector de pantalla.

```toml
[[secciones]]
tipo = "imagen"
etiqueta = "Sistema"
titulo = "Sistema de *proyección social*"
archivo = "sistema.png"
descripcion = "Ejes, líneas y productos del sistema de proyección social de la Facultad"
```

**Las fotos**

- Cópialas en `datos/semestral/2026-2/fotos/`.
- Usa nombres en minúscula y sin espacios: `siembra-filandia.jpg`, no `WhatsApp Image 2026-11-02.jpeg`.
- El nombre en `edicion.toml` debe ser **exactamente** el del archivo, con mayúsculas y extensión.
- No te preocupes por el tamaño: el programa reduce las fotos grandes al armar.
- **El repositorio es público.** Solo copia fotos que la Coordinación haya entregado para el boletín.

#### (Opcional) Pedirle a Claude un borrador de los textos

Si tienes una clave de la API de Anthropic, guarda el texto del correo de la Coordinación en un archivo
(por ejemplo `correo.txt`) y corre:

```bash
uv run semestral borrador 2026-2 --correo correo.txt
```

Claude propone un texto por sección en `datos/semestral/2026-2/borrador-sugerido.toml`. **Ese archivo
no se publica, y el programa nunca toca `edicion.toml`.** Copia lo que te sirva y revisa cada dato
contra el correo original. Este paso es opcional: todo lo demás funciona sin él.

#### Paso 4: la vista previa

```bash
uv run semestral armar 2026-2
```

Genera la web y el PDF con la marca **BORRADOR**, en `salida/semestral/2026-2/`. Verás algo así:

```
Vista previa: salida\semestral\2026-2\index.html
PDF: salida\semestral\2026-2\boletin-vol-8-borrador.pdf
Fotos reducidas: siembra.jpg, taller.jpg
Pendientes (3):
- 06 · Prácticas empresariales — Indicadores de *prácticas*: Faltan los indicadores de prácticas de este semestre (...)
- 09 · Docentes — Vinculación de *docentes*: Faltan los docentes vinculados por programa. (...)
- 10 · Videos — Videos de la *proyección social*: Faltan los enlaces de los videos del semestre. (...)
```

Cada pendiente dice qué falta y a quién pedirlo. En el PDF aparece como un recuadro rojo en su página,
para que Mónica lo vea. El programa nunca inventa un dato para llenar un hueco.

Si el programa avisa `Secciones de más de una página: ...`, esa sección no cabe en una hoja. Se puede
dejar así, porque sigue en la página siguiente, o acortar el texto.

#### Paso 5: la aprobación

Manda a Mónica Vásquez el PDF de la vista previa (`boletin-vol-8-borrador.pdf`). Si pide cambios,
corrige `edicion.toml` y vuelve a correr `armar`.

#### Paso 6: aprobar

Cuando Mónica apruebe y no quede ningún pendiente, cambia en `edicion.toml`:

```toml
estado = "aprobada"
```

y vuelve a correr:

```bash
uv run semestral armar 2026-2
```

Ahora el resultado va a `datos/semestral/2026-2/publicada/`, sin la marca BORRADOR, con el PDF
`boletin-vol-8.pdf`. **Una edición aprobada con pendientes no se puede publicar**: el programa se
detiene y te dice cuáles quedan.

#### Paso 7: publicar

Sube a `main` la carpeta de la edición (o abre un pull request, si así lo maneja el equipo):

```bash
git add datos/semestral/2026-2
```

```bash
git commit -m "chore(semestral): Vol. 8 aprobado"
```

```bash
git push
```

GitHub publica la edición en el sitio, en la sección `/semestral/`, en menos de un minuto. El sitio
solo muestra ediciones aprobadas: un borrador nunca llega ahí.

#### Paso 8: subir a Heyzine

Descarga el PDF desde el sitio (botón "Descargar PDF") o tómalo de
`datos/semestral/2026-2/publicada/boletin-vol-8.pdf`, y súbelo a Heyzine como se hacía con las
ediciones anteriores.

### Si ves este mensaje, haz esto

| Mensaje | Qué hacer |
|---|---|
| `edicion.toml, línea N: no es un TOML válido (...)` | Hay un error de escritura en esa línea: casi siempre una comilla sin cerrar o una coma de más. |
| `Hay errores en edicion.toml:` seguido de `Sección N («...»), campo ...` | Ve a esa sección y corrige el campo que nombra; el mensaje dice qué esperaba. |
| `el tipo «...» no existe; usa uno de estos: texto, cifras, proyectos, comparativo, videos, imagen` | El `tipo` está mal escrito. Usa uno de los seis. |
| `este campo no existe (¿está bien escrito?)` | Ese nombre de campo tiene un error de dedo, o el campo no es de ese tipo de sección. |
| `vale 101.0 y debe ser como máximo 100.0` | Los valores del comparativo van de 0 a 100. |
| `el enlace del video debe empezar con https://` | Copia el enlace completo desde el navegador. |
| `Faltan estas fotos en ... (el nombre debe coincidir exacto, con mayúsculas y extensión): ...` | Copia esas fotos en `fotos/`, o corrige el nombre en `edicion.toml` para que sea idéntico al del archivo. |
| `La carpeta se llama «...» pero edicion.toml dice semestre = "...". Deben coincidir.` | Corrige el `semestre` del archivo o el nombre de la carpeta. |
| `Fotos pequeñas (se verán borrosas): ...` | Es un aviso, no un error. Pide a la Coordinación la foto original, no la reenviada por WhatsApp. |
| `Secciones de más de una página: ...` | Es un aviso. Acorta el texto si quieres que quepa en una hoja. |
| `La edición está aprobada pero tiene pendientes:` | Completa los pendientes de la lista o quita esas secciones del archivo. |
| `Falta el navegador con el que se genera el PDF. Instálalo una sola vez con: uv run playwright install chromium` | Corre ese comando una vez. |
| `La edición 2026-2 ya existe en ...; no se sobrescribe.` | La edición ya fue creada: ábrela y sigue llenándola. |
| `El semestre «...» no es válido: usa la forma AAAA-1 o AAAA-2, por ejemplo 2026-2.` | Escribe el semestre como `2026-2`. |
| `Falta ANTHROPIC_API_KEY; el resto del programa funciona sin este paso.` | El borrador con Claude necesita una clave. Puedes seguir sin él. |
| `No se pudo obtener una propuesta de Claude; el resto del programa funciona sin este paso.` | Falló la conexión o la clave. Llena los textos a mano. |

---

## Parte 2 — Para la Coordinación de Proyección Social

Para que el boletín salga completo, cada semestre necesitamos, **unas tres semanas antes del cierre
del semestre** (a mediados de mayo y a mediados de noviembre):

1. **El correo de actividades del semestre**, como el que se envía a la Facultad.
2. **Las fotos en tamaño original**, no reenviadas por WhatsApp, que se ven borrosas al imprimir.
3. **Las cifras del semestre**: personas sensibilizadas, emprendedores vinculados, participantes en
   talleres y diplomados.
4. **Los indicadores de prácticas empresariales** de este semestre y del mismo semestre del año
   anterior, por programa.
5. **Los proyectos nucleares** del semestre y sus empresas aliadas.
6. **Los egresados vinculados con Team Teaching** y en qué asignaturas.
7. **Los docentes vinculados por programa.**
8. **Los enlaces de los videos** del semestre.

Lo que no llegue queda marcado como **pendiente** en la vista previa: el boletín no inventa datos.

**Importante:** el boletín y su repositorio son públicos. Solo envíen fotos que se puedan publicar.
En las fotos con menores de edad, como las de los colegios, la Coordinación responde por la
autorización de uso, igual que en las ediciones anteriores.

---

## Datos por confirmar

- Quién administra la cuenta de Heyzine donde se publican los PDF.

---

*Diseño completo del programa: `docs/superpowers/specs/2026-11-11-boletin-semestral-design.md`.*
