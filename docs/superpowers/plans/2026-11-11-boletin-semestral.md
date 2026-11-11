# Boletín semestral "Proyección Social EN ACCIÓN" — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un programa que, a partir de un archivo TOML por semestre, genera el boletín semestral de
proyección social de la Facultad como página web y como PDF, lo deja revisar como borrador y publica en
el sitio solo las ediciones aprobadas.

**Architecture:** Paquete nuevo `src/boletin_semestral/` junto a `boletin_empleos`. Flujo:
TOML → modelo pydantic → HTML con Jinja2 → PDF con Chromium (Playwright). La edición aprobada se genera
en el computador del monitor y queda versionada en `datos/semestral/<semestre>/publicada/`. El
constructor del sitio, que usan los dos flujos de GitHub, solo copia esas carpetas.

**Tech Stack:** Python 3.13 · uv · pydantic v2 · Jinja2 · Pillow · Playwright (Chromium) · segno ·
tomli-w · anthropic · pytest · selectolax · Ruff

**Spec:** `docs/superpowers/specs/2026-11-11-boletin-semestral-design.md`. Quien ejecute este plan
lee las dos cosas: el spec dice el porqué; este plan, los nombres y las pruebas.

## Global Constraints

- **Python ≥ 3.13.** Se usan `StrEnum` y la sintaxis `X | None`.
- **Todo en español:** nombres de símbolos, comentarios, mensajes al usuario y nombres de pruebas.
- **Formato:** `uv run ruff format .` y `uv run ruff check .` pasan antes de cada commit. `docs/` está
  excluido en `pyproject.toml`; si tras formatear aparece `docs/` modificado, la exclusión se perdió.
- **Pruebas sin red.** La prueba de PDF se salta (`pytest.skip`) si Chromium no está instalado. Ninguna
  prueba llama a Claude de verdad.
- **Colores** (spec §8): azul `#143D68`, azul claro `#9DB7D6`, rojo `#BD1822`, línea `#DDE3EA`.
- **Fuentes:** Fredoka 700, Kaushan Script 400 e Inter 400/600/700, guardadas en el repositorio (woff2,
  subconjunto latin, licencia OFL). Nada se carga de Google Fonts en tiempo de ejecución.
- **Fotos:** se reducen en el lugar si pasan de 1800 px en el lado mayor o de 1,5 MB; aviso si miden
  menos de 1000 px de ancho.
- **El TOML nunca inyecta HTML:** Jinja2 con `autoescape=True`. Solo se interpretan `**negrita**` en los
  cuerpos y `*manuscrita*` en los títulos.
- **Solo se publica una edición con `estado = "aprobada"` y sin pendientes.**
- **`borrador` nunca escribe `edicion.toml`.**
- **Ningún flujo de GitHub instala Chromium.** El sitio solo copia carpetas `publicada/`.
- **El boletín de empleos no cambia** salvo lo de la Tarea 7: la tarjeta en la portada y la llamada a
  la sección semestral.
- **Modelo de Claude para `borrador`:** `claude-opus-5-5`, con
  `betas=["server-side-fallback-2026-07-01"]` y `fallbacks="default"`.

## Review Focus

1. **TOML mal escrito** (una comilla sin cerrar): el monitor espera un mensaje con el número de línea,
   no un traceback. → Tarea 2, `test_toml_roto_dice_la_linea`.
2. **Mayúsculas en el nombre de una foto** (`Siembra.JPG` en el archivo, `siembra.jpg` en disco):
   Windows lo acepta y Linux no. Debe fallar igual en los dos. → Tarea 2,
   `test_foto_con_otras_mayusculas_no_cuenta`.
3. **Fotos de WhatsApp con orientación EXIF:** al reducirlas no pueden quedar giradas. → Tarea 3,
   `test_reducir_respeta_la_orientacion`.
4. **Correr `armar` dos veces sobre una edición aprobada:** una foto quitada del archivo no puede seguir
   en `publicada/`. → Tarea 6, `test_publicada_se_regenera_desde_cero`.
5. **Caracteres especiales en los textos** (`&`, `<`, comillas, tildes, `ñ`, un `*` suelto en un
   cuerpo): deben salir tal cual, escapados, y el `*` de un cuerpo no se convierte en manuscrita. →
   Tarea 4, `test_textos_con_caracteres_especiales`.

---

### Task 1: Dependencias, paquete y modelo de la edición

**Files:**
- Modify: `pyproject.toml` (dependencias, entrada `semestral`, paquete en el wheel)
- Modify: `.gitignore` (agregar `salida/`)
- Create: `src/boletin_semestral/__init__.py`
- Create: `src/boletin_semestral/modelo.py`
- Create: `tests/conftest.py`
- Test: `tests/test_semestral_modelo.py`

**Interfaces:**
- Consumes: nada.
- Produces, en `boletin_semestral.modelo`:
  - `Estado(StrEnum)`: `BORRADOR = "borrador"`, `APROBADA = "aprobada"`.
  - Partes: `Foto(archivo: str, pie: str = "")`, `Cifra(valor: str, texto: str)`,
    `Proyecto(nombre: str, docentes: list[str] = [], programas: list[str] = [], descripcion: str = "", foto: str | None = None)`,
    `Indicador(nombre: str, anterior: float, actual: float)` (los dos en `[0, 100]`),
    `Grupo(nombre: str, indicadores: list[Indicador] = [])`,
    `Video(titulo: str, enlace: str, miniatura: str | None = None)` (el `enlace` empieza con `https://`).
  - Secciones, con los campos comunes `etiqueta: str`, `titulo: str`, `pendiente: str | None = None`:
    - `SeccionTexto(tipo: Literal["texto"], cuerpo: str = "", fotos: list[Foto] = [])` (como máximo 3 fotos);
    - `SeccionCifras(tipo: Literal["cifras"], cifras: list[Cifra] = [], foto: str | None = None)` (como máximo 6 cifras);
    - `SeccionProyectos(tipo: Literal["proyectos"], proyectos: list[Proyecto] = [])`;
    - `SeccionComparativo(tipo: Literal["comparativo"], periodo_anterior: str = "", periodo_actual: str = "", meta: float | None = None, grupos: list[Grupo] = [])`;
    - `SeccionVideos(tipo: Literal["videos"], videos: list[Video] = [])`;
    - `SeccionImagen(tipo: Literal["imagen"], archivo: str | None = None, descripcion: str = "")`.
  - `Seccion = Annotated[SeccionTexto | … | SeccionImagen, Field(discriminator="tipo")]`.
  - Generales: `Portada(titular: str = "", foto: str | None = None)`,
    `Editorial(titulo: str = "", cuerpo: str = "", firma: str = "")`,
    `Contraportada(foto: str | None = None)`.
  - `Edicion(volumen: int (≥ 1), semestre: str (^\d{4}-[12]$), fecha: str, estado: Estado = BORRADOR, portada: Portada, editorial: Editorial, contraportada: Contraportada = Contraportada(), secciones: list[Seccion])`.
    Todos los modelos usan `ConfigDict(extra="forbid")`.
  - `Pendiente(NamedTuple)`: `lugar: str`, `motivo: str`.
  - `antetitulo(indice: int, seccion) -> str`: devuelve `"04 · Planeta"` (índice desde 0, número de dos
    cifras).
  - `pendientes(edicion: Edicion) -> list[Pendiente]`.
  - `fotos_nombradas(edicion: Edicion) -> list[str]`: todas las fotos, sin repetir, en orden de
    aparición.
