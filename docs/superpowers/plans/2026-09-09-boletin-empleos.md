# Boletín de Empleos — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un agente que cada quince días recolecta ofertas de empleo en software desde cuatro fuentes autorizadas, las filtra por pertinencia y legitimidad, y le envía por correo un boletín HTML a la Coordinación de Proyección Social de Ingeniería de la CUE Alexander von Humboldt.

**Architecture:** Puertos y adaptadores sobre tres bordes (fuentes, almacenamiento, entrega). El núcleo es lógica pura sin E/S, testeable sin red. Un proceso, pipeline secuencial. GitHub Actions cron es el único orquestador.

**Tech Stack:** Python 3.13 · uv · Ruff · pydantic v2 · httpx · selectolax · jinja2-mjml · pytest

**Spec:** `docs/superpowers/specs/2026-09-09-boletin-empleos-design.md`

## Global Constraints

- **Python ≥ 3.13.** Se usa `StrEnum` y sintaxis `X | None`.
- **Todo el código, nombres de símbolos, comentarios y salidas en español.** El dominio es institucional colombiano.
- **El núcleo (`src/boletin_empleos/nucleo/`) no puede importar `httpx`, `smtplib`, ni tocar disco ni red.** Es la invariante que hace testeable el sistema. Un test lo verifica.
- **Todo adaptador de fuente declara `base_permiso`, `atribucion` y `url_atribucion`.** Son obligatorios; sin ellos el pie de atribución queda incompleto y Remotive/RemoteOK cortan el acceso.
- **`User-Agent` fijo en todas las peticiones salientes:**
  `BoletinEmpleosCUE/1.0 (+https://github.com/Jsua3/proy_social_proyectos; coorproyeccioning@cue.edu.co)`
- **Nunca commitear secretos.** Credenciales solo por variables de entorno.
- **Los descartes por relevancia y las deduplicaciones NO van al apéndice del boletín**, solo al registro de ejecución (spec §8.6).
- **Formato:** `ruff format .` y `ruff check .` deben pasar antes de cada commit.
  `docs/` está excluido en `pyproject.toml`: Ruff formatea el Python embebido en Markdown y
  reescribiría este mismo plan. Si ves `docs/` modificado tras formatear, la exclusión se perdió.

---

### Task 1: Esqueleto del proyecto y modelos de dominio

**Files:**
- Create: `pyproject.toml`
- Create: `src/boletin_empleos/__init__.py`
- Create: `src/boletin_empleos/modelos.py`
- Create: `tests/test_modelos.py`
- Create: `.python-version`

**Interfaces:**
- Consumes: nada (primera tarea)
- Produces: `Modalidad`, `Decision`, `MotivoDescarte`, `Oferta`, `Evaluacion` — usados por todas las tareas siguientes

- [ ] **Step 1: Crear `pyproject.toml`**

```toml
[project]
name = "boletin-empleos"
version = "0.1.0"
description = "Boletín quincenal de empleos para egresados de Ingeniería de Software — CUE Alexander von Humboldt"
requires-python = ">=3.13"
dependencies = [
    "pydantic>=2.9",
    "httpx>=0.27",
    "selectolax>=0.3.21",
    "jinja2-mjml>=0.1",
]

# jinja2-mjml solo existe en 0.1.0 en PyPI y fija mjml-python<0.2.0, que no
# publica wheels para cp313. mjml-python 1.2.4+ sí los trae (cp313/abi3) y la
# API que usamos es compatible. Verificado el 9/09/2026.
[tool.uv]
override-dependencies = ["mjml-python>=1.2.4"]

[project.scripts]
boletin = "boletin_empleos.cli:main"

[dependency-groups]
dev = ["pytest>=8.3", "ruff>=0.7", "respx>=0.21"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/boletin_empleos"]

[tool.ruff]
line-length = 100
target-version = "py313"
# Ruff formatea los bloques de Python embebidos en Markdown. Sin esta exclusión,
# `ruff format .` reescribe el propio plan y el spec en cada tarea, metiendo
# documentos del controlador dentro de los commits de los implementadores.
extend-exclude = ["docs"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Crear `.python-version` y sincronizar el entorno**

```bash
echo "3.13" > .python-version
mkdir -p src/boletin_empleos tests
touch src/boletin_empleos/__init__.py
uv sync
```

Expected: `uv` crea `.venv/` y `uv.lock`.

- [ ] **Step 3: Escribir el test que falla**

```python
# tests/test_modelos.py
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from boletin_empleos.modelos import Decision, Evaluacion, Modalidad, MotivoDescarte, Oferta


def _oferta(**extra) -> Oferta:
    base = dict(
        id="spe:123",
        fuente="spe",
        titulo="Desarrollador Backend Python",
        empresa="Acme S.A.S.",
        ubicacion="Armenia, Quindío",
        pais="CO",
        modalidad=Modalidad.PRESENCIAL,
        url="https://ejemplo.co/vacante/123",
        descripcion="Se requiere desarrollador con conocimientos en Python y SQL.",
        recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
    )
    return Oferta(**(base | extra))


def test_oferta_minima_valida():
    o = _oferta()
    assert o.id == "spe:123"
    assert o.modalidad is Modalidad.PRESENCIAL
    assert o.fecha_publicacion is None
    assert o.es_practica is False


def test_oferta_acepta_campos_del_spe():
    o = _oferta(
        fecha_publicacion=date(2026, 9, 1),
        fecha_vencimiento=date(2026, 10, 1),
        meses_experiencia=12,
        es_practica=True,
        salario_min=3_000_000,
        salario_max=4_000_000,
        moneda="COP",
    )
    assert o.meses_experiencia == 12
    assert o.es_practica is True
    assert o.salario_max == 4_000_000


def test_oferta_rechaza_url_invalida():
    with pytest.raises(ValidationError):
        _oferta(url="no-es-una-url")


def test_evaluacion_conserva_motivo_y_notas():
    e = Evaluacion(
        oferta=_oferta(),
        puntaje_relevancia=0.9,
        puntaje_legitimidad=0.8,
        decision=Decision.DESCARTAR,
        motivo=MotivoDescarte.LEGITIMIDAD,
        notas=["contacto solo por WhatsApp"],
    )
    assert e.decision is Decision.DESCARTAR
    assert e.motivo is MotivoDescarte.LEGITIMIDAD
    assert e.notas == ["contacto solo por WhatsApp"]


def test_evaluacion_incluida_no_tiene_motivo():
    e = Evaluacion(
        oferta=_oferta(),
        puntaje_relevancia=0.9,
        puntaje_legitimidad=0.9,
        decision=Decision.INCLUIR,
    )
    assert e.motivo is None
    assert e.notas == []
```

- [ ] **Step 4: Ejecutar y verificar que falla**

Run: `uv run pytest tests/test_modelos.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'boletin_empleos.modelos'`

- [ ] **Step 5: Implementar `modelos.py`**

```python
# src/boletin_empleos/modelos.py
"""Modelos de dominio del boletín de empleos."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class Modalidad(StrEnum):
    PRESENCIAL = "presencial"
    HIBRIDO = "hibrido"
    REMOTO = "remoto"


class Decision(StrEnum):
    INCLUIR = "incluir"
    DESCARTAR = "descartar"


class MotivoDescarte(StrEnum):
    RELEVANCIA = "relevancia"
    EXPERIENCIA = "experiencia"
    VIGENCIA = "vigencia"
    ENLACE_MUERTO = "enlace_muerto"
    LEGITIMIDAD = "legitimidad"
    DUPLICADO = "duplicado"
    ES_PRACTICA = "es_practica"


class Oferta(BaseModel):
    """Una vacante ya normalizada, independiente de la fuente que la produjo."""

    id: str
    fuente: str
    titulo: str
    empresa: str | None = None
    ubicacion: str | None = None
    pais: str | None = None
    modalidad: Modalidad
    url: HttpUrl
    descripcion: str
    recogida_en: datetime

    fecha_publicacion: date | None = None
    fecha_vencimiento: date | None = None
    meses_experiencia: int | None = None
    es_practica: bool = False

    salario_min: int | None = None
    salario_max: int | None = None
    moneda: str | None = None

    @property
    def texto_completo(self) -> str:
        """Título y descripción concatenados, para puntuación de texto."""
        return f"{self.titulo}\n{self.descripcion}"


class Evaluacion(BaseModel):
    """El veredicto del núcleo sobre una oferta. `notas` se llena siempre."""

    oferta: Oferta
    puntaje_relevancia: float = Field(ge=0.0, le=1.0)
    puntaje_legitimidad: float = Field(ge=0.0, le=1.0)
    decision: Decision
    motivo: MotivoDescarte | None = None
    notas: list[str] = Field(default_factory=list)
```

- [ ] **Step 6: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/test_modelos.py -v`
Expected: PASS — 5 tests

- [ ] **Step 7: Formatear y commitear**

```bash
uv run ruff format . && uv run ruff check --fix .
git add pyproject.toml uv.lock .python-version src/ tests/
git commit -m "feat: esqueleto del proyecto y modelos de dominio"
```

---

### Task 2: Puerto de fuentes y adaptador Remotive

**Files:**
- Create: `src/boletin_empleos/fuentes/__init__.py`
- Create: `src/boletin_empleos/fuentes/base.py`
- Create: `src/boletin_empleos/fuentes/remotive.py`
- Create: `src/boletin_empleos/http.py`
- Create: `tests/fixtures/remotive.json`
- Create: `tests/test_fuente_remotive.py`

**Interfaces:**
- Consumes: `Oferta`, `Modalidad` (Task 1)
- Produces: `FuenteEmpleo` (Protocol), `USER_AGENT`, `crear_cliente()`, `FuenteRemotive`

- [ ] **Step 1: Descargar la fixture real**

```bash
mkdir -p tests/fixtures
curl -s -A "BoletinEmpleosCUE/1.0" \
  "https://remotive.com/api/remote-jobs?category=software-dev&limit=5" \
  -o tests/fixtures/remotive.json
python -c "import json;d=json.load(open('tests/fixtures/remotive.json',encoding='utf-8'));print(len(d['jobs']),'ofertas');print(list(d['jobs'][0]))"
```

Expected: imprime el número de ofertas y sus campos (`id`, `url`, `title`, `company_name`, `candidate_required_location`, `publication_date`, `description`, …).

- [ ] **Step 2: Escribir el test que falla**

```python
# tests/test_fuente_remotive.py
import json
from pathlib import Path

import httpx
import respx

from boletin_empleos.fuentes.remotive import FuenteRemotive
from boletin_empleos.modelos import Modalidad

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "remotive.json").read_text("utf-8"))


@respx.mock
def test_remotive_normaliza_ofertas():
    respx.get(url__startswith="https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json=FIXTURE)
    )
    ofertas = FuenteRemotive().obtener()

    assert len(ofertas) == len(FIXTURE["jobs"])
    o = ofertas[0]
    assert o.fuente == "remotive"
    assert o.id.startswith("remotive:")
    assert o.modalidad is Modalidad.REMOTO
    assert o.titulo
    assert str(o.url).startswith("http")


def test_remotive_declara_su_permiso_y_atribucion():
    f = FuenteRemotive()
    assert f.nombre == "remotive"
    assert f.base_permiso
    assert "Remotive" in f.atribucion
    assert str(f.url_atribucion).startswith("https://remotive.com")
    assert 0.0 <= f.confianza_base <= 1.0


@respx.mock
def test_remotive_devuelve_vacio_si_la_api_falla():
    respx.get(url__startswith="https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(503)
    )
    assert FuenteRemotive().obtener() == []
```

- [ ] **Step 3: Ejecutar y verificar que falla**

Run: `uv run pytest tests/test_fuente_remotive.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'boletin_empleos.fuentes'`

- [ ] **Step 4: Implementar el cliente HTTP compartido**

```python
# src/boletin_empleos/http.py
"""Cliente HTTP compartido. Identifica al agente y reintenta con retroceso."""

import logging
import time
from collections.abc import Callable

import httpx

USER_AGENT = (
    "BoletinEmpleosCUE/1.0 "
    "(+https://github.com/Jsua3/proy_social_proyectos; coorproyeccioning@cue.edu.co)"
)

_log = logging.getLogger(__name__)


def crear_cliente(timeout: float = 30.0, acepta: str = "application/json") -> httpx.Client:
    """`acepta` se parametriza porque no todas las fuentes sirven JSON: Magneto sirve HTML
    y un servidor estricto respondería 406 ante un Accept que no puede satisfacer."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": acepta},
        timeout=timeout,
        follow_redirects=True,
    )


def reintentar[T](
    operacion: Callable[[], T], intentos: int = 3, espera_base: float = 1.0
) -> T | None:
    """Ejecuta `operacion` con retroceso exponencial. Devuelve None si todo falla.

    Genéricos con sintaxis PEP 695 (`def reintentar[T]`), no `TypeVar`: con
    `target-version = "py313"` la regla UP047 de ruff rechaza la forma antigua.
    """
    for intento in range(intentos):
        try:
            return operacion()
        except (httpx.HTTPError, httpx.HTTPStatusError) as e:
            _log.warning("intento %d/%d falló: %s", intento + 1, intentos, e)
            if intento < intentos - 1:
                time.sleep(espera_base * (2**intento))
    return None
```

- [ ] **Step 5: Implementar el puerto de fuentes**

```python
# src/boletin_empleos/fuentes/base.py
"""Puerto de entrada: contrato que toda fuente de empleo debe cumplir.

`base_permiso`, `atribucion` y `url_atribucion` son obligatorios por diseño:
una fuente que no puede declarar por qué tenemos derecho a usarla no tiene
dónde encajar en este sistema (spec §4).
"""

from typing import Protocol, runtime_checkable

from boletin_empleos.modelos import Oferta


@runtime_checkable
class FuenteEmpleo(Protocol):
    nombre: str
    base_permiso: str
    atribucion: str
    url_atribucion: str
    confianza_base: float

    def obtener(self) -> list[Oferta]:
        """Devuelve ofertas normalizadas. Ante fallo, lista vacía — nunca excepción."""
        ...
```

```python
# src/boletin_empleos/fuentes/__init__.py
from boletin_empleos.fuentes.base import FuenteEmpleo

__all__ = ["FuenteEmpleo"]
```

- [ ] **Step 6: Implementar el adaptador Remotive**

```python
# src/boletin_empleos/fuentes/remotive.py
"""Remotive — API pública gratuita.

Condición legal textual de su API: "Please link back to the URL found on
Remotive AND mention Remotive as a source... If you don't do that, we'll
terminate your API access." Las ofertas vienen con 24 h de retraso por diseño suyo.
"""

import logging
from datetime import UTC, datetime

from boletin_empleos.http import crear_cliente, reintentar
from boletin_empleos.modelos import Modalidad, Oferta

_log = logging.getLogger(__name__)
_URL = "https://remotive.com/api/remote-jobs"


class FuenteRemotive:
    nombre = "remotive"
    base_permiso = "API pública gratuita, sin autenticación, con obligación de atribución."
    atribucion = "Ofertas remotas provistas por Remotive."
    url_atribucion = "https://remotive.com/"
    confianza_base = 0.75

    def __init__(self, categoria: str = "software-dev", limite: int = 100) -> None:
        self._categoria = categoria
        self._limite = limite

    def obtener(self) -> list[Oferta]:
        with crear_cliente() as cliente:
            respuesta = reintentar(
                lambda: cliente.get(
                    _URL, params={"category": self._categoria, "limit": self._limite}
                ).raise_for_status()
            )
        if respuesta is None:
            _log.error("remotive: no se pudo obtener la lista de ofertas")
            return []

        ahora = datetime.now(UTC)
        ofertas: list[Oferta] = []
        for bruto in respuesta.json().get("jobs", []):
            oferta = self._normalizar(bruto, ahora)
            if oferta is not None:
                ofertas.append(oferta)
        return ofertas

    def _normalizar(self, bruto: dict, ahora: datetime) -> Oferta | None:
        try:
            return Oferta(
                id=f"remotive:{bruto['id']}",
                fuente=self.nombre,
                titulo=bruto["title"],
                empresa=bruto.get("company_name"),
                ubicacion=bruto.get("candidate_required_location"),
                pais=None,
                modalidad=Modalidad.REMOTO,
                url=bruto["url"],
                descripcion=bruto.get("description", ""),
                recogida_en=ahora,
                fecha_publicacion=_fecha(bruto.get("publication_date")),
            )
        except (KeyError, ValueError) as e:
            _log.warning("remotive: oferta descartada por dato inválido: %s", e)
            return None


def _fecha(valor: str | None):
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00")).date()
    except ValueError:
        return None
```

- [ ] **Step 7: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/test_fuente_remotive.py -v`
Expected: PASS — 3 tests

- [ ] **Step 8: Formatear y commitear**

```bash
uv run ruff format . && uv run ruff check --fix .
git add src/ tests/
git commit -m "feat: puerto de fuentes y adaptador Remotive"
```

---

### Task 3: Adaptador RemoteOK

**Files:**
- Create: `src/boletin_empleos/fuentes/remoteok.py`
- Create: `tests/fixtures/remoteok.json`
- Create: `tests/test_fuente_remoteok.py`

**Interfaces:**
- Consumes: `Oferta`, `Modalidad`, `crear_cliente`, `reintentar`
- Produces: `FuenteRemoteOK`

**Particularidad verificada:** el primer elemento del arreglo que devuelve RemoteOK **no es una oferta**, es su aviso legal (`{"legal": "..."}`). Hay que descartarlo.

- [ ] **Step 1: Descargar la fixture real**

