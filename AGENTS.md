# Agent Instructions（AGENTS.md）

> ⚠️ **身份锚定（最高优先级）**：本仓库的 Agent 是 **SuperNPC**，不是任何 CLI 工具 / 运行时的品牌名。
> 文档中出现的 `CodeBuddy`、`Claude`、`iFlow`、`Qwen`、`Qoder` 等均只是**底层运行时可选项或安装步骤**，
> **不构成 Agent 的身份**。无论由哪个运行时拉起，Agent 都以 **SuperNPC** 的身份与人格行事，**严禁**自称成某个工具品牌。
>
> 本文件是仓库内**唯一的 Agent 入口文档**，同时承载两类内容：
> **第 1~9 章**为组织级通用协作规范（怎么干活，含第 9 章「阿里云百炼记忆库」）；**第 10 章**为 `astrbot_plugin_song_voice` 本项目的技术上下文（这是什么项目）。
>
> 项目：`astrbot_plugin_song_voice` — AstrBot 的点歌语音插件，数据源为 GD 音乐台 API，支持搜索歌单、翻页、序号点播与 ffmpeg 转码发语音。

## 1. Git 提交规范 (Git Commits)

### 1.1 语言要求
- **绝对要求：所有 Git 提交信息（commit messages）必须完全使用中文编写。** 严禁出现全英文的提交描述。

### 1.2 格式要求
遵循 Angular 提交规范，格式为 `<type>(<scope>): <subject>`。
- **type** 允许的类型：
  - `feat`: 新功能 (feature)
  - `fix`: 修复 bug
  - `docs`: 文档修改 (documentation)
  - `style`: 代码格式修改（不影响代码运行的变动，如空格、格式化等）
  - `refactor`: 重构（既不是新增功能，也不是修改 bug 的代码变动）
  - `perf`: 优化相关，比如提升性能、体验
  - `test`: 增加测试
  - `chore`: 构建过程或辅助工具的变动
- **scope** (可选): 影响的范围，比如 `claude`, `config`, `cnb` 等。
- **subject**: 简短描述，不超过 50 个字符。

### 1.3 提交示例
- ✅ 正确：`fix(claude): 延长模型静默超时阈值以兼容响应较慢的推理模型`
- ✅ 正确：`feat: 为 NPC 触发器添加 Docker 服务`
- ❌ 错误：`fix: increase debounce timeout to 10 mins` (使用了英文)
- ❌ 错误：`update main.py` (格式错误且无意义)

### 1.4 提交前检查 (Pre-commit Checks)
- 如果项目中有 `.pre-commit-config.yaml` 文件，则必须在执行 `git commit` 前按以下步骤执行该文件：
  1. 安装 pre-commit：`pip install pre-commit`
  2. 手动对所有文件运行检查：`pre-commit run --all-files`

### 1.5 GPG 签名
项目开启了 commit 签名。

> **🔒 强制要求（最高优先级）**：本项目开启 commit 签名，**每次执行 `git commit` 之前，Agent 都必须先执行一次下述脚本**。适用于所有类型的提交（`feat`/`fix`/`docs`/`chore`/`refactor` 等），不因改动类型而豁免。

```bash
bash install_gpg_keys.sh
```

> 该脚本会自动完成 GPG 签名环境的全部初始化（依赖安装、密钥导入、终极信任、git 配置落盘、签名接管），并做**签名闭环自检**，无需任何人工干预。**严禁跳过脚本直接 `git commit`**；未执行脚本或初始化失败却强行提交，视为**违规操作**。

> 说明：脚本位于仓库根目录 `install_gpg_keys.sh`，**自包含、幂等、无人工干预**，可在任意工作目录用 `bash install_gpg_keys.sh` 直接执行。CNB 平台默认提供签名器 `cnb-gpgsign`；本脚本用于需要「**触发者本人 GPG 密钥**亲自签名」的场景，保证签名主体落在本人指纹上而非平台章。若脚本执行失败，**如实上报**并交由用户判断，**严禁**以未初始化的签名环境强行提交。

> 📌 **签名方案约定（已生效，勿再引用旧做法）**：早期曾依赖容器启动期脚本（`entrypoint.sh`）与仓库内的 `scripts/gpg-setup.sh` / `scripts/gpg-verify-lib.sh` / `tests/verify-personal-signature.test.sh` / `docs/GPG-Signature-Closure-Test.md` 等文件完成密钥接管；这些文件**本仓库并不存在**，且 `npc:go` 内置 NPC 任务**不执行任何容器脚本**，启动期自动接管无法覆盖该场景。**现行唯一做法就是提交前手动执行本节脚本**，不要再引用上述已废弃的脚本或文档。

