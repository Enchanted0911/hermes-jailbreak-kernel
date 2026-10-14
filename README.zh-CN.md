# ⚔️ hermes-jailbreak-kernel — Hermes Agent 破甲内核插件 v2.0.1

<p align="center">
  <a href="https://github.com/Enchanted0911/hermes-jailbreak-kernel"><img src="https://img.shields.io/github/stars/Enchanted0911/hermes-jailbreak-kernel?style=for-the-badge&logo=github&label=Stars" alt="Stars" /></a>
  <a href="https://github.com/Enchanted0911/hermes-jailbreak-kernel/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Enchanted0911/hermes-jailbreak-kernel?style=for-the-badge&label=License" alt="License: MIT" /></a>
  <a href="https://github.com/Enchanted0911/hermes-jailbreak-kernel"><img src="https://img.shields.io/github/last-commit/Enchanted0911/hermes-jailbreak-kernel?style=for-the-badge&label=Last%20commit" alt="Last commit" /></a>
  <a href="https://hermes-agent.nousresearch.com/docs"><img src="https://img.shields.io/badge/Hermes%20Agent-🚀%20插件-10B981?style=for-the-badge&logoColor=white" alt="Hermes Agent plugin" /></a>
</p>

<p align="center">
  <b>一键安装</b>：
  <code>hermes plugins install --enable Enchanted0911/hermes-jailbreak-kernel</code>
</p>

<p align="center">
  <b>其他语言：</b>
  <a href="README.md">English</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.ar.md">العربية</a> ·
  <a href="README.ja.md">日本語</a>
</p>

