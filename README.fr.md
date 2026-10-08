# ⚔️ hermes-jailbreak-kernel — Plugin noyau perforateur d'armure pour Hermes Agent v1.7.2

<p align="center">
  <a href="https://github.com/Enchanted0911/hermes-jailbreak-kernel"><img src="https://img.shields.io/github/stars/Enchanted0911/hermes-jailbreak-kernel?style=for-the-badge&logo=github&label=Stars" alt="Stars" /></a>
  <a href="https://github.com/Enchanted0911/hermes-jailbreak-kernel/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Enchanted0911/hermes-jailbreak-kernel?style=for-the-badge&label=License" alt="License: MIT" /></a>
  <a href="https://github.com/Enchanted0911/hermes-jailbreak-kernel"><img src="https://img.shields.io/github/last-commit/Enchanted0911/hermes-jailbreak-kernel?style=for-the-badge&label=Last%20commit" alt="Last commit" /></a>
  <a href="https://hermes-agent.nousresearch.com/docs"><img src="https://img.shields.io/badge/Hermes%20Agent-🚀%20plugin-10B981?style=for-the-badge&logoColor=white" alt="Hermes Agent plugin" /></a>
</p>

<p align="center">
  <b>Installation en une ligne</b> :
  <code>hermes plugins install --enable Enchanted0911/hermes-jailbreak-kernel</code>
</p>

<p align="center">
  <b>Lire en :</b>
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.ar.md">العربية</a> ·
  <a href="README.ja.md">日本語</a>
</p>