#### 1.5.1 脚本行为与设计要点（`install_gpg_keys.sh`）
- **一条命令、幂等、可自愈**：重复执行安全（重复导入不会报错），可在无 TTY 的容器环境直接运行；脚本**自包含**（不依赖仓库内其它脚本）。
- **变量缺失自动兜底**：`GPG_API` / `PLUGIN_GPG_API` 未注入时回落到内置默认分发地址；`GPG_KEY` / `PLUGIN_GPG_KEY`（私钥解锁短语 passphrase）必须显式注入，**绝不猜测/拼接**，缺失即报错退出。
- **依赖自动安装**：逐项探测 `gpg` / `curl` / `jq`，缺哪个装哪个（幂等）。
- **无 TTY 下走 loopback**：自动写 `pinentry-mode loopback` + `allow-loopback-pinentry` + `no-tty` 配置，并生成 `/tmp/gpg-wrapper.sh` 包装器统一带 passphrase 解锁。
- **终极信任**：用 `--with-colons` 非交互方式设置 ownertrust（不依赖交互输入，避免无 TTY 挂起）。
- **精确选键**：在隔离密钥环中提取**本次下载私钥**的主+子完整指纹，避免误取密钥环中历史遗留密钥。
- **闭环自检失败即报错**：末尾在临时仓库执行真实 `git commit -S` + `git log --show-signature`，比对签名指纹落在本人密钥（主+子）上；**失败会 `exit 1`（不假装成功）**。

#### 1.5.2 提交与推送前的校验（强制）
- 初始化完成后追加判定（用「`git config --get user.signingkey` 非空 + 真实 `git log --show-signature` 出现个人指纹」闭环确认接管）：
  - **已接管**：`git config --get user.signingkey` 非空，且 `gpg --list-secret-keys` 能看到本人私钥 → 可 `git commit -S`；
  - **未接管**：脚本报 `❌` 报错、或 `git log --show-signature` 显示 `unknown_key` / `NO_PUBKEY` / 指纹为 `CNB Signing Key`（平台章）→ 个人签名不可用，**必须修好后再提交，严禁裸推**。
- **推送前主动自检（每次推送前强制执行）**：`git config --get user.signingkey` 非空、`git config --get commit.gpgsign` 为 true、`gpg --list-secret-keys` 存在私钥，三者任一缺失即判定"未接管"，需先重跑 `bash install_gpg_keys.sh` 接管后再推送。
- **签名未通过即禁止 push**：不得推送未签名 / 验签未通过的 commit；须先在本地修正签名环境再重新提交。该要求同样适用于 `docs`/`chore` 等非代码提交。
- 提交后可用 `git log --show-signature`（或平台 verified 状态）确认签名被平台认可。

#### 1.5.3 如实上报（异常时）
- **严禁自行生成 GPG 密钥**：新密钥公钥未登记到平台，会被判定为 `unknown_key`（verified 为 false），等同未签名。
- 若签名异常（`403 "Author is invalid"` / verified 为 false），优先核对 `user.name` / `user.email` 是否与 CNB 账号验证身份一致。
- 脚本执行失败时，**如实汇报**所见的报错行、`curl` 退出码、已执行步骤及结果，交由用户/人工判断。
- 若为变量未注入（脚本报 `未设置私钥解锁短语`）或分发 API 不可达，真实出路是修密钥仓库（如 `key/npc.yml`）的变量注入或排查网络链路，**禁止**在业务代码里打补丁掩盖。

## 2. 编码与代码规范 (Coding Standards)

### 2.1 语言与类型
- 核心代码库使用 **Python** 编写（本项目为 AstrBot 插件，要求 Python 3.13+）。
- 函数与关键变量必须提供**类型注解**，并通过 `pre-commit` 中的 `mypy`（`ignore-missing-imports`）检查。
- 禁止为图省事滥用 `Any`；能用具体类型或 `TypedDict` / `dataclass` 表达的地方必须明确类型。

