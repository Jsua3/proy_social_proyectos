# Viabilidad legal y técnica de las fuentes de empleo — Programa 1

**Verificado el 9 de septiembre de 2026** consultando directamente `robots.txt`, `llms.txt` y los
endpoints de cada fuente. No es una opinión: son las reglas que cada sitio publica.

---

## Semáforo de fuentes

### 🔴 PROHIBIDAS — no usar

#### elempleo.com
Su `robots.txt` incluye una cláusula legal explícita:

> *"Use of any device, tool, or process designed to data mine or scrape the content, using automated
> means, it is prohibited without prior written permission from ELEMPLEO."*
>
> Usos prohibidos, textual: *"(1) text and data mining activities; (2) the development of any software,
> machine learning, artificial intelligence (AI), and/or large language models (LLMs); (3) creating or
> providing archived or cached data sets containing our content to others; (4) any commercial purposes."*

Además bloquea por nombre a los agregadores: `linkedin`, `jooble`, `neuvoo`, `bebee`, `Fidanto`,
`buscaempleoefectivo`.

**Veredicto:** usar elempleo sería violar sus términos de servicio de forma expresa y documentada.
Inaceptable para un sistema que opera en nombre de una universidad.
**Vía legítima:** solicitar permiso escrito a `notificaciones@elempleo.com`. Si lo conceden, entra.

#### co.computrabajo.com
`robots.txt` responde **HTTP 403 Forbidden** — ni siquiera permite leer sus reglas de forma automatizada.
Protección anti-bot activa; los scrapers comerciales que existen requieren proxies residenciales para
evadirla.

**Veredicto:** evadir protección anti-bot para un proyecto institucional es un riesgo reputacional y
legal que no compensa.

#### LinkedIn
Sus términos prohíben el scraping y hay jurisprudencia abundante al respecto.
**Veredicto:** fuera.

---

### 🟢 PERMITIDAS — usar estas

#### Magneto365 (magneto365.com) — la mejor fuente colombiana
Publica un **`llms.txt`**: un archivo de guía *explícitamente dirigido a asistentes de IA y agentes*.

> *"Guía de páginas canónicas para que asistentes de IA entiendan Magneto (Colombia), respondan preguntas
> frecuentes y citen URLs estables de alta calidad."*
> *"Prioridad: usar primero secciones Core. Evitar URLs con parámetros."*

`robots.txt`: `Allow: /` con `Disallow: /*?` — coherente con la instrucción de evitar parámetros.

URLs canónicas relevantes que el propio sitio ofrece:
- `https://www.magneto365.com/co/trabajos/buscar`
- `https://www.magneto365.com/co/trabajos/ofertas-empleo-trabajo-remoto`
- Por ciudad: `.../ofertas-empleo-en-{bogota|medellin|cali|pereira|...}`

**Veredicto:** consentimiento explícito para agentes de IA. Es la fuente colombiana de referencia.
**Condición:** usar solo rutas canónicas sin query string, y citar Magneto como fuente.

#### Servicio Público de Empleo — `serviciodeempleo.gov.co` / `buscadordeempleo.gov.co`
Plataforma **oficial del Ministerio del Trabajo**. Agrega vacantes de todas las bolsas autorizadas del país.
`robots.txt` permisivo (solo bloquea `/wp-admin/`). Publica **datos abiertos**.

**Veredicto:** la fuente más "seria y con seguridad" que existe para Colombia — es del Estado, las
vacantes están verificadas y las empresas registradas. Debe ser la fuente primaria.
**Pendiente de diseño:** identificar el endpoint de búsqueda del buscador (el portal es HTML; hay que
localizar la petición XHR que alimenta los resultados) o usar el portal de datos abiertos. ⚠️

#### Remotive — `remotive.com/api/remote-jobs`
API pública gratuita, sin autenticación. Categoría `software-dev` disponible. Probada y funcionando.
**Condición legal, textual:** *"Please link back to the URL found on Remotive AND mention Remotive as a
source... If you don't do that, we'll terminate your API access."* Vacantes con 24 h de retraso.
**Veredicto:** usable, cumpliendo la atribución.

#### RemoteOK — `remoteok.com/api`
API pública gratuita. Probada y funcionando.
**Condición legal, textual:** *"Please link back (with follow, and without nofollow!) to the URL on
Remote OK and mention Remote OK as a source."* No usar su logo.
**Veredicto:** usable, cumpliendo la atribución.

#### Arbeitnow — `arbeitnow.com/api/job-board-api`
API pública gratuita, sin autenticación. Probada y funcionando. Incluye campo `remote`.
**Limitación real:** el contenido observado es mayoritariamente **alemán/europeo**. Aporta poco a un
egresado en Colombia salvo en vacantes remotas globales.
**Veredicto:** opcional, de baja prioridad.

---

### 🟡 POR VERIFICAR

| Fuente | Qué falta averiguar |
|---|---|
| **Adzuna API** | Free tier de 1.000 llamadas/mes, pero **no está confirmado que cubra Colombia**. Requiere `app_id` + `app_key`. Verificar antes de contar con ella. |
| **SENA — Agencia Pública de Empleo** | Es fuente oficial y gratuita. Verificar si expone datos de forma consultable. |
| **Bolsas de cajas de compensación** (Comfenalco Quindío, Comfamiliar) | Relevantes para el mercado local del Quindío. Verificar términos. |
| **Empresas aliadas de la CUE** | Cafequipe, Daluzed, JR Mecanizados y las ~50 empresas del modelo dual. Fuente propia, sin problemas legales, y de altísima pertinencia. |

---

## Consecuencia para el diseño

El requisito de la directora — *"sitios serios y con seguridad"* — resulta tener **dos capas**, y la
primera no la habíamos visto:

1. **Legalidad de la fuente.** No podemos extraer de donde nos lo prohíben. Un boletín institucional
   construido violando términos de servicio es un problema para la universidad, no una optimización.
   Esta capa se resuelve eligiendo fuentes, no filtrando resultados.

2. **Legitimidad de la oferta.** Filtrar estafas y ofertas engañosas dentro de las fuentes permitidas:
   sin datos de contacto verificables, que pidan dinero al aspirante, sueldos irreales, empresas sin
   identificar, enlaces a formularios externos sospechosos.

**Principio de diseño resultante:** cada fuente del sistema debe declarar su base de permiso (API pública
con atribución / `llms.txt` explícito / portal estatal / permiso escrito) y el sistema debe registrar esa
atribución en cada edición del boletín. Si una fuente no puede declarar su permiso, no entra.