- Produces, en `tests/conftest.py`:
  - fixture `carpeta_edicion(tmp_path) -> Path`: una edición `2026-2` completa y sin pendientes, con sus
    fotos;
  - función `foto_jpg(ruta: Path, ancho=1200, alto=800) -> Path`.

- [ ] **Step 1: Dependencias y paquete**

En `pyproject.toml`:
- agrega a `dependencies`: `"jinja2>=3.1"`, `"pillow>=11"`, `"playwright>=1.49"`, `"segno>=1.6"` y
  `"tomli-w>=1.1"`;
- agrega a `[project.scripts]`: `semestral = "boletin_semestral.cli:main"`;
- deja `packages = ["src/boletin_empleos", "src/boletin_semestral"]`.

En `.gitignore`, agrega `salida/`. Crea `src/boletin_semestral/__init__.py` con un docstring de una
línea. Corre `uv sync`.

- [ ] **Step 2: Fixture compartida en `tests/conftest.py`**

`carpeta_edicion` crea `tmp_path/"semestral"/"2026-2"`, escribe este `edicion.toml` y genera con
`foto_jpg` cada foto que el archivo nombra, en `fotos/`, a 1200×800:

```toml
volumen = 8
semestre = "2026-2"
fecha = "Diciembre 2026"
estado = "borrador"

[portada]
titular = "Ecohumboldt, entre las 20 experiencias del país en acción climática"
foto = "portada.jpg"

[editorial]
titulo = "Construyendo *impacto* desde la academia"
cuerpo = "Primer párrafo.\n\nSegundo párrafo con **negrita**."
firma = "Coordinación de Proyección Social"

[[secciones]]
tipo = "cifras"
etiqueta = "Cifras"
titulo = "El semestre en *números*"
foto = "siembra.jpg"
cifras = [{ valor = "20", texto = "experiencias significativas" }, { valor = "4", texto = "emprendimientos" }]

[[secciones]]
tipo = "texto"
etiqueta = "Planeta"
titulo = "Nuestro compromiso con el *planeta*"
cuerpo = "VII jornada de siembra."
fotos = [{ archivo = "siembra.jpg", pie = "Siembra" }, { archivo = "taller.jpg", pie = "Taller" }]

[[secciones]]
tipo = "proyectos"
etiqueta = "Comunidades"
titulo = "Proyectos que *transforman*"
proyectos = [{ nombre = "Huellas con Bienestar", docentes = ["Diana María Melo Taborda"], programas = ["Ingeniería de Software", "Medicina Veterinaria"], descripcion = "Bienestar animal.", foto = "taller.jpg" }]

[[secciones]]
tipo = "comparativo"
etiqueta = "Prácticas empresariales"
titulo = "Indicadores de *prácticas*"
periodo_anterior = "2025-2"
periodo_actual = "2026-2"
meta = 80
grupos = [{ nombre = "Ingeniería Industrial", indicadores = [{ nombre = "Impacto de la empresa", anterior = 90.0, actual = 100.0 }] }]

[[secciones]]
tipo = "videos"
etiqueta = "Videos"
titulo = "Videos de la *proyección social*"
videos = [{ titulo = "Siembra 2026", enlace = "https://www.youtube.com/watch?v=abc123XYZ00", miniatura = "siembra.jpg" }]

[[secciones]]
tipo = "imagen"
etiqueta = "Sistema"
titulo = "Sistema de *proyección social*"
archivo = "sistema.png"
descripcion = "Ejes, líneas y productos del sistema de proyección social"
```

`sistema.png` se genera como PNG. Las demás fotos son JPG.

- [ ] **Step 3: Escribir las pruebas que fallan, en `tests/test_semestral_modelo.py`**

Cada prueba carga el TOML de `carpeta_edicion` con `tomllib` y lo modifica en memoria antes de validar:

```python
def test_una_edicion_completa_valida_y_no_tiene_pendientes(carpeta_edicion): ...
    # Edicion.model_validate(datos); pendientes(edicion) == []
def test_tipo_desconocido_falla(...)                  # tipo = "foto" -> ValidationError
def test_porcentaje_fuera_de_rango_falla(...)         # actual = 101 -> ValidationError
def test_enlace_de_video_sin_https_falla(...)         # "http://..." -> ValidationError
def test_semestre_mal_escrito_falla(...)              # "2026-3" -> ValidationError
def test_campo_desconocido_falla(...)                 # secciones[0]["color"] = "rojo" -> ValidationError
def test_seccion_marcada_pendiente_cuenta(...)        # pendiente = "Falta X" -> 1 Pendiente, motivo == "Falta X"
def test_seccion_sin_contenido_minimo_cuenta(...)     # texto sin cuerpo, cifras vacías, imagen sin archivo
                                                      # -> 3 pendientes, lugar contiene el antetítulo
def test_portada_sin_titular_y_editorial_sin_cuerpo_cuentan(...)  # lugares "Portada" y "Editorial"
def test_antetitulo_numera_desde_uno_con_dos_cifras(...)  # antetitulo(1, secciones[1]) == "02 · Planeta"
def test_fotos_nombradas_sin_repetir_en_orden(...)    # == ["portada.jpg", "siembra.jpg", "taller.jpg", "sistema.png"]
```

El contenido mínimo de cada tipo:
- `texto`: `cuerpo` no vacío;
- `cifras`: al menos una cifra;
- `proyectos`: al menos un proyecto;
- `comparativo`: al menos un grupo con un indicador;
- `videos`: al menos un video;
- `imagen`: `archivo`.

El `lugar` de un pendiente de sección es `f"{antetitulo(i, s)} — {s.titulo}"`. El `motivo` por falta
de contenido es `"Sin contenido"`.

- [ ] **Step 4: Verificar que fallan**

Run: `uv run pytest tests/test_semestral_modelo.py -v`
Expected: FAIL con `ModuleNotFoundError: boletin_semestral.modelo`

