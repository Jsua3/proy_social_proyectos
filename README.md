# Boletín de empleos — Ingeniería de Software

Agente que cada quince días recolecta ofertas de empleo en desarrollo de software desde fuentes
autorizadas, las filtra por pertinencia y legitimidad, y entrega un boletín HTML a la Coordinación de
Proyección Social de la Facultad de Ingenierías y Ciencias Básicas.

Corporación Universitaria Empresarial Alexander von Humboldt · Armenia, Quindío.

El seguimiento a la empleabilidad de los egresados es una obligación del CNA (Acuerdo 01 de 2025,
Factor 12, Características 39 y 40). Este programa deja rastro de cada edición: qué se recogió, qué se
descartó y por qué.

## Estado: vista previa

La ejecución automática ya corre cada quince días, pero **todavía no envía correo**. Genera el boletín,
publica la edición en el sitio y la deja además como archivo descargable de la corrida, en *Actions →
Boletín de empleos → la última corrida → Artifacts*. Se hace así porque las credenciales del correo
institucional aún no están entregadas.

En el índice del sitio, cada edición dice si fue *enviada a la Coordinación* o si es una *vista previa*.
Decir lo contrario sería falso: hasta el primer envío real, nadie las ha recibido.

**Para pasar a envío real**, sin tocar una sola línea de código:

1. Cargar los secretos `SMTP_HOST`, `SMTP_USUARIO` y `SMTP_CLAVE`.
2. Crear la variable `ENVIO_REAL` con el valor `true`, en
   *Settings → Secrets and variables → Actions → Variables*.

Para volver a vista previa, basta con borrar esa variable o ponerla en `false`.

## Uso local

```bash
uv sync
uv run boletin --dry-run     # vista previa: no envía nada ni toca el historial
uv run boletin               # genera y envía (exige las variables SMTP_*)
uv run python -m boletin_empleos.sitio   # arma el sitio en sitio/ a partir de datos/ediciones/
uv run pytest                # 287 pruebas, sin red
```

Una vista previa deja dos archivos en `datos/ediciones/`:

| Archivo | Qué es |
|---|---|
| `AAAA-MM-DD.html` | La edición completa, la que se publica en el sitio |
| `AAAA-MM-DD-correo.html` | Lo que recibiría la directora: las vacantes más pertinentes y el enlace a la edición |

Una corrida completa tarda unos diez minutos: el Servicio Público de Empleo se pagina de a decenas de
páginas y después se comprueba, uno por uno, que los enlaces sigan vivos.

## El sitio y el correo

El boletín completo ronda los 300 KB y Gmail recorta los mensajes de más de unos 102 KB: la directora
vería el correo cortado. Por eso se reparte en dos:

- **El correo** lleva las vacantes más pertinentes (`vacantes_en_correo` en `config.toml`, hoy 10) y un
  enlace a la edición completa. Pesa unas decenas de kilobytes.
- **El sitio** guarda cada edición entera, con su fecha, en
  `https://jsua3.github.io/proy_social_proyectos`. Se reconstruye en cada corrida a partir de las
  ediciones versionadas en `datos/ediciones/`.

Ese archivo fechado es además el rastro que pide el CNA para el seguimiento a la empleabilidad
(Acuerdo 01 de 2025, Factor 12, Características 39 y 40).

Si se borra `url_base` de `config.toml`, no hay enlace y el correo vuelve a llevar el boletín completo.

## Prioridad geográfica

La Coordinación está en Armenia, así que el boletín ordena las vacantes por cercanía:

1. **Quindío y eje cafetero** — Quindío, Risaralda y Caldas, en cualquier modalidad.
2. **Colombia — remoto** — desde Armenia se puede tomar sin mudarse.
3. **Colombia — presencial e híbrido** — el resto del país.
4. **Remoto internacional**.

Esto **solo ordena**: ninguna vacante se descarta por estar lejos. Importa sobre todo en el correo,
que lleva las diez primeras. El vocabulario está en `[geografia]` de `config.toml`; vaciarlo devuelve
el boletín al trato parejo.

Los nombres de municipios chocan en los dos sentidos —Antioquia tiene su propio Armenia y su propio
Caldas, y el Quindío tiene un municipio llamado Córdoba—, así que manda el último departamento
nombrado, que es como el Servicio Público de Empleo escribe la ubicación.

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

El agente se identifica con el nombre del proyecto y un correo de contacto institucional en cada
petición. Es deliberado: si un portal tiene un problema con el agente, sabe a quién escribir en vez de
bloquearlo sin aviso.

## Configuración

Todo lo ajustable vive en `config.toml`: destinatarios, vocabulario de cargos y tecnologías, umbrales y
heurísticas antiestafa. **No hace falta saber Python para afinar el filtro.**

## Secretos y variables

*Settings → Secrets and variables → Actions*

| Nombre | Tipo | Obligatorio | Para qué |
|---|---|---|---|
| `SMTP_HOST` | Secreto | Solo para enviar | Servidor de correo institucional |
| `SMTP_PUERTO` | Secreto | No (587) | Puerto SMTP |
| `SMTP_USUARIO` | Secreto | Solo para enviar | Cuenta remitente |
| `SMTP_CLAVE` | Secreto | Solo para enviar | Contraseña o contraseña de aplicación |
| `ANTHROPIC_API_KEY` | Secreto | No | Resúmenes y editorial. Sin ella el boletín sale igual, más escueto |
| `ENVIO_REAL` | Variable | No | `true` activa el envío por correo; ausente o `false` deja vista previa |

Para guardar el historial tras un envío real hay que activar además
*Settings → Actions → General → Workflow permissions → **Read and write permissions***.

## Cuando algo falla

| Código de salida | Significa |
|---|---|
| 0 | Boletín generado y entregado |
| 1 | Error de configuración, de render o de entrega |
| 2 | **Ningún portal respondió** — no se envía un boletín vacío |
| 3 | No hay vacantes nuevas para esta edición |

Un código distinto de cero hace fallar la corrida, y GitHub notifica por correo a quien administra el
repositorio. Esa notificación **es** la alerta: llega al mantenedor, no a la directora. Un fallo de
recolección es un problema técnico, y la coordinación solo debe recibir boletines.

El código 3 no hace fallar la corrida: queda como aviso en el resumen.

## Arquitectura

Puertos y adaptadores sobre tres bordes: fuentes, almacenamiento y entrega. El núcleo
(`src/boletin_empleos/nucleo/`) es lógica pura sin entrada ni salida, y se prueba sin red. Hay una
prueba que verifica esa pureza y falla si alguien mete una llamada de red en el núcleo.

Diseño completo: `docs/superpowers/specs/2026-09-09-boletin-empleos-design.md`

## Lo que falta

- Generar el boletín desde muestras guardadas, sin red (`--desde`), para demostrarlo sin internet.
- Deduplicación aproximada entre portales, hoy exacta.
- Magneto365 nunca trae salario y marca todo como presencial: ninguna de sus vacantes puede caer en
  las secciones de remoto.
- Mover el repositorio a una cuenta institucional: hoy el sitio vive bajo una cuenta personal.