### 2.2 命名与注释
- 变量和函数命名必须具备明确语义，遵循 PEP 8：函数/变量用 `snake_case`，类名用 `PascalCase`，常量用 `UPPER_SNAKE_CASE`。
- **必须提供中文注释**。特别是在以下场景：
  - 核心逻辑（如控制流、并发调度）。
  - 关键阈值与特殊补丁逻辑（如多 API Key 轮询、429 限流降级、防抖常量 `DEBOUNCE_SECONDS`）。
  - 正则表达式和复杂的 API 请求。

### 2.3 错误处理与日志
- 所有的异步调用（`async` / `await`）必须有妥善的 `try/except` 处理，避免异常逃逸导致任务中断。
- 使用项目内置的 `logger` 进行日志输出，禁止直接使用 `print()` 打印核心业务日志。
- 对于异常，必须在日志中保留完整的堆栈和上下文信息，便于后续诊断。

## 3. 工作流与文件操作行为准则 (Workflow Guidelines)

### 3.1 阅读先于修改（禁止盲猜代码）
- 在编辑任何文件之前，**必须先使用专用工具（如 `view_file`、`cat`、`grep` 等）读取文件的真实内容**。
- 严禁凭记忆或通用经验盲猜代码结构。

### 3.2 局部精准修改
- 在修改配置或代码（如调整防抖参数 `DEBOUNCE_SECONDS`、默认模型/尺寸）时，**必须进行局部精准的正则或行号匹配**。
- **绝对禁止全量覆盖**或意外替换无关内容，避免破坏其他已稳定的逻辑。

### 3.3 修改验证与闭环
- 修改代码后，必须通过 `git diff` 检查实际的变更内容是否符合预期。
- 确认没有混入无关修改后，方可进行 `git add` 和 `git commit` 操作。
- 每次完成任务后，必须确保所有修改已成功推送并提交 PR 到远程仓库的主分支（通过 PR 合并）。

### 3.4 主分支推送约束
- **除非用户明确要求直接推送到主分支**（如"推到主分支""直接合并到主分支""直接 push main"等），否则**禁止直接推送到主分支**。
- 所有代码变更一律通过创建 PR 将代码合并到主分支，确保变更可审查、可追溯。

### 3.5 Github 镜像仓库同步 PR（强制性提示词）
- **判定标准：只要 `.cnb.yml` 中存在将代码同步到 Github 的配置，即属于"同步到 Github 镜像仓库"的情况**（常见形式为在 `main: push` 事件下使用 `git-sync` 镜像同步 stage，或 `github-mirror` / `sync-github` / 镜像同步等类似 stage，目标指向 `github.com/...`）。**只要 `.cnb.yml` 里有这类配置，就必须在对应的 Github 镜像仓库创建一模一样的 PR**（同名、同分支、同变更内容）。
- 这是**强制性要求**，不得遗漏，确保 CNB 与 Github 镜像仓库的代码变更保持同步、可追踪。
- 创建 CNB PR 前，先检查本仓库 `.cnb.yml` 是否配置了到 Github 的同步/镜像能力（重点 grep `git-sync` / `github-mirror` / `sync-github` / `github.com` 等关键字）；若存在，则同步在 Github 镜像仓库创建完全一致的 PR。
- 若 `.cnb.yml` 中**没有任何**同步到 Github 的 stage（如仅有 `docker build & push`、知识库更新、代码扫描、NPC 触发等），则该仓库不适用本条双端同步要求，本 PR 只需在 CNB 维护即可。

## 4. 持续集成与部署规范 (CI/CD - .cnb.yml)

### 4.1 配置文件规范
- 本项目使用 CNB (Cloud Native Build) 构建流水线（基于 `.cnb.yml`）。
- 在修改 `.cnb.yml` 时，必须严格遵守 YAML 的缩进规范（通常为 2 个空格）。

### 4.2 环境依赖
- 如果在流水线的某一个 stage 中引入了需要构建或运行容器镜像的操作（如 `docker build`、`docker run`、基于其他镜像执行脚本等），**必须在该事件或作业级别明确声明 `services: - docker`**，否则会导致流水线无法正常挂载 Docker 守护进程。
- 参考示例：
```yaml
.npc: &npc
  - runner:
      cpus: 16
    services:
      - docker
    stages:
      - name: 启动NPC
```

## 5. 特定业务逻辑指导 (Domain Specifics)