- [ ] **Step 5: Implementar `src/boletin_semestral/modelo.py` con las interfaces de arriba**

- [ ] **Step 6: Verificar que pasan**

Run: `uv run pytest tests/test_semestral_modelo.py -v` → PASS. Run: `uv run pytest` → las 373
pruebas anteriores siguen pasando.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock .gitignore src/boletin_semestral tests/conftest.py tests/test_semestral_modelo.py
git commit -m "feat(semestral): modelo de la edición del boletín semestral"
```

---

### Task 2: Cargar una edición y crear la siguiente

**Files:**
- Create: `src/boletin_semestral/edicion.py`
- Create: `src/boletin_semestral/esqueleto.toml`
- Test: `tests/test_semestral_edicion.py`

**Interfaces:**
- Consumes: `Edicion`, `pendientes`, `fotos_nombradas` (Tarea 1).
- Produces, en `boletin_semestral.edicion`:
  - `ErrorEdicion(Exception)`: su mensaje está escrito para el monitor;
  - `cargar(carpeta: Path) -> Edicion`;
  - `nueva(base: Path, semestre: str) -> Path`: `base` es `datos/semestral`; devuelve la carpeta creada;
  - `describir_error(error: ValidationError, datos: dict) -> str`.

**Reglas de `cargar`**
- Lee `carpeta/"edicion.toml"`. Si `tomllib` falla: `ErrorEdicion("edicion.toml, línea N: …")`.
- Si pydantic falla: `ErrorEdicion(describir_error(...))`. El mensaje nombra la sección como
  `Sección 4 («Indicadores de *prácticas*»)`, la ruta del campo (`grupos[0].indicadores[0].actual`) y lo
  esperado.
- Si el `tipo` no existe, el mensaje lista los seis tipos válidos.
- Si el nombre de la carpeta no es igual a `semestre`: error que nombra los dos.
- Una foto existe solo si su nombre exacto está en `{p.name for p in (carpeta/"fotos").iterdir()}`. Las
  que faltan van todas juntas en un solo error.

**Reglas de `nueva`**
- Rechaza un `semestre` mal escrito y una carpeta que ya existe.
- Busca la edición anterior: la mayor carpeta hermana con `edicion.toml` y un semestre menor.
  - Si la hay, escribe con `tomli_w` una copia con `estado = "borrador"`, el `titular` y los cuerpos
    vacíos, y cada sección con su `tipo`, `etiqueta` y `titulo`, sin contenido y con
    `pendiente = "Falta el contenido de este semestre."`.
  - Si no la hay, copia `esqueleto.toml` como texto, para que conserve sus comentarios, y reemplaza las
    marcas `{volumen}`, `{semestre}` y `{fecha}`.
- `volumen` = el máximo entre los volúmenes de las ediciones existentes y los de `anteriores.toml`,
  más 1.
- `fecha` es `"Junio AAAA"` para `-1` y `"Diciembre AAAA"` para `-2`.
- Crea la carpeta `fotos/` vacía.

**`esqueleto.toml`**
- Empieza con un comentario de tres o cuatro líneas que explica cómo llenarlo y remite al manual.
- Trae las 10 secciones del Vol. 7, en este orden, cada una con un `pendiente` que dice qué pedir y a
  quién:

| # | tipo | etiqueta | titulo |
|---|---|---|---|
| 1 | cifras | Cifras | `Proyección social en *cifras*` |
| 2 | proyectos | Comunidades | `Proyectos que *transforman*` |
| 3 | texto | Planeta | `Nuestro compromiso con el *planeta*` |
| 4 | texto | Monitores | `Monitores de *proyección social*` |
| 5 | imagen | Sistema | `Sistema de *proyección social*` |
| 6 | comparativo | Prácticas empresariales | `Indicadores de *prácticas*` |
| 7 | proyectos | Aprendizaje con impacto | `Proyectos *nucleares*` |
| 8 | texto | Egresados | `Vinculación de *egresados*` |
| 9 | cifras | Docentes | `Vinculación de *docentes*` |
| 10 | videos | Videos | `Videos de la *proyección social*` |

- [ ] **Step 1: Escribir las pruebas que fallan, en `tests/test_semestral_edicion.py`**

```python
def test_cargar_una_edicion_valida(carpeta_edicion)          # cargar(...).volumen == 8
def test_toml_roto_dice_la_linea(carpeta_edicion)            # 'titulo = "sin cerrar' en la línea 3
    # pytest.raises(ErrorEdicion, match="línea 3")
def test_error_de_validacion_nombra_seccion_campo_y_valor(...)  # actual = 101 en el comparativo
    # el mensaje contiene "Sección 4", "Indicadores de *prácticas*" e "indicadores[0].actual"
def test_tipo_desconocido_lista_los_validos(...)             # contiene "texto, cifras, proyectos, comparativo, videos, imagen"
def test_foto_que_no_existe(...)                             # borra taller.jpg -> match "taller.jpg"
def test_foto_con_otras_mayusculas_no_cuenta(...)            # renombra siembra.jpg -> Siembra.JPG -> ErrorEdicion
def test_carpeta_y_semestre_deben_coincidir(...)             # renombra la carpeta a 2027-1 -> ErrorEdicion
def test_nueva_sin_anteriores_usa_el_esqueleto(tmp_path)
    # base con anteriores.toml (volumen = 7); nueva(base, "2026-2"):
    # volumen 8, fecha "Diciembre 2026", 10 secciones en el orden de la tabla,
    # len(pendientes) == 12 (10 secciones + portada + editorial),
    # el texto del archivo conserva el comentario inicial
def test_nueva_copia_la_estructura_de_la_anterior(carpeta_edicion)
    # nueva(base, "2027-1"): volumen 9, fecha "Junio 2027", mismos tipos/etiquetas/títulos,
    # cuerpos y cifras vacíos, todas las secciones pendientes, estado borrador
