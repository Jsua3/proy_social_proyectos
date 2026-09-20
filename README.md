# Boletín de empleos — Ingeniería de Software

Agente que cada quince días recolecta ofertas de empleo en desarrollo de software desde fuentes
autorizadas, las filtra por pertinencia y legitimidad, y entrega un boletín HTML a la Coordinación de
Proyección Social de la Facultad de Ingenierías y Ciencias Básicas.

Corporación Universitaria Empresarial Alexander von Humboldt · Armenia, Quindío.

El seguimiento a la empleabilidad de los egresados es una obligación del CNA (Acuerdo 01 de 2025,
Factor 12, Características 39 y 40). Este programa deja rastro de cada edición: qué se recogió, qué se
descartó y por qué.

## Estado: vista previa

La ejecución automática ya corre cada quince días, pero **todavía no envía correo**. Genera el boletín
y lo deja como archivo descargable al final de la corrida, en *Actions → Boletín de empleos → la última
corrida → Artifacts*. Se hace así porque las credenciales del correo institucional aún no están
entregadas.

**Para pasar a envío real**, sin tocar una sola línea de código:

1. Cargar los secretos `SMTP_HOST`, `SMTP_USUARIO` y `SMTP_CLAVE`.
2. Crear la variable `ENVIO_REAL` con el valor `true`, en
   *Settings → Secrets and variables → Actions → Variables*.

Para volver a vista previa, basta con borrar esa variable o ponerla en `false`.

## Uso local

```bash
uv sync
uv run boletin --dry-run     # vista previa: deja el HTML en datos/ediciones/ y no toca el historial
uv run boletin               # genera y envía (exige las variables SMTP_*)
uv run pytest                # 237 pruebas, sin red
```

Una corrida completa tarda unos diez minutos: el Servicio Público de Empleo se pagina de a decenas de
páginas y después se comprueba, uno por uno, que los enlaces sigan vivos.

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
- Bajar el peso del correo: el HTML ronda los 300 KB y Gmail recorta a partir de unos 102 KB.
- Priorizar el eje cafetero: hoy el boletín trata igual una vacante de Armenia y una de Bogotá.
- Deduplicación aproximada entre portales, hoy exacta.
