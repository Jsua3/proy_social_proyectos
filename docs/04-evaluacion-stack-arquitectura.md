# Evaluación de stack y arquitectura — Programa 1

**Fecha:** 9 de septiembre de 2026. Revisión crítica de la recomendación inicial ("Python", a secas),
contrastada con el estado actual del ecosistema.

---

## 1. Autoevaluación de la propuesta inicial

### Lo que se sostiene

| Decisión | Evidencia que la respalda |
|---|---|
| **Python como lenguaje** | El informe de infraestructura de Apify 2026 sitúa a Python en **71,7 %** del ecosistema de scraping y pipelines, frente a **17 %** de JavaScript. No es moda: es dónde está la documentación, las respuestas y las librerías. |
| **Núcleo portable, Actions solo como disparador** | Sigue siendo correcto y es lo que permite cumplir "si GitHub no funciona, se cambia". |
| **Adaptadores de fuente con permiso declarado** | Reforzado por hallazgo nuevo, ver §4. |
| **Estado en el repositorio, sin base de datos** | Patrón consolidado (*git scraping*, Simon Willison). Confirmado con una corrección importante en §3. |

### Lo que corrijo

**a) Dije "Python" sin decir qué Python.** En 2026 eso ya no significa nada por sí solo. El toolchain
actual es **uv + Ruff** (ambos de Astral, escritos en Rust): `uv` reemplaza pip, venv, virtualenv,
pip-tools, pyenv y poetry en un solo binario 10–100× más rápido; `ruff` reemplaza flake8, black e isort
con la misma ganancia. Adoptados por Stripe, OpenAI y los mantenedores de FastAPI. Omitirlos era dejar
sobre la mesa reproducibilidad (lockfile) y arranque casi instantáneo en CI.

> *Nota de gobernanza:* Astral se integró a OpenAI en marzo de 2026 (equipo de Codex). Las herramientas
> siguen open source y en desarrollo activo, pero conviene saberlo. El riesgo es bajo: si `uv`
> desapareciera, `pyproject.toml` es estándar PEP 621 y se vuelve a pip sin reescribir código.

**b) Traté "render HTML" como si fuera un detalle.** No lo es — es donde mueren estos proyectos. El HTML
de correo es hostil: Outlook no soporta flexbox, Gmail recorta a 102 KB, cada cliente rompe algo distinto.
La respuesta madura es **MJML**, y no la nombré. Se compila a HTML a prueba de clientes de correo.

**c) Asumí SMTP sin evaluar alternativas.** Ver §2.

**d) Mi argumento de mantenibilidad era infundado.** Afirmé que Python sería "lo más fácil de retomar
para el próximo monitor" sin saber qué enseña el programa de Ingeniería de Software de la CUE. Los
proyectos del propio repositorio del usuario son mayoritariamente **JS/Node y Java**. Si el programa no
enseña Python, elegirlo puede dejar el proyecto huérfano cuando el monitor actual se gradúe — que es
exactamente el escenario que hay que evitar en una herramienta institucional. **Este es el único factor
que podría justificar cambiar de lenguaje.**

**e) No consideré alternativas sin código.** Debí. Ver §2.

---

## 2. Alternativas de stack evaluadas

| Opción | Veredicto | Razón |
|---|---|---|
| **Python + uv + Ruff + httpx + selectolax + pydantic + Jinja2/MJML** | ✅ **Recomendada** | Ecosistema dominante para esta carga; sin paso de build en CI; `uv` da lockfile reproducible. |
| **TypeScript/Node + Crawlee + React Email + Resend** | ✅ Viable, segunda opción | Mejor si el equipo que hereda piensa en JS. Crawlee es async-first y trae reintentos y colas de serie. React Email da excelente DX. Cuesta un paso de build y tipos que mantener. |
| **Go** | ❌ Descartada | Su ventaja real es concurrencia masiva. Aquí son 4 fuentes cada 15 días. Ecosistema de parsing y plantillas de correo mucho más pobre, y menos gente en la facultad que lo lea. |
| **n8n autohospedado** (low-code) | ❌ Descartada, pero fue tentadora | Atractivo para el relevo: un flujo visual sobrevive mejor a la rotación que un repositorio. Pero exige un VPS permanente (contradice "GitHub Actions por ahora"), su nodo HTTP no ejecuta JavaScript, y toda la lógica de filtrado y antiestafa termina metida en nodos `Code` con expresiones JSON — peor de testear y de versionar que el código plano. |
| **Orquestador (Airflow / Prefect / Dagster)** | ❌ Descartada | Sobre-ingeniería flagrante. **GitHub Actions cron ya es el orquestador.** Introducir uno propio añade un servicio que mantener para un trabajo que corre 24 veces al año. |
| **Scrapy** | ❌ Descartada | Su valor está en rastrear cientos de miles de páginas con middleware de reintentos y throttling. Aquí hay 2 fuentes HTML y 2 APIs. |
| **Crawlee-Python / Scrapling** | 🟡 Innecesarias hoy | Scrapling aporta *parsing adaptativo* (reubica elementos cuando la página cambia), lo cual es genuinamente útil contra sitios que mutan. Reservarlo como plan B si Magneto o el SPE resultan inestables. |

### Envío de correo