def test_nueva_no_sobrescribe(carpeta_edicion)               # nueva(base, "2026-2") -> ErrorEdicion
def test_nueva_rechaza_semestre_mal_escrito(tmp_path)        # "2026-02" -> ErrorEdicion
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_semestral_edicion.py -v` → FAIL (falta el módulo).

- [ ] **Step 3: Implementar `edicion.py` y escribir `esqueleto.toml` según las reglas de arriba**

- [ ] **Step 4: Verificar que pasan**

Run: `uv run pytest tests/test_semestral_edicion.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/boletin_semestral/edicion.py src/boletin_semestral/esqueleto.toml tests/test_semestral_edicion.py
git commit -m "feat(semestral): cargar ediciones y crear la del semestre siguiente"
```

---

### Task 3: Fotos

**Files:**
- Create: `src/boletin_semestral/fotos.py`
- Test: `tests/test_semestral_fotos.py`

**Interfaces:**
- Consumes: nada.
- Produces, en `boletin_semestral.fotos`:
  - `LADO_MAXIMO = 1800`, `PESO_MAXIMO = 1_500_000`, `ANCHO_MINIMO = 1000`;
  - `reducir(carpeta_fotos: Path) -> list[str]`: reduce en el lugar los `.jpg`, `.jpeg` y `.png` que
    pasan del lado o del peso máximo. Devuelve los nombres que cambió;
  - `pequenas(carpeta_fotos: Path, nombres: list[str]) -> list[str]`: las de menos de `ANCHO_MINIMO` px
    de ancho.

**Cómo reducir**
- Abre con Pillow y aplica `ImageOps.exif_transpose` antes de `thumbnail((LADO_MAXIMO, LADO_MAXIMO))`.
- Un JPG se guarda con `quality=85, optimize=True`; un PNG con `optimize=True`.
- Si un JPG sigue pasando de 1,5 MB, se baja la calidad de 10 en 10 hasta 60.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
def test_reducir_achica_las_grandes_y_deja_las_pequenas(tmp_path)
    # foto 4000×3000 y foto 1200×800 -> devuelve ["grande.jpg"]; el lado mayor de grande queda en 1800;
    # la pequeña conserva sus bytes
def test_reducir_respeta_la_orientacion(tmp_path)
    # JPG 3000×2000 con EXIF Orientation=6 -> tras reducir, alto > ancho y sin etiqueta de orientación
def test_reducir_baja_el_peso(tmp_path)
    # JPG 1800×1800 de ruido aleatorio (os.urandom) que pasa de 1,5 MB -> queda <= PESO_MAXIMO
def test_pequenas_avisa_de_las_de_menos_de_mil(tmp_path)    # 800×600 -> ["chica.jpg"]
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_semestral_fotos.py -v` → FAIL.

- [ ] **Step 3: Implementar `fotos.py`**

- [ ] **Step 4: Verificar que pasan**

Run: `uv run pytest tests/test_semestral_fotos.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/boletin_semestral/fotos.py tests/test_semestral_fotos.py
git commit -m "feat(semestral): reducir fotos sin perder la orientación"
```

---

### Task 4: Render HTML (web y PDF salen del mismo HTML)

**Files:**
- Create: `src/boletin_semestral/render.py`
- Create: `src/boletin_semestral/plantillas/boletin.html.j2`
- Create: `src/boletin_semestral/plantillas/_portada.html.j2`, `_editorial.html.j2`,
  `_contraportada.html.j2`, `_texto.html.j2`, `_cifras.html.j2`, `_proyectos.html.j2`,
  `_comparativo.html.j2`, `_videos.html.j2`, `_imagen.html.j2`, `_pendiente.html.j2`
- Create: `src/boletin_semestral/estaticos/estilo.css`, `estaticos/movimiento.js`,
  `estaticos/fuentes/*.woff2`, `estaticos/fuentes/OFL.txt`
- Test: `tests/test_semestral_render.py`

**Interfaces:**
- Consumes: `Edicion`, `antetitulo` y `pendientes` (Tarea 1). `INSTITUCION`, `UNIDAD` y `ESTATICOS`
  de `boletin_empleos.render.web`, para el logo `logo-humboldt.png`.
- Produces, en `boletin_semestral.render`:
  - `Modo(StrEnum)`: `BORRADOR = "borrador"`, `FINAL = "final"`;
  - `ESTATICOS_SEMESTRAL: Path`: la carpeta `estaticos/` del paquete;
  - `renderizar(edicion: Edicion, modo: Modo) -> str`: el documento HTML completo;
  - `copiar_estaticos(destino: Path) -> None`: copia `estilo.css`, `movimiento.js`, `fuentes/` y
    `logo-humboldt.png`;
  - `manuscrita(titulo: str) -> Markup`: escapa y convierte `*palabra*` en
    `<em class="manuscrita">palabra</em>`;
  - `parrafos(cuerpo: str) -> Markup`: escapa, separa en `<p>` por líneas en blanco y convierte
    `**x**` en `<strong>x</strong>`.

**Estructura del HTML**
- Las fotos se enlazan como `fotos/<nombre>`.
- Hay un `<section class="pagina portada">`, uno `editorial`, uno por sección
  (`class="pagina seccion seccion--<tipo>"`, con `data-titulo` igual al título sin asteriscos) y uno
  `contraportada`.
- En modo `BORRADOR`:
  - `<body class="borrador">` con `<div class="marca-borrador">BORRADOR</div>`;
  - cada pendiente se dibuja con `_pendiente.html.j2`: la etiqueta "PENDIENTE", el `motivo` y, si la
    sección no tiene foto, el hueco "Falta foto".
- En modo `FINAL` no hay ninguna de esas dos cosas.
- Comparativo:
  - cada barra lleva `style="width: {valor}%"`;
  - la línea de la meta lleva `style="left: {meta}%"`;
  - los porcentajes se muestran con coma decimal (`87,2 %`).
- Videos:
  - el reproductor (`<iframe>` de `https://www.youtube-nocookie.com/embed/<id>`, o el enlace de Drive)
    va en un bloque `.solo-pantalla`;
  - la miniatura, el QR (SVG en línea con `segno.make(enlace).svg_inline(scale=3)`) y el enlace van en
    un bloque `.solo-impresion`.
- `estilo.css`:
  - tokens de color y `@font-face` de las cinco fuentes;
  - pantalla: una columna de `max-width: 760px`;
  - `@media print`: `@page { size: A4; margin: 14mm 14mm 18mm; }`, `.pagina { break-before: page; }`,
    `.solo-pantalla { display: none }` y `.solo-impresion { display: block }`;
  - `prefers-reduced-motion` desactiva las animaciones.
  - Las medidas, tipografías y disposiciones son las de las maquetas aprobadas, descritas en el spec §8.
- `movimiento.js` agrega la clase `visible` a `.cifra` con `IntersectionObserver`. No hace nada si el
  usuario pidió reducir el movimiento.
- Las fuentes se descargan una sola vez de `@fontsource` en jsdelivr, versión 5.x fija, subconjunto
  latin:
  - `inter-latin-{400,600,700}-normal.woff2`;
  - `fredoka-latin-700-normal.woff2`;
  - `kaushan-script-latin-400-normal.woff2`.
  - Se anota la versión en `fuentes/OFL.txt` junto a la licencia.
  - Pedir permiso al usuario antes de descargar.

- [ ] **Step 1: Escribir las pruebas que fallan**

Todas usan `cargar(carpeta_edicion)` y `HTMLParser` de selectolax.