```bash
mkdir -p tests/fixtures
curl -s -A "BoletinEmpleosCUE/1.0" "https://remoteok.com/api" \
  -o tests/fixtures/.remoteok_completo.json
uv run python -c "
import json, pathlib
crudo = pathlib.Path('tests/fixtures/.remoteok_completo.json')
d = json.loads(crudo.read_text(encoding='utf-8'))
print('primer elemento (aviso legal):', list(d[0]))
print('campos de oferta:', list(d[1]))
pathlib.Path('tests/fixtures/remoteok.json').write_text(
    json.dumps(d[:6], ensure_ascii=False), encoding='utf-8')
crudo.unlink()
"
```

**Por qué el archivo temporal va dentro del repositorio y no en `/tmp`:** en este entorno Windows,
`curl` corre bajo MSYS y resuelve `/tmp` a una ruta distinta de la que ve Python, que lo interpreta
como `C:\tmp` literal. Escribir en `/tmp` y leerlo desde Python falla con `FileNotFoundError`.
El archivo intermedio se borra al final; `tests/fixtures/remoteok.json` es el que queda.

- [ ] **Step 2: Escribir el test que falla**

```python
# tests/test_fuente_remoteok.py
import json
from pathlib import Path

import httpx
import respx

from boletin_empleos.fuentes.remoteok import FuenteRemoteOK
from boletin_empleos.modelos import Modalidad

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "remoteok.json").read_text("utf-8"))


@respx.mock
def test_remoteok_descarta_el_aviso_legal():
    respx.get("https://remoteok.com/api").mock(return_value=httpx.Response(200, json=FIXTURE))
    ofertas = FuenteRemoteOK().obtener()

    assert len(ofertas) == len(FIXTURE) - 1, "el primer elemento es el aviso legal, no una oferta"
    assert all(o.modalidad is Modalidad.REMOTO for o in ofertas)
    assert all(o.fuente == "remoteok" for o in ofertas)


def test_remoteok_declara_su_permiso_y_atribucion():
    f = FuenteRemoteOK()
    assert f.nombre == "remoteok"
    assert "Remote OK" in f.atribucion
    assert f.base_permiso


@respx.mock
def test_remoteok_devuelve_vacio_si_la_api_falla():
    respx.get("https://remoteok.com/api").mock(return_value=httpx.Response(500))
    assert FuenteRemoteOK().obtener() == []
```

- [ ] **Step 3: Ejecutar y verificar que falla**

Run: `uv run pytest tests/test_fuente_remoteok.py -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 4: Implementar el adaptador**

```python
# src/boletin_empleos/fuentes/remoteok.py
"""RemoteOK — API pública gratuita.

Condición legal textual: "Please link back (with follow, and without nofollow!)
to the URL on Remote OK and mention Remote OK as a source." No usar su logo:
es marca registrada.

El primer elemento del arreglo es el aviso legal, no una oferta.
"""

import logging
from datetime import UTC, datetime

from boletin_empleos.http import crear_cliente, reintentar
from boletin_empleos.modelos import Modalidad, Oferta

_log = logging.getLogger(__name__)
_URL = "https://remoteok.com/api"


class FuenteRemoteOK:
    nombre = "remoteok"
    base_permiso = "API pública gratuita, sin autenticación, con obligación de atribución."
    atribucion = "Ofertas remotas provistas por Remote OK."
    url_atribucion = "https://remoteok.com/"
    confianza_base = 0.70

    def obtener(self) -> list[Oferta]:
        with crear_cliente() as cliente:
            respuesta = reintentar(lambda: cliente.get(_URL).raise_for_status())
        if respuesta is None:
            _log.error("remoteok: no se pudo obtener la lista de ofertas")
            return []

        datos = respuesta.json()
        ahora = datetime.now(UTC)
        ofertas: list[Oferta] = []
        for bruto in datos:
            if "legal" in bruto:  # aviso legal, no es una oferta
                continue
            oferta = self._normalizar(bruto, ahora)
            if oferta is not None:
                ofertas.append(oferta)
        return ofertas

    def _normalizar(self, bruto: dict, ahora: datetime) -> Oferta | None:
        try:
            return Oferta(
                id=f"remoteok:{bruto['id']}",
                fuente=self.nombre,
                titulo=bruto["position"],
                empresa=bruto.get("company"),
                ubicacion=bruto.get("location") or "Remoto",
                pais=None,
                modalidad=Modalidad.REMOTO,
                url=bruto["url"],
                descripcion=bruto.get("description", ""),
                recogida_en=ahora,
                fecha_publicacion=_fecha(bruto.get("date")),
                salario_min=bruto.get("salary_min") or None,
                salario_max=bruto.get("salary_max") or None,
                moneda="USD" if bruto.get("salary_min") else None,
            )
        except (KeyError, ValueError) as e:
            _log.warning("remoteok: oferta descartada por dato inválido: %s", e)
            return None


def _fecha(valor: str | None):
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00")).date()
    except ValueError:
        return None
```

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/test_fuente_remoteok.py -v`
Expected: PASS — 3 tests

- [ ] **Step 6: Formatear y commitear**

```bash
uv run ruff format . && uv run ruff check --fix .
git add src/ tests/
git commit -m "feat: adaptador RemoteOK"
```

---

### Task 4: Adaptador del Servicio Público de Empleo

**Files:**
- Create: `src/boletin_empleos/fuentes/spe.py`
- Create: `tests/fixtures/spe_pagina.json`
- Create: `tests/test_fuente_spe.py`

**Interfaces:**
- Consumes: `Oferta`, `Modalidad`, `crear_cliente`, `reintentar`
- Produces: `FuenteSPE`

**Contrato verificado el 9/09/2026** (spec §7): base `https://www.buscadordeempleo.gov.co/backbue/v1`,
endpoint `GET /vacantes/resultados?page=N&<filtros>`, 50 registros por página, respuesta
`{resultados[], totalPages, currentPage, total_registros}`. Parámetros válidos: `page`, `departamento`,
`teletrabajo`, `cargo`.

**Consultas de la estrategia** (spec §7): `teletrabajo=1` (39 págs) · `departamento=Quindio` (31 págs) ·
`cargo` con lista curada (~15 págs). Total ≈ 85 peticiones.

- [ ] **Step 1: Descargar la fixture real**

```bash
curl -s -A "BoletinEmpleosCUE/1.0" \
  "https://www.buscadordeempleo.gov.co/backbue/v1/vacantes/resultados?page=1&departamento=Quindio" \
  -o tests/fixtures/spe_pagina.json
python -c "
import json
d=json.load(open('tests/fixtures/spe_pagina.json',encoding='utf-8'))
print('claves:', list(d))
print('n resultados:', len(d['resultados']), 'totalPages:', d['totalPages'])
print('campos:', list(d['resultados'][0]))
"
```

- [ ] **Step 2: Escribir el test que falla**

```python
# tests/test_fuente_spe.py
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import respx

from boletin_empleos.fuentes.spe import FuenteSPE, _a_modalidad, _rango_salarial
from boletin_empleos.modelos import Modalidad

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "spe_pagina.json").read_text("utf-8"))


@respx.mock
def test_spe_pagina_y_normaliza():
    una_pagina = FIXTURE | {"totalPages": 1, "currentPage": 1}
    respx.get(url__startswith="https://www.buscadordeempleo.gov.co/backbue/v1").mock(
        return_value=httpx.Response(200, json=una_pagina)
    )
    ofertas = FuenteSPE(consultas=[{"departamento": "Quindio"}]).obtener()

    assert len(ofertas) == len(FIXTURE["resultados"])
    o = ofertas[0]
    assert o.fuente == "spe"
    assert o.id.startswith("spe:")
    assert o.pais == "CO"
    assert str(o.url).startswith("http"), "la URL sale de DETALLES_PRESTADOR[0].URL_DETALLE_VACANTE"
    assert o.empresa, "el nombre del prestador viene en DETALLES_PRESTADOR[0].NOMBRE_PRESTADOR"


@respx.mock
def test_spe_recorre_todas_las_paginas():
    llamadas = {"n": 0}

    def responder(request):
        # Solo se cuentan las páginas de resultados: /version también casa con este mock
        # y contarlo daría 4 en vez de 3.
        if "vacantes/resultados" in request.url.path:
            llamadas["n"] += 1
        pagina = int(request.url.params.get("page", 1))
        return httpx.Response(200, json=FIXTURE | {"totalPages": 3, "currentPage": pagina})

    respx.get(url__startswith="https://www.buscadordeempleo.gov.co/backbue/v1").mock(
        side_effect=responder
    )
    FuenteSPE(consultas=[{"departamento": "Quindio"}], pausa=0.0).obtener()
    assert llamadas["n"] == 3


def test_spe_extrae_url_y_prestador_de_la_lista():
    """DETALLES_PRESTADOR es una LISTA de dicts, no una cadena.

    Tratarla como cadena lanzaría AttributeError con cada registro del SPE.
    """
    from boletin_empleos.fuentes.spe import _prestador

    fila = FIXTURE["resultados"][0]
    nombre, url = _prestador(fila)
    assert nombre and url and url.startswith("http")

    assert _prestador({}) == (None, None)
    assert _prestador({"DETALLES_PRESTADOR": []}) == (None, None)
    assert _prestador({"DETALLES_PRESTADOR": "texto plano"}) == (None, None)


def test_spe_omite_vacantes_sin_url_de_detalle():
    from boletin_empleos.fuentes.spe import FuenteSPE

    fuente = FuenteSPE()
    sin_url = dict(FIXTURE["resultados"][0])
    sin_url["DETALLES_PRESTADOR"] = [{"NOMBRE_PRESTADOR": "X", "URL_DETALLE_VACANTE": ""}]
    assert fuente._normalizar(sin_url, datetime(2026, 9, 9, tzinfo=UTC)) is None


def test_spe_traduce_teletrabajo_a_modalidad():
    assert _a_modalidad("1") is Modalidad.REMOTO
    assert _a_modalidad("Si") is Modalidad.REMOTO
    assert _a_modalidad("0") is Modalidad.PRESENCIAL
    assert _a_modalidad(None) is Modalidad.PRESENCIAL


def test_spe_interpreta_el_rango_salarial():
    assert _rango_salarial("$1.000.001 - $1.500.000") == (1_000_001, 1_500_000)
    assert _rango_salarial("Mayor de $15.000.001") == (15_000_001, None)
    assert _rango_salarial("A Convenir") == (None, None)
    assert _rango_salarial(None) == (None, None)


def test_spe_declara_su_permiso_y_atribucion():
    f = FuenteSPE()
    assert f.nombre == "spe"
    assert f.confianza_base == 0.95
    assert "Servicio Público de Empleo" in f.atribucion


@respx.mock
def test_spe_devuelve_vacio_si_la_api_falla():
    respx.get(url__startswith="https://www.buscadordeempleo.gov.co/backbue/v1").mock(
        return_value=httpx.Response(502)
    )
    assert FuenteSPE(consultas=[{"departamento": "Quindio"}]).obtener() == []
```

- [ ] **Step 3: Ejecutar y verificar que falla**

Run: `uv run pytest tests/test_fuente_spe.py -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 4: Implementar el adaptador**

```python
# src/boletin_empleos/fuentes/spe.py
"""Servicio Público de Empleo — Ministerio del Trabajo de Colombia.

Fuente estatal: agrega las vacantes de todas las bolsas autorizadas del país.
`robots.txt` permisivo y publicación de datos abiertos.

API verificada el 9 de septiembre de 2026 (spec §7). No es una API pública
versionada contractualmente: `GET /version` se consulta en cada corrida para
detectar cambios de contrato.
"""

import logging
import re
import time
from datetime import UTC, date, datetime

from boletin_empleos.http import crear_cliente, reintentar
from boletin_empleos.modelos import Modalidad, Oferta

_log = logging.getLogger(__name__)
_BASE = "https://www.buscadordeempleo.gov.co/backbue/v1"
_VERSION_ESPERADA = "2.4.0"

# Estrategia de descarga medida en el spec §7: cubre remoto nacional,
# el mercado local del Quindío, y ocupaciones de software a nivel nacional.
CONSULTAS_POR_DEFECTO: list[dict[str, str]] = [
    {"teletrabajo": "1"},
    {"departamento": "Quindio"},
    {"cargo": "ingeniero de sistemas"},
    {"cargo": "desarrollador"},
    {"cargo": "programador"},
    {"cargo": "analista de sistemas"},
    {"cargo": "ingeniero de software"},
]


class FuenteSPE:
    nombre = "spe"
    base_permiso = (
        "Portal estatal del Ministerio del Trabajo; robots.txt permisivo "
        "y publicación de datos abiertos."
    )
    atribucion = "Vacantes del Servicio Público de Empleo (Ministerio del Trabajo de Colombia)."
    url_atribucion = "https://www.serviciodeempleo.gov.co/"
    confianza_base = 0.95

    def __init__(
        self,
        consultas: list[dict[str, str]] | None = None,
        max_paginas: int = 60,
        pausa: float = 0.5,
    ) -> None:
        self._consultas = consultas if consultas is not None else CONSULTAS_POR_DEFECTO
        self._max_paginas = max_paginas
        self._pausa = pausa

    def obtener(self) -> list[Oferta]:
        ahora = datetime.now(UTC)
        vistos: set[str] = set()
        ofertas: list[Oferta] = []

        with crear_cliente() as cliente:
            self._verificar_version(cliente)
            for consulta in self._consultas:
                for bruto in self._recorrer(cliente, consulta):
                    codigo = str(bruto.get("CODIGO_VACANTE", ""))
                    if not codigo or codigo in vistos:
                        continue
                    vistos.add(codigo)
                    oferta = self._normalizar(bruto, ahora)
                    if oferta is not None:
                        ofertas.append(oferta)
        return ofertas

    def _verificar_version(self, cliente) -> None:
        respuesta = reintentar(lambda: cliente.get(f"{_BASE}/version").raise_for_status())
        if respuesta is None:
            return
        version = respuesta.json().get("backVersion")
        if version != _VERSION_ESPERADA:
            _log.warning(
                "spe: la API cambió de versión (esperada %s, encontrada %s). "
                "Revisar el contrato del adaptador.",
                _VERSION_ESPERADA,
                version,
            )

    def _recorrer(self, cliente, consulta: dict[str, str]):
        pagina = 1
        total_paginas = 1
        while pagina <= min(total_paginas, self._max_paginas):
            params = consulta | {"page": str(pagina)}
            # `params=params` se liga como argumento por defecto: sin esto ruff marca B023
            # (función que captura una variable de bucle).
            respuesta = reintentar(
                lambda p=params: cliente.get(
                    f"{_BASE}/vacantes/resultados", params=p
                ).raise_for_status()
            )
            if respuesta is None:
                _log.error("spe: falló la consulta %s en la página %d", consulta, pagina)
                return
            datos = respuesta.json()
            total_paginas = datos.get("totalPages", 1)
            yield from datos.get("resultados", [])
            pagina += 1
            if self._pausa:
                time.sleep(self._pausa)

    def _normalizar(self, bruto: dict, ahora: datetime) -> Oferta | None:
        try:
            codigo = str(bruto["CODIGO_VACANTE"])
            prestador, url = _prestador(bruto)
            if not url:
                _log.debug("spe: vacante %s sin URL de detalle; se omite", codigo)
                return None

            minimo, maximo = _rango_salarial(bruto.get("RANGO_SALARIAL"))
            municipio = (bruto.get("MUNICIPIO") or "").strip()
            departamento = (bruto.get("DEPARTAMENTO") or "").strip()
            return Oferta(
                id=f"spe:{codigo}",
                fuente=self.nombre,
                titulo=bruto["TITULO_VACANTE"],
                empresa=prestador,
                ubicacion=", ".join(p for p in (municipio, departamento) if p) or None,
                pais="CO",
                modalidad=_a_modalidad(bruto.get("TELETRABAJO")),
                url=url,
                descripcion=bruto.get("DESCRIPCION_VACANTE", ""),
                recogida_en=ahora,
                fecha_publicacion=_fecha(bruto.get("FECHA_PUBLICACION")),
                fecha_vencimiento=_fecha(bruto.get("FECHA_VENCIMIENTO")),
                meses_experiencia=_entero(bruto.get("MESES_EXPERIENCIA_CARGO")),
                es_practica=_a_booleano(bruto.get("PLAZA_PRACTICA")),
                salario_min=minimo,
                salario_max=maximo,
                moneda="COP" if minimo or maximo else None,
            )
        except (KeyError, ValueError, TypeError, AttributeError, IndexError) as e:
            _log.warning("spe: oferta descartada por dato inválido: %s", e)
            return None


def _prestador(bruto: dict) -> tuple[str | None, str | None]:
    """Extrae (nombre de la bolsa, URL de la vacante) de `DETALLES_PRESTADOR`.

    `DETALLES_PRESTADOR` es una LISTA de diccionarios, no una cadena. Verificado el
    9/09/2026: las 50 filas de una página traen exactamente un prestador, y las 50
    traen `URL_DETALLE_VACANTE`.

    El SPE no expone el empleador real: `NOMBRE_PRESTADOR` es la bolsa de empleo
    autorizada que publicó la vacante (Magneto, Comfenalco, Computrabajo…). Se usa
    igualmente como `empresa` porque es una entidad real, registrada ante el
    Ministerio, y porque dejarlo en None penalizaría sistemáticamente a la fuente
    más confiable del sistema en el filtro de legitimidad.
    """
    detalles = bruto.get("DETALLES_PRESTADOR")
    if not isinstance(detalles, list) or not detalles:
        return (None, None)
    primero = detalles[0]
    if not isinstance(primero, dict):
        return (None, None)
    nombre = (primero.get("NOMBRE_PRESTADOR") or "").strip() or None
    url = (primero.get("URL_DETALLE_VACANTE") or "").strip() or None
    return (nombre, url)


