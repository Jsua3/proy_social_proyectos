# Diseño — Boletín quincenal de empleos para egresados de Ingeniería de Software

**Programa 1 de 3** · Área de Proyección Social, Facultad de Ingenierías y Ciencias Básicas
Corporación Universitaria Empresarial Alexander von Humboldt · Armenia, Quindío

**Fecha:** 9 de septiembre de 2026
**Estado:** aprobado en brainstorming, pendiente de plan de implementación

---

## 1. Propósito

Un agente automatizado que, cada quince días, recolecta ofertas de empleo en desarrollo de software desde
fuentes que autorizan expresamente su uso, las filtra por pertinencia y legitimidad, y le entrega a la
Coordinación de Proyección Social de Ingeniería un boletín listo para leer y para reenviar.

**Problema que resuelve.** El seguimiento a la empleabilidad de los egresados es una obligación explícita
del CNA (Acuerdo 01 de 2025, Factor 12, Características 39 y 40, que exigen literalmente *"sistemas de
información"*). Hoy la búsqueda y curaduría de vacantes, si ocurre, es manual y no deja rastro.

## 2. Alcance

### Dentro
- Recolección desde cuatro fuentes con permiso declarado.
- Filtrado por relevancia, seniority, vigencia y legitimidad.
- Deduplicación entre fuentes y contra ediciones anteriores.
- Render de un boletín HTML apto para clientes de correo.
- Envío por SMTP a **un** destinatario: la directora/coordinadora.
- Archivo histórico de cada edición dentro del repositorio.
- Ejecución programada quincenal en GitHub Actions.

### Fuera (fase 2, previsto pero no construido)
- Envío a una lista de egresados (requiere Habeas Data, Ley 1581 de 2012, y gestión de bajas).
- Publicación web de las ediciones.
- Postulación o seguimiento de candidatos.
- Cualquier fuente que no autorice su uso.

## 3. Decisiones tomadas y su razón

| Decisión | Elección | Razón |
|---|---|---|
| Audiencia | Egresados de Ingeniería de Software | Definido por la coordinación |
| Destinatario | Solo la directora, con la entrega abstraída para abrir a lista después | Evita Habeas Data en fase 1 sin cerrar la puerta |
| Frecuencia | Quincenal | Definido por la coordinación. Obliga a manejar caducidad de vacantes |
| Ejecución | GitHub Actions cron, núcleo portable | Sin servidor; migrable si Actions no cumple |
| Fuentes | Solo con permiso declarado | Ver §4 |
| LLM | Híbrido degradable | Sin API key el boletín igual sale completo |
| Lenguaje | Python 3.13 | Ecosistema dominante (71,7 % en scraping/pipelines) y el equipo lo maneja |

## 4. Política de fuentes — la restricción estructural del sistema

**Regla:** toda fuente debe declarar su base de permiso y su texto de atribución. Son campos obligatorios
del adaptador. Una fuente que no puede declararlos no tiene dónde encajar en el código.

| Fuente | Base de permiso | Obligación |
|---|---|---|
| **Servicio Público de Empleo** (`serviciodeempleo.gov.co`) | Portal estatal del Ministerio del Trabajo; `robots.txt` permisivo; publica datos abiertos | Citar como fuente |
| **Magneto365** | Publica `llms.txt` dirigido explícitamente a asistentes de IA, con URLs canónicas | Usar solo rutas canónicas sin query string; citar |
| **Remotive** (`remotive.com/api/remote-jobs`) | API pública gratuita | *"Link back to the URL found on Remotive AND mention Remotive as a source"* — so pena de corte de acceso |
| **RemoteOK** (`remoteok.com/api`) | API pública gratuita | *"Link back (with follow, and without nofollow!) ... and mention Remote OK as a source"*. No usar su logo |

**Excluidas y por qué:**
- **elempleo.com** — su `robots.txt` prohíbe expresamente *"text and data mining"* y *"the development of
  any software, machine learning, artificial intelligence (AI), and/or large language models"* sin permiso
  escrito previo. Vía legítima abierta: escribir a `notificaciones@elempleo.com`.
- **Computrabajo** — devuelve HTTP 403 incluso en `robots.txt`; usarlo exige evadir protección anti-bot.
- **LinkedIn** — prohibido por términos de servicio.

**Contexto legal:** desde enero de 2026 la autoridad francesa de protección de datos trata el desacato del
`robots.txt` como evidencia en contra de la base de interés legítimo bajo GDPR. Respetarlo no vuelve legal
un scraping por sí solo, pero ignorarlo juega en contra.

## 5. Arquitectura

Puertos y adaptadores sobre **tres** bordes. Los tres son los que sabemos que van a cambiar.

```
   ENTRADA                    NÚCLEO                      SALIDA
                                                    ┌──────────────────┐
  ┌───────────┐                                     │  Almacenamiento  │
  │  Fuentes  │        ┌────────────────────┐       │  json → sqlite   │
  │  spe      │───────▶│  normalizar        │──────▶└──────────────────┘
  │  magneto  │        │  filtrar           │
  │  remotive │        │  deduplicar        │       ┌──────────────────┐
  │  remoteok │        │  ordenar           │──────▶│     Entrega      │
  └───────────┘        └────────────────────┘       │  smtp → brevo    │
                         sin E/S · testeable        └──────────────────┘
                            sin red

                       ┌────────────────────┐
                       │  Enriquecimiento   │  opcional, degradable
                       │  anthropic → nulo  │
                       └────────────────────┘
```

**El núcleo no hace E/S.** Recibe ofertas normalizadas, devuelve ofertas evaluadas y ordenadas. Se prueba
completo sin red, sin correo y sin credenciales.

**Proceso único, pipeline secuencial.** Sin colas, sin concurrencia, sin orquestador propio: GitHub Actions
cron ya cumple ese papel. Para cuatro fuentes cada quince días, cualquier cosa más elaborada es complejidad
sin beneficio.

## 6. Modelo de datos

```python
class Modalidad(StrEnum):
    PRESENCIAL = "presencial"
    HIBRIDO = "hibrido"
    REMOTO = "remoto"


class Oferta(BaseModel):
    id: str  # hash estable de (fuente, id_nativo)
    fuente: str
    titulo: str
    empresa: str | None
    ubicacion: str | None
    pais: str | None
    modalidad: Modalidad
    url: HttpUrl
    fecha_publicacion: date | None
    salario_min: int | None
    salario_max: int | None
    moneda: str | None
    descripcion: str
    recogida_en: datetime


class Decision(StrEnum):
    INCLUIR = "incluir"
    DESCARTAR = "descartar"


class Evaluacion(BaseModel):
    oferta: Oferta
    puntaje_relevancia: float  # 0.0 – 1.0
    puntaje_legitimidad: float  # 0.0 – 1.0
    vigente: bool
    enlace_vivo: bool
    decision: Decision
    motivos: list[str]  # siempre poblado, incluso al incluir
```

`motivos` se llena **siempre**, no solo al descartar. Es lo que permite auditar el filtro y ajustarlo.

## 7. Puerto de fuentes

```python
class FuenteEmpleo(Protocol):
    nombre: str
    base_permiso: str  # por qué podemos usarla — obligatorio
    atribucion: str  # texto que aparecerá en el pie — obligatorio
    url_atribucion: str
    confianza_base: float  # 0.0 – 1.0, sesga el puntaje de legitimidad

    def obtener(self) -> list[Oferta]: ...
```

`confianza_base` inicial: SPE `0.95` (estatal, empresas registradas) · Magneto `0.80` · Remotive `0.75` ·
RemoteOK `0.70`.

**Notas por adaptador**
- **SPE** — ✅ **resuelto el 9 de septiembre de 2026.** API JSON pública, sin autenticación:

  **Base:** `https://www.buscadordeempleo.gov.co/backbue/v1`

  | Endpoint | Uso |
  |---|---|
  | `GET /version` | `{"backVersion":"2.4.0"}` — verificación de contrato |
  | `GET /vacantes/date` | `{"max_date":"..."}` — fecha del último cargue |
  | `GET /filters` | catálogos: `rangoSalarial`, `prestador`, `tipoContrato`, `nivelDeEstudios` |
  | `GET /vacantes/resultados?page=N&<filtros>` | **búsqueda principal**, 50 por página |

  Respuesta: `{resultados[], totalPages, currentPage, total_registros, total, total_departments, total_municipios}`

  **Campos por vacante:** `CODIGO_VACANTE`, `TITULO_VACANTE`, `DESCRIPCION_VACANTE`, `NIVEL_ESTUDIOS`,
  `RANGO_SALARIAL`, `DEPARTAMENTO`, `MUNICIPIO`, `TIPO_CONTRATO`, `CANTIDAD_VACANTES`, `CARGO`,
  `FECHA_VENCIMIENTO`, `SECTOR_ECONOMICO`, `TELETRABAJO`, `DISCAPACIDAD`, `MESES_EXPERIENCIA_CARGO`,
  `HIDROCARBUROS`, `PLAZA_PRACTICA`, `FECHA_PUBLICACION`, `BUSQUEDA`, `DETALLES_PRESTADOR`.

  ⚠️ **`DETALLES_PRESTADOR` es una LISTA de diccionarios**, no una cadena, con las claves
  `NOMBRE_PRESTADOR` y **`URL_DETALLE_VACANTE`**. Verificado sobre 50 registros: todos traen
  exactamente un prestador y todos traen la URL.

  **La URL de la vacante sale de ahí.** No existe una ruta pública tipo
  `buscadordeempleo.gov.co/vacante/<codigo>`: el portal es una SPA sin ruta de detalle y esa URL
  devuelve 404. `URL_DETALLE_VACANTE` apunta al sitio de la bolsa que publicó la vacante
  (Magneto, Comfenalco, Computrabajo…).

  Algunas de esas URLs apuntan a **Computrabajo**, que este sistema excluye como *fuente*. No hay
  contradicción: enlazar no es extraer. Publicamos un enlace que el portal oficial del Estado nos
  entrega; nunca automatizamos peticiones contra Computrabajo.

  `NOMBRE_PRESTADOR` es **la bolsa de empleo, no el empleador**: el SPE no expone el empleador real.
  Se usa igualmente como `empresa` porque es una entidad registrada ante el Ministerio, y porque
  dejarla vacía penalizaría sistemáticamente a la fuente más confiable del sistema en el filtro de
  legitimidad (§8.4).

  **Es más rico de lo previsto y simplifica dos filtros del núcleo:**
  - `FECHA_VENCIMIENTO` da la caducidad declarada por el empleador — no hay que estimarla.
  - `MESES_EXPERIENCIA_CARGO` vuelve el filtro de seniority numérico en vez de heurístico.
  - `PLAZA_PRACTICA` separa prácticas de empleo real (nuestra audiencia son egresados: se excluyen).
  - `TELETRABAJO` da la modalidad sin inferirla del texto.

  **Parámetros verificados:** `page` ✅ · `departamento` ✅ · `teletrabajo=1` ✅ · `cargo` ✅
  (coincidencia **exacta** sobre texto libre del empleador, no búsqueda parcial).
  Rechazados: `nivelDeEstudios`, `fechaPublicacion`, `experiencia`, `municipio`, `q`, `search`.

  **Codificación:** UTF-8 correcto y bien declarado. Verificado a nivel de bytes (`Ã­` = `í`).
  No requiere tratamiento especial.

  **Estrategia de descarga** (volúmenes medidos el 9/09/2026; total nacional: 258.967 vacantes):

  | Consulta | Registros | Páginas |
  |---|---|---|
  | `teletrabajo=1` — remoto nacional | 1.829 | 39 |
  | `departamento=Quindio` — mercado local | 1.476 | 31 |
  | `cargo=<lista curada>` — alcance nacional dirigido | ~200 | ~15 |

  Total ≈ **85 peticiones por ejecución**, holgado para una corrida quincenal.
  Se descartan barridos por departamento grande: Antioquia son 1.319 páginas y Valle del Cauca 405.
  El filtrado de relevancia ocurre **del lado nuestro**, no en la consulta.
- **Magneto** — parsing HTML con `selectolax` sobre rutas canónicas listadas en su `llms.txt`
  (`/co/trabajos/buscar`, `/co/trabajos/ofertas-empleo-trabajo-remoto`, y ciudades). **Nunca con query string.**
- **Remotive** — `GET /api/remote-jobs?category=software-dev`. Vacantes con 24 h de retraso por diseño suyo.
- **RemoteOK** — `GET /api`. El primer elemento del arreglo es el aviso legal, no una oferta: descartarlo.

## 8. Núcleo — evaluación

### 8.1 Relevancia (puntaje, no binario)
Vocabulario configurable en `config.toml`. Semilla:

- **Cargos:** desarrollador, developer, programador, ingeniero de software, backend, frontend, full stack,
  QA, tester, automatización de pruebas, DevOps, SRE, ingeniero de datos, data engineer, móvil, Android, iOS.
- **Tecnologías:** Java, Python, JavaScript, TypeScript, React, Angular, Vue, Node, .NET, C#, PHP, Spring,
  Django, SQL, Docker, Kubernetes, AWS, Azure, Git.

Puntaje ponderado entre coincidencias en título (peso alto) y descripción (peso bajo). Umbral configurable.
Se usa puntaje porque en Colombia abundan títulos opacos ("Analista de Desarrollo III", "Profesional TI").

### 8.2 Seniority
Objetivo: junior a semi-senior. Descarte por: *senior, lead, líder técnico, arquitecto, jefe, gerente,
head of, principal, staff*, y exigencias de 5+ años de experiencia detectadas por expresión regular.

### 8.3 Vigencia
- Descartar publicaciones con más de **30 días** (configurable).
- Cuando la fuente no da fecha, usar la fecha de primera observación.
- **Verificar que el enlace responda** antes de incluir la oferta. Petición `HEAD` con caída a `GET`
  parcial. Evita el peor defecto posible: un boletín lleno de vacantes muertas.

### 8.4 Legitimidad (antiestafa)
Heurísticas que restan puntaje; parten de `confianza_base` de la fuente:

| Señal | Efecto |
|---|---|
| Pide dinero al aspirante (inversión, kit, curso, "pago de trámites") | Descarte directo |
| Sin empresa identificada **y** contacto por mensajería personal | Descarte directo |
| Contacto únicamente por WhatsApp o Telegram | Penalización fuerte |
| Enlace de postulación a acortador o formulario genérico | Penalización fuerte |
| Salario declarado fuera del rango `[salario_minimo_legal, 3× promedio junior]` definido en `config.toml` | Penalización media |
| Frases de captación ("altos ingresos", "sin experiencia, gana desde casa", "cupos limitados") | Penalización media |
| Descripción ausente o menor a 200 caracteres (configurable) | Penalización leve |

> ⚠️ **Estas heurísticas se escribieron sin conocimiento local.** Deben revisarse con la coordinación,
> que conoce cómo se ven las ofertas falsas en el Quindío. Van en `config.toml` para poder ajustarlas
> sin tocar código.

### 8.5 Deduplicación
1. **Intra-edición:** clave difusa sobre `(empresa normalizada, título normalizado, ubicación)`. La misma
   vacante aparece en varias fuentes; se conserva la de mayor `confianza_base` y se registran las demás
   como fuentes secundarias.
2. **Inter-edición:** contra `historial.json`. Nada que ya se haya enviado se repite.

### 8.6 Transparencia del descarte
Lo descartado **no se borra en silencio**. Sin eso no hay forma de saber si el filtro está botando ofertas
buenas, y la coordinación no tiene por qué confiar a ciegas en un algoritmo.

Ahora bien, no todo descarte va al apéndice — si incluyera los descartes por relevancia serían cientos de
filas de vacantes de contabilidad y logística, y el apéndice se volvería ilegible:

| Motivo del descarte | ¿Va al apéndice? |
|---|---|
| Legitimidad (sospecha de estafa) | **Sí**, con la señal que lo activó |
| Seniority (senior, lead, 5+ años) | **Sí**, en conteo agregado |
| Vigencia o enlace muerto | **Sí**, en conteo agregado |
| Relevancia (no es de software) | No — solo el conteo total |
| Deduplicación | No es un descarte: la oferta sí entra, una sola vez |

Los descartes por relevancia y las deduplicaciones **sí quedan en el registro de ejecución**, aunque no en
el boletín. El apéndice es para la coordinación; el registro es para quien afine el filtro.

## 9. Render y entrega

**Plantilla:** MJML compilado vía `jinja2-mjml` (usa un port de MJML en Rust; **no requiere Node**).
MJML genera HTML tolerante a Outlook, Gmail y compañía.

**Estructura del boletín**
1. Encabezado: periodo cubierto, número de edición, conteo de ofertas.
2. Párrafo editorial (LLM si hay key; texto fijo si no).
3. **Colombia — presencial e híbrido**
4. **Colombia — remoto**
5. **Remoto internacional**
6. Apéndice: descartadas y su motivo.
7. **Pie de atribución generado desde los adaptadores que participaron.**

Cada oferta muestra: título, empresa, ubicación, modalidad, salario si existe, fecha de publicación,
enlace, y una línea de resumen si el enriquecimiento estuvo activo.

**El pie no se escribe a mano.** Se construye recorriendo los adaptadores usados y concatenando su
`atribucion` y `url_atribucion`. Remotive y RemoteOK cortan el acceso si no se les cita; generarlo desde
el código hace imposible olvidarlo.

**Entrega:** SMTP institucional a la directora. Todo en línea, sin adjuntos.

**Archivo:** cada edición se guarda como HTML en `datos/ediciones/AAAA-MM-DD.html` dentro del repositorio.
Sale gratis, deja historial, y habilita la publicación web de la fase 2 sin reescribir nada.

## 10. Enriquecimiento opcional (LLM)

Puerto con dos implementaciones: `anthropic` y `nulo`. La selección es automática según exista o no
`ANTHROPIC_API_KEY`.

- Aporta: una línea de resumen por oferta y el párrafo editorial.
- **No decide nada.** Relevancia, legitimidad y descarte son siempre determinísticos. Un fallo del
  proveedor, un saldo agotado o una respuesta rara jamás alteran qué ofertas entran al boletín.
- Ante cualquier error, cae a `nulo` y el boletín sale igual, más escueto.

## 11. Persistencia

`datos/historial.json`, **commiteado al repositorio** por el propio workflow.

No se usa la caché de GitHub Actions: se borra a los 7 días sin uso, lo que la vuelve inservible para un
ciclo quincenal. Requiere activar *Read and write permissions* en Settings → Actions → General.

Volumen estimado: decenas de registros por edición. JSON es suficiente y produce diffs legibles en git.
Si algún día crece, se cambia el adaptador de almacenamiento a SQLite sin tocar el núcleo.

## 12. Fallos, ética operativa y pruebas

**Degradación por fuente.** Una fuente caída no tumba el boletín: se envía con las demás y el pie indica
cuál no respondió. Degradación visible, nunca silenciosa.

**Fallo total.** Si ninguna fuente responde, **no se envía un boletín vacío**: se manda una alerta. Un
boletín vacío erosiona más la confianza que un aviso honesto de que algo se rompió.

**Reintentos** con retroceso exponencial en HTTP. **Rate limiting** y respeto de `Crawl-delay` en las
fuentes HTML.

**User-Agent identificado**, con nombre del proyecto y correo institucional de contacto. Es la práctica
ética correcta y además protege: si una fuente tiene un problema con el agente, sabe a quién escribir en
vez de bloquear sin más.

**Pruebas**
- Núcleo: `pytest` sobre respuestas reales guardadas como fixtures. Sin red.
- Adaptadores: contra fixtures; un test de contrato marcado para ejecución manual verifica que la fuente
  real siga respondiendo con la forma esperada.
- Render: comprobación de que el HTML se genera y de que el pie contiene la atribución de cada fuente usada.
- `--dry-run`: renderiza y muestra sin enviar. Necesario para que la coordinación apruebe el formato antes
  del primer envío real.

## 13. Riesgos abiertos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| ~~El SPE no expone un endpoint utilizable~~ | — | ✅ **Cerrado el 9/09/2026.** API pública verificada y documentada en §7 |
| **El SPE cambia su API sin aviso** (no es pública ni versionada contractualmente) | Medio | `GET /version` en cada corrida; si `backVersion` cambia, alertar. Tests de contrato sobre fixtures |
| **TI no entrega credenciales SMTP** | Alto — no hay entrega | Plan B: cuenta de aplicación con contraseña de aplicación; o Brevo con verificación de dominio (también requiere TI) |
| **Magneto cambia su HTML** | Medio | Tests de contrato; `selectolax` con selectores tolerantes; considerar Scrapling (parsing adaptativo) si se vuelve inestable |
| **Volumen bajo de vacantes junior en Colombia** | Medio — boletines flacos | Medir en la primera ejecución real; ampliar el radio geográfico o relajar el filtro de seniority |
| **Remotive o RemoteOK cambian términos** | Bajo | La atribución generada ya cumple sus condiciones actuales; revisar en cada fallo 4xx |

## 14. Estructura de archivos propuesta

```
boletin_empleos/
├── pyproject.toml · uv.lock
├── config.toml                      # vocabulario, umbrales, destinatarios
├── .github/workflows/boletin.yml
├── src/boletin_empleos/
│   ├── cli.py                       # --dry-run, --desde, --solo-fuente
│   ├── modelos.py
│   ├── nucleo/                      # sin E/S
│   │   ├── relevancia.py · seniority.py · vigencia.py
│   │   ├── legitimidad.py · deduplicacion.py · pipeline.py
│   ├── fuentes/
│   │   ├── base.py · spe.py · magneto.py · remotive.py · remoteok.py
│   ├── almacenamiento/  base.py · json_repo.py
│   ├── entrega/         base.py · smtp.py · consola.py
│   ├── render/          renderizador.py · plantillas/boletin.mjml
│   └── enriquecimiento/ base.py · anthropic.py · nulo.py
├── datos/
│   ├── historial.json
│   └── ediciones/
└── tests/  fixtures/ · ...
```

`config.toml` existe para que el vocabulario, los umbrales y las heurísticas antiestafa se ajusten **sin
tocar Python**. Quien herede esto puede afinar el filtro sin saber programar.

## 15. Criterios de aceptación

1. `uv run boletin --dry-run` produce un boletín HTML válido desde fixtures, sin red.
2. El pie contiene la atribución exacta de cada fuente que aportó ofertas.
3. Ninguna oferta del boletín tiene enlace muerto.
4. Ninguna oferta presente en `historial.json` reaparece en una edición posterior, sin importar cuántas ediciones hayan pasado.
5. Con una fuente forzada a fallar, el boletín se envía y el pie lo declara.
6. Con todas las fuentes fallando, no se envía boletín: se envía alerta.
7. Sin `ANTHROPIC_API_KEY`, el boletín se genera completo y correcto.
8. El workflow corre en GitHub Actions y commitea el historial actualizado.