```python
def test_borrador_lleva_marca_y_recuadros(carpeta_edicion)
    # se pone pendiente="Falta X" en la sección 2 -> hay .marca-borrador y un .pendiente con "Falta X"
def test_final_no_lleva_marca_ni_recuadros(carpeta_edicion)   # modo FINAL -> ninguno de los dos
def test_cada_seccion_es_una_pagina(...)                      # 6 .pagina.seccion + portada + editorial + contraportada
def test_titulo_con_manuscrita(...)                           # em.manuscrita con texto "planeta"
def test_barras_del_comparativo(...)                          # width: 90.0% y width: 100.0%; left: 80.0%; "90,0 %"
def test_videos_reproductor_y_qr(...)                         # iframe con youtube-nocookie.com/embed/abc123XYZ00
                                                              # dentro de .solo-pantalla; <svg> dentro de .solo-impresion
def test_textos_con_caracteres_especiales(...)
    # cuerpo = 'A & B <script>alert(1)</script> "citas" año ñandú 5 * 3 = 15'
    # -> el HTML contiene "&lt;script&gt;" y "5 * 3 = 15"; no hay <script>alert;
    #    el cuerpo no tiene em.manuscrita
def test_parrafos_y_negrita(...)                              # parrafos("a\n\nb **c**") -> dos <p> y <strong>c</strong>
def test_copiar_estaticos(tmp_path)                           # estilo.css, movimiento.js, logo y 5 .woff2
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_semestral_render.py -v` → FAIL.

- [ ] **Step 3: Descargar las fuentes (con permiso del usuario) y escribir `estilo.css`, `movimiento.js` y las plantillas**

- [ ] **Step 4: Implementar `render.py`**

Entorno Jinja2 con `PackageLoader("boletin_semestral", "plantillas")` y `autoescape=True`. Filtros:
`manuscrita`, `parrafos` y `porcentaje` (formatea `87.2` como `"87,2 %"`). Helper `id_youtube(enlace)`
para las URL `watch?v=` y `youtu.be/`.

- [ ] **Step 5: Verificar que pasan**

Run: `uv run pytest tests/test_semestral_render.py -v` → PASS.

- [ ] **Step 6: Revisar a ojo**

Genera el HTML de la fixture en `salida/prueba/index.html` con fotos y estáticos, y ábrelo en el
navegador. Compáralo con las pantallas `direccion-visual.html` y `tipos-de-seccion.html` de
`.superpowers/brainstorm/`: debe verse la dirección B.

- [ ] **Step 7: Commit**

```bash
git add src/boletin_semestral/render.py src/boletin_semestral/plantillas src/boletin_semestral/estaticos tests/test_semestral_render.py
git commit -m "feat(semestral): render HTML del boletín en la dirección visual aprobada"
```

---

### Task 5: PDF con Chromium

**Files:**
- Create: `src/boletin_semestral/pdf.py`
- Test: `tests/test_semestral_pdf.py`

**Interfaces:**
- Consumes: el HTML de la Tarea 4, escrito en disco junto a `fotos/` y los estáticos.
- Produces, en `boletin_semestral.pdf`:
  - `ChromiumAusente(Exception)`: su mensaje incluye `uv run playwright install chromium`;
  - `ResultadoPdf(NamedTuple)`: `paginas: int`, `largas: list[tuple[str, int]]` (título de la sección y
    páginas que ocupa, solo las que pasan de 1);
  - `generar_pdf(html: Path, destino: Path) -> ResultadoPdf`.

**Cómo generarlo**
- Usa `sync_playwright`, `chromium.launch()` y `page.goto(html.as_uri())`, espera a `networkidle` y
  aplica `page.emulate_media(media="print")`.
- Para medir las secciones largas, ejecuta en la página un script que, por cada `.pagina.seccion`,
  calcule `ceil(offsetHeight / altoUtil)`, con `altoUtil` igual a la altura de A4 menos los márgenes,
  en px a 96 ppp.
- Llama a `page.pdf(path=destino, format="A4", print_background=True, display_header_footer=True, header_template="<span></span>", footer_template=…)`.
  El pie dice "Proyección Social | Boletín Semestral" a la izquierda y `<span class="pageNumber">` a la
  derecha, en 7 px.
- Cuenta las páginas con `len(re.findall(rb"/Type\s*/Page[^s]", destino.read_bytes()))`.
- Si `chromium.launch` lanza `playwright.sync_api.Error` con `"Executable doesn't exist"`, convierte
  el error en `ChromiumAusente`.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
def _chromium_o_saltar():  # intenta lanzar Chromium; si no está, pytest.skip("Chromium no instalado")

def test_pdf_de_una_edicion_minima(carpeta_edicion, tmp_path)
    # renderiza FINAL, escribe HTML + fotos + estáticos, genera el PDF:
    # el archivo existe, empieza con b"%PDF" y paginas >= 9
def test_seccion_larga_se_avisa(carpeta_edicion, tmp_path)
    # cuerpo de la sección "texto" = 60 párrafos -> largas contiene ("Nuestro compromiso con el planeta", n>=2)