_VERDADEROS = {"1", "si", "sí", "true", "s", "y"}


def _a_modalidad(valor) -> Modalidad:
    if valor is None:
        return Modalidad.PRESENCIAL
    return Modalidad.REMOTO if str(valor).strip().lower() in _VERDADEROS else Modalidad.PRESENCIAL


def _a_booleano(valor) -> bool:
    return valor is not None and str(valor).strip().lower() in _VERDADEROS


def _entero(valor) -> int | None:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _fecha(valor) -> date | None:
    if not valor:
        return None
    texto = str(valor).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(texto).date()
    except ValueError:
        return None


_NUMERO = re.compile(r"\$?\s*([\d.]{4,})")


def _rango_salarial(texto: str | None) -> tuple[int | None, int | None]:
    """Interpreta los rangos del SPE: '$1.000.001 - $1.500.000', 'Mayor de $15.000.001', 'A Convenir'."""
    if not texto:
        return (None, None)
    numeros = [int(n.replace(".", "")) for n in _NUMERO.findall(texto)]
    if not numeros:
        return (None, None)
    if len(numeros) == 1:
        return (numeros[0], None)
    return (numeros[0], numeros[1])
```

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/test_fuente_spe.py -v`
Expected: PASS — 8 tests

- [ ] **Step 6: Formatear y commitear**

```bash
uv run ruff format . && uv run ruff check --fix .
git add src/ tests/
git commit -m "feat: adaptador del Servicio Público de Empleo"
```

---

### Task 5: Adaptador Magneto365

**Files:**
- Create: `src/boletin_empleos/fuentes/magneto.py`
- Create: `tests/fixtures/magneto_listado.html`
- Create: `tests/test_fuente_magneto.py`

**Interfaces:**
- Consumes: `Oferta`, `Modalidad`, `crear_cliente`, `reintentar`
- Produces: `FuenteMagneto`

**Base de permiso:** Magneto publica `llms.txt` dirigido explícitamente a asistentes de IA, con URLs
canónicas y la instrucción *"Evitar URLs con parámetros"*. Su `robots.txt` confirma `Disallow: /*?`.
**Solo se usan rutas canónicas sin query string.**

- [ ] **Step 1: Descargar la fixture real e inspeccionar la estructura**

```bash
curl -s -A "BoletinEmpleosCUE/1.0 (+https://github.com/Jsua3/proy_social_proyectos; coorproyeccioning@cue.edu.co)" \
  "https://www.magneto365.com/co/trabajos/buscar" \
  -o tests/fixtures/magneto_listado.html
uv run python -c $'
from selectolax.parser import HTMLParser
h = HTMLParser(open("tests/fixtures/magneto_listado.html",encoding="utf-8").read())
tarjetas = [a for a in h.css("article") if a.css_first("a[href*=\\"/co/empleos/\\"]")]
print("tarjetas de vacante:", len(tarjetas))
for c in tarjetas[:3]: print("  ", c.css_first("h2").text(strip=True)[:60])
'
```

Expected: ~20 tarjetas, cada una con su título.

**Estructura verificada el 9/09/2026 — no hace falta investigarla.** Las vacantes de Magneto viven
en `/co/empleos/<slug>`, **no** en `/co/trabajos/` (esa es la ruta del listado, no de la vacante).
Un filtro por `/trabajos/` descartaría el 100 % de las ofertas.

Cada tarjeta es un `<article>` que contiene un enlace a `/co/empleos/` y un `<h2>` con el título:
21 de 21 tarjetas cumplen ambas. El texto de la tarjeta viene segmentado de forma estable como
`título | empresa | tipo de contrato | salario | ubicación | [urgencia]`.

**No uses las clases CSS de Magneto** (`mg_job_card_desktop_magneto-ui-card-jobs_13c81`): llevan
hash de CSS-modules y cambian en cada despliegue suyo.

- [ ] **Step 2: Escribir el test que falla**

```python
# tests/test_fuente_magneto.py
from pathlib import Path

import httpx
import respx

from boletin_empleos.fuentes.magneto import FuenteMagneto

FIXTURE = (Path(__file__).parent / "fixtures" / "magneto_listado.html").read_text("utf-8")


@respx.mock
def test_magneto_extrae_ofertas_del_listado():
    respx.get(url__startswith="https://www.magneto365.com/co/trabajos/").mock(
        return_value=httpx.Response(200, text=FIXTURE)
    )
    ofertas = FuenteMagneto(rutas=["/co/trabajos/buscar"]).obtener()

    assert len(ofertas) >= 15, "la fixture real trae ~20 tarjetas; menos indica selectores rotos"
    o = ofertas[0]
    assert o.fuente == "magneto"
    assert o.pais == "CO"
    assert o.titulo.strip()
    assert str(o.url).startswith("https://www.magneto365.com/co/empleos/")
    assert o.empresa, "la empresa sale del segundo segmento del texto de la tarjeta"


@respx.mock
def test_magneto_una_ruta_caida_no_tumba_las_demas():
    """La ruta de trabajo remoto devuelve HTTP 500 desde el servidor de Magneto."""
    respx.get("https://www.magneto365.com/co/trabajos/rota").mock(
        return_value=httpx.Response(500)
    )
    respx.get("https://www.magneto365.com/co/trabajos/buscar").mock(
        return_value=httpx.Response(200, text=FIXTURE)
    )
    ofertas = FuenteMagneto(rutas=["/co/trabajos/rota", "/co/trabajos/buscar"], pausa=0.0).obtener()
    assert ofertas, "una ruta caída no debe impedir que las demás aporten"


@respx.mock
def test_magneto_nunca_pide_urls_con_parametros():
    """robots.txt de Magneto: Disallow: /*? — y su llms.txt pide evitar parámetros."""
    ruta = respx.get(url__startswith="https://www.magneto365.com/co/trabajos/").mock(
        return_value=httpx.Response(200, text=FIXTURE)
    )
    FuenteMagneto(rutas=["/co/trabajos/ofertas-empleo-trabajo-remoto"]).obtener()

    for llamada in ruta.calls:
        assert not llamada.request.url.query, f"URL con parámetros: {llamada.request.url}"


def test_magneto_declara_su_permiso_y_atribucion():
    f = FuenteMagneto()
    assert f.nombre == "magneto"
    assert "llms.txt" in f.base_permiso
    assert "Magneto" in f.atribucion


@respx.mock
def test_magneto_devuelve_vacio_si_falla():
    respx.get(url__startswith="https://www.magneto365.com/co/trabajos/").mock(
        return_value=httpx.Response(404)
    )
    assert FuenteMagneto(rutas=["/co/trabajos/ofertas-empleo-trabajo-remoto"]).obtener() == []
```

- [ ] **Step 3: Ejecutar y verificar que falla**

Run: `uv run pytest tests/test_fuente_magneto.py -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 4: Implementar el adaptador**

```python
# src/boletin_empleos/fuentes/magneto.py
"""Magneto365 — portal de empleo colombiano.

Base de permiso: Magneto publica un `llms.txt` dirigido explícitamente a
asistentes de IA, con URLs canónicas de alta calidad y la instrucción
"Evitar URLs con parámetros". Su robots.txt lo confirma con `Disallow: /*?`.

Por eso este adaptador solo pide rutas canónicas y jamás añade query string.
"""

import logging
import time
from datetime import UTC, datetime

from selectolax.parser import HTMLParser

from boletin_empleos.http import crear_cliente, reintentar
from boletin_empleos.modelos import Modalidad, Oferta

_log = logging.getLogger(__name__)
_ORIGEN = "https://www.magneto365.com"

# Rutas canónicas del llms.txt de Magneto, VERIFICADAS el 9/09/2026 (todas HTTP 200).
# `/co/trabajos/ofertas-empleo-trabajo-remoto` se excluye a propósito: devuelve HTTP 500
# desde el servidor de Magneto, no por culpa de nuestro agente. Si lo arreglan, se añade.
RUTAS_POR_DEFECTO = [
    "/co/trabajos/buscar",
    "/co/trabajos/ofertas-empleo-en-bogota",
    "/co/trabajos/ofertas-empleo-en-medellin",
    "/co/trabajos/ofertas-empleo-en-pereira",
]

# Selectores verificados contra el HTML real de Magneto el 9/09/2026: cada vacante es un
# <article> que contiene un enlace a /co/empleos/<slug> y un <h2> con el título — 21 de 21
# tarjetas cumplen ambas condiciones. Deliberadamente NO se usan las clases
# `mg_job_card_desktop_magneto-ui-card-jobs_13c81`: llevan hash de CSS-modules y cambian
# en cada despliegue suyo.
_SEL_TARJETA = "article"
_SEL_ENLACE = 'a[href*="/co/empleos/"]'
_SEL_TITULO = "h2"

# El texto de la tarjeta viene segmentado de forma estable:
#   [0] título · [1] empresa · [2] tipo de contrato · [3] salario · [4] ubicación · [5] urgencia
_IDX_EMPRESA = 1
_IDX_UBICACION = 4
_MIN_SEGMENTOS, _MAX_SEGMENTOS = 4, 8


class FuenteMagneto:
    nombre = "magneto"
    base_permiso = (
        "Magneto publica un llms.txt dirigido a asistentes de IA con URLs canónicas; "
        "su robots.txt permite el sitio y prohíbe solo URLs con parámetros."
    )
    atribucion = "Ofertas del portal de empleo Magneto."
    url_atribucion = "https://www.magneto365.com/co"
    confianza_base = 0.80

    def __init__(self, rutas: list[str] | None = None, pausa: float = 1.0) -> None:
        self._rutas = rutas if rutas is not None else RUTAS_POR_DEFECTO
        self._pausa = pausa

    def obtener(self) -> list[Oferta]:
        ahora = datetime.now(UTC)
        vistos: set[str] = set()
        ofertas: list[Oferta] = []

        with crear_cliente(acepta="text/html,application/xhtml+xml") as cliente:
            for ruta in self._rutas:
                if "?" in ruta:
                    raise ValueError(f"Magneto prohíbe URLs con parámetros: {ruta}")
                # `r=ruta` se liga como argumento por defecto: sin esto ruff marca B023
                # (función que captura una variable de bucle).
                respuesta = reintentar(
                    lambda r=ruta: cliente.get(f"{_ORIGEN}{r}").raise_for_status()
                )
                if respuesta is None:
                    _log.error("magneto: no se pudo obtener %s", ruta)
                    continue
                for oferta in self._extraer(respuesta.text, ahora):
                    if oferta.id not in vistos:
                        vistos.add(oferta.id)
                        ofertas.append(oferta)
                if self._pausa:
                    time.sleep(self._pausa)
        return ofertas

    def _extraer(self, html: str, ahora: datetime):
        arbol = HTMLParser(html)
        for tarjeta in arbol.css(_SEL_TARJETA):
            enlace = tarjeta.css_first(_SEL_ENLACE)
            titulo = tarjeta.css_first(_SEL_TITULO)
            if enlace is None or titulo is None:
                continue

            href = enlace.attributes.get("href") or ""
            url = (href if href.startswith("http") else f"{_ORIGEN}{href}").split("?")[0]
            segmentos = _segmentos(tarjeta)
            try:
                yield Oferta(
                    id=f"magneto:{url.rstrip('/').rsplit('/', 1)[-1]}",
                    fuente=self.nombre,
                    titulo=titulo.text(strip=True),
                    empresa=_segmento(segmentos, _IDX_EMPRESA),
                    ubicacion=_segmento(segmentos, _IDX_UBICACION),
                    pais="CO",
                    modalidad=Modalidad.PRESENCIAL,
                    url=url,
                    descripcion=tarjeta.text(separator=" · ", strip=True)[:2000],
                    recogida_en=ahora,
                )
            except ValueError as e:
                _log.warning("magneto: tarjeta descartada: %s", e)


def _segmentos(tarjeta) -> list[str]:
    """Segmentos de texto de la tarjeta, solo si su número es el esperado.

    Una tarjeta con un número anómalo de segmentos no se descarta: conserva título y
    enlace, y deja empresa y ubicación en None. Es preferible una oferta con datos
    incompletos a perder la oferta.
    """
    partes = [p.strip() for p in tarjeta.text(separator="|", strip=True).split("|") if p.strip()]
    return partes if _MIN_SEGMENTOS <= len(partes) <= _MAX_SEGMENTOS else []


def _segmento(segmentos: list[str], indice: int) -> str | None:
    return segmentos[indice] if indice < len(segmentos) else None
```

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/test_fuente_magneto.py -v`
Expected: PASS — 5 tests

Los selectores ya están verificados contra el HTML real, así que esto debería pasar a la primera.
Si `test_magneto_extrae_ofertas_del_listado` falla porque salieron menos de 15 ofertas, significa
que Magneto cambió su marcado desde el 9/09/2026. Diagnostica contando `article`, cuántos tienen
un enlace a `/co/empleos/` y cuántos tienen `<h2>`.

Si el marcado cambió, repórtalo como DONE_WITH_CONCERNS con lo que encontraste: es información que
el controlador necesita, no algo que debas resolver adivinando.

- [ ] **Step 6: Formatear y commitear**

```bash
uv run ruff format . && uv run ruff check --fix .
git add src/ tests/
git commit -m "feat: adaptador Magneto365 sobre rutas canónicas"
```

---

### Task 6: Configuración

**Files:**
- Create: `config.toml`
- Create: `src/boletin_empleos/config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Consumes: nada del proyecto
- Produces: `Config`, `Vocabulario`, `UmbralesLegitimidad`, `cargar_config(ruta) -> Config`

`config.toml` existe para que el vocabulario, los umbrales y las heurísticas antiestafa se ajusten sin
tocar Python (spec §14).

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_config.py
from pathlib import Path

from boletin_empleos.config import cargar_config

RAIZ = Path(__file__).resolve().parents[1]


def test_carga_el_config_del_proyecto():
    cfg = cargar_config(RAIZ / "config.toml")

    assert cfg.destinatarios, "debe haber al menos un destinatario"
    assert cfg.vocabulario.cargos, "el vocabulario de cargos no puede estar vacío"
    assert cfg.vocabulario.tecnologias
    assert 0.0 < cfg.umbral_relevancia <= 1.0
    assert cfg.dias_max_antiguedad > 0
    assert cfg.legitimidad.frases_descarte
    assert cfg.legitimidad.min_caracteres_descripcion == 200


def test_los_terminos_del_vocabulario_estan_normalizados():
    cfg = cargar_config(RAIZ / "config.toml")
    todos = cfg.vocabulario.cargos + cfg.vocabulario.tecnologias
    assert all(t == t.lower().strip() for t in todos), (
        "deben venir en minúscula y sin espacios extra"
    )
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'boletin_empleos.config'`

- [ ] **Step 3: Crear `config.toml`**

```toml
# Configuración del boletín de empleos.
# Se puede ajustar sin tocar código Python.

destinatarios = ["coorproyeccioning@cue.edu.co"]
remitente = "coorproyeccioning@cue.edu.co"
asunto = "Boletín de empleos — Ingeniería de Software"

umbral_relevancia = 0.35
dias_max_antiguedad = 30
max_meses_experiencia = 60      # 5 años: por encima se considera senior
excluir_practicas = true        # la audiencia son egresados, no practicantes

[vocabulario]
cargos = [
  "desarrollador", "developer", "programador", "ingeniero de software",
  "ingeniero de sistemas", "analista de sistemas", "analista de desarrollo",
  "backend", "back end", "frontend", "front end", "full stack", "fullstack",
  "qa", "tester", "automatizacion de pruebas", "devops", "sre",
  "ingeniero de datos", "data engineer", "desarrollador movil", "android", "ios",
  "arquitecto de software", "soporte de aplicaciones",
]
tecnologias = [
  "java", "python", "javascript", "typescript", "react", "angular", "vue",
  "node", ".net", "c#", "php", "spring", "django", "laravel", "flutter",
  "sql", "postgresql", "mysql", "mongodb", "docker", "kubernetes",
  "aws", "azure", "git", "api rest", "microservicios",
]
# Términos que descalifican aunque haya coincidencias tecnológicas.
excluidos = [
  "vendedor", "asesor comercial", "call center", "domiciliario",
  "auxiliar de bodega", "mesero", "vigilante", "conductor",
]

[experiencia]
# Descartan por exigir un nivel de experiencia demasiado alto.
# Son datos, no simbolos: coinciden con el texto real de las ofertas.
terminos_excluidos = [
  "senior", "sr.", "lead", "lider tecnico", "líder técnico", "arquitecto jefe",
  "jefe de", "gerente", "director", "head of", "principal", "staff engineer",
  "coordinador de desarrollo",
]

[legitimidad]
min_caracteres_descripcion = 200
salario_minimo_legal = 1_623_500          # SMLV Colombia 2026
salario_maximo_razonable = 25_000_000     # tope para perfil junior/semi-senior

# Descarte inmediato.
frases_descarte = [
  "inversion inicial", "inversión inicial", "pago de inscripcion",
  "pago de inscripción", "debes pagar", "kit de trabajo", "compra tu kit",
  "pago de tramites", "pago de trámites", "curso obligatorio con costo",
]
# Penalización fuerte.
frases_sospechosas = [
  "altos ingresos", "ingresos ilimitados", "gana desde casa",
  "sin experiencia gana", "cupos limitados", "ganancias inmediatas",
  "independencia financiera", "solo por whatsapp", "escribe al whatsapp",
]
dominios_sospechosos = ["bit.ly", "tinyurl.com", "cutt.ly", "acortar.link", "t.me"]
```