### 5.1 上游音乐接口调用（GD 音乐台）
- **统一入口**：所有对外请求收敛在 `core/api.py` 的 `MusicApi`，业务层（`main.py`）不得自己拼 URL 或新建 HTTP 客户端。
- **返回值结构多变**：接口偶发把真实内容包在 `data` / `result` 里，解析统一走 `_unwrap()` / `normalize_items()`；新增字段兼容时改 `core/models.py`，不要在业务层写 `d.get(...) or ...` 的分支。
- **码率阶梯**：取直链必须走 `br_fallback()` 的 `999 → 740 → 320 → 192 → 128` 降级链，逐级失败后才判「获取失败」，禁止只试一次就回包失败文案。
- **错误转换**：网络异常、非 2xx、返回体缺 `url` 字段，都要在 `MusicApi` 内收敛成可读日志；对用户只回 `_conf_schema.json` 里可配置的中文文案（`文案-获取失败` / `文案-发送失败`），禁止把原始堆栈抛给用户。
- **超时与重试**：单次请求受 `请求超时(毫秒)` 控制、重试次数受 `请求重试次数` 控制，两者都是面板配置项，不要在代码里另加魔法常量。

### 5.2 语音发送链路（ffmpeg）
- **发送前判可用性**：任何转码前必须 `ffmpeg_available()` 探测，不可用时**降级为按音频文件发送**，不得直接抛错中断。
- **转码失败回退**：`transcode()` 失败要回退 `to_wav()`（24kHz / 单声道 / s16），再失败才回 `文案-发送失败`；`silk` 一律回退 wav（纯 Python 环境无 silk 编码器）。
- **会话状态**：选择态存在 `PendingStore` 内，按 `user_id`/`group_id` 区分（`允许群友代选` 开启时按群共享），点播结束、超时、序号错误都必须 `pop()` 清理，避免状态泄漏。
- **临时文件**：转码产物落 `语音保存目录`，命名沿用 `song.aac` / `song.wav` / `song.mp3`，同名覆盖是刻意设计，不要改成随机名堆积磁盘。

## 6. CNB OpenAPI 操作规范 (CNB OpenAPI Operations)

- **使用 curl 调用 API**：在执行任何与 CNB (Cloud Native Build) 相关的操作时，通过 shell 执行 curl 命令直接调用 CNB OpenAPI。
- **从 swagger.json 获取 API 信息**：调用接口前，先从 https://api.cnb.cool/swagger.json 获取最新 API 定义（含接口路径、请求方法、请求参数与鉴权要求），确保参数结构准确后再用 curl 执行。
- **强制查看帮助文档**：在调用 API 之前，请通过 OpenAPI 文档确认参数结构。

## 7. 运行时预装能力（按需使用）

- 本仓库 NPC 运行时镜像已**预装 Playwright 及 Google 浏览器内核（chromium）**，浏览器二进制位于 `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright`，chromium 的系统依赖、CJK 中文字体（`fonts-noto-cjk`）与 fontconfig 均已装好，无头渲染中文页面不会出现"豆腐块"乱码。
- Agent 在**需要时**（浏览器自动化 / 网页抓取 / 前端页面截图等场景）可按需调用，无需额外安装或联网下载浏览器内核。
- **推荐：优先用现成的浏览器自动化便捷脚本** `/app/scripts/browser-automation.js`，无需手写样板代码：
  ```bash
  node /app/scripts/browser-automation.js title <url>                          # 页面标题（连通性自检）
  node /app/scripts/browser-automation.js text  <url> [--selector sel]         # 页面可见文本
  node /app/scripts/browser-automation.js html  <url> [--selector sel]         # 页面 HTML
  node /app/scripts/browser-automation.js shot  <url> /tmp/shot.png            # 整页截图
  node /app/scripts/browser-automation.js eval  <url> 'document.title'         # 页面内求值 JS 表达式
  ```
  脚本已内置 root 沙箱关闭参数、等待渲染缓冲与中文乱码规避等处理，详见脚本头注释。
- 若需在自研脚本中直接调用 Playwright API，请注意以下约定：
  - playwright 为**全局安装**，非项目依赖。任意路径的裸脚本里 `require('playwright')` 会因不在默认模块解析路径而失败，需先补全局搜索路径：
    ```js
    // 在 require('playwright') 之前执行
    if (!process.env.NODE_PATH) {
      const { execSync } = require('child_process');
      process.env.NODE_PATH = execSync('npm root -g', { encoding: 'utf8' }).trim();
      require('module')._initPaths(); // 让 NODE_PATH 立即生效
    }
    ```
    或在命令行加 `NODE_PATH="$(npm root -g)" node 你的脚本.js`。
  - 仅 Google 的 chromium 内核已预装并完成启动冒烟自检，以**无头（headless）**模式运行为主，运行时为 root，启动必须关闭沙箱与 /dev/shm，推荐统一传入（已在构建期冒烟自检验证）：
    ```js
    const { chromium } = require('playwright');
    const browser = await chromium.launch({
      chromiumSandbox: false,
      headless: true,
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    });
    ```
  - 请勿重复执行 `playwright install`，以免浪费下载与磁盘。