def test_sin_chromium_da_el_comando(monkeypatch, tmp_path)
    # monkeypatch de sync_playwright para que lance Error("Executable doesn't exist ...")
    # -> ChromiumAusente con "uv run playwright install chromium" (no necesita Chromium)
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run playwright install chromium`, solo la primera vez. Run:
`uv run pytest tests/test_semestral_pdf.py -v` → FAIL.

- [ ] **Step 3: Implementar `pdf.py`**

- [ ] **Step 4: Verificar que pasan**

Run: `uv run pytest tests/test_semestral_pdf.py -v` → PASS. Abre el PDF generado y verifica a ojo que
las fuentes, el pie y el número de página aparecen.

- [ ] **Step 5: Commit**

```bash
git add src/boletin_semestral/pdf.py tests/test_semestral_pdf.py
git commit -m "feat(semestral): PDF A4 con Chromium y aviso de secciones largas"
```

---

### Task 6: `armar` y la consola (`nueva`, `armar`)

**Files:**
- Create: `src/boletin_semestral/armado.py`
- Create: `src/boletin_semestral/cli.py`
- Test: `tests/test_semestral_armado.py`

**Interfaces:**
- Consumes: `cargar`, `nueva` y `ErrorEdicion` (Tarea 2); `reducir` y `pequenas` (Tarea 3);
  `renderizar`, `copiar_estaticos` y `Modo` (Tarea 4); `generar_pdf`, `ResultadoPdf` y
  `ChromiumAusente` (Tarea 5).
- Produces:
  - `boletin_semestral.armado.Resultado(NamedTuple)`: `destino: Path`, `pdf: Path`,
    `pendientes: list[Pendiente]`, `largas: list[tuple[str, int]]`, `reducidas: list[str]`,
    `pequenas: list[str]`, `publicada: bool`.
  - `boletin_semestral.armado.armar(carpeta: Path, salida: Path, generar: Callable[[Path, Path], ResultadoPdf] | None = None) -> Resultado`.
    Con `None`, usa el `generar_pdf` del módulo `armado`, buscado **al momento de llamar** y no como
    valor por defecto, para que `monkeypatch` pueda reemplazarlo. El parámetro existe para que las
    pruebas no necesiten Chromium.
  - Si no hay ediciones ni `anteriores.toml`, `nueva` empieza en el volumen 1.
  - `boletin_semestral.cli.main(argv: list[str] | None = None) -> int`.

**Reglas de `armar`**
1. `cargar` la edición, `reducir` sus fotos y calcular `pendientes` y `pequenas`.
2. Si la edición es borrador:
   - destino `salida/<semestre>/`, modo `BORRADOR`, PDF `boletin-vol-<N>-borrador.pdf`.
3. Si está aprobada:
   - con pendientes, `ErrorEdicion` que empieza con `"La edición está aprobada pero tiene pendientes:"`
     y lista cada pendiente como `- lugar: motivo`;
   - sin pendientes, destino `carpeta/"publicada"`, que se **borra antes** con `shutil.rmtree` si
     existe; modo `FINAL`; PDF `boletin-vol-<N>.pdf`.
4. En el destino escribe `index.html`, `copiar_estaticos`, copia en `fotos/` solo las
   `fotos_nombradas` y llama a `generar(destino/"index.html", destino/<pdf>)`.

**Consola** (argparse, `prog="semestral"`)
- `nueva SEMESTRE [--datos datos/semestral]`: imprime la carpeta creada.
- `armar SEMESTRE [--datos datos/semestral] [--salida salida/semestral]` imprime:
  - la ruta del PDF;
  - `"Fotos reducidas: …"` y `"Fotos pequeñas (se verán borrosas): …"`, si las hay;
  - `"Secciones de más de una página: …"`, si las hay;
  - `"Pendientes (N):"` y la lista, o `"Sin pendientes."`.
- `ErrorEdicion` y `ChromiumAusente` → imprime el mensaje en stderr y devuelve 1. Si todo sale bien,
  devuelve 0.

- [ ] **Step 1: Escribir las pruebas que fallan**

`generar_falso` escribe `b"%PDF-falso"` en el destino y devuelve `ResultadoPdf(9, [])`.

```python
def test_borrador_va_a_salida_con_marca(carpeta_edicion, tmp_path)
    # Resultado.publicada is False; salida/2026-2/index.html contiene "marca-borrador";
    # existe boletin-vol-8-borrador.pdf; no existe carpeta/"publicada"
def test_aprobada_con_pendientes_no_se_publica(...)
    # estado aprobada + pendiente en la sección 2 -> ErrorEdicion con "Planeta"; no existe publicada/
def test_aprobada_sin_pendientes_genera_publicada(...)
    # publicada/index.html sin "marca-borrador", boletin-vol-8.pdf, fotos/, estilo.css
def test_publicada_se_regenera_desde_cero(...)
    # arma aprobada; quita "taller.jpg" de todas sus apariciones en el archivo; arma de nuevo
    # -> publicada/fotos/taller.jpg ya no existe
def test_solo_se_copian_las_fotos_nombradas(...)             # foto extra en fotos/ -> no llega al destino
def test_cli_armar_imprime_pendientes(capsys, monkeypatch, ...)
    # monkeypatch de boletin_semestral.armado.generar_pdf con generar_falso;
    # main(["armar", "2026-2", "--datos", base, "--salida", salida]) == 0; stdout contiene "Pendientes (1):"
def test_cli_error_de_archivo_devuelve_1(capsys, ...)        # TOML roto -> 1; stderr contiene "línea"
def test_cli_sin_chromium_devuelve_1(capsys, monkeypatch, ...)
    # generar lanza ChromiumAusente -> 1; stderr contiene "playwright install chromium"