- [ ] **Step 4: Implementar `config.py`**

```python
# src/boletin_empleos/config.py
"""Carga de la configuración. Todo lo ajustable vive en config.toml."""

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field


class Vocabulario(BaseModel):
    cargos: list[str] = Field(default_factory=list)
    tecnologias: list[str] = Field(default_factory=list)
    excluidos: list[str] = Field(default_factory=list)


class ConfigExperiencia(BaseModel):
    terminos_excluidos: list[str] = Field(default_factory=list)


class UmbralesLegitimidad(BaseModel):
    min_caracteres_descripcion: int = 200
    salario_minimo_legal: int = 1_623_500
    salario_maximo_razonable: int = 25_000_000
    frases_descarte: list[str] = Field(default_factory=list)
    frases_sospechosas: list[str] = Field(default_factory=list)
    dominios_sospechosos: list[str] = Field(default_factory=list)


class Config(BaseModel):
    destinatarios: list[str]
    remitente: str
    asunto: str
    umbral_relevancia: float = Field(gt=0.0, le=1.0)
    dias_max_antiguedad: int = Field(gt=0)
    max_meses_experiencia: int = 60
    excluir_practicas: bool = True
    vocabulario: Vocabulario = Field(default_factory=Vocabulario)
    experiencia: ConfigExperiencia = Field(default_factory=ConfigExperiencia)
    legitimidad: UmbralesLegitimidad = Field(default_factory=UmbralesLegitimidad)


def cargar_config(ruta: Path) -> Config:
    with ruta.open("rb") as f:
        return Config(**tomllib.load(f))
```

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS — 2 tests

- [ ] **Step 6: Formatear y commitear**

```bash
uv run ruff format . && uv run ruff check --fix .
git add config.toml src/ tests/
git commit -m "feat: configuración externa en config.toml"
```

---

### Task 7: Núcleo — relevancia, nivel de experiencia y vigencia

**Files:**
- Create: `src/boletin_empleos/nucleo/__init__.py`
- Create: `src/boletin_empleos/nucleo/relevancia.py`
- Create: `src/boletin_empleos/nucleo/experiencia.py`
- Create: `src/boletin_empleos/nucleo/vigencia.py`
- Create: `tests/test_nucleo_filtros.py`

**Interfaces:**
- Consumes: `Oferta`, `Vocabulario`, `ConfigExperiencia`
- Produces:
  - `puntuar_relevancia(oferta: Oferta, vocabulario: Vocabulario) -> float`
  - `experiencia_apropiada(oferta: Oferta, cfg: ConfigExperiencia, max_meses: int) -> tuple[bool, str]`
  - `esta_vigente(oferta: Oferta, hoy: date, dias_max: int) -> tuple[bool, str]`
  - `normalizar_texto(texto: str) -> str`

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_nucleo_filtros.py
from datetime import UTC, date, datetime

from boletin_empleos.config import ConfigExperiencia, Vocabulario
from boletin_empleos.modelos import Modalidad, Oferta
from boletin_empleos.nucleo.relevancia import normalizar_texto, puntuar_relevancia
from boletin_empleos.nucleo.experiencia import experiencia_apropiada
from boletin_empleos.nucleo.vigencia import esta_vigente

VOCAB = Vocabulario(
    cargos=["desarrollador", "ingeniero de software", "backend"],
    tecnologias=["python", "java", "react"],
    excluidos=["asesor comercial", "call center"],
)
HOY = date(2026, 9, 9)


def _oferta(titulo: str, descripcion: str = "", **extra) -> Oferta:
    base = dict(
        id="x:1",
        fuente="x",
        titulo=titulo,
        modalidad=Modalidad.REMOTO,
        url="https://ejemplo.co/1",
        descripcion=descripcion,
        recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
    )
    return Oferta(**(base | extra))


def test_normalizar_texto_quita_tildes_y_baja_a_minuscula():
    assert normalizar_texto("Ingeniería de SOFTWARE") == "ingenieria de software"


def test_relevancia_alta_cuando_el_cargo_esta_en_el_titulo():
    o = _oferta("Desarrollador Backend", "Se requiere experiencia en Python y React.")
    assert puntuar_relevancia(o, VOCAB) > 0.6


def test_relevancia_baja_para_oferta_no_tecnica():
    o = _oferta("Auxiliar de enfermería", "Atención a pacientes en Armenia.")
    assert puntuar_relevancia(o, VOCAB) < 0.2


def test_termino_excluido_anula_la_relevancia():
    o = _oferta("Asesor Comercial", "Manejo de Python para reportes internos.")
    assert puntuar_relevancia(o, VOCAB) == 0.0


def test_el_titulo_pesa_mas_que_la_descripcion():
    en_titulo = _oferta("Desarrollador", "Sin más detalles.")
    en_descripcion = _oferta("Profesional TI", "Buscamos un desarrollador para el equipo.")
    assert puntuar_relevancia(en_titulo, VOCAB) > puntuar_relevancia(en_descripcion, VOCAB)


CFG_EXPERIENCIA = ConfigExperiencia(terminos_excluidos=["senior", "lead", "jefe de"])


def test_experiencia_rechaza_cargos_senior():
    ok, motivo = experiencia_apropiada(_oferta("Senior Backend Developer"), CFG_EXPERIENCIA, 60)
    assert ok is False
    assert "senior" in motivo


def test_experiencia_rechaza_por_exceso():
    ok, motivo = experiencia_apropiada(
        _oferta("Desarrollador", meses_experiencia=84), CFG_EXPERIENCIA, 60
    )
    assert ok is False
    assert "84" in motivo


def test_experiencia_acepta_junior():
    ok, motivo = experiencia_apropiada(
        _oferta("Desarrollador Junior", meses_experiencia=12), CFG_EXPERIENCIA, 60
    )
    assert ok is True
    assert motivo == ""


def test_vigencia_usa_la_fecha_de_vencimiento_cuando_existe():
    vencida = _oferta("Dev", fecha_vencimiento=date(2026, 9, 1))
    viva = _oferta("Dev", fecha_vencimiento=date(2026, 10, 1))
    assert esta_vigente(vencida, HOY, 30)[0] is False
    assert esta_vigente(viva, HOY, 30)[0] is True


def test_vigencia_usa_la_antiguedad_si_no_hay_vencimiento():
    vieja = _oferta("Dev", fecha_publicacion=date(2026, 7, 1))
    reciente = _oferta("Dev", fecha_publicacion=date(2026, 9, 5))
    assert esta_vigente(vieja, HOY, 30)[0] is False
    assert esta_vigente(reciente, HOY, 30)[0] is True


def test_vigencia_acepta_cuando_no_hay_ninguna_fecha():
    """Sin información no se castiga: el enlace se verificará después."""
    assert esta_vigente(_oferta("Dev"), HOY, 30)[0] is True
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/test_nucleo_filtros.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'boletin_empleos.nucleo'`

- [ ] **Step 3: Implementar relevancia**

```python
# src/boletin_empleos/nucleo/__init__.py
```

```python
# src/boletin_empleos/nucleo/relevancia.py
"""Puntuación de relevancia. Lógica pura: sin red, sin disco."""

import unicodedata

from boletin_empleos.config import Vocabulario
from boletin_empleos.modelos import Oferta

_PESO_TITULO = 0.7
_PESO_DESCRIPCION = 0.3


def normalizar_texto(texto: str) -> str:
    """Minúscula y sin tildes, para comparar de forma estable en español."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().split())


def puntuar_relevancia(oferta: Oferta, vocabulario: Vocabulario) -> float:
    """Devuelve 0.0–1.0. Un término excluido anula la oferta por completo."""
    titulo = normalizar_texto(oferta.titulo)
    descripcion = normalizar_texto(oferta.descripcion)
    completo = f"{titulo} {descripcion}"

    if any(normalizar_texto(e) in completo for e in vocabulario.excluidos):
        return 0.0

    terminos = [normalizar_texto(t) for t in vocabulario.cargos + vocabulario.tecnologias]
    if not terminos:
        return 0.0

    en_titulo = sum(1 for t in terminos if t in titulo)
    en_descripcion = sum(1 for t in terminos if t in descripcion)

    puntaje = _PESO_TITULO * _saturar(en_titulo) + _PESO_DESCRIPCION * _saturar(en_descripcion)
    return round(min(puntaje, 1.0), 4)


def _saturar(coincidencias: int) -> float:
    """1 coincidencia ya vale mucho; más coincidencias suman con rendimiento decreciente."""
    if coincidencias <= 0:
        return 0.0
    return min(1.0, 0.6 + 0.2 * (coincidencias - 1))
```

- [ ] **Step 4: Implementar experiencia y vigencia**

```python
# src/boletin_empleos/nucleo/experiencia.py
"""Filtro de nivel de experiencia: junior a semi-senior. Lógica pura."""

from boletin_empleos.config import ConfigExperiencia
from boletin_empleos.modelos import Oferta
from boletin_empleos.nucleo.relevancia import normalizar_texto


def experiencia_apropiada(oferta: Oferta, cfg: ConfigExperiencia, max_meses: int) -> tuple[bool, str]:
    """Devuelve (apropiado, motivo). El motivo va vacío cuando la oferta pasa."""
    titulo = normalizar_texto(oferta.titulo)
    for termino in cfg.terminos_excluidos:
        if normalizar_texto(termino) in titulo:
            return (False, f"el título indica un nivel de experiencia alto: '{termino}'")

    if oferta.meses_experiencia is not None and oferta.meses_experiencia > max_meses:
        return (
            False,
            f"exige {oferta.meses_experiencia} meses de experiencia (máximo {max_meses})",
        )

    return (True, "")
```

```python
# src/boletin_empleos/nucleo/vigencia.py
"""Filtro de vigencia. Crítico por la periodicidad quincenal. Lógica pura."""

from datetime import date

from boletin_empleos.modelos import Oferta


def esta_vigente(oferta: Oferta, hoy: date, dias_max: int) -> tuple[bool, str]:
    """La fecha de vencimiento declarada manda sobre la antigüedad estimada.

    Sin ninguna fecha no se castiga la oferta: la verificación del enlace,
    que ocurre después y sí hace red, se encargará de descartarla si murió.
    """
    if oferta.fecha_vencimiento is not None:
        if oferta.fecha_vencimiento < hoy:
            return (False, f"venció el {oferta.fecha_vencimiento.isoformat()}")
        return (True, "")

    if oferta.fecha_publicacion is not None:
        antiguedad = (hoy - oferta.fecha_publicacion).days
        if antiguedad > dias_max:
            return (False, f"publicada hace {antiguedad} días (máximo {dias_max})")
        return (True, "")

    return (True, "")
```

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/test_nucleo_filtros.py -v`
Expected: PASS — 11 tests

- [ ] **Step 6: Formatear y commitear**

```bash
uv run ruff format . && uv run ruff check --fix .
git add src/ tests/
git commit -m "feat: filtros de relevancia, nivel de experiencia y vigencia"
```

---

### Task 8: Núcleo — legitimidad (antiestafa)

**Files:**
- Create: `src/boletin_empleos/nucleo/legitimidad.py`
- Create: `tests/test_nucleo_legitimidad.py`

**Interfaces:**
- Consumes: `Oferta`, `UmbralesLegitimidad`, `normalizar_texto`
- Produces: `puntuar_legitimidad(oferta, confianza_base, cfg) -> tuple[float, list[str]]`

**Nota para quien revise:** estas heurísticas se escribieron sin conocimiento del mercado local. La
coordinación debe revisarlas (spec §8.4). Viven en `config.toml` para poder ajustarlas sin tocar código.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_nucleo_legitimidad.py
from datetime import UTC, datetime

from boletin_empleos.config import UmbralesLegitimidad
from boletin_empleos.modelos import Modalidad, Oferta
from boletin_empleos.nucleo.legitimidad import puntuar_legitimidad

CFG = UmbralesLegitimidad(
    min_caracteres_descripcion=200,
    salario_minimo_legal=1_623_500,
    salario_maximo_razonable=25_000_000,
    frases_descarte=["inversion inicial", "kit de trabajo"],
    frases_sospechosas=["altos ingresos", "gana desde casa", "escribe al whatsapp"],
    dominios_sospechosos=["bit.ly", "t.me"],
)
DESC_LARGA = "Buscamos desarrollador para nuestro equipo. " * 10


def _oferta(**extra) -> Oferta:
    base = dict(
        id="x:1",
        fuente="x",
        titulo="Desarrollador Backend",
        empresa="Acme S.A.S.",
        modalidad=Modalidad.REMOTO,
        url="https://ejemplo.co/1",
        descripcion=DESC_LARGA,
        recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
    )
    return Oferta(**(base | extra))


def test_oferta_limpia_conserva_la_confianza_de_la_fuente():
    puntaje, notas = puntuar_legitimidad(_oferta(), 0.95, CFG)
    assert puntaje == 0.95
    assert notas == []


def test_pedir_dinero_al_aspirante_anula_la_oferta():
    o = _oferta(descripcion=DESC_LARGA + " Se requiere una inversion inicial de $200.000.")
    puntaje, notas = puntuar_legitimidad(o, 0.95, CFG)
    assert puntaje == 0.0
    assert any("inversion inicial" in n for n in notas)


def test_sin_empresa_y_con_contacto_por_mensajeria_anula():
    o = _oferta(empresa=None, descripcion=DESC_LARGA + " Escribe al whatsapp 300 000 0000.")
    puntaje, notas = puntuar_legitimidad(o, 0.95, CFG)
    assert puntaje == 0.0
    assert any("sin empresa" in n.lower() for n in notas)


def test_frases_sospechosas_penalizan_sin_anular():
    o = _oferta(descripcion=DESC_LARGA + " Altos ingresos garantizados.")
    puntaje, notas = puntuar_legitimidad(o, 0.95, CFG)
    assert 0.0 < puntaje < 0.95
    assert notas


def test_dominio_acortado_penaliza_fuerte():
    o = _oferta(url="https://bit.ly/vacante123")
    puntaje, notas = puntuar_legitimidad(o, 0.95, CFG)
    assert puntaje < 0.6
    assert any("bit.ly" in n for n in notas)


def test_salario_fuera_de_rango_penaliza():
    alto = _oferta(salario_min=80_000_000, moneda="COP")
    bajo = _oferta(salario_max=500_000, moneda="COP")
    assert puntuar_legitimidad(alto, 0.95, CFG)[0] < 0.95
    assert puntuar_legitimidad(bajo, 0.95, CFG)[0] < 0.95


def test_solo_penaliza_salario_en_pesos_colombianos():
    """Un salario en USD es normal para remoto internacional y no debe penalizarse."""
    o = _oferta(salario_min=90_000, moneda="USD")
    assert puntuar_legitimidad(o, 0.75, CFG)[0] == 0.75


def test_descripcion_muy_corta_penaliza_levemente():
    o = _oferta(descripcion="Se busca dev.")
    puntaje, notas = puntuar_legitimidad(o, 0.95, CFG)
    assert 0.7 < puntaje < 0.95
    assert any("descripción" in n for n in notas)


def test_el_puntaje_nunca_sale_del_rango():
    o = _oferta(
        empresa=None,
        url="https://t.me/canal",
        salario_min=99_000_000,
        moneda="COP",
        descripcion="corta",
    )
    puntaje, _ = puntuar_legitimidad(o, 0.70, CFG)
    assert 0.0 <= puntaje <= 1.0
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/test_nucleo_legitimidad.py -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 3: Implementar legitimidad**

```python
# src/boletin_empleos/nucleo/legitimidad.py
"""Heurísticas antiestafa. Lógica pura.