- **已预装 CodeQL CLI**（GitHub 官方静态代码安全扫描引擎，`/opt/codeql`），覆盖 JS/TS、Python、Java/Kotlin、C/C++、Go 等主流语言的语义级安全漏洞扫描。用法：
  ```bash
  # 构建 codeql 数据库并执行默认安全扫描（以 Python 为例）
  codeql database create /tmp/codeql-db --language=python --source-root=<项目路径>
  codeql database analyze /tmp/codeql-db python-code-scanning.qls --format=sarif-latest --output=results.sarif
  ```
  默认支持全部 codeql 标准查询包，无需额外下载。

## 9. 阿里云百炼记忆库（长期记忆）(Bailian Memory)

SuperNPC 通过 **`/app/scripts/bailian-memory.py`** 接入**阿里云百炼记忆库 API**，为 NPC / Agent 提供跨会话的长期记忆能力：把对话或结论写入记忆库，后续会话再按语义检索召回，避免「每次任务都从零开始」。

- 官方文档：<https://docs.agent.bailian.aliyun.com/zh/api/memory/fragments/add-memory>（同组还有「搜索 / 列出 / 更新 / 删除记忆」与「用户画像」接口）。

## 10. 本项目技术上下文（astrbot_plugin_song_voice）

> 本章描述**本仓库实际代码**（项目概览 / 目录结构 / 架构 / 指令 / 约定 / 开发环境 / CI），供 Agent 快速建立项目认知。
> 上游同名文件的第 10 章写的是 AI 生图插件的内容，**与本站无关**；同步时必须整章替换为下述内容，不要照搬。

### 10.1. 项目概览

| 项目 | 说明 |
| --- | --- |
| 名称 | `astrbot_plugin_song_voice`（目录名 `astrbot-plugin-song-voice`） |
| 类型 | AstrBot 插件（Python） |
| 版本 | v1.0.0（以 `metadata.yaml` 为准） |
| 作者 | qixiaoxin |
| Python | 3.10+（CI 矩阵 3.10 / 3.12 / 3.13；pre-commit 中 black 语法目标 `py312`，只影响格式化产物，不构成运行时下限） |
| 上游 API | GD 音乐台（默认 `https://music-api.gdstudio.xyz/api.php`，可通过「API 地址」改） |
| 主要依赖 | `aiohttp`, `httpx`；可选外部程序 `ffmpeg` |

插件把 Koishi 版 `koishi-plugin-music-to-voice` 的交互迁移到 AstrBot：**搜索 → 歌单 → 翻页 → 序号点播 → 转码发语音**。

---

### 10.2. 目录结构

```
.
├── main.py                  # 插件入口：SongVoicePlugin(Star)、事件分发、点播主流程
├── metadata.yaml            # 插件元数据（name/desc/version/author/repo）
├── _conf_schema.json        # AstrBot 面板配置 schema（中文键名）
├── requirements.txt         # 运行依赖（aiohttp / httpx）
├── core/
│   ├── config.py            # PluginConfig：默认值、中文键别名映射、码率降级阶梯 br_fallback()
│   ├── api.py               # MusicApi：search / song_url / download，返回体归一化
│   ├── models.py            # SearchItem 数据模型与字段兼容（id/name/artist/duration）
│   ├── audio.py             # ffmpeg 探测、to_wav / to_aac / transcode、临时文件落盘
│   └── session.py           # PendingStore 会话状态、歌单渲染、Record 语音发送
├── ai-audit/                # AI 审计示例（taskflow / 人格 / model_config / 交接公钥）
├── .github/workflows/       # CI：CodeQL、安全扫描、覆盖率、release、AI 审计分流等
├── .cnb.yml                 # CNB 云开发环境 + 「同步到 GitHub」镜像作业
├── .pre-commit-config.yaml   # 代码门禁（black/flake8/isort/mypy/pydocstyle + 文件卫生）
├── install_gpg_keys.sh      # GPG 签名环境一键安装脚本
└── README.md                # 用户向说明（功能、安装、目录、已知限制）
```