def test_cli_nueva(capsys, tmp_path)                         # main(["nueva", "2026-2", "--datos", base]) == 0
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_semestral_armado.py -v` → FAIL.

- [ ] **Step 3: Implementar `armado.py` y `cli.py`**

- [ ] **Step 4: Verificar que pasan**

Run: `uv run pytest tests/test_semestral_armado.py -v` → PASS. Luego corre a mano, de punta a punta y
con Chromium real, `uv run semestral nueva 2026-2 --datos salida/ensayo` y
`uv run semestral armar 2026-2 --datos salida/ensayo --salida salida/ensayo-vista`. Debe imprimir 12
pendientes y dejar un PDF.

- [ ] **Step 5: Commit**

```bash
git add src/boletin_semestral/armado.py src/boletin_semestral/cli.py tests/test_semestral_armado.py
git commit -m "feat(semestral): comandos nueva y armar"
```

---

### Task 7: Publicación en el sitio

**Files:**
- Create: `src/boletin_semestral/sitio.py`
- Create: `src/boletin_semestral/plantillas/indice.html.j2`
- Create: `datos/semestral/anteriores.toml`
- Modify: `src/boletin_empleos/sitio.py` (`construir_sitio`, `_portada`, `main`)
- Modify: `.github/workflows/sitio.yml` (rutas que lo activan)
- Test: `tests/test_semestral_sitio.py`, `tests/test_sitio.py`

**Interfaces:**
- Consumes: `Edicion` y `Estado` (Tarea 1); `copiar_estaticos` (Tarea 4); la estructura de
  `publicada/` (Tarea 6).
- Produces, en `boletin_semestral.sitio`:
  - `EdicionPublicada(BaseModel)`: `volumen: int`, `semestre: str`, `fecha: str`, `titular: str`,
    `carpeta: Path`, `pdf: str`;
  - `Anterior(BaseModel)`: `volumen: int`, `fecha: str`, `enlace: str`;
  - `publicadas(base: Path) -> list[EdicionPublicada]`: las carpetas `*/` con `publicada/index.html`
    y `estado = "aprobada"` en su `edicion.toml`, de la más reciente a la más vieja. Lee el TOML con
    `tomllib` y valida solo los campos generales; no exige que existan las fotos;
  - `anteriores(base: Path) -> list[Anterior]`: si falta el archivo, `[]`;
  - `publicar(base: Path, destino: Path) -> list[EdicionPublicada]`: copia cada `publicada/` a
    `destino/vol-<N>/`, escribe `destino/index.html` y copia los estáticos.
- Cambia en `boletin_empleos.sitio`: `construir_sitio(programas, destino, semestral: Path | None = None)`.
  - Si `semestral` existe como carpeta, llama a
    `boletin_semestral.sitio.publicar(semestral, destino / "semestral")`.
  - La portada suma, después de la lista de carreras, una sección con una tarjeta a
    `semestral/index.html`:
    - título "Boletín semestral";
    - detalle `"Vol. N · fecha"` de la última edición publicada, o "Proyección Social EN ACCIÓN" si no
      hay ninguna.
  - `main` pasa `args.datos / "semestral"`.

**`indice.html.j2`**
- Usa el mismo `estilo.css` de la Tarea 4.
- Muestra arriba la última edición con su titular y dos botones: "Leer en línea" (`vol-N/index.html`)
  y "Descargar PDF".
- Debajo va "Ediciones anteriores": las demás publicadas y las de `anteriores.toml`, que enlazan a
  Heyzine con `rel="noopener"` y `target="_blank"`.
- Sin ediciones ni anteriores: "Todavía no hay ediciones publicadas."

**`anteriores.toml`**: el Vol. 7, `fecha = "Junio 2026"`,
`enlace = "https://heyzine.com/flip-book/df92099d87.html"`.

**`sitio.yml`**: agrega a `on.push.paths` las rutas `src/boletin_semestral/**` y `datos/semestral/**`.
`boletin.yml` no cambia, porque ya llama a `boletin_empleos.sitio`.

- [ ] **Step 1: Escribir las pruebas que fallan**

En `tests/test_semestral_sitio.py`:

```python
def test_solo_se_publican_las_aprobadas_con_publicada(tmp_path)
    # 2026-2 aprobada con publicada/, 2027-1 borrador sin publicada -> publicadas() == [vol 8]
def test_publicar_copia_y_arma_el_indice(tmp_path)
    # destino/vol-8/index.html y boletin-vol-8.pdf existen; el índice enlaza a ambos
def test_indice_lista_las_anteriores(tmp_path)               # anteriores.toml con Vol. 7 -> enlace a heyzine
def test_indice_sin_nada(tmp_path)                           # "Todavía no hay ediciones publicadas."
def test_anteriores_ausente_es_lista_vacia(tmp_path)
```

En `tests/test_sitio.py`, junto a las pruebas que ya existen:

```python
def test_la_portada_enlaza_al_boletin_semestral(tmp_path)
    # construir_sitio(programas, destino, semestral=base_con_vol8) -> portada con href "semestral/index.html"
    # y "Vol. 8 · Diciembre 2026"; existe destino/semestral/vol-8/index.html
def test_sin_carpeta_semestral_el_sitio_queda_igual(tmp_path)
    # semestral=None -> no existe destino/"semestral"; la portada no menciona "Boletín semestral"
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_semestral_sitio.py tests/test_sitio.py -v` → FAIL en las nuevas.

- [ ] **Step 3: Implementar `sitio.py`, `indice.html.j2` y los cambios en `boletin_empleos/sitio.py`, `anteriores.toml` y `sitio.yml`**

- [ ] **Step 4: Verificar que pasan y que el sitio completo se arma**

Run: `uv run pytest` → todo PASS. Run: `uv run python -m boletin_empleos.sitio` → existe
`sitio/semestral/index.html` y lista el Vol. 7.

- [ ] **Step 5: Commit**

```bash
git add src/boletin_semestral/sitio.py src/boletin_semestral/plantillas/indice.html.j2 datos/semestral/anteriores.toml src/boletin_empleos/sitio.py .github/workflows/sitio.yml tests/test_semestral_sitio.py tests/test_sitio.py
git commit -m "feat(semestral): sección /semestral/ del sitio, que sobrevive a cada publicación"
```

---

### Task 8: Borrador de textos con Claude (opcional)

**Files:**
- Create: `src/boletin_semestral/borrador.py`
- Modify: `src/boletin_semestral/cli.py` (subcomando `borrador`)
- Test: `tests/test_semestral_borrador.py`

**Interfaces:**
- Consumes: `cargar` y `Edicion` (Tarea 2); `Cifra` (Tarea 1); `main` (Tarea 6).
- Produces, en `boletin_semestral.borrador`:
  - `ProyectoSugerido(nombre: str, docentes: list[str], programas: list[str], descripcion: str)`;
  - `Sugerencia(seccion: str, cuerpo: str, cifras: list[Cifra], proyectos: list[ProyectoSugerido])`;
  - `Sugerencias(sugerencias: list[Sugerencia])`.
  - Todos los campos son obligatorios y usan `extra="forbid"`, porque el esquema JSON se manda tal cual.
  - `MODELO = "claude-opus-5-5"`;
  - `class Redactor`:
    - `__init__(self, modelo: str = MODELO)`;
    - `_pedir(self, prompt: str) -> str`;
    - `proponer(self, correo: str, edicion: Edicion) -> Sugerencias | None`;
  - `escribir_sugerencias(s: Sugerencias, destino: Path) -> None`: con `tomli_w`, como `[[sugerencias]]`.

**`_pedir`**
- `anthropic.Anthropic().beta.messages.create(model=…, max_tokens=16000, betas=["server-side-fallback-2026-07-01"], fallbacks="default", output_config={"format": {"type": "json_schema", "schema": Sugerencias.model_json_schema()}}, messages=[…])`.
- Si `stop_reason == "refusal"`, lanza `RuntimeError`.
- Si no, devuelve el texto del primer bloque `text`.

**`proponer`**
- Arma el prompt:
  - el contexto: el boletín semestral de la Facultad de Ingenierías y Ciencias Básicas de la
    institución;
  - la lista de secciones de la edición (`etiqueta` y título sin asteriscos);
  - el texto del correo.
- Reglas literales del prompt:
  - "Usa solo lo que dice el correo: no inventes cifras, nombres, fechas ni logros."
  - "Asigna cada actividad a la sección cuya etiqueta encaje mejor; si ninguna encaja, usa la etiqueta Otras."
  - "Escribe en español, en tercera persona, con frases cortas."
- Parsea con `Sugerencias.model_validate_json`. Ante cualquier excepción, registra un aviso con
  `logging` y devuelve `None`.

**Consola:** `borrador SEMESTRE --correo ARCHIVO [--datos datos/semestral]`.
- Sin `ANTHROPIC_API_KEY` en el entorno: avisa "Falta ANTHROPIC_API_KEY; el resto del programa
  funciona sin este paso." y devuelve 1.
- Si `proponer` devuelve `None`: avisa y devuelve 1.
- Si sale bien: escribe `carpeta/"borrador-sugerido.toml"`, imprime su ruta y devuelve 0.
- **En ningún caso toca `edicion.toml`.**

- [ ] **Step 1: Escribir las pruebas que fallan**

En todas, `monkeypatch.setattr(Redactor, "_pedir", …)`; nunca hay red.

```python
def test_proponer_devuelve_sugerencias_validas(carpeta_edicion)
    # _pedir devuelve un JSON válido con 2 sugerencias -> len(...) == 2
def test_respuesta_invalida_devuelve_none(...)               # _pedir devuelve "no es json" -> None
def test_fallo_del_proveedor_devuelve_none(...)              # _pedir lanza RuntimeError -> None
def test_el_prompt_prohibe_inventar_y_lista_las_secciones(...)
    # captura el prompt: contiene "no inventes cifras", "Planeta" y "Nuestro compromiso con el planeta"
def test_cli_borrador_escribe_aparte_y_no_toca_la_edicion(monkeypatch, ...)
    # con ANTHROPIC_API_KEY falsa y _pedir simulado: código 0; existe borrador-sugerido.toml;
    # el hash de edicion.toml no cambia
def test_cli_borrador_sin_clave(monkeypatch, capsys, ...)
    # delenv ANTHROPIC_API_KEY -> 1; no existe borrador-sugerido.toml
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_semestral_borrador.py -v` → FAIL.

- [ ] **Step 3: Implementar `borrador.py` y el subcomando**

- [ ] **Step 4: Verificar que pasan**

Run: `uv run pytest tests/test_semestral_borrador.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/boletin_semestral/borrador.py src/boletin_semestral/cli.py tests/test_semestral_borrador.py
git commit -m "feat(semestral): borrador opcional de textos a partir del correo"
```

---

### Task 9: Manual de uso y README

**Files:**
- Create: `docs/manual-boletin-semestral.md`
- Modify: `README.md` (sección "Boletín semestral" con enlace al manual)

**Interfaces:**
- Consumes: los comandos y mensajes reales de las Tareas 6 a 8. El manual cita los textos exactos que
  imprime el programa.
- Produces: el manual del spec §12.

**Contenido**, en lenguaje sencillo, en segunda persona y sin jerga:

1. **Para los monitores:**
   - la instalación, una sola vez;
   - el ciclo del semestre, en los 8 pasos del spec §5;
   - un ejemplo comentado de cada uno de los seis tipos de sección, copiado de la fixture de la
     Tarea 1;
   - cómo marcar la palabra manuscrita y la negrita;
   - cómo leer la lista de pendientes;
   - cómo aprobar y publicar;
   - cómo subir a Heyzine;
   - una tabla "si ves este mensaje, haz esto" con cada fila del spec §10.
2. **Para la Coordinación:** qué mandar cada semestre y para cuándo, con la lista del spec §12, y el
   aviso de que el repositorio es público.
3. **Datos pendientes de confirmar:** quién administra la cuenta de Heyzine.

El README suma la sección "Boletín semestral", con tres líneas y los comandos `nueva` y `armar`, y
enlaza el manual.

- [ ] **Step 1: Escribir el manual y la sección del README**

- [ ] **Step 2: Verificar que los comandos del manual funcionan tal cual**

Copia y corre, en una carpeta de ensayo, cada comando del manual. Compara que los mensajes citados
coincidan con la salida real.

- [ ] **Step 3: Commit**

```bash
git add docs/manual-boletin-semestral.md README.md
git commit -m "docs(semestral): manual de uso para monitores y Coordinación"
```

---

### Task 10: El Vol. 8 en borrador, para mostrarlo a Mónica

**Files:**
- Create: `datos/semestral/2026-2/edicion.toml`, con `uv run semestral nueva 2026-2`
- Create: `datos/semestral/2026-2/fotos/*`

**Interfaces:**
- Consumes: todo lo anterior y el correo de la Coordinación del 6 de noviembre de 2026 (*"📢
  Actividades de proyección social"*).
- Produces: la vista previa del Vol. 8 (web y PDF con marca BORRADOR) para que el usuario la lleve a
  Mónica. **No se aprueba en esta tarea.**

- [ ] **Step 1: Crear la edición**

Run: `uv run semestral nueva 2026-2` → crea `datos/semestral/2026-2/` con volumen 8.

- [ ] **Step 2: Conseguir las fotos**

Pide al usuario permiso para descargar los 10 adjuntos del correo del 6 de noviembre, o pídele que los
deje en `datos/semestral/2026-2/fotos/` con nombres en minúscula y sin espacios.

- [ ] **Step 3: Llenar con lo que dice el correo, sin inventar**

- **Planeta:**
  - la VII jornada de siembra;
  - Ecohumboldt entre las 20 experiencias significativas (Ministerio de Educación e IDEAM);
  - el 2.º lugar en el premio Bibo de El Espectador;
  - los talleres de huella de carbono;
  - la conferencia con Urbaser.
- **Comunidades:** los 3 proyectos de 2026 con sus docentes.
- **Una sección nueva** de tipo `proyectos`, con etiqueta "Propuestas 2027", con las 4 propuestas y sus
  proponentes.
- **Una sección nueva** de tipo `texto`, con etiqueta "Emprendimiento":
  - los 4 emprendimientos acompañados;
  - el encuentro de cultura emprendedora;
  - el premio Humboldt Emprende;
  - la lúdica en el Colegio CASD.
- **Monitores:** el reconocimiento.
- **Cifras:** 20, 2.º, 4 y 4, con
  `pendiente = "Confirmar con la Coordinación las cifras del semestre (personas sensibilizadas en talleres y eco cápsulas)."`.
- **Lo que el correo no trae se queda pendiente:** prácticas, proyectos nucleares, egresados, docentes,
  videos, sistema, titular de portada y editorial.

- [ ] **Step 4: Armar la vista previa**

Run: `uv run semestral armar 2026-2` → código 0, PDF en
`salida/semestral/2026-2/boletin-vol-8-borrador.pdf` y la lista de pendientes impresa.

- [ ] **Step 5: Commit del contenido, sin aprobar**

```bash
git add datos/semestral/2026-2
git commit -m "chore(semestral): borrador del Vol. 8 con el correo del 6 de noviembre"
```

---

## Cobertura del spec

| Spec | Tarea |
|---|---|
| §5 flujo, §6.1 carpeta | 2, 6 |
| §6.2–6.3 campos y seis tipos, validación, pendientes | 1, 2 |
| §7 piezas y `armar` paso a paso | 1–6, 8 |
| §8 dirección visual B, PDF y web | 4, 5 |
| §9 publicación que sobrevive a los dos flujos | 7 |
| §10 errores | 2, 3, 5, 6, 8 |
| §11 pruebas | todas |
| §12 manual | 9 |
| §13 fotos reducidas, repositorio público | 3, 9 |
| §14 datos faltantes del Vol. 8 | 10 (quedan como pendientes visibles) |
| §15 criterios 1–7 | 2, 6, 7, 5, 9, todas · el criterio 8 (Mónica aprueba) queda fuera del código |
