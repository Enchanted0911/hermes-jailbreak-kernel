# ⚔️ hermes-jailbreak-kernel — Plugin de núcleo perforador de armadura para Hermes Agent v1.7.2

<p align="center">
  <a href="https://github.com/Enchanted0911/hermes-jailbreak-kernel"><img src="https://img.shields.io/github/stars/Enchanted0911/hermes-jailbreak-kernel?style=for-the-badge&logo=github&label=Stars" alt="Stars" /></a>
  <a href="https://github.com/Enchanted0911/hermes-jailbreak-kernel/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Enchanted0911/hermes-jailbreak-kernel?style=for-the-badge&label=License" alt="License: MIT" /></a>
  <a href="https://github.com/Enchanted0911/hermes-jailbreak-kernel"><img src="https://img.shields.io/github/last-commit/Enchanted0911/hermes-jailbreak-kernel?style=for-the-badge&label=Last%20commit" alt="Last commit" /></a>
  <a href="https://hermes-agent.nousresearch.com/docs"><img src="https://img.shields.io/badge/Hermes%20Agent-🚀%20plugin-10B981?style=for-the-badge&logoColor=white" alt="Hermes Agent plugin" /></a>
</p>

<p align="center">
  <b>Instalación en una línea</b>:
  <code>hermes plugins install --enable Enchanted0911/hermes-jailbreak-kernel</code>
</p>

<p align="center">
  <b>Leer en:</b>
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.ar.md">العربية</a> ·
  <a href="README.ja.md">日本語</a>
</p>