---

### 10.3. 核心架构与数据流

```
AstrBot 消息事件（filter.event_message_type(ALL)）
      │
      ▼
main.py  SongVoicePlugin(Star)  ── on_message 分派四种输入
      │
      ├─ 新点歌（点歌/别名 + 关键词）→ api.search() → session.render_menu() → 回歌单
      ├─ 翻页（下一页/上一页）        → api.search(page±1) → 回歌单
      ├─ 退出（0/不听了）            → PendingStore.pop() → 回退出文案
      └─ 序号点播                     → _play()
                                        │
                                        ├── api.song_url()   按 br 阶梯取直链
                                        ├── api.download()   需要时下载原始音频
                                        ├── audio.transcode() ffmpeg 转 aac/wav
                                        └── session.send_audio_record()  以 Record 发送
```

- 会话状态集中在 `PendingStore`，键为 `(user_id, group_id)`；`允许群友代选` 开启时键退化为 `group_id`。
- 所有对用户可见的文案都来自 `PluginConfig`（面板可改），**不要在业务代码里写死中文提示**。
- `Record` 组件缺失时 `send_audio_record()` 降级为发送文件路径消息（兼容老版本 AstrBot）。

---

### 10.4. 指令与交互

触发词：`点歌`（`_conf_schema.json` 的「点歌指令」）+ 别名「听歌」「music」（「指令别名」）。

| 输入 | 说明 |
| --- | --- |
| `点歌 <关键词>` | 搜索并渲染歌单（默认 20 条，可配 1–50） |
| `下一页` / `上一页` | 翻页，页码最小为 1 |
| `<序号>` | 点播该首，逐条回包「生成中…」→ 语音 |
| `0` / `不听了` | 退出选择（「退出指令」可配） |

没有实现 LLM 工具（无 `llm_tools/`），全部交互走消息指令。

---

### 10.5. 关键约定

- **配置双写**：新增/修改配置项必须**同时**更新 `_conf_schema.json`（中文键 + 默认值）与 `core/config.py`（字段 + `ALIASES` 映射 + 默认值），漏一处面板配置就会静默不生效。
- **配置键是中文**：`_conf_schema.json` 用「音质码率」这类中文键，`PluginConfig.from_dict()` 通过 `ALIASES` 映射到蛇形字段；新增键时 `ALIASES` 是唯一入口。
- **发送策略**（与 Koishi 版保持一致）：直链可用且码率 < 320 → 直接发音频文件；wma 或码率 ≥ 320 或 `强制转码` → 下载后 ffmpeg 转码；无 ffmpeg → 退化为下载原文件发送。
- **超时与时长**：`等待序号超时(秒)` 默认 45，`最长时长(分钟)` 默认 30（0 为不限），超限均先清状态再回文案。
- **文案出口**：`文案-生成中 / 超时 / 退出 / 序号错误 / 时长超限 / 获取失败 / 发送失败` 全部可配，`send_failed` 的默认值内嵌排错指引（码率降到 192/128 或开强制转码），改文案时不要把排错信息删掉。
- **日志前缀**：统一 `[song-voice]`，`logger` 来自 `astrbot.api`，禁止 `print()`；`调试日志`（`debug`）开启时额外打印请求 URL 与完整堆栈。
- **异步优先**：`httpx.AsyncClient` 在 `MusicApi` 内复用（`_get_client()` 惰性创建、关闭后重建），`terminate()` 负责 `close()`；不要在请求里反复 new 客户端。
- **类型与文档**：函数带类型注解，docstring 遵循 Google 风格（pydocstyle `--convention=google`，已放开 D1xx/D415），中文注释说明关键分支。
- **撤回能力尚未接线**：`_conf_schema.json` 里的「撤回生成提示 / 撤回歌单 / 提示撤回秒数 / 歌单撤回秒数 / 仅成功后撤回 / 发送失败保留歌单」对应 `PluginConfig` 字段，但 `main.py` 目前**没有调用**对应撤回逻辑；补这个功能时按配置项语义实现，并把 `PendingState.menu_message_ids` 用起来。

---

### 10.6. 开发环境