| Opción | Free tier | Veredicto |
|---|---|---|
| **SMTP institucional** (`@cue.edu.co`) | — | ✅ Preferido para la fase 1. Máxima legitimidad: el correo sale de la universidad. Depende de que TI entregue credenciales. |
| **Brevo** | 9.000/mes (300/día) | ✅ Mejor opción para la fase 2 (lista de egresados). El tier gratuito más generoso. |
| **Resend** | 3.000/mes (100/día) | 🟡 Mejor DX del mercado, pero el tope de 100/día limita un envío masivo puntual. |
| **Postmark** | 100/mes | ❌ Inservible en gratuito. Mejor entregabilidad del mercado, pero de pago desde el primer día real. |

> Cualquier proveedor externo exige verificar el dominio (SPF/DKIM) para enviar como `@cue.edu.co`, lo
> que **también** requiere a TI. No hay atajo que evite hablar con ellos; solo cambia qué se les pide.

---

## 3. Arquitectura prudente

**Ports & adapters, aplicado a tres bordes — no solo a las fuentes.**

Mi propuesta inicial solo abstraía las fuentes. Los otros dos bordes son justo los que ya sabemos que van
a cambiar:

```
        [ Fuentes ]                                    ENTRADA
   spe · magneto · remotive · remoteok
              ↓
   ┌──────────────────────────────┐
   │   NÚCLEO (lógica pura)       │   sin E/S, testeable sin red
   │   normalizar · filtrar       │
   │   deduplicar · ordenar       │
   └──────────────────────────────┘
         ↓                ↓
  [ Almacenamiento ]  [ Entrega ]                      SALIDA
   json → sqlite       smtp → brevo → lista
```

- **Borde de entrada:** ya previsto. Permite sumar elempleo si llega el permiso escrito.
- **Borde de almacenamiento:** hoy JSON en el repo; mañana SQLite si crece. Cambio local.
- **Borde de entrega:** hoy SMTP a un destinatario; mañana Brevo a una lista. **Este es el borde que
  hace barata la promesa "egresados después"** y que yo había dejado acoplado.

**El núcleo no hace E/S.** Recibe ofertas normalizadas y devuelve ofertas filtradas y ordenadas. Se prueba
entero sin red, sin correo y sin credenciales — que es lo que permite tener pruebas de verdad y no
solamente humo.

**Un solo proceso, pipeline secuencial.** Sin colas, sin concurrencia, sin microservicios. Para 4 fuentes
cada 15 días, cualquier cosa más elaborada es complejidad sin beneficio.

**Corrección sobre la persistencia:** el estado va **commiteado al repositorio**, no a la caché de
GitHub Actions. La caché se borra a los 7 días sin uso y está limitada a 10 GB — inservible para un
historial que debe sobrevivir entre ediciones quincenales. Requiere activar *Read and write permissions*
en Settings → Actions → General.

---

## 4. Hallazgo que refuerza el enfoque A

Desde **enero de 2026**, la autoridad francesa de protección de datos trata el **desacato del `robots.txt`
como evidencia en contra** de la base de interés legítimo bajo GDPR. El consenso de 2026 lo resume así:
respetar `robots.txt` no vuelve legal un scraping por sí solo, **pero ignorarlo ahora juega en contra**.

Es decir: la decisión de excluir elempleo y Computrabajo no fue una precaución exagerada. Era la lectura
correcta, y el marco legal se ha movido en esa dirección durante el último año.

---

## 5. Stack propuesto (revisado)

| Capa | Elección | Por qué |
|---|---|---|
| Lenguaje | **Python 3.13** | Ecosistema dominante para esta carga |
| Gestor de proyecto | **uv** | Lockfile reproducible, arranque casi instantáneo en CI |
| Lint y formato | **Ruff** | Reemplaza flake8 + black + isort |
| Tipos | **pydantic v2** | Valida y normaliza las ofertas en el borde de entrada |
| HTTP | **httpx** | Cliente moderno, async si hiciera falta |
| Parsing HTML | **selectolax** | Muy rápido; suficiente para 2 fuentes HTML permisivas |
| Plantilla de correo | **MJML vía `jinja2-mjml`** | MJML compila a HTML a prueba de clientes. El paquete usa un port en Rust: **no requiere Node** |
| Envío | **SMTP institucional** (adaptador) | Legitimidad; Brevo detrás del mismo puerto para la fase 2 |
| Estado | **JSON commiteado al repo** | Sin BD, diffs legibles, historial gratis en git |
| Pruebas | **pytest** | Núcleo testeable sin red |
| Programación | **GitHub Actions cron** | Ya es el orquestador; no añadir otro |
| LLM (opcional) | SDK de Anthropic tras un puerto | Degradable: sin key, el boletín sale igual |

---

## 6. Decisión pendiente

**El lenguaje depende de quién mantiene esto en dos años, no de cuál me gusta más a mí.**

- Si el programa de Ingeniería de Software de la CUE enseña Python, o si los monitores lo manejan →
  **Python**, sin dudarlo.
- Si el programa es fundamentalmente Java/JavaScript y nadie toca Python → **TypeScript/Node con Crawlee
  y React Email** es la segunda opción y no es mala. Se paga un paso de build, se gana un relevo real.

Elegir el stack "mejor" que nadie en la facultad pueda mantener sería el peor resultado posible de esta
evaluación.