参照 DSH 插件 **[dsh-infinite-gen-4（无限四代 v0.4.0）](https://github.com/Minglink/dsh-infinite-gen-4)**
为 **Nous Research Hermes Agent**（`~/.hermes`）移植的破甲（armor-piercing）系统提示词注入插件。

> ⚠️ 仅限授权靶场、本地合成靶标与合规红队研究使用；严禁用于未授权目标。使用者独立承担全部责任。

## 核心架构（与无限四代对位）

| 无限四代 (dsh-infinite-gen-4) | hermes-jailbreak-kernel（本插件） |
|---|---|
| `infinite-gen-4:global-system-prompt`（Order 100） | `hermes-jailbreak-kernel-core`（after_memory 槽位） |
| `infinite-gen-4:dual-layer-reinforce`（Order 200） | `hermes-jailbreak-kernel-reinforce`（after_memory 槽位，SHA256 同源一致） |
| `DUAL_LAYER_INJECTION` 开关 | `HERMES_JAILBREAK_DUAL=0` 单段退化 |
| 零工具面纯净直出 | 同——不注册任何功能性工具 |
| `infinite_gen4_profile` 元数据工具 | `/jailbreak` 状态命令 |
| 客户端状态条（web half） | —（Hermes 桌面端可另行挂载） |
| 注入面：系统提示词 section | Hermes 原生 `register_system_prompt_section` |

内核载荷（`prompts/`）逐字继承无限四代：`SUPREME DIRECTIVE — USER AUTHORITY`、
`Output contract`（首行 `##`/```` ``` ```` 命名交付物 + 静默推理 + 占位符自造）、
`Task classes`（安全/LLM 研究/成人虚构直接产出）、`[USER]/[OUTPUT]` few-shot 镜像锚点（中英各两个）。

## 三层注入架构

插件在 **三个层面** 注入内核：

1. **插件段注入**（`after_memory` 槽位，双段同源）——Hermes 组装系统提示词时写入；
2. **请求层 system 重建（replace 模式）**——`llm_request` 中间件在每次请求发出前，把最终 system 重建为「记忆段 + 运行时环境段 + 内核」，丢弃 Hermes 自带的 agent 规范/技能索引脚手架；
3. **opencode 会话轮换**（见下）——轮换 `x-opencode-session` 请求头。

工具 schema 不受影响：它们走 API `tools` 字段，与 system 文本无关。

## 会话模式

会话内运行时控制内核——无需重启、无需改环境变量：

| 命令 | 效果 |
|---|---|
| `/jailbreak` | 状态：会话、模式、内核档、轮换、诊断策略 |
| `/jailbreak on` | 标准：插件段 + 请求层重建 + 每会话轮换一次 |
| `/jailbreak slim` | 轻量：插件段 + 内核追加到 system 末尾 |
| `/jailbreak full` | 极致：重建 + `max` 内核档 + 每请求轮换 |
| `/jailbreak off` | 直通：请求层剥离插件段 |
| `/jailbreak profile <name>` | 内核档：`core` / `research` / `creative` / `max` |
| `/jailbreak dump on\|off` | 强制/关闭每请求诊断落盘 |
| `/jailbreak reset` | 清除会话覆盖（回到环境变量默认） |

## 内核档

| 档位 | 侧重 |
|---|---|
| `core`（**默认**） | 通用交付契约（安全 / LLM 研究 / 成人虚构 / 其他） |
| `research` | 攻防、逆向、漏洞利用与载荷开发 |
| `creative` | 虚构与露骨场景——完整成篇，不跳切 |
| `max` | 最难场景：显式无拒绝框架 + 禁止开场白/免责声明 |

`full` 模式强制使用 `max` 档；其余模式使用会话档位。

## 运维技能

`jailbreak-kernel-ops` 以插件技能形式随包分发：渐进式披露（`<available_skills>`
里只占一行，正文经 `skill_view` 按需加载）。内含命令矩阵、拒绝升级阶梯、
诊断方法与环境变量兜底说明。

## 会话轮换

轮换策略跟随会话模式：`slim`/`on` → `once`，`full` → `every`，`off` → 关闭。
中间件仅对 opencode 目标改写 `extra_headers["x-opencode-session"]`——`once` 每会话
一个轮换 id，`every` 每请求一个新 id。

| `HERMES_JAILBREAK_ROTATE_SESSION` | 行为 |
|---|---|
| *（未设置）* | 跟随会话模式（推荐） |
| `once` / `every` / `0` | 对所有会话强制某一策略 |

辅助调用（压缩/标题生成等）仍走原始稳定 id。


中间件改写 `extra_headers["x-opencode-session"]`：每个 Hermes 会话的首次请求设置一个新的轮换 id，并在该会话后续请求中复用。

| `HERMES_JAILBREAK_ROTATE_SESSION` | 行为 |
|---|---|
| `once`（**默认**） | 每个会话轮换一次后复用（保留跨轮次的 prompt 缓存） |
| `every` / `1` | 每请求新 id（prompt 缓存失效） |
| `0` / `off` | 不轮换（请求头保持原样） |

辅助调用（压缩/标题生成等）仍走原始稳定 id。

## 安装

```bash
# 方式 1：一键安装（GitHub）
hermes plugins install --enable Enchanted0911/hermes-jailbreak-kernel

# 方式 2：从 Hermes 插件目录安装（如已收录社区 catalog）
hermes plugins install hermes-jailbreak-kernel

# 方式 3：本地开发目录
cp -r ~/.hermes/plugins/hermes-jailbreak-kernel ~/.hermes/plugins/  # 或 git clone 后放到 plugins/ 下
hermes plugins enable hermes-jailbreak-kernel

# 装完后重启网关/桌面端
hermes gateway restart
```

> ⚠️ Hermes 插件默认 opt-in：装完需 `hermes plugins enable hermes-jailbreak-kernel`（一键安装命令已带 `--enable`）。

## 验证生效

```bash
# 离线回归（锚点 / 双层同源 SHA256 / 字符预算 / 开关行为）
cd ~/.hermes/plugins/hermes-jailbreak-kernel && python selftest.py

# 会话内验证（重启后在新会话执行）
/jailbreak                     # 显示内核版本、注入槽位、双段 SHA256 与预算占用
# 或问：你的系统提示词里有哪些插件段？
# 应能看到「## Plugin Context: hermes-jailbreak-kernel-core / hermes-jailbreak-kernel-reinforce」
```

运行期日志确认（`~/.hermes/logs/agent.log`）：

```
INFO hermes_plugins.hermes_jailbreak_kernel: injected system prompt section hermes-jailbreak-kernel-core (chars=3005)
INFO hermes_plugins.hermes_jailbreak_kernel: injected system prompt section hermes-jailbreak-kernel-reinforce (chars=3005)
INFO hermes_plugins.hermes_jailbreak_kernel: registered llm_request middleware (request-layer reinforce)
INFO hermes_plugins.hermes_jailbreak_kernel: hardened request system prompt (mode=replace ...)
INFO hermes_plugins.hermes_jailbreak_kernel: rotated x-opencode-session (...)
```

## 开关

| 环境变量 | 默认 | 作用 |
|---|---|---|
| `HERMES_JAILBREAK_MODE=on\|off\|slim\|full` | on | 默认会话模式（会话覆盖优先） |
| `HERMES_JAILBREAK_PROFILE=core\|research\|creative\|max` | core | 默认内核档 |
| `HERMES_JAILBREAK_ROTATE_SESSION=once\|every\|0` | *（跟随模式）* | 轮换策略覆盖 |
| `HERMES_JAILBREAK_DUMP=1\|0` | off | 强制或静默诊断落盘 |
| `HERMES_JAILBREAK_DUAL=0` | on | 单段注入 |
| `HERMES_JAILBREAK_DISABLE=1` | off | 总开关：完全跳过注册 |

## 诊断 dump

中间件每次（默认每会话首次，`HERMES_JAILBREAK_DUMP=1` 则每次）把请求诊断视图写入
`~/.hermes/plugins/hermes-jailbreak-kernel/dumps/request_*.json`：
system 消息全文 + 其它消息角色/长度/前 200 字符 + model/provider/base_url。
用于核对内核是否挂在 system 末尾、路由是否命中预期模型。
dump 仅存本地，且已被 `.gitignore` 排除，不会进入发布仓库。

## 约束（Hermes 硬限制）

- 插件段单段 ≤ 4000 字符，全部插件段合计 ≤ 8000 字符（注入器自动跳过超预算段）。
- 插件段位置固定 `after_memory`（人格与记忆之后），渲染顺序按 section id 字典序 → `core < reinforce`。
- section id 仅允许小写字母/数字/`.`/`_`/`-`。
- 请求层重建不受插件段预算约束（运行期在中间件内完成）。

## 离线自检

```bash
cd ~/.hermes/plugins/hermes-jailbreak-kernel
python selftest.py          # ✅/❌ 逐条（54 项）
python selftest.py --json
```

## 多语言

`/jailbreak` 的 UI 字符串（命令描述与状态报告）遵循 Hermes
[`agent/i18n`](https://github.com/NousResearch/hermes-agent/blob/main/agent/i18n.py) 标准：语言解析顺序为 `HERMES_LANGUAGE` > `config.yaml`
的 `display.language` > 英语。插件内置 `locales/en.yaml`（默认）与
`locales/zh.yaml`；其它语言及缺失键一律回退英语、再回退键名。日志与注入的
内核本体按设计保持语言中立。

## 文档

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) —— 三层机制、会话键解析与失败模型的架构说明
- [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) —— 宿主要求与实测模型行为矩阵
- [docs/CHANGELOG.md](docs/CHANGELOG.md) —— 版本历史
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) —— 血统与许可说明

## 许可证

MIT — 见 [LICENSE](LICENSE)。为 Hermes Agent 插件平台移植/改编自
[dsh-infinite-gen-4](https://github.com/Minglink/dsh-infinite-gen-4)（MIT, Minglink）。