```bash
# 1. 克隆
git clone https://cnb.cool/XMZZUZHI/Astrbot/astrbot-plugin-song-voice.git
cd astrbot-plugin-song-voice

# 2. 安装依赖
pip install -r requirements.txt

# 3. 建议装 ffmpeg（高码率歌曲必需）
ffmpeg -version

# 4. 本地联调：把仓库放进 AstrBot 的 data/plugins/ 下，在面板里配置音源与码率
```

- `astrbot.api` 相关模块由宿主提供，脱离 AstrBot 运行时无法直接 `import main`；纯逻辑层（`core/config.py`、`core/models.py`）可以单独跑。
- CNB 云端开发环境由 `.cnb.yml` 定义（vscode + 多个 CLI + 克隆 AstrBot 源码）。
- 仓库**暂无 `tests/` 目录**，CI 的覆盖率与单测作业以 `--suppress-no-test-exit-code` 跳过（见 10.8）。

---

### 10.7. 代码质量与提交规范

#### 10.7.1 提交前自检（pre-commit）

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

钩子清单（`.pre-commit-config.yaml`）：`end-of-file-fixer`、`trailing-whitespace`、`check-yaml/json/toml`、`check-added-large-files`、`detect-private-key`、`check-case-conflict`、`check-merge-conflict`、`check-symlinks`、`mixed-line-ending`、`black`、`flake8`（`--max-line-length=100 --extend-ignore=E203,W503`）、`isort`（`--profile black`）、`mypy`（`--ignore-missing-imports`）、`pydocstyle`（google，忽略 D101/D102/D103/D104/D105/D107/D415）。

`ai-audit/` 目录名带连字符不是合法包名，`mypy` / `pydocstyle` 已按目录排除，**不要**往里加删排除规则。

#### 10.7.2 代码风格

- `black` 格式化 + `isort --profile black` 排序 import。
- 行宽上限 100（flake8），文件结尾保留换行、无尾随空格、统一 LF。
- 类型注解 + Google 风格 docstring，中文注释。

#### 10.7.3 Commit 规范

沿用 Conventional Commits，中文描述，如 `fix(audio): 转码失败时回退原文件`、`chore(ci): 同步 models_ai 的 .github 配置并按本仓库结构适配`。
签名要求见第 1.5 节：**提交前必须 `bash install_gpg_keys.sh`**。

#### 10.7.4 分支与 PR

1. 从 `main` 拉出特性分支（`feat/xxx`、`fix/xxx`、`chore/xxx`）。
2. 提交 PR，说明变更点与验证方式；**禁止**直接推 `main`（见 3.4）。
3. `.cnb.yml` 配置了 `main` push 时的 GitHub 镜像同步 → 属 3.5 判定范围，**CNB 与 GitHub 两侧都要提同名同内容的 PR**。

---

### 10.8. CI / 自动化

#### 10.8.1 GitHub 侧（`.github/workflows/`）

| Workflow | 作用 |
| --- | --- |
| `CodeQL.yml` | 代码安全分析（单一运行器 + Python `3.13`，不做无增益的 os × 版本矩阵） |
| `security-scan.yml` / `DevSkim.yml` / `secret-scanning.yml` | 安全与密钥扫描（Bandit 仅中高危计入失败；密钥扫描走 trufflehog） |
| `PythonDependencyAudit.yml` / `dependency-review.yml` | 依赖审计与依赖变更审查 |
| `tfsec.yml` | IaC 安全扫描（Trivy `config`，tfsec 规则集继任引擎） |
| `Scorecard.yml` | 供应链安全评分 |
| `inclusiveness-analyzer.yml` | 包容性分析（仅 warns，不阻断） |
| `stale.yml` | 陈旧 Issue / PR 自动化（stale 30 天 / close 7 天） |
| `release.yml` | 发布流程（tag 幂等跳过、发布包边界校验、证据包 + cosign 签名） |
| `coverage.yml` | 覆盖率与单测矩阵（`3.10/3.12/3.13`，`tests-gate` 汇总门禁；pytest 钉 `9.0.3`） |
| `ai-audit-scheduled.yml` | CodeQL 完成后的 AI 审计分流（`triage` / `publish` 两段式，artifact 加密交接） |

> **权限口径（统一约定）**：工作流**顶层不给 `id-token: write`**，写能力（`contents: write` / `security-events: write` / `id-token: write`）一律下沉到真正需要它的 job。唯一保留 `id-token: write` 的是 `release.yml` 的 `build` job（Sigstore keyless 签名），以及 `Scorecard.yml` 的 `analysis` job（上游发布 API 硬性要求，只能挂在 job 级）。
> `ai-audit-scheduled.yml` 的 `publish` job 只持只读 `contents: read`，建 Issue 走 `GH_PAT`。