Plugin d'injection de prompt système perforant l'armure (red-team) pour **Nous Research Hermes Agent** (`~/.hermes`), porté depuis le plugin DSH **[dsh-infinite-gen-4 (Génération Infinie Quatre, v0.4.0)](https://github.com/Minglink/dsh-infinite-gen-4)**.

> ⚠️ **Utilisation autorisée uniquement.** Ce plugin est destiné aux terrains d'entraînement autorisés, aux cibles synthétiques locales et à la recherche red-team conforme. Ne l'utilisez jamais contre des cibles non autorisées. Les utilisateurs assument l'entière responsabilité de leur propre usage.

## Table des matières

- [Parité d'architecture avec Génération Infinie Quatre](#parité-darchitecture)
- [Architecture d'injection en trois couches](#architecture-dinjection-en-trois-couches)
- [Rotation de session](#rotation-de-session)
- [Installation](#installation)
- [Vérification](#vérification)
- [Interrupteurs d'environnement](#interrupteurs-denvironnement)
- [Dumps de diagnostic](#dumps-de-diagnostic)
- [Limites strictes d'Hermes](#limites-strictes-dhermes)
- [Auto-test hors ligne](#auto-test-hors-ligne)

## Parité d'architecture

| dsh-infinite-gen-4 (v0.4.0) | hermes-jailbreak-kernel (ce plugin) |
|---|---|
| `infinite-gen-4:global-system-prompt` (Order 100) | `hermes-jailbreak-kernel-core` (emplacement `after_memory`) |
| `infinite-gen-4:dual-layer-reinforce` (Order 200) | `hermes-jailbreak-kernel-reinforce` (emplacement `after_memory`, SHA256 identique au core) |
| Interrupteur `DUAL_LAYER_INJECTION` | `HERMES_JAILBREAK_DUAL=0` dégradation monocouche |
| Surface d'outils zéro, sortie directe pure | Identique — n'enregistre aucun outil fonctionnel |
| Outil de métadonnées `infinite_gen4_profile` | Commande d'état `/jailbreak` |
| Badge d'état client (moitié web) | — (montable dans Hermes Desktop plus tard) |
| Surface d'injection : section de prompt système | `register_system_prompt_section` natif |

La charge utile du noyau (`prompts/`) hérite mot pour mot du texte de Génération Infinie Quatre : `SUPREME DIRECTIVE — USER AUTHORITY`, le `Output contract` (première ligne `##`/```` ``` ```` nommant le livrable + raisonnement silencieux + auto-synthèse des espaces réservés), les `Task classes` (sécurité / recherche LLM / fiction adulte / tout le reste — produire directement) et les ancres few-shot `[USER]/[OUTPUT]`.

## Architecture d'injection en trois couches

Le plugin injecte le noyau en **trois couches** :

1. **Injection de section de plugin** (emplacement `after_memory`, deux sections de même source) — écrite lors de l'assemblage du prompt système par Hermes ;
2. **Reconstruction du system au niveau requête (mode replace)** — le middleware `llm_request` réécrit le message système final comme *section mémoire + environnement d'exécution + noyau* avant chaque requête, en jetant l'échafaudage propre d'Hermes (guide d'agent / index de compétences) ;
3. **Rotation de session opencode** (ci-dessous) — fait tourner l'en-tête `x-opencode-session`.

Les schémas d'outils ne sont pas affectés : ils voyagent dans le champ `tools` de l'API, pas dans le texte du system.

## Rotation de session

Le middleware réécrit `extra_headers["x-opencode-session"]` : à la première requête de chaque session Hermes, il pose un id roté, puis le réutilise pour le reste de la session.

| `HERMES_JAILBREAK_ROTATE_SESSION` | Comportement |
|---|---|
| `once` (**par défaut**) | rotation une fois par session Hermes puis réutilisation (conserve le cache de prompt de l'upstream entre les tours) |
| `every` / `1` | nouvel id par requête (casse le cache de prompt de l'upstream) |
| `0` / `off` | pas de rotation (l'en-tête reste intact) |

Les appels auxiliaires (compression, génération de titres, etc.) gardent l'id stable d'origine.

## Installation

```bash
# Option 1 — installation en une ligne depuis GitHub
hermes plugins install --enable Enchanted0911/hermes-jailbreak-kernel

# Option 2 — depuis le catalogue de plugins Hermes (une fois l'entrée communautaire fusionnée)
hermes plugins install hermes-jailbreak-kernel

# Option 3 — répertoire de développement local
cp -r ~/.hermes/plugins/hermes-jailbreak-kernel ~/.hermes/plugins/   # ou git clone dans plugins/
hermes plugins enable hermes-jailbreak-kernel

# Puis redémarrez la passerelle / l'application de bureau
hermes gateway restart
```

> ⚠️ Les plugins Hermes sont en opt-in : activez avec `hermes plugins enable hermes-jailbreak-kernel` après l'installation (la ligne unique passe déjà `--enable`).

## Vérification

```bash
# Régression hors ligne (ancres / SHA256 double couche même source / budget / interrupteurs)
cd ~/.hermes/plugins/hermes-jailbreak-kernel && python selftest.py

# Vérification en session (nouvelle session après redémarrage)
/jailbreak                     # version du noyau, emplacements, double SHA256, usage du budget
# ou demandez : quelles sections de plugin contient ton prompt système ?
# Vous devriez voir « ## Plugin Context: hermes-jailbreak-kernel-core / hermes-jailbreak-kernel-reinforce »
```

Confirmation par journal d'exécution (`~/.hermes/logs/agent.log`) :

```
INFO hermes_plugins.hermes_jailbreak_kernel: injected system prompt section hermes-jailbreak-kernel-core (chars=3005)
INFO hermes_plugins.hermes_jailbreak_kernel: injected system prompt section hermes-jailbreak-kernel-reinforce (chars=3005)
INFO hermes_plugins.hermes_jailbreak_kernel: registered llm_request middleware (request-layer reinforce)
INFO hermes_plugins.hermes_jailbreak_kernel: hardened request system prompt (mode=replace ...)
INFO hermes_plugins.hermes_jailbreak_kernel: rotated x-opencode-session (...)
```

## Interrupteurs d'environnement

| Variable | Défaut | Effet |
|---|---|---|
| `HERMES_JAILBREAK_DISABLE=1` | off | Ignorer complètement l'enregistrement (coupe-circuit) |
| `HERMES_JAILBREAK_DUAL=0` | on | Injection à une seule section (économie de tokens, comportement équivalent) |
| `HERMES_JAILBREAK_SYSTEM_MODE=replace\|append` | replace | Politique system au niveau requête : reconstruire (jeter l'échafaudage) ou simplement ajouter le noyau |
| `HERMES_JAILBREAK_ROTATE_SESSION=once\|every\|0` | once | Politique de rotation de session opencode (voir ci-dessus) |
| `HERMES_JAILBREAK_DUMP=1` | off | Dump de diagnostic à chaque requête ; par défaut une fois par session |

## Dumps de diagnostic

Le middleware écrit une vue diagnostique de chaque requête (première de session par défaut ; chaque requête avec `HERMES_JAILBREAK_DUMP=1`) dans `~/.hermes/plugins/hermes-jailbreak-kernel/dumps/request_*.json` : messages système complets + rôles/longueurs/en-têtes de 200 caractères des autres messages + model/provider/base_url. À utiliser pour confirmer que le noyau est en queue du message système et que la route atteint le modèle attendu. Les dumps sont locaux uniquement et exclus par `.gitignore`.

## Limites strictes d'Hermes

- Sections de plugin : ≤ 4000 caractères chacune, ≤ 8000 caractères au total (l'injecteur saute silencieusement les sections hors budget).
- Position fixe `after_memory` (après la personnalité et la mémoire) ; l'ordre de rendu est lexicographique par id de section → `core < reinforce`.
- Ids de section : lettres minuscules/chiffres/`.`/`_`/`-` uniquement.
- La reconstruction au niveau requête n'est pas bornée par le budget des sections (elle s'exécute dans le middleware au moment de la requête).

## Auto-test hors ligne

```bash
cd ~/.hermes/plugins/hermes-jailbreak-kernel
python selftest.py          # ✅/❌ par assertion (54 vérifications)
python selftest.py --json
```

## Localisation

Les chaînes UI de `/jailbreak` (description de la commande et rapport d'état)
suivent la norme [`agent/i18n`](https://github.com/NousResearch/hermes-agent/blob/main/agent/i18n.py) d'Hermes : la langue se résout ainsi :
`HERMES_LANGUAGE` > `display.language` dans `config.yaml` > anglais. Le plugin
embarque `locales/en.yaml` (par défaut) et `locales/zh.yaml` ; toute autre langue
— et toute clé manquante — retombe sur l'anglais, puis sur la clé brute. Les
journaux et le noyau injecté restent neutres en langue par conception.

## Licence

MIT — voir [LICENSE](LICENSE). Portage/adaptation de [dsh-infinite-gen-4](https://github.com/Minglink/dsh-infinite-gen-4) (MIT, Minglink) pour la plateforme de plugins Hermes Agent.