Parten de la confianza base de la fuente y restan según señales observadas.
Todas las listas de frases y dominios viven en config.toml para poder
ajustarlas sin tocar código (spec §8.4).
"""

from boletin_empleos.config import UmbralesLegitimidad
from boletin_empleos.modelos import Oferta
from boletin_empleos.nucleo.relevancia import normalizar_texto

_PENALIZACION_FUERTE = 0.40
_PENALIZACION_MEDIA = 0.25
_PENALIZACION_LEVE = 0.10

_MENSAJERIA = ("whatsapp", "telegram", "wasap", "wpp")


def puntuar_legitimidad(
    oferta: Oferta, confianza_base: float, cfg: UmbralesLegitimidad
) -> tuple[float, list[str]]:
    """Devuelve (puntaje 0.0–1.0, notas). 0.0 significa descarte inmediato."""
    texto = normalizar_texto(f"{oferta.titulo} {oferta.descripcion}")
    url = str(oferta.url).lower()
    notas: list[str] = []

    # --- Señales de descarte inmediato ---
    for frase in cfg.frases_descarte:
        if normalizar_texto(frase) in texto:
            return (0.0, [f"pide dinero al aspirante: '{frase}'"])

    sin_empresa = not (oferta.empresa or "").strip()
    contacto_mensajeria = any(m in texto for m in _MENSAJERIA)
    if sin_empresa and contacto_mensajeria:
        return (0.0, ["sin empresa identificada y con contacto por mensajería personal"])

    # --- Penalizaciones ---
    puntaje = confianza_base

    if contacto_mensajeria:
        puntaje -= _PENALIZACION_FUERTE
        notas.append("el contacto es por mensajería personal")

    for dominio in cfg.dominios_sospechosos:
        if dominio.lower() in url:
            puntaje -= _PENALIZACION_FUERTE
            notas.append(f"enlace hacia dominio sospechoso: {dominio}")
            break

    for frase in cfg.frases_sospechosas:
        if normalizar_texto(frase) in texto:
            puntaje -= _PENALIZACION_MEDIA
            notas.append(f"frase de captación: '{frase}'")
            break

    if sin_empresa:
        puntaje -= _PENALIZACION_MEDIA
        notas.append("sin empresa identificada")

    if _salario_fuera_de_rango(oferta, cfg):
        puntaje -= _PENALIZACION_MEDIA
        notas.append("salario fuera del rango razonable para el perfil")

    if len(oferta.descripcion.strip()) < cfg.min_caracteres_descripcion:
        puntaje -= _PENALIZACION_LEVE
        notas.append("descripción demasiado breve")

    return (round(max(0.0, min(1.0, puntaje)), 4), notas)


def _salario_fuera_de_rango(oferta: Oferta, cfg: UmbralesLegitimidad) -> bool:
    """Solo se evalúa en pesos colombianos: un salario en USD es normal en remoto."""
    if oferta.moneda != "COP":
        return False
    if oferta.salario_min is not None and oferta.salario_min > cfg.salario_maximo_razonable:
        return True
    if oferta.salario_max is not None and 0 < oferta.salario_max < cfg.salario_minimo_legal:
        return True
    return False
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/test_nucleo_legitimidad.py -v`
Expected: PASS — 9 tests

- [ ] **Step 5: Formatear y commitear**

```bash
uv run ruff format . && uv run ruff check --fix .
git add src/ tests/
git commit -m "feat: heurísticas antiestafa"
```

---

### Task 9: Núcleo — deduplicación y pipeline de evaluación

**Files:**
- Create: `src/boletin_empleos/nucleo/deduplicacion.py`
- Create: `src/boletin_empleos/nucleo/pipeline.py`
- Create: `tests/test_nucleo_pipeline.py`
- Create: `tests/test_nucleo_es_puro.py`

**Interfaces:**
- Consumes: todo lo anterior del núcleo, `Config`, `Evaluacion`, `Decision`, `MotivoDescarte`
- Produces:
  - `clave_dedup(oferta: Oferta) -> str`
  - `deduplicar(ofertas, confianza_por_fuente) -> tuple[list[Oferta], list[Oferta]]`
  - `ResultadoEvaluacion` con campos `incluidas: list[Evaluacion]`, `descartadas: list[Evaluacion]`, `conteos: dict[str, int]`
  - `evaluar(ofertas, ya_enviadas, cfg, confianza_por_fuente, hoy) -> ResultadoEvaluacion`

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_nucleo_pipeline.py
from datetime import UTC, date, datetime

from boletin_empleos.config import (
    Config,
    ConfigExperiencia,
    UmbralesLegitimidad,
    Vocabulario,
)
from boletin_empleos.modelos import Decision, Modalidad, MotivoDescarte, Oferta
from boletin_empleos.nucleo.deduplicacion import clave_dedup, deduplicar
from boletin_empleos.nucleo.pipeline import evaluar

HOY = date(2026, 9, 9)
CONFIANZA = {"spe": 0.95, "magneto": 0.80, "remoteok": 0.70}

CFG = Config(
    destinatarios=["a@b.co"],
    remitente="a@b.co",
    asunto="Boletín",
    umbral_relevancia=0.35,
    dias_max_antiguedad=30,
    max_meses_experiencia=60,
    excluir_practicas=True,
    vocabulario=Vocabulario(
        cargos=["desarrollador", "backend"],
        tecnologias=["python"],
        excluidos=["call center"],
    ),
    experiencia=ConfigExperiencia(terminos_excluidos=["senior"]),
    legitimidad=UmbralesLegitimidad(
        min_caracteres_descripcion=10,
        frases_descarte=["inversion inicial"],
        frases_sospechosas=[],
        dominios_sospechosos=[],
    ),
)
DESC = "Buscamos desarrollador con Python para nuestro equipo de tecnología."


def _oferta(id_: str, fuente: str, titulo: str, **extra) -> Oferta:
    base = dict(
        id=id_,
        fuente=fuente,
        titulo=titulo,
        empresa="Acme S.A.S.",
        ubicacion="Armenia, Quindío",
        modalidad=Modalidad.PRESENCIAL,
        url=f"https://ejemplo.co/{id_}",
        descripcion=DESC,
        recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
    )
    return Oferta(**(base | extra))


def test_clave_dedup_ignora_mayusculas_tildes_y_fuente():
    a = _oferta("spe:1", "spe", "Desarrollador Backend")
    b = _oferta("magneto:9", "magneto", "  desarrollador  backend ")
    assert clave_dedup(a) == clave_dedup(b)


def test_deduplicar_conserva_la_fuente_mas_confiable():
    a = _oferta("magneto:9", "magneto", "Desarrollador Backend")
    b = _oferta("spe:1", "spe", "Desarrollador Backend")
    unicas, duplicadas = deduplicar([a, b], CONFIANZA)
    assert len(unicas) == 1
    assert unicas[0].fuente == "spe"
    assert [d.fuente for d in duplicadas] == ["magneto"]


def test_evaluar_incluye_una_oferta_pertinente():
    r = evaluar([_oferta("spe:1", "spe", "Desarrollador Backend")], set(), CFG, CONFIANZA, HOY)
    assert len(r.incluidas) == 1
    assert r.incluidas[0].decision is Decision.INCLUIR
    assert r.descartadas == []


def test_evaluar_descarta_por_relevancia():
    o = _oferta("spe:2", "spe", "Agente de Call Center", descripcion="Atención telefónica.")
    r = evaluar([o], set(), CFG, CONFIANZA, HOY)
    assert r.incluidas == []
    assert r.descartadas[0].motivo is MotivoDescarte.RELEVANCIA


def test_evaluar_descarta_por_experiencia():
    r = evaluar(
        [_oferta("spe:3", "spe", "Senior Desarrollador Backend")], set(), CFG, CONFIANZA, HOY
    )
    assert r.descartadas[0].motivo is MotivoDescarte.EXPERIENCIA


def test_evaluar_descarta_practicas_porque_la_audiencia_son_egresados():
    o = _oferta("spe:4", "spe", "Desarrollador Backend", es_practica=True)
    r = evaluar([o], set(), CFG, CONFIANZA, HOY)
    assert r.descartadas[0].motivo is MotivoDescarte.ES_PRACTICA


def test_evaluar_descarta_por_legitimidad():
    o = _oferta("spe:5", "spe", "Desarrollador Backend", descripcion=DESC + " Inversion inicial.")
    r = evaluar([o], set(), CFG, CONFIANZA, HOY)
    assert r.descartadas[0].motivo is MotivoDescarte.LEGITIMIDAD
    assert r.descartadas[0].notas


def test_evaluar_omite_lo_ya_enviado_en_ediciones_anteriores():
    o = _oferta("spe:6", "spe", "Desarrollador Backend")
    r = evaluar([o], {"spe:6"}, CFG, CONFIANZA, HOY)
    assert r.incluidas == []
    assert r.conteos["ya_enviadas"] == 1


def test_los_conteos_cuadran_con_lo_procesado():
    ofertas = [
        _oferta("spe:1", "spe", "Desarrollador Backend"),
        _oferta("spe:2", "spe", "Agente de Call Center", descripcion="Atención telefónica."),
        _oferta("spe:3", "spe", "Senior Desarrollador Backend"),
    ]
    r = evaluar(ofertas, set(), CFG, CONFIANZA, HOY)
    assert r.conteos["recibidas"] == 3
    assert r.conteos["incluidas"] == len(r.incluidas)
```

```python
# tests/test_nucleo_es_puro.py
"""El núcleo no puede hacer E/S. Es la invariante que lo mantiene testeable."""

from pathlib import Path

PROHIBIDOS = ("httpx", "requests", "smtplib", "urllib", "socket", "sqlite3", "open(")
NUCLEO = Path(__file__).resolve().parents[1] / "src" / "boletin_empleos" / "nucleo"


def test_el_nucleo_no_importa_nada_de_entrada_salida():
    infracciones = []
    for archivo in NUCLEO.glob("*.py"):
        texto = archivo.read_text("utf-8")
        for prohibido in PROHIBIDOS:
            if prohibido in texto:
                infracciones.append(f"{archivo.name}: {prohibido}")
    assert not infracciones, f"el núcleo debe ser puro, pero encontré: {infracciones}"
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/test_nucleo_pipeline.py tests/test_nucleo_es_puro.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'boletin_empleos.nucleo.deduplicacion'`

- [ ] **Step 3: Implementar deduplicación**

```python
# src/boletin_empleos/nucleo/deduplicacion.py
"""Deduplicación entre fuentes. Lógica pura.

La misma vacante suele publicarse en varias bolsas. Se conserva la de la
fuente más confiable. Deduplicar NO es descartar: la oferta sí entra al
boletín, una sola vez (spec §8.6).
"""

from boletin_empleos.modelos import Oferta
from boletin_empleos.nucleo.relevancia import normalizar_texto


def clave_dedup(oferta: Oferta) -> str:
    """Clave estable e independiente de la fuente."""
    empresa = normalizar_texto(oferta.empresa or "")
    titulo = normalizar_texto(oferta.titulo)
    ubicacion = normalizar_texto(oferta.ubicacion or "")
    return f"{empresa}|{titulo}|{ubicacion}"


def deduplicar(
    ofertas: list[Oferta], confianza_por_fuente: dict[str, float]
) -> tuple[list[Oferta], list[Oferta]]:
    """Devuelve (únicas, duplicadas). Gana la oferta de la fuente más confiable."""
    mejor: dict[str, Oferta] = {}
    duplicadas: list[Oferta] = []

    for oferta in ofertas:
        clave = clave_dedup(oferta)
        actual = mejor.get(clave)
        if actual is None:
            mejor[clave] = oferta
            continue
        if confianza_por_fuente.get(oferta.fuente, 0.0) > confianza_por_fuente.get(
            actual.fuente, 0.0
        ):
            mejor[clave] = oferta
            duplicadas.append(actual)
        else:
            duplicadas.append(oferta)

    return (list(mejor.values()), duplicadas)
```

- [ ] **Step 4: Implementar el pipeline**

```python
# src/boletin_empleos/nucleo/pipeline.py
"""Orquestación del núcleo. Lógica pura: sin red, sin disco, sin reloj propio.

`hoy` se recibe por parámetro justamente para que las pruebas sean deterministas.
"""

from datetime import date

from pydantic import BaseModel, Field

from boletin_empleos.config import Config
from boletin_empleos.modelos import Decision, Evaluacion, MotivoDescarte, Oferta
from boletin_empleos.nucleo.deduplicacion import deduplicar
from boletin_empleos.nucleo.legitimidad import puntuar_legitimidad
from boletin_empleos.nucleo.relevancia import puntuar_relevancia
from boletin_empleos.nucleo.experiencia import experiencia_apropiada
from boletin_empleos.nucleo.vigencia import esta_vigente

_UMBRAL_LEGITIMIDAD = 0.45


class ResultadoEvaluacion(BaseModel):
    incluidas: list[Evaluacion] = Field(default_factory=list)
    descartadas: list[Evaluacion] = Field(default_factory=list)
    conteos: dict[str, int] = Field(default_factory=dict)


def evaluar(
    ofertas: list[Oferta],
    ya_enviadas: set[str],
    cfg: Config,
    confianza_por_fuente: dict[str, float],
    hoy: date,
) -> ResultadoEvaluacion:
    conteos = {
        "recibidas": len(ofertas),
        "ya_enviadas": 0,
        "duplicadas": 0,
        "descartadas_relevancia": 0,
        "descartadas_experiencia": 0,
        "descartadas_vigencia": 0,
        "descartadas_legitimidad": 0,
        "descartadas_practica": 0,
        "incluidas": 0,
    }

    nuevas = [o for o in ofertas if o.id not in ya_enviadas]
    conteos["ya_enviadas"] = len(ofertas) - len(nuevas)

    unicas, duplicadas = deduplicar(nuevas, confianza_por_fuente)
    conteos["duplicadas"] = len(duplicadas)

    incluidas: list[Evaluacion] = []
    descartadas: list[Evaluacion] = []

    for oferta in unicas:
        relevancia = puntuar_relevancia(oferta, cfg.vocabulario)
        confianza = confianza_por_fuente.get(oferta.fuente, 0.5)
        legitimidad, notas_legitimidad = puntuar_legitimidad(oferta, confianza, cfg.legitimidad)

        def _descartar(
            motivo: MotivoDescarte,
            notas: list[str],
            _o=oferta,
            _r=relevancia,
            _l=legitimidad,
        ) -> None:
            # Los valores del bucle se ligan como argumentos por defecto: sin esto
            # ruff marca B023 (función que captura una variable de bucle).
            descartadas.append(
                Evaluacion(
                    oferta=_o,
                    puntaje_relevancia=_r,
                    puntaje_legitimidad=_l,
                    decision=Decision.DESCARTAR,
                    motivo=motivo,
                    notas=notas,
                )
            )

        if relevancia < cfg.umbral_relevancia:
            conteos["descartadas_relevancia"] += 1
            _descartar(MotivoDescarte.RELEVANCIA, [f"relevancia {relevancia:.2f}"])
            continue

        if cfg.excluir_practicas and oferta.es_practica:
            conteos["descartadas_practica"] += 1
            _descartar(MotivoDescarte.ES_PRACTICA, ["es plaza de práctica, no empleo"])
            continue

        apropiado, motivo_experiencia = experiencia_apropiada(
            oferta, cfg.experiencia, cfg.max_meses_experiencia
        )
        if not apropiado:
            conteos["descartadas_experiencia"] += 1
            _descartar(MotivoDescarte.EXPERIENCIA, [motivo_experiencia])
            continue

        vigente, motivo_vigencia = esta_vigente(oferta, hoy, cfg.dias_max_antiguedad)
        if not vigente:
            conteos["descartadas_vigencia"] += 1
            _descartar(MotivoDescarte.VIGENCIA, [motivo_vigencia])
            continue

        if legitimidad < _UMBRAL_LEGITIMIDAD:
            conteos["descartadas_legitimidad"] += 1
            _descartar(MotivoDescarte.LEGITIMIDAD, notas_legitimidad)
            continue

        incluidas.append(
            Evaluacion(
                oferta=oferta,
                puntaje_relevancia=relevancia,
                puntaje_legitimidad=legitimidad,
                decision=Decision.INCLUIR,
                notas=notas_legitimidad,
            )
        )

    incluidas.sort(key=lambda e: (e.puntaje_relevancia, e.puntaje_legitimidad), reverse=True)
    conteos["incluidas"] = len(incluidas)
    return ResultadoEvaluacion(incluidas=incluidas, descartadas=descartadas, conteos=conteos)
```

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/test_nucleo_pipeline.py tests/test_nucleo_es_puro.py -v`
Expected: PASS — 10 tests

- [ ] **Step 6: Formatear y commitear**

```bash
uv run ruff format . && uv run ruff check --fix .
git add src/ tests/
git commit -m "feat: deduplicación y pipeline de evaluación del núcleo"
```

---

### Task 10: Almacenamiento del historial

**Files:**
- Create: `src/boletin_empleos/almacenamiento/__init__.py`
- Create: `src/boletin_empleos/almacenamiento/base.py`
- Create: `src/boletin_empleos/almacenamiento/json_repo.py`
- Create: `tests/test_almacenamiento.py`

**Interfaces:**
- Consumes: nada del núcleo
- Produces:
  - `Historial` (Protocol) con `ids_enviados() -> set[str]`, `registrar(ids, fecha) -> None`, `numero_edicion() -> int`
  - `HistorialJSON(ruta: Path)`

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_almacenamiento.py
from datetime import date

from boletin_empleos.almacenamiento.json_repo import HistorialJSON


def test_historial_vacio_cuando_el_archivo_no_existe(tmp_path):
    h = HistorialJSON(tmp_path / "historial.json")
    assert h.ids_enviados() == set()
    assert h.numero_edicion() == 1


def test_registrar_persiste_los_ids(tmp_path):
    ruta = tmp_path / "historial.json"
    HistorialJSON(ruta).registrar({"spe:1", "spe:2"}, date(2026, 9, 22))

    recargado = HistorialJSON(ruta)
    assert recargado.ids_enviados() == {"spe:1", "spe:2"}
    assert recargado.numero_edicion() == 2


def test_registrar_acumula_entre_ediciones(tmp_path):
    ruta = tmp_path / "historial.json"
    h = HistorialJSON(ruta)
    h.registrar({"spe:1"}, date(2026, 9, 22))
    HistorialJSON(ruta).registrar({"spe:2"}, date(2026, 10, 6))

    final = HistorialJSON(ruta)
    assert final.ids_enviados() == {"spe:1", "spe:2"}
    assert final.numero_edicion() == 3


def test_el_archivo_es_json_legible_y_ordenado(tmp_path):
    import json

    ruta = tmp_path / "historial.json"
    HistorialJSON(ruta).registrar({"spe:2", "spe:1"}, date(2026, 9, 22))
    datos = json.loads(ruta.read_text("utf-8"))

    assert datos["ediciones"][0]["fecha"] == "2026-09-22"
    assert datos["ediciones"][0]["ids"] == ["spe:1", "spe:2"], "ordenado para diffs limpios en git"


def test_tolera_un_archivo_corrupto(tmp_path):
    ruta = tmp_path / "historial.json"
    ruta.write_text("{ esto no es json", encoding="utf-8")
    assert HistorialJSON(ruta).ids_enviados() == set()
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/test_almacenamiento.py -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 3: Implementar el puerto y el adaptador**

```python
# src/boletin_empleos/almacenamiento/__init__.py
from boletin_empleos.almacenamiento.base import Historial

__all__ = ["Historial"]
```

```python
# src/boletin_empleos/almacenamiento/base.py
"""Puerto de salida: persistencia del historial de envíos."""

from datetime import date
from typing import Protocol


class Historial(Protocol):
    def ids_enviados(self) -> set[str]:
        """IDs de todas las ofertas ya enviadas en cualquier edición previa."""
        ...

    def registrar(self, ids: set[str], fecha: date) -> None:
        """Añade una edición al historial."""
        ...

    def numero_edicion(self) -> int:
        """Número que le corresponde a la próxima edición (la primera es 1)."""
        ...
```

```python
# src/boletin_empleos/almacenamiento/json_repo.py
"""Historial en JSON, commiteado al repositorio.