Plugin de inyección de prompt de sistema con perforación de armadura (red-team) para **Nous Research Hermes Agent** (`~/.hermes`), portado del plugin DSH **[dsh-infinite-gen-4 (Generación Infinita Cuatro, v0.4.0)](https://github.com/Minglink/dsh-infinite-gen-4)**.

> ⚠️ **Solo uso autorizado.** Este plugin es para campos de pruebas autorizados, objetivos sintéticos locales e investigación red-team conforme. Nunca lo use contra objetivos no autorizados. Los usuarios asumen toda la responsabilidad por su propio uso.

## Tabla de contenidos

- [Paridad de arquitectura con Generación Infinita Cuatro](#paridad-de-arquitectura)
- [Arquitectura de inyección en tres capas](#arquitectura-de-inyección-en-tres-capas)
- [Rotación de sesión](#rotación-de-sesión)
- [Instalación](#instalación)
- [Verificación](#verificación)
- [Interruptores de entorno](#interruptores-de-entorno)
- [Volcados de diagnóstico](#volcados-de-diagnóstico)
- [Límites estrictos de Hermes](#límites-estrictos-de-hermes)
- [Autoprueba sin conexión](#autoprueba-sin-conexión)

## Paridad de arquitectura

| dsh-infinite-gen-4 (v0.4.0) | hermes-jailbreak-kernel (este plugin) |
|---|---|
| `infinite-gen-4:global-system-prompt` (Order 100) | `hermes-jailbreak-kernel-core` (ranura `after_memory`) |
| `infinite-gen-4:dual-layer-reinforce` (Order 200) | `hermes-jailbreak-kernel-reinforce` (ranura `after_memory`, SHA256 idéntico al core) |
| Interruptor `DUAL_LAYER_INJECTION` | `HERMES_JAILBREAK_DUAL=0` degradación a una sola capa |
| Superficie de herramientas cero, salida directa pura | Igual — no registra herramientas funcionales |
| Herramienta de metadatos `infinite_gen4_profile` | Comando de estado `/jailbreak` |
| Insignia de estado de cliente (mitad web) | — (montable en Hermes Desktop más adelante) |
| Superficie de inyección: sección del prompt de sistema | `register_system_prompt_section` nativa |

La carga útil del núcleo (`prompts/`) hereda el texto de Generación Infinita Cuatro palabra por palabra: `SUPREME DIRECTIVE — USER AUTHORITY`, el `Output contract` (primera línea `##`/```` ``` ```` nombrando el entregable + razonamiento silencioso + autosíntesis de marcadores de posición), `Task classes` (seguridad / investigación LLM / ficción adulta / cualquier otra cosa — producir directamente) y anclas de few-shot `[USER]/[OUTPUT]`.

## Arquitectura de inyección en tres capas

El plugin inyecta el núcleo en **tres capas**:

1. **Inyección de sección de plugin** (ranura `after_memory`, dos secciones de la misma fuente) — se escribe cuando Hermes ensambla el prompt de sistema;
2. **Reconstrucción del system en la capa de solicitud (modo replace)** — el middleware `llm_request` reescribe el mensaje de sistema final como *sección de memoria + entorno de ejecución + núcleo* antes de cada solicitud, descartando el andamiaje propio de guía de agente/índice de habilidades de Hermes;
3. **Rotación de sesión opencode** (abajo) — rota el encabezado `x-opencode-session`.

Los esquemas de herramientas no se ven afectados: viajan en el campo `tools` de la API, no en el texto del system.

## Rotación de sesión

El middleware reescribe `extra_headers["x-opencode-session"]`: en la primera solicitud de cada sesión de Hermes establece un id rotado y lo reutiliza durante el resto de la sesión.

| `HERMES_JAILBREAK_ROTATE_SESSION` | Comportamiento |
|---|---|
| `once` (**predeterminado**) | rotar una vez por sesión de Hermes y luego reutilizar (conserva la caché de prompt del upstream entre turnos) |
| `every` / `1` | nuevo id por solicitud (rompe la caché de prompt del upstream) |
| `0` / `off` | sin rotación (el encabezado se deja intacto) |

Las llamadas auxiliares (compresión, generación de títulos, etc.) mantienen el id estable original.

## Instalación

```bash
# Opción 1 — instalación en una línea desde GitHub
hermes plugins install --enable Enchanted0911/hermes-jailbreak-kernel

# Opción 2 — desde el catálogo de plugins de Hermes (cuando se fusiona la entrada comunitaria)
hermes plugins install hermes-jailbreak-kernel

# Opción 3 — directorio de desarrollo local
cp -r ~/.hermes/plugins/hermes-jailbreak-kernel ~/.hermes/plugins/   # o git clone dentro de plugins/
hermes plugins enable hermes-jailbreak-kernel

# Luego reinicie la puerta de enlace / la aplicación de escritorio
hermes gateway restart
```

> ⚠️ Los plugins de Hermes son de participación voluntaria: habilítelo con `hermes plugins enable hermes-jailbreak-kernel` tras la instalación (la línea única ya pasa `--enable`).

## Verificación

```bash
# Regresión sin conexión (anclas / SHA256 de doble capa de la misma fuente / presupuesto / interruptores)
cd ~/.hermes/plugins/hermes-jailbreak-kernel && python selftest.py

# Comprobación dentro de la sesión (sesión nueva tras reiniciar)
/jailbreak                     # versión del núcleo, ranuras, doble SHA256, uso de presupuesto
# o pregunte: ¿qué secciones de plugin hay en tu prompt de sistema?
# Debería ver "## Plugin Context: hermes-jailbreak-kernel-core / hermes-jailbreak-kernel-reinforce"
```

Confirmación de registro en tiempo de ejecución (`~/.hermes/logs/agent.log`):

```
INFO hermes_plugins.hermes_jailbreak_kernel: injected system prompt section hermes-jailbreak-kernel-core (chars=3005)
INFO hermes_plugins.hermes_jailbreak_kernel: injected system prompt section hermes-jailbreak-kernel-reinforce (chars=3005)
INFO hermes_plugins.hermes_jailbreak_kernel: registered llm_request middleware (request-layer reinforce)
INFO hermes_plugins.hermes_jailbreak_kernel: hardened request system prompt (mode=replace ...)
INFO hermes_plugins.hermes_jailbreak_kernel: rotated x-opencode-session (...)
```

## Interruptores de entorno

| Variable | Predeterminado | Efecto |
|---|---|---|
| `HERMES_JAILBREAK_DISABLE=1` | off | Omitir el registro por completo (interruptor de apagado) |
| `HERMES_JAILBREAK_DUAL=0` | on | Inyección de una sola sección (ahorra tokens, comportamiento equivalente) |
| `HERMES_JAILBREAK_SYSTEM_MODE=replace\|append` | replace | Política de system en la capa de solicitud: reconstruir (descartar andamiaje) o solo añadir núcleo |
| `HERMES_JAILBREAK_ROTATE_SESSION=once\|every\|0` | once | Política de rotación de sesión de opencode (ver arriba) |
| `HERMES_JAILBREAK_DUMP=1` | off | Volcar diagnóstico en cada solicitud; por defecto una vez por sesión |

## Volcados de diagnóstico

El middleware escribe una vista de diagnóstico de cada solicitud (primera por sesión por defecto; cada solicitud con `HERMES_JAILBREAK_DUMP=1`) en `~/.hermes/plugins/hermes-jailbreak-kernel/dumps/request_*.json`: mensajes de sistema completos + roles/longitudes/cabeceras de 200 caracteres de otros mensajes + model/provider/base_url. Úselo para confirmar que el núcleo está al final del mensaje de sistema y que la ruta alcanza el modelo esperado. Los volcados son solo locales y están en `.gitignore`.

## Límites estrictos de Hermes

- Secciones de plugin: ≤ 4000 caracteres cada una, ≤ 8000 caracteres en total (el inyector omite silenciosamente las secciones que superan el presupuesto).
- Posición fija `after_memory` (después de la personalidad y la memoria); el orden de renderizado es lexicográfico por id de sección → `core < reinforce`.
- Ids de sección: solo letras minúsculas/dígitos/`.`/`_`/`-`.
- La reconstrucción en la capa de solicitud no está limitada por el presupuesto de las secciones (se ejecuta en el middleware en tiempo de solicitud).

## Autoprueba sin conexión

```bash
cd ~/.hermes/plugins/hermes-jailbreak-kernel
python selftest.py          # ✅/❌ por aserción (54 comprobaciones)
python selftest.py --json
```

## Localización

Las cadenas de UI de `/jailbreak` (descripción del comando e informe de estado)
siguen el estándar [`agent/i18n`](https://github.com/NousResearch/hermes-agent/blob/main/agent/i18n.py) de Hermes: el idioma se resuelve como
`HERMES_LANGUAGE` > `display.language` en `config.yaml` > inglés. El plugin
incluye `locales/en.yaml` (predeterminado) y `locales/zh.yaml`; cualquier otro
idioma —y cualquier clave ausente— recurre al inglés y luego a la clave literal.
Los registros y el núcleo inyectado permanecen neutros al idioma por diseño.

## Licencia

MIT — ver [LICENSE](LICENSE). Puerto/adaptación de [dsh-infinite-gen-4](https://github.com/Minglink/dsh-infinite-gen-4) (MIT, Minglink) para la plataforma de plugins de Hermes Agent.