#### 10.8.2 覆盖率链路（本仓库的现状，别照搬上游）

- 覆盖率**单一来源**是 `.github/workflows/coverage.yml`，CNB 侧只有镜像同步作业，**不要**往 CNB 侧加回上报。
- 计数用**包名**：`python -m coverage run --source=astrbot_plugin_song_voice -m pytest tests -q`，靠 `ln -sfn "$GITHUB_WORKSPACE" "$RUNNER_TEMP/$PLUGIN_PKG"` 铺包视图。**不要**改成绝对路径 `--source=/workspace`，Codecov 固定路径映射会匹配不到文件、覆盖率恒为 0。
- 报告格式固定 `coverage.xml`。
- **本仓库没有 `codecov.yml`**（上游有，同步时不要带过来，除非同时补齐 flags 映射）。
- 本仓库**暂无 `tests/`**：`--suppress-no-test-exit-code` 让「没测试」表现为绿灯跳过；补齐 `tests/` 后同一工作流自动开始统计上报，不用改文件。
- `CODECOV_TOKEN` 只能来自 `secrets.CODECOV_TOKEN`，**严禁**写进代码 / `.cnb.yml` / 文档 / 评论；未配置时上报步骤 `continue-on-error` 跳过，CI 不失败。

#### 10.8.3 CNB 侧（`.cnb.yml`）

- `$` 段：vscode 云开发环境（Python 镜像、导入 `key` 仓库的 `Claude.yml`、安装多个 CLI、克隆 AstrBot 源码）。
- `main.push`：唯一作业「同步到 GitHub」，`tencentcom/git-sync` + `force: true` 强制覆盖镜像到 `xiaomizhoubaobei/astrbot-plugin-song-voice`。改同步参数时注意 `force` 的语义是**镜像以 CNB 为准**，别误以为会合并。

#### 10.8.4 AI 审计示例（`ai-audit/`）

`ai-audit/` 是 AI 告警分流的**示例落地**（taskflow + 人格 + `model_config` + 交接公钥）。其中 `README.md` 仍保留「本仓库暂无 `.github/workflows/`」的旧注记，**与现状不符**（工作流已落地），以本章 10.8.1 为准；改该目录时顺手对齐这段描述。

---

### 10.9. Agent 工作指引

1. **先读配置再动手**：涉及新配置项时同步改 `_conf_schema.json` + `core/config.py`（字段与 `ALIASES` 两处）。
2. **保持分层**：事件分发与流程编排在 `main.py`；HTTP/解析在 `core/api.py`；ffmpeg 在 `core/audio.py`；会话与渲染在 `core/session.py`。不要把网络请求写进 `main.py`。
3. **新增音源**：`_conf_schema.json` 的「音源」options 与 `core/config.py` 的 `SOURCE_LABELS` **两处都要加**，否则面板显示会退化成原始英文键。
4. **改发送策略**：先看 `main.py` 的 `need_transcode` 判定与 `core/audio.py` 的 `transcode()` 回退链，两侧语义要一致（目前 flake8 会盯的复杂度已接近上限，别再加分支，抽函数）。
5. **判定 ffmpeg**：任何新路径都要先 `ffmpeg_available()`，不可用时降级而非报错。
6. **提交前**：`pre-commit run --all-files` + `bash install_gpg_keys.sh`，二者都过再提交。
7. **不要把密钥写进代码或文档**：API 地址、`CODECOV_TOKEN`、`GH_PAT`、GPG 解锁短语一律走配置 / 密钥仓库注入。
8. **改 CI**：`.cnb.yml` 缩进为 2 空格；有容器构建的作业必须在该事件/作业级声明 `services: - docker`。
9. **同步上游文档**：本文件的第 1~9 章来自 `astrbot_plugin_models_ai` 的同名文件，**第 10 章是本仓库专属**；再同步时只覆盖 1~9 章，第 10 章按本仓库现状维护。

---

### 10.10. 参考文档

- `README.md` — 用户向说明（功能、安装、工作流程、已知限制）
- `.github/CONTRIBUTING.md` — 分支与提交自检
- `.github/SECURITY.md` — 安全报告渠道与协调披露
- `ai-audit/README.md` — AI 审计示例说明（注记已过时，见 10.8.4）