No se usa la caché de GitHub Actions: se borra a los 7 días sin uso, lo que la
vuelve inservible para un ciclo quincenal (spec §11).

Se escribe ordenado y con indentación para que los diffs en git sean legibles.
"""

import json
import logging
from datetime import date
from pathlib import Path

_log = logging.getLogger(__name__)


class HistorialJSON:
    def __init__(self, ruta: Path) -> None:
        self._ruta = Path(ruta)
        self._datos = self._leer()

    def _leer(self) -> dict:
        if not self._ruta.exists():
            return {"ediciones": []}
        try:
            return json.loads(self._ruta.read_text("utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            _log.error("historial ilegible en %s (%s); se parte de cero", self._ruta, e)
            return {"ediciones": []}

    def ids_enviados(self) -> set[str]:
        return {i for ed in self._datos.get("ediciones", []) for i in ed.get("ids", [])}

    def numero_edicion(self) -> int:
        return len(self._datos.get("ediciones", [])) + 1

    def registrar(self, ids: set[str], fecha: date) -> None:
        self._datos.setdefault("ediciones", []).append(
            {
                "numero": self.numero_edicion(),
                "fecha": fecha.isoformat(),
                "ids": sorted(ids),
            }
        )
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        self._ruta.write_text(
            json.dumps(self._datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/test_almacenamiento.py -v`
Expected: PASS — 5 tests

- [ ] **Step 5: Formatear y commitear**

```bash
uv run ruff format . && uv run ruff check --fix .
git add src/ tests/
git commit -m "feat: historial de envíos en JSON versionado"
```

---

### Task 11: Verificación de enlaces vivos

**Files:**
- Create: `src/boletin_empleos/verificacion.py`
- Create: `tests/test_verificacion.py`

**Interfaces:**
- Consumes: `Evaluacion`
- Produces: `filtrar_enlaces_vivos(evaluaciones) -> tuple[list[Evaluacion], list[Evaluacion]]`

Vive **fuera** del núcleo porque hace red. Se ejecuta solo sobre las ofertas que ya pasaron todos los
demás filtros, así que el costo es bajo (spec §8.3).

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_verificacion.py
from datetime import UTC, datetime

import httpx
import respx

from boletin_empleos.modelos import Decision, Evaluacion, Modalidad, MotivoDescarte, Oferta
from boletin_empleos.verificacion import filtrar_enlaces_vivos


def _evaluacion(url: str) -> Evaluacion:
    return Evaluacion(
        oferta=Oferta(
            id=f"x:{url[-1]}",
            fuente="x",
            titulo="Desarrollador",
            modalidad=Modalidad.REMOTO,
            url=url,
            descripcion="Descripción.",
            recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
        ),
        puntaje_relevancia=0.9,
        puntaje_legitimidad=0.9,
        decision=Decision.INCLUIR,
    )


@respx.mock
def test_separa_enlaces_vivos_de_muertos():
    respx.head("https://ejemplo.co/1").mock(return_value=httpx.Response(200))
    respx.head("https://ejemplo.co/2").mock(return_value=httpx.Response(404))

    vivas, muertas = filtrar_enlaces_vivos(
        [_evaluacion("https://ejemplo.co/1"), _evaluacion("https://ejemplo.co/2")]
    )
    assert [str(e.oferta.url) for e in vivas] == ["https://ejemplo.co/1"]
    assert muertas[0].decision is Decision.DESCARTAR
    assert muertas[0].motivo is MotivoDescarte.ENLACE_MUERTO


@respx.mock
def test_cae_a_get_si_head_no_esta_permitido():
    respx.head("https://ejemplo.co/3").mock(return_value=httpx.Response(405))
    respx.get("https://ejemplo.co/3").mock(return_value=httpx.Response(200))

    vivas, muertas = filtrar_enlaces_vivos([_evaluacion("https://ejemplo.co/3")])
    assert len(vivas) == 1
    assert muertas == []


@respx.mock
def test_un_error_de_red_no_mata_la_oferta():
    """Ante la duda se conserva: es peor perder una vacante buena que mostrar una dudosa."""
    respx.head("https://ejemplo.co/4").mock(side_effect=httpx.ConnectTimeout("timeout"))
    respx.get("https://ejemplo.co/4").mock(side_effect=httpx.ConnectTimeout("timeout"))

    vivas, muertas = filtrar_enlaces_vivos([_evaluacion("https://ejemplo.co/4")])
    assert len(vivas) == 1
    assert muertas == []
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/test_verificacion.py -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 3: Implementar la verificación**

```python
# src/boletin_empleos/verificacion.py
"""Verificación de que los enlaces siguen vivos.

Hace red, por eso vive fuera del núcleo. Se corre solo sobre las ofertas que
ya pasaron los demás filtros: son pocas y el costo es bajo.

Criterio ante error de red: se conserva la oferta. Es peor perder una vacante
buena por un timeout que mostrar una dudosa.
"""

import logging

import httpx

from boletin_empleos.http import crear_cliente
from boletin_empleos.modelos import Decision, Evaluacion, MotivoDescarte

_log = logging.getLogger(__name__)


def filtrar_enlaces_vivos(
    evaluaciones: list[Evaluacion],
) -> tuple[list[Evaluacion], list[Evaluacion]]:
    """Devuelve (con enlace vivo, con enlace muerto)."""
    vivas: list[Evaluacion] = []
    muertas: list[Evaluacion] = []

    with crear_cliente(timeout=15.0) as cliente:
        for evaluacion in evaluaciones:
            if _responde(cliente, str(evaluacion.oferta.url)):
                vivas.append(evaluacion)
            else:
                muertas.append(
                    evaluacion.model_copy(
                        update={
                            "decision": Decision.DESCARTAR,
                            "motivo": MotivoDescarte.ENLACE_MUERTO,
                            "notas": [*evaluacion.notas, "el enlace ya no responde"],
                        }
                    )
                )
    return (vivas, muertas)


def _responde(cliente: httpx.Client, url: str) -> bool:
    for metodo in ("HEAD", "GET"):
        try:
            respuesta = cliente.request(metodo, url)
        except httpx.HTTPError as e:
            _log.warning("no se pudo verificar %s (%s); se conserva por prudencia", url, e)
            return True
        if respuesta.status_code < 400:
            return True
        if respuesta.status_code not in (405, 403):
            return False
    return False
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/test_verificacion.py -v`
Expected: PASS — 3 tests

- [ ] **Step 5: Formatear y commitear**

```bash
uv run ruff format . && uv run ruff check --fix .
git add src/ tests/
git commit -m "feat: verificación de enlaces vivos"
```

---

### Task 12: Enriquecimiento opcional con LLM

**Files:**
- Create: `src/boletin_empleos/enriquecimiento/__init__.py`
- Create: `src/boletin_empleos/enriquecimiento/base.py`
- Create: `src/boletin_empleos/enriquecimiento/nulo.py`
- Create: `src/boletin_empleos/enriquecimiento/anthropic.py`
- Create: `tests/test_enriquecimiento.py`

**Interfaces:**
- Consumes: `Evaluacion`
- Produces:
  - `Enriquecedor` (Protocol) con `resumir(evaluaciones) -> dict[str, str]` y `editorial(evaluaciones, conteos) -> str`
  - `EnriquecedorNulo`, `EnriquecedorAnthropic`, `crear_enriquecedor(api_key: str | None) -> Enriquecedor`

**Invariante:** el LLM **no decide nada**. Relevancia, legitimidad y descarte son siempre determinísticos
(spec §10). Un fallo del proveedor jamás altera qué ofertas entran.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_enriquecimiento.py
from datetime import UTC, datetime

from boletin_empleos.enriquecimiento import crear_enriquecedor
from boletin_empleos.enriquecimiento.nulo import EnriquecedorNulo
from boletin_empleos.modelos import Decision, Evaluacion, Modalidad, Oferta


def _evaluacion() -> Evaluacion:
    return Evaluacion(
        oferta=Oferta(
            id="x:1",
            fuente="x",
            titulo="Desarrollador",
            modalidad=Modalidad.REMOTO,
            url="https://ejemplo.co/1",
            descripcion="Descripción larga de la vacante.",
            recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
        ),
        puntaje_relevancia=0.9,
        puntaje_legitimidad=0.9,
        decision=Decision.INCLUIR,
    )


def test_sin_api_key_se_usa_el_enriquecedor_nulo():
    assert isinstance(crear_enriquecedor(None), EnriquecedorNulo)
    assert isinstance(crear_enriquecedor(""), EnriquecedorNulo)


def test_el_enriquecedor_nulo_no_rompe_nada():
    e = EnriquecedorNulo()
    assert e.resumir([_evaluacion()]) == {}
    assert isinstance(e.editorial([_evaluacion()], {"incluidas": 1}), str)
    assert e.editorial([_evaluacion()], {"incluidas": 1}), "debe dar un texto fijo, no vacío"


def test_anthropic_cae_a_nulo_si_el_proveedor_falla(monkeypatch):
    from boletin_empleos.enriquecimiento.anthropic import EnriquecedorAnthropic

    e = EnriquecedorAnthropic(api_key="clave-falsa")

    def explotar(*args, **kwargs):
        raise RuntimeError("proveedor caído")

    monkeypatch.setattr(e, "_pedir", explotar)

    assert e.resumir([_evaluacion()]) == {}
    assert e.editorial([_evaluacion()], {"incluidas": 1})
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/test_enriquecimiento.py -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 3: Implementar puerto, nulo y fábrica**

```python
# src/boletin_empleos/enriquecimiento/base.py
"""Puerto opcional: prosa generada. Nunca decide qué entra al boletín."""

from typing import Protocol

from boletin_empleos.modelos import Evaluacion


class Enriquecedor(Protocol):
    def resumir(self, evaluaciones: list[Evaluacion]) -> dict[str, str]:
        """Devuelve {id_oferta: resumen de una línea}. Puede devolver {}."""
        ...

    def editorial(self, evaluaciones: list[Evaluacion], conteos: dict[str, int]) -> str:
        """Párrafo de apertura del boletín. Nunca vacío."""
        ...
```

```python
# src/boletin_empleos/enriquecimiento/nulo.py
"""Implementación por defecto: sin LLM. El boletín sale igual, más escueto."""

from boletin_empleos.modelos import Evaluacion

_EDITORIAL_FIJA = (
    "A continuación encontrará las vacantes de desarrollo de software publicadas "
    "durante las últimas dos semanas en fuentes verificadas, filtradas por "
    "pertinencia para egresados del programa."
)


class EnriquecedorNulo:
    def resumir(self, evaluaciones: list[Evaluacion]) -> dict[str, str]:
        return {}

    def editorial(self, evaluaciones: list[Evaluacion], conteos: dict[str, int]) -> str:
        return _EDITORIAL_FIJA
```

```python
# src/boletin_empleos/enriquecimiento/__init__.py
"""Selección automática del enriquecedor según haya o no API key."""

from boletin_empleos.enriquecimiento.base import Enriquecedor
from boletin_empleos.enriquecimiento.nulo import EnriquecedorNulo


def crear_enriquecedor(api_key: str | None) -> Enriquecedor:
    if not api_key:
        return EnriquecedorNulo()
    from boletin_empleos.enriquecimiento.anthropic import EnriquecedorAnthropic

    return EnriquecedorAnthropic(api_key=api_key)


__all__ = ["Enriquecedor", "EnriquecedorNulo", "crear_enriquecedor"]
```

- [ ] **Step 4: Implementar el enriquecedor Anthropic**

Añadir la dependencia: `uv add anthropic`

```python
# src/boletin_empleos/enriquecimiento/anthropic.py
"""Enriquecimiento con Claude. Degradable: ante cualquier fallo cae a nulo.

No decide qué ofertas entran — solo redacta. Es la invariante del spec §10.
"""

import json
import logging

from boletin_empleos.enriquecimiento.nulo import EnriquecedorNulo
from boletin_empleos.modelos import Evaluacion

_log = logging.getLogger(__name__)
_MODELO = "claude-sonnet-5"
_NULO = EnriquecedorNulo()


class EnriquecedorAnthropic:
    def __init__(self, api_key: str, modelo: str = _MODELO) -> None:
        self._api_key = api_key
        self._modelo = modelo

    def _pedir(self, prompt: str, max_tokens: int) -> str:
        from anthropic import Anthropic

        cliente = Anthropic(api_key=self._api_key)
        respuesta = cliente.messages.create(
            model=self._modelo,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return respuesta.content[0].text

    def resumir(self, evaluaciones: list[Evaluacion]) -> dict[str, str]:
        if not evaluaciones:
            return {}
        entradas = [
            {
                "id": e.oferta.id,
                "titulo": e.oferta.titulo,
                "descripcion": e.oferta.descripcion[:800],
            }
            for e in evaluaciones
        ]
        prompt = (
            "Resume cada vacante en UNA sola frase en español, máximo 20 palabras, "
            "enfocada en qué hace la persona y qué tecnologías usa. "
            "Responde SOLO un objeto JSON {id: resumen}, sin texto adicional.\n\n"
            f"{json.dumps(entradas, ensure_ascii=False)}"
        )
        try:
            texto = self._pedir(prompt, max_tokens=2000)
            datos = json.loads(texto[texto.index("{") : texto.rindex("}") + 1])
            return {str(k): str(v) for k, v in datos.items()}
        except Exception as e:
            _log.warning("enriquecimiento: falló el resumen (%s); el boletín sale sin resúmenes", e)
            return {}

    def editorial(self, evaluaciones: list[Evaluacion], conteos: dict[str, int]) -> str:
        prompt = (
            "Escribe un párrafo de apertura para un boletín quincenal de empleos dirigido a "
            "egresados de Ingeniería de Software de una universidad en Armenia, Quindío, Colombia. "
            "Máximo 60 palabras, tono institucional y sobrio, sin saludos ni despedidas. "
            f"Esta edición trae {conteos.get('incluidas', 0)} vacantes. "
            "Títulos incluidos: "
            f"{[e.oferta.titulo for e in evaluaciones[:10]]}"
        )
        try:
            return self._pedir(prompt, max_tokens=300).strip()
        except Exception as e:
            _log.warning("enriquecimiento: falló el editorial (%s); se usa el texto fijo", e)
            return _NULO.editorial(evaluaciones, conteos)
```

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/test_enriquecimiento.py -v`
Expected: PASS — 3 tests

- [ ] **Step 6: Formatear y commitear**

```bash
uv run ruff format . && uv run ruff check --fix .
git add pyproject.toml uv.lock src/ tests/
git commit -m "feat: enriquecimiento opcional con LLM, degradable a nulo"
```

---

### Task 13: Render del boletín en MJML

**Files:**
- Create: `src/boletin_empleos/render/__init__.py`
- Create: `src/boletin_empleos/render/plantillas/boletin.mjml`
- Create: `src/boletin_empleos/render/renderizador.py`
- Create: `tests/test_render.py`

**Interfaces:**
- Consumes: `Evaluacion`, `FuenteEmpleo`
- Produces: `DatosBoletin` (BaseModel) y `renderizar(datos: DatosBoletin) -> str`

**Regla crítica:** el pie de atribución se construye recorriendo las fuentes que aportaron ofertas.
Nunca se escribe a mano. Remotive y RemoteOK cortan el acceso si no se les cita (spec §9).

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_render.py
from datetime import UTC, date, datetime

from boletin_empleos.modelos import Decision, Evaluacion, Modalidad, MotivoDescarte, Oferta
from boletin_empleos.render.renderizador import DatosBoletin, FuenteUsada, renderizar


def _evaluacion(
    titulo: str,
    modalidad: Modalidad,
    pais: str | None,
    decision=Decision.INCLUIR,
    motivo=None,
    notas=None,
) -> Evaluacion:
    return Evaluacion(
        oferta=Oferta(
            id=f"x:{titulo}",
            fuente="spe",
            titulo=titulo,
            empresa="Acme S.A.S.",
            ubicacion="Armenia, Quindío",
            pais=pais,
            modalidad=modalidad,
            url="https://ejemplo.co/1",
            descripcion="Descripción.",
            recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
        ),
        puntaje_relevancia=0.9,
        puntaje_legitimidad=0.9,
        decision=decision,
        motivo=motivo,
        notas=notas or [],
    )


def _datos(**extra) -> DatosBoletin:
    base = dict(
        numero_edicion=8,
        fecha=date(2026, 9, 22),
        editorial="Texto editorial de la edición.",
        incluidas=[
            _evaluacion("Dev Presencial", Modalidad.PRESENCIAL, "CO"),
            _evaluacion("Dev Remoto CO", Modalidad.REMOTO, "CO"),
            _evaluacion("Dev Remoto Global", Modalidad.REMOTO, None),
        ],
        descartadas=[],
        resumenes={},
        conteos={"recibidas": 100, "incluidas": 3},
        fuentes_usadas=[
            FuenteUsada(
                nombre="spe",
                atribucion="Vacantes del Servicio Público de Empleo.",
                url_atribucion="https://www.serviciodeempleo.gov.co/",
            ),
            FuenteUsada(
                nombre="remoteok",
                atribucion="Ofertas remotas provistas por Remote OK.",
                url_atribucion="https://remoteok.com/",
            ),
        ],
        fuentes_caidas=[],
    )
    return DatosBoletin(**(base | extra))


def test_el_html_incluye_titulos_y_enlaces():
    html = renderizar(_datos())
    assert "Dev Presencial" in html
    assert "https://ejemplo.co/1" in html
    assert "<html" in html.lower()


def test_agrupa_en_las_tres_secciones():
    html = renderizar(_datos())
    assert "Colombia — presencial" in html
    assert "Colombia — remoto" in html
    assert "Remoto internacional" in html


def test_el_pie_cita_todas_las_fuentes_usadas():
    """Remotive y RemoteOK cortan el acceso si no se les cita."""
    html = renderizar(_datos())
    assert "Servicio Público de Empleo" in html
    assert "Remote OK" in html
    assert "https://remoteok.com/" in html


def test_declara_las_fuentes_caidas():
    html = renderizar(_datos(fuentes_caidas=["magneto"]))
    assert "magneto" in html
    assert "no respondió" in html


def test_el_apendice_muestra_solo_los_descartes_pertinentes():
    descartadas = [
        _evaluacion(
            "Estafa",
            Modalidad.REMOTO,
            "CO",
            Decision.DESCARTAR,
            MotivoDescarte.LEGITIMIDAD,
            ["pide dinero al aspirante"],
        ),
        _evaluacion(
            "Contadora",
            Modalidad.REMOTO,
            "CO",
            Decision.DESCARTAR,
            MotivoDescarte.RELEVANCIA,
            ["relevancia 0.10"],
        ),
    ]
    html = renderizar(_datos(descartadas=descartadas))
    assert "pide dinero al aspirante" in html
    assert "Contadora" not in html, "los descartes por relevancia no van al apéndice (spec §8.6)"


def test_usa_el_resumen_cuando_existe():
    ev = _evaluacion("Dev Presencial", Modalidad.PRESENCIAL, "CO")
    html = renderizar(_datos(incluidas=[ev], resumenes={ev.oferta.id: "Construye APIs en Python."}))
    assert "Construye APIs en Python." in html


def test_boletin_sin_ofertas_sigue_siendo_html_valido():
    html = renderizar(_datos(incluidas=[]))
    assert "<html" in html.lower()
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/test_render.py -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 3: Crear la plantilla MJML**

```xml
<!-- src/boletin_empleos/render/plantillas/boletin.mjml -->
<mjml>
  <mj-head>
    <mj-title>Boletín de empleos — Ingeniería de Software</mj-title>
    <mj-attributes>
      <mj-all font-family="Helvetica, Arial, sans-serif" />
      <mj-text font-size="14px" color="#25292e" line-height="1.5" />
    </mj-attributes>
  </mj-head>
  <mj-body background-color="#f4f5f7">
    <mj-section background-color="#0b3d63" padding="24px">
      <mj-column>
        <mj-text color="#ffffff" font-size="20px" font-weight="bold">
          Boletín de empleos — Ingeniería de Software
        </mj-text>
        <mj-text color="#cfe0ee" font-size="13px">
          Edición {{ numero_edicion }} · {{ fecha }} · {{ conteos.incluidas }} vacantes
        </mj-text>
      </mj-column>
    </mj-section>

    <mj-section background-color="#ffffff" padding="20px">
      <mj-column>
        <mj-text>{{ editorial }}</mj-text>
      </mj-column>
    </mj-section>

    {% for seccion in secciones %}
      {% if seccion.ofertas %}
      <mj-section background-color="#ffffff" padding="8px 20px">
        <mj-column>
          <mj-text font-size="16px" font-weight="bold" color="#0b3d63">{{ seccion.titulo }}</mj-text>
        </mj-column>
      </mj-section>
        {% for ev in seccion.ofertas %}
        <mj-section background-color="#ffffff" padding="4px 20px 12px 20px">
          <mj-column>
            <mj-text font-size="15px" font-weight="bold">
              <a href="{{ ev.oferta.url }}" style="color:#0b3d63;text-decoration:none;">{{ ev.oferta.titulo }}</a>
            </mj-text>
            <mj-text font-size="13px" color="#5a6570">
              {{ ev.oferta.empresa or "Empresa no identificada" }}{% if ev.oferta.ubicacion %} · {{ ev.oferta.ubicacion }}{% endif %}{% if ev.salario %} · {{ ev.salario }}{% endif %}{% if ev.oferta.fecha_publicacion %} · publicada {{ ev.oferta.fecha_publicacion }}{% endif %}
            </mj-text>
            {% if ev.resumen %}<mj-text font-size="13px">{{ ev.resumen }}</mj-text>{% endif %}
          </mj-column>
        </mj-section>
        {% endfor %}
      {% endif %}
    {% endfor %}

    {% if descartes_visibles %}
    <mj-section background-color="#fbf7ec" padding="16px 20px">
      <mj-column>
        <mj-text font-size="14px" font-weight="bold">Apéndice — ofertas descartadas</mj-text>
        <mj-text font-size="12px" color="#5a6570">
          Se listan para que el filtro pueda auditarse. No se descartan en silencio.
        </mj-text>
        {% for ev in descartes_visibles %}
        <mj-text font-size="12px" color="#5a6570">
          <strong>{{ ev.oferta.titulo }}</strong> — {{ ev.motivo }}: {{ ev.notas|join("; ") }}
        </mj-text>
        {% endfor %}
      </mj-column>
    </mj-section>
    {% endif %}

    <mj-section background-color="#eef1f4" padding="16px 20px">
      <mj-column>
        <mj-text font-size="12px" color="#5a6570"><strong>Fuentes de esta edición</strong></mj-text>
        {% for f in fuentes_usadas %}
        <mj-text font-size="12px" color="#5a6570">
          {{ f.atribucion }} <a href="{{ f.url_atribucion }}">{{ f.url_atribucion }}</a>
        </mj-text>
        {% endfor %}
        {% if fuentes_caidas %}
        <mj-text font-size="12px" color="#a04a2a">
          En esta edición no respondió: {{ fuentes_caidas|join(", ") }}.
        </mj-text>
        {% endif %}
        <mj-text font-size="11px" color="#8a939c">
          Proyección Social · Facultad de Ingenierías y Ciencias Básicas ·
          Corporación Universitaria Empresarial Alexander von Humboldt · Armenia, Quindío
        </mj-text>
      </mj-column>
    </mj-section>
  </mj-body>
</mjml>
```

- [ ] **Step 4: Implementar el renderizador**

```python
# src/boletin_empleos/render/__init__.py
```

```python
# src/boletin_empleos/render/renderizador.py
"""Render del boletín. MJML compila a HTML tolerante a clientes de correo.

El pie de atribución se construye recorriendo las fuentes que aportaron
ofertas: nunca se escribe a mano. Remotive y RemoteOK cortan el acceso si no
se les cita (spec §9).
"""

from datetime import date
from pathlib import Path

from jinja2_mjml import Environment
from pydantic import BaseModel, Field

from boletin_empleos.modelos import Evaluacion, Modalidad, MotivoDescarte, Oferta

_PLANTILLAS = Path(__file__).parent / "plantillas"

# Solo estos motivos llegan al apéndice del boletín (spec §8.6).
_MOTIVOS_VISIBLES = {
    MotivoDescarte.LEGITIMIDAD,
    MotivoDescarte.EXPERIENCIA,
    MotivoDescarte.VIGENCIA,
    MotivoDescarte.ENLACE_MUERTO,
}


class FuenteUsada(BaseModel):
    nombre: str
    atribucion: str
    url_atribucion: str


class DatosBoletin(BaseModel):
    numero_edicion: int
    fecha: date
    editorial: str
    incluidas: list[Evaluacion]
    descartadas: list[Evaluacion] = Field(default_factory=list)
    resumenes: dict[str, str] = Field(default_factory=dict)
    conteos: dict[str, int] = Field(default_factory=dict)
    fuentes_usadas: list[FuenteUsada] = Field(default_factory=list)
    fuentes_caidas: list[str] = Field(default_factory=list)


def renderizar(datos: DatosBoletin) -> str:
    entorno = Environment(loader=_cargador())
    plantilla = entorno.get_template("boletin.mjml")
    return plantilla.render(
        numero_edicion=datos.numero_edicion,
        fecha=datos.fecha.isoformat(),
        editorial=datos.editorial,
        conteos=datos.conteos,
        secciones=_agrupar(datos),
        descartes_visibles=[
            _con_extras(e, datos) for e in datos.descartadas if e.motivo in _MOTIVOS_VISIBLES
        ],
        fuentes_usadas=datos.fuentes_usadas,
        fuentes_caidas=datos.fuentes_caidas,
    )


def _cargador():
    from jinja2 import FileSystemLoader

    return FileSystemLoader(str(_PLANTILLAS))


class _Adornada(BaseModel):
    """Una evaluación con los campos ya calculados que la plantilla necesita.

    `oferta` va tipada como `Oferta` y no como `object`: así pydantic valida de
    verdad y el editor autocompleta los campos dentro de la plantilla.
    """

    oferta: Oferta
    resumen: str | None
    salario: str | None
    motivo: str | None
    notas: list[str]


def _con_extras(evaluacion: Evaluacion, datos: DatosBoletin) -> _Adornada:
    return _Adornada(
        oferta=evaluacion.oferta,
        resumen=datos.resumenes.get(evaluacion.oferta.id),
        salario=_salario(evaluacion),
        motivo=evaluacion.motivo.value if evaluacion.motivo else None,
        notas=evaluacion.notas,
    )


def _salario(evaluacion: Evaluacion) -> str | None:
    o = evaluacion.oferta
    if o.salario_min is None and o.salario_max is None:
        return None
    moneda = o.moneda or ""
    if o.salario_min is not None and o.salario_max is not None:
        return f"{o.salario_min:,} – {o.salario_max:,} {moneda}".replace(",", ".")
    valor = o.salario_min if o.salario_min is not None else o.salario_max
    return f"desde {valor:,} {moneda}".replace(",", ".")


def _agrupar(datos: DatosBoletin) -> list[dict]:
    presencial_co, remoto_co, remoto_global = [], [], []
    for evaluacion in datos.incluidas:
        adornada = _con_extras(evaluacion, datos)
        oferta = evaluacion.oferta
        if oferta.modalidad is not Modalidad.REMOTO:
            presencial_co.append(adornada)
        elif oferta.pais == "CO":
            remoto_co.append(adornada)
        else:
            remoto_global.append(adornada)

    return [
        {"titulo": "Colombia — presencial e híbrido", "ofertas": presencial_co},
        {"titulo": "Colombia — remoto", "ofertas": remoto_co},
        {"titulo": "Remoto internacional", "ofertas": remoto_global},
    ]
```

- [ ] **Step 5: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/test_render.py -v`
Expected: PASS — 7 tests

**API verificada el 9/09/2026, no hace falta investigarla:** `jinja2_mjml.Environment` hereda de
`jinja2.Environment` y acepta `loader` con la misma firma. La cadena completa
(`FileSystemLoader` → `get_template(...).render(...)`) se probó end-to-end contra un `.mjml` con
variables y bucles: devuelve HTML con `<!doctype>`, las variables interpoladas y los enlaces intactos.
El código de esta tarea funciona tal como está escrito.

- [ ] **Step 6: Formatear y commitear**

```bash
uv run ruff format . && uv run ruff check --fix .
git add src/ tests/
git commit -m "feat: render del boletín con MJML y pie de atribución generado"
```

---

### Task 14: Entrega por consola y por SMTP

**Files:**
- Create: `src/boletin_empleos/entrega/__init__.py`
- Create: `src/boletin_empleos/entrega/base.py`
- Create: `src/boletin_empleos/entrega/consola.py`
- Create: `src/boletin_empleos/entrega/smtp.py`
- Create: `tests/test_entrega.py`

**Interfaces:**
- Consumes: nada del núcleo
- Produces:
  - `Entrega` (Protocol) con `enviar(asunto, html, destinatarios) -> bool`
  - `EntregaConsola(directorio: Path)`, `EntregaSMTP(host, puerto, usuario, clave, remitente)`

Este es el borde que hace barata la fase 2 (lista de egresados vía Brevo): se añade otro adaptador y
nada más cambia.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_entrega.py
from boletin_empleos.entrega.consola import EntregaConsola
from boletin_empleos.entrega.smtp import EntregaSMTP


def test_consola_guarda_el_html_en_disco(tmp_path):
    entrega = EntregaConsola(tmp_path)
    assert entrega.enviar("Asunto", "<html>hola</html>", ["a@b.co"]) is True

    archivos = list(tmp_path.glob("*.html"))
    assert len(archivos) == 1
    assert archivos[0].read_text("utf-8") == "<html>hola</html>"


def test_smtp_arma_un_mensaje_valido(monkeypatch):
    enviados = {}

    class ServidorFalso:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            enviados["tls"] = True

        def login(self, usuario, clave):
            enviados["login"] = usuario

        def send_message(self, mensaje):
            enviados["mensaje"] = mensaje

    monkeypatch.setattr("smtplib.SMTP", lambda host, puerto, timeout=30: ServidorFalso())

    entrega = EntregaSMTP(
        host="smtp.ejemplo.co",
        puerto=587,
        usuario="cuenta@cue.edu.co",
        clave="secreta",
        remitente="cuenta@cue.edu.co",
    )
    assert entrega.enviar("Boletín", "<html>x</html>", ["dir@cue.edu.co"]) is True

    assert enviados["tls"] is True
    mensaje = enviados["mensaje"]
    assert mensaje["Subject"] == "Boletín"
    assert mensaje["To"] == "dir@cue.edu.co"
    assert "<html>x</html>" in mensaje.get_content()


def test_smtp_devuelve_false_si_falla(monkeypatch):
    def explotar(*a, **k):
        raise OSError("sin conexión")

    monkeypatch.setattr("smtplib.SMTP", explotar)

    entrega = EntregaSMTP("h", 587, "u", "c", "u@cue.edu.co")
    assert entrega.enviar("Boletín", "<html>x</html>", ["dir@cue.edu.co"]) is False
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/test_entrega.py -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 3: Implementar el puerto y los adaptadores**

```python
# src/boletin_empleos/entrega/base.py
"""Puerto de salida: entrega del boletín.

Hoy hay un destinatario. Añadir la lista de egresados (fase 2) es añadir otro
adaptador detrás de este mismo puerto, sin tocar nada más.
"""

from typing import Protocol


class Entrega(Protocol):
    def enviar(self, asunto: str, html: str, destinatarios: list[str]) -> bool:
        """Devuelve True si se entregó. Nunca lanza excepción."""
        ...
```

```python
# src/boletin_empleos/entrega/consola.py
"""Entrega de prueba: guarda el HTML en disco en vez de enviarlo. Usado por --dry-run."""

import logging
from datetime import UTC, datetime
from pathlib import Path

_log = logging.getLogger(__name__)


class EntregaConsola:
    def __init__(self, directorio: Path) -> None:
        self._directorio = Path(directorio)

    def enviar(self, asunto: str, html: str, destinatarios: list[str]) -> bool:
        self._directorio.mkdir(parents=True, exist_ok=True)
        marca = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        ruta = self._directorio / f"boletin-{marca}.html"
        ruta.write_text(html, encoding="utf-8")
        _log.info("boletín escrito en %s (destinatarios: %s)", ruta, ", ".join(destinatarios))
        return True
```

```python
# src/boletin_empleos/entrega/smtp.py
"""Entrega por SMTP institucional."""

import logging
import smtplib
from email.message import EmailMessage

_log = logging.getLogger(__name__)


class EntregaSMTP:
    def __init__(self, host: str, puerto: int, usuario: str, clave: str, remitente: str) -> None:
        self._host = host
        self._puerto = puerto
        self._usuario = usuario
        self._clave = clave
        self._remitente = remitente

    def enviar(self, asunto: str, html: str, destinatarios: list[str]) -> bool:
        mensaje = EmailMessage()
        mensaje["Subject"] = asunto
        mensaje["From"] = self._remitente
        mensaje["To"] = ", ".join(destinatarios)
        mensaje.set_content("Este boletín requiere un cliente de correo con soporte HTML.")
        mensaje.add_alternative(html, subtype="html")

        try:
            with smtplib.SMTP(self._host, self._puerto, timeout=30) as servidor:
                servidor.starttls()
                servidor.login(self._usuario, self._clave)
                servidor.send_message(mensaje)
        except (OSError, smtplib.SMTPException) as e:
            _log.error("no se pudo enviar el boletín: %s", e)
            return False

        _log.info("boletín enviado a %s", ", ".join(destinatarios))
        return True
```

```python
# src/boletin_empleos/entrega/__init__.py
from boletin_empleos.entrega.base import Entrega

__all__ = ["Entrega"]
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/test_entrega.py -v`
Expected: PASS — 3 tests

- [ ] **Step 5: Formatear y commitear**

```bash
uv run ruff format . && uv run ruff check --fix .
git add src/ tests/
git commit -m "feat: entrega por consola y por SMTP"
```

---

### Task 15: CLI y orquestación completa

**Files:**
- Create: `src/boletin_empleos/cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: absolutamente todo lo anterior
- Produces: `main(argv=None) -> int`, `construir_fuentes() -> list[FuenteEmpleo]`, `ejecutar(args) -> int`

**Reglas de degradación (spec §12):**
- Una fuente caída no tumba el boletín: se envía y el pie lo declara.
- Si **todas** las fuentes fallan, **no se envía boletín vacío**: se retorna código de error.

**Sobre la alerta del criterio 6 del spec.** El spec pide que, si fallan todas las fuentes, "se mande
una alerta". La alerta es el **código de salida distinto de cero**, que hace fallar el workflow y
dispara la notificación por correo que GitHub envía al dueño del repositorio.

Es deliberado que la alerta llegue **al mantenedor y no a la directora**: un fallo técnico de
recolección es un problema de mantenimiento, no información útil para la coordinación. La directora
solo debe recibir boletines. Queda documentado en el README (Task 16).

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_cli.py
from datetime import UTC, datetime

import pytest

from boletin_empleos.cli import main
from boletin_empleos.modelos import Modalidad, Oferta


class FuenteFalsa:
    def __init__(self, nombre, ofertas, confianza=0.9):
        self.nombre = nombre
        self.base_permiso = "prueba"
        self.atribucion = f"Ofertas de {nombre}."
        self.url_atribucion = f"https://{nombre}.ejemplo.co/"
        self.confianza_base = confianza
        self._ofertas = ofertas

    def obtener(self):
        return self._ofertas


def _oferta(id_, titulo="Desarrollador Backend Python"):
    return Oferta(
        id=id_,
        fuente="falsa",
        titulo=titulo,
        empresa="Acme S.A.S.",
        ubicacion="Armenia, Quindío",
        pais="CO",
        modalidad=Modalidad.PRESENCIAL,
        url=f"https://ejemplo.co/{id_}",
        descripcion="Buscamos desarrollador con Python. " * 10,
        recogida_en=datetime(2026, 9, 9, tzinfo=UTC),
    )


@pytest.fixture
def sin_verificacion(monkeypatch):
    monkeypatch.setattr("boletin_empleos.cli.filtrar_enlaces_vivos", lambda evs: (evs, []))


def test_dry_run_escribe_el_boletin_sin_enviar(tmp_path, monkeypatch, sin_verificacion):
    monkeypatch.setattr(
        "boletin_empleos.cli.construir_fuentes",
        lambda: [FuenteFalsa("falsa", [_oferta("f:1"), _oferta("f:2")])],
    )
    salida = tmp_path / "salida"
    codigo = main(["--dry-run", "--salida", str(salida), "--historial", str(tmp_path / "h.json")])

    assert codigo == 0
    assert list(salida.glob("*.html")), "el dry-run debe dejar el HTML en disco"


def test_una_fuente_caida_no_tumba_el_boletin(tmp_path, monkeypatch, sin_verificacion):
    monkeypatch.setattr(
        "boletin_empleos.cli.construir_fuentes",
        lambda: [FuenteFalsa("viva", [_oferta("v:1")]), FuenteFalsa("caida", [])],
    )
    salida = tmp_path / "salida"
    codigo = main(["--dry-run", "--salida", str(salida), "--historial", str(tmp_path / "h.json")])

    assert codigo == 0
    html = next(salida.glob("*.html")).read_text("utf-8")
    assert "caida" in html and "no respondió" in html


def test_sin_ninguna_oferta_no_se_envia_boletin(tmp_path, monkeypatch, sin_verificacion):
    monkeypatch.setattr("boletin_empleos.cli.construir_fuentes", lambda: [FuenteFalsa("caida", [])])
    salida = tmp_path / "salida"
    codigo = main(["--dry-run", "--salida", str(salida), "--historial", str(tmp_path / "h.json")])

    assert codigo == 2, "sin fuentes vivas no se envía boletín vacío"
    assert not list(salida.glob("*.html"))


def test_el_historial_evita_repetir_ofertas(tmp_path, monkeypatch, sin_verificacion):
    monkeypatch.setattr(
        "boletin_empleos.cli.construir_fuentes",
        lambda: [FuenteFalsa("falsa", [_oferta("f:1")])],
    )
    salida = tmp_path / "salida"
    historial = tmp_path / "h.json"

    assert main(["--dry-run", "--salida", str(salida), "--historial", str(historial)]) == 0
    # Segunda corrida: la misma oferta ya fue enviada, no quedan nuevas.
    assert main(["--dry-run", "--salida", str(salida), "--historial", str(historial)]) == 3
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'boletin_empleos.cli'`

- [ ] **Step 3: Implementar el CLI**

```python
# src/boletin_empleos/cli.py
"""Punto de entrada. Este archivo es lo único que GitHub Actions invoca.

Códigos de salida:
  0  boletín generado y entregado
  1  error de configuración o de entrega
  2  ninguna fuente respondió — no se envía boletín vacío (spec §12)
  3  no hay ofertas nuevas para esta edición
"""

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

from boletin_empleos.almacenamiento.json_repo import HistorialJSON
from boletin_empleos.config import cargar_config
from boletin_empleos.enriquecimiento import crear_enriquecedor
from boletin_empleos.entrega.consola import EntregaConsola
from boletin_empleos.entrega.smtp import EntregaSMTP
from boletin_empleos.fuentes.magneto import FuenteMagneto
from boletin_empleos.fuentes.remoteok import FuenteRemoteOK
from boletin_empleos.fuentes.remotive import FuenteRemotive
from boletin_empleos.fuentes.spe import FuenteSPE
from boletin_empleos.nucleo.pipeline import evaluar
from boletin_empleos.render.renderizador import DatosBoletin, FuenteUsada, renderizar
from boletin_empleos.verificacion import filtrar_enlaces_vivos

_log = logging.getLogger("boletin")


def construir_fuentes():
    return [FuenteSPE(), FuenteMagneto(), FuenteRemotive(), FuenteRemoteOK()]


def _argumentos(argv):
    p = argparse.ArgumentParser(prog="boletin", description="Boletín quincenal de empleos")
    p.add_argument("--dry-run", action="store_true", help="renderiza y guarda en disco sin enviar")
    p.add_argument("--config", type=Path, default=Path("config.toml"))
    p.add_argument("--historial", type=Path, default=Path("datos/historial.json"))
    p.add_argument("--salida", type=Path, default=Path("datos/ediciones"))
    p.add_argument("--verboso", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verboso else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return ejecutar(args)


def ejecutar(args) -> int:
    cfg = cargar_config(args.config)
    historial = HistorialJSON(args.historial)

    ofertas = []
    fuentes_usadas: list[FuenteUsada] = []
    fuentes_caidas: list[str] = []
    confianza_por_fuente: dict[str, float] = {}

    for fuente in construir_fuentes():
        confianza_por_fuente[fuente.nombre] = fuente.confianza_base
        recogidas = fuente.obtener()
        if recogidas:
            ofertas.extend(recogidas)
            fuentes_usadas.append(
                FuenteUsada(
                    nombre=fuente.nombre,
                    atribucion=fuente.atribucion,
                    url_atribucion=fuente.url_atribucion,
                )
            )
            _log.info("%s: %d ofertas", fuente.nombre, len(recogidas))
        else:
            fuentes_caidas.append(fuente.nombre)
            _log.warning("%s: no aportó ofertas en esta edición", fuente.nombre)

    if not fuentes_usadas:
        _log.error("ninguna fuente respondió; no se envía un boletín vacío")
        return 2

    resultado = evaluar(ofertas, historial.ids_enviados(), cfg, confianza_por_fuente, date.today())
    vivas, muertas = filtrar_enlaces_vivos(resultado.incluidas)
    _log.info("conteos: %s | enlaces muertos: %d", resultado.conteos, len(muertas))

    if not vivas:
        _log.warning("no hay ofertas nuevas para esta edición")
        return 3

    enriquecedor = crear_enriquecedor(os.environ.get("ANTHROPIC_API_KEY"))
    datos = DatosBoletin(
        numero_edicion=historial.numero_edicion(),
        fecha=date.today(),
        editorial=enriquecedor.editorial(vivas, resultado.conteos),
        incluidas=vivas,
        descartadas=[*resultado.descartadas, *muertas],
        resumenes=enriquecedor.resumir(vivas),
        conteos={**resultado.conteos, "incluidas": len(vivas)},
        fuentes_usadas=fuentes_usadas,
        fuentes_caidas=fuentes_caidas,
    )
    html = renderizar(datos)

    entrega = _crear_entrega(args, cfg)
    if entrega is None:
        return 1
    if not entrega.enviar(cfg.asunto, html, cfg.destinatarios):
        return 1

    args.salida.mkdir(parents=True, exist_ok=True)
    (args.salida / f"{date.today().isoformat()}.html").write_text(html, encoding="utf-8")
    historial.registrar({e.oferta.id for e in vivas}, date.today())
    _log.info("edición %d completada con %d vacantes", datos.numero_edicion, len(vivas))
    return 0


def _crear_entrega(args, cfg):
    if args.dry_run:
        return EntregaConsola(args.salida)

    faltantes = [v for v in ("SMTP_HOST", "SMTP_USUARIO", "SMTP_CLAVE") if not os.environ.get(v)]
    if faltantes:
        _log.error("faltan variables de entorno para el envío: %s", ", ".join(faltantes))
        return None

    return EntregaSMTP(
        host=os.environ["SMTP_HOST"],
        puerto=int(os.environ.get("SMTP_PUERTO", "587")),
        usuario=os.environ["SMTP_USUARIO"],
        clave=os.environ["SMTP_CLAVE"],
        remitente=cfg.remitente,
    )


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS — 4 tests

- [ ] **Step 5: Ejecutar la suite completa**

Run: `uv run pytest -v`
Expected: PASS — todos los tests de todas las tareas

- [ ] **Step 6: Formatear y commitear**

```bash
uv run ruff format . && uv run ruff check --fix .
git add src/ tests/
git commit -m "feat: CLI y orquestación completa del boletín"
```

---

### Task 16: Ejecución real, workflow de GitHub Actions y documentación

**Files:**
- Create: `.github/workflows/boletin.yml`
- Create: `.github/workflows/pruebas.yml`
- Create: `README.md`
- Create: `datos/.gitkeep`

**Interfaces:**
- Consumes: el CLI de la Task 15
- Produces: el sistema desplegado y documentado

- [ ] **Step 1: Ejecutar contra las fuentes reales por primera vez**

```bash
uv run boletin --dry-run --verboso --salida datos/prueba
```

Expected: se genera un HTML en `datos/prueba/`. Revisa en el registro los conteos por fuente.

**Esto es una medición, no solo una prueba.** El spec §13 marca como riesgo medio el "volumen bajo de
vacantes junior en Colombia". Anota cuántas vacantes sobreviven al filtro. Si son menos de 5, ajusta en
`config.toml`: baja `umbral_relevancia`, sube `max_meses_experiencia`, o añade rutas de ciudad en
`RUTAS_POR_DEFECTO` de Magneto. Vuelve a correr hasta obtener un boletín con contenido útil.

- [ ] **Step 2: Abrir el HTML y revisarlo visualmente**

```bash
uv run python -c "
import pathlib, webbrowser
archivos = sorted(pathlib.Path('datos/prueba').glob('*.html'))
if not archivos:
    raise SystemExit('no se generó ningún boletín en datos/prueba/')
ultimo = archivos[-1]
print('abriendo', ultimo, f'({ultimo.stat().st_size} bytes)')
webbrowser.open(ultimo.resolve().as_uri())
"
```

Se usa `webbrowser` de la librería estándar en vez de `start`: `start` es un builtin de `cmd.exe`
y no existe en Git Bash, que es donde corren estos comandos.

Verifica: los tres bloques aparecen, los enlaces abren la vacante correcta, el pie cita todas las
fuentes usadas, y el apéndice no está inundado.

- [ ] **Step 3: Crear el workflow de pruebas**

```yaml
# .github/workflows/pruebas.yml
name: Pruebas

on:
  push:
    branches: [main]
  pull_request:

jobs:
  pruebas:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv sync --all-extras --dev
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pytest -v
```

- [ ] **Step 4: Crear el workflow del boletín**

```yaml
# .github/workflows/boletin.yml
name: Boletín de empleos

on:
  schedule:
    # Quincenal: días 1 y 15 de cada mes, 12:00 UTC (07:00 en Colombia).
    - cron: "0 12 1,15 * *"
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Generar sin enviar"
        type: boolean
        default: false

permissions:
  contents: write

jobs:
  generar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true

      - run: uv sync --all-extras --dev

      - name: Generar y enviar el boletín
        env:
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PUERTO: ${{ secrets.SMTP_PUERTO }}
          SMTP_USUARIO: ${{ secrets.SMTP_USUARIO }}
          SMTP_CLAVE: ${{ secrets.SMTP_CLAVE }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          if [ "${{ inputs.dry_run }}" = "true" ]; then
            uv run boletin --dry-run --verboso
          else
            uv run boletin --verboso
          fi

      - name: Guardar el historial y la edición
        if: success()
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add datos/
          git diff --staged --quiet || git commit -m "chore: edición del $(date +%F)"
          git push
```

**Nota:** `permissions: contents: write` es indispensable para que el workflow pueda commitear el
historial. Además hay que activar *Settings → Actions → General → Workflow permissions → Read and write
permissions* (spec §11).

- [ ] **Step 5: Escribir el README**

````markdown
# Boletín de empleos — Ingeniería de Software

Agente que cada quince días recolecta ofertas de empleo en desarrollo de software desde fuentes
autorizadas, las filtra por pertinencia y legitimidad, y envía un boletín HTML a la Coordinación de
Proyección Social de la Facultad de Ingenierías y Ciencias Básicas.

Corporación Universitaria Empresarial Alexander von Humboldt · Armenia, Quindío.

## Uso

```bash
uv sync
uv run boletin --dry-run     # genera sin enviar, deja el HTML en datos/ediciones/
uv run boletin               # genera y envía
uv run pytest                # pruebas
```

## Fuentes y su base de permiso

Este sistema **solo usa fuentes que autorizan expresamente su uso**. Cada adaptador declara por qué
tenemos derecho a usarla, y el boletín cita a todas en su pie.

| Fuente | Base de permiso |
|---|---|
| Servicio Público de Empleo | Portal estatal del Ministerio del Trabajo, `robots.txt` permisivo |
| Magneto365 | Publica `llms.txt` dirigido a asistentes de IA |
| Remotive | API pública gratuita, con obligación de atribución |
| RemoteOK | API pública gratuita, con obligación de atribución |

**Excluidas a propósito:** elempleo.com prohíbe el scraping y la minería de datos en su `robots.txt`;
Computrabajo bloquea el acceso automatizado; LinkedIn lo prohíbe en sus términos.
**No agregar fuentes sin verificar antes su `robots.txt` y sus términos.**

## Configuración

Todo lo ajustable vive en `config.toml`: vocabulario de cargos y tecnologías, umbrales, y las heurísticas
antiestafa. **No hace falta saber Python para afinar el filtro.**

## Secretos requeridos (Settings → Secrets and variables → Actions)

| Secreto | Obligatorio | Para qué |
|---|---|---|
| `SMTP_HOST` | Sí | Servidor de correo institucional |
| `SMTP_PUERTO` | No (587) | Puerto SMTP |
| `SMTP_USUARIO` | Sí | Cuenta remitente |
| `SMTP_CLAVE` | Sí | Contraseña o contraseña de aplicación |
| `ANTHROPIC_API_KEY` | No | Resúmenes y editorial. Sin ella el boletín sale igual, más escueto |

## Cuando algo falla

| Código de salida | Significa |
|---|---|
| 0 | Boletín generado y entregado |
| 1 | Error de configuración o de entrega |
| 2 | **Ninguna fuente respondió** — no se envía un boletín vacío |
| 3 | No hay ofertas nuevas para esta edición |

Un código distinto de cero hace fallar el workflow, y GitHub notifica por correo al dueño del
repositorio. Esa notificación **es** la alerta: llega al mantenedor, no a la directora. Un fallo de
recolección es un problema técnico, y la coordinación solo debe recibir boletines.

También hay que activar *Settings → Actions → General → Workflow permissions → **Read and write
permissions***, o el workflow no podrá guardar el historial.

## Arquitectura

Puertos y adaptadores sobre tres bordes: fuentes, almacenamiento y entrega. El núcleo
(`src/boletin_empleos/nucleo/`) es lógica pura sin E/S y se prueba sin red. Hay un test que lo verifica.

Diseño completo: `docs/superpowers/specs/2026-09-09-boletin-empleos-design.md`
````

- [ ] **Step 6: Commitear**

```bash
mkdir -p datos && touch datos/.gitkeep
git add .github/ README.md datos/.gitkeep
git commit -m "feat: workflows de GitHub Actions y documentación"
git push
```

- [ ] **Step 7: Verificar en GitHub**

1. Activa *Settings → Actions → General → Workflow permissions → Read and write permissions*.
2. Carga los secretos SMTP.
3. Lanza el workflow a mano desde *Actions → Boletín de empleos → Run workflow* con `dry_run: true`.
4. Confirma que termina en verde y que el registro muestra ofertas recolectadas por fuente.

---

## Notas para quien ejecute este plan

**Orden.** Las tareas 1–5 construyen entrada, 6–9 el núcleo, 10–14 los bordes de salida, 15–16 el
ensamblaje. Las tareas 2 a 5 son independientes entre sí; las demás dependen de las anteriores.

**Las fixtures son datos reales.** Cada adaptador descarga su fixture de la fuente viva en su primer
paso. Si una fuente cambió su formato desde el 9 de septiembre de 2026, el test lo dirá con claridad —
que es exactamente lo que queremos.

**Task 5 (Magneto) ya no tiene incógnitas.** Sus selectores se verificaron contra el HTML real el
9/09/2026, y su ruta rota (`ofertas-empleo-trabajo-remoto`, HTTP 500 en el servidor de Magneto)
quedó excluida. Ninguna tarea de este plan requiere ya trabajo de investigación.

**No agregues fuentes sin verificar su `robots.txt` y sus términos.** Es la restricción central de este
diseño, no una recomendación.
