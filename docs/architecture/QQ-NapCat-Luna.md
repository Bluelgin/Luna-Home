# Luna-Home：私人 QQ / NapCat / nanobot 多模态与记忆架构（设计方案）

> 状态：**方案与首轮代码实现已提交，GitHub CI 验证进行中；尚未 Linux / QQ 实机验收**。目标为 Linux 旧主机常驻、一个独立 QQ 账号、仅主人 QQ 私聊。上游源码固定在 `upstream/nanobot/`；上游版本详见 `UPSTREAM.md`。本设计以仓库当前 `nanobot/channels/napcat/runtime.py`、`manifest.py` 和上游文档为依据。

## 1. 目标与边界

- P0：QQ 小号通过 NapCat Forward WebSocket 与 nanobot gateway 通信，文字双向可用；只允许配置的主人 QQ 号向 Luna 触发模型调用。
- P1：QQ 图片接收、验证、下载、视觉理解、图片回复；无视觉模型时文字明确降级。
- P2：接收 QQ 语音，转码后 ASR 转文字，接入同一个私聊会话。
- P3：可选文字转语音（TTS），发送 QQ 语音消息；默认文字回答，不自动对每句话生成语音。
- P4：短期上下文与 Dream 长期记忆，明确的查看、更正、遗忘、备份操作。
- P5：Debian 13 或相容发行版 24×7 部署、健康检查、最小权限、审计、恢复与更新。

非目标：公开 QQ 机器人、全群自动聊天、QQ 多账号群发、通过非官方接口绕过 QQ 风控、无限制代理工具、任意命令执行。

## 2. 为什么选用现有底座

当前纳入仓库的 nanobot 源码已经包含 `nanobot/channels/napcat/`。配置包括 `wsUrl`、`accessToken`、`allowFrom`、`groupPolicy`、`welcomeNewMembers`、`maxImageBytes`。

已具备：
- NapCat OneBot v11 **Forward WebSocket**：连接、鉴权头、重连、心跳式登录检查、接收私聊 / 群消息、发送文本和图片。
- QQ 图片：入站图片 URL 下载、大小限制与 SSRF 目标校验，出站图片段发送。
- 会话及记忆：SQLite 会话、压缩后的 `memory/history.jsonl`、`SOUL.md` / `USER.md` / `memory/MEMORY.md`，Dream 定期整理。
- 可配置语音转录引擎，**但当前 NapCat runtime 不解析 `record` 音频段，也不会在出站构造语音段**。不能把 nanobot 的通用转录能力误说成 QQ 语音已经可用。

注意：当前 `_on_message` 会先下载入站图片，再调用通用 `_handle_message` 进行后续权限处理，需提前增加权限判定以避免陌生消息触发资源获取。当前 `groupPolicy: "mention"` 只控制是否回应群里被 @ 的内容，**不是严格禁止群聊**。

## 3. 运行拓扑

```text
个人 QQ 主号
    |
    v
QQ 平台 <---> 独立 QQ 小号（NapCat 登录）
                   |
                   | OneBot v11 Forward WebSocket + bearer token
                   v
Debian 主机：NapCat Docker（localhost:3001 / WebUI localhost:6099）
                   |
                   v
          Luna NapCat Channel 边界层
          ├─ QQ 主号白名单 + 私聊限定
          ├─ message_id 幂等检查与排队
          ├─ text / image / record 标准化
          ├─ 限流、媒体大小、存储与过期
          └─ 发送 text / image / record
                   |
                   v
              nanobot gateway
          ├─ agent / model provider
          ├─ session SQLite
          ├─ Dream + durable memory
          └─ model usage accounting
                   |
                   +--> GPT (以账号模型目录实际支持为准)
                   +--> 图像视觉模型（需可处理图片）
                   +--> ASR（独立语音转录后端）
                   +--> TTS（可选，独立引擎）
```

NapCat 管理端口、OneBot WebSocket、nanobot WebUI 均默认绑定 127.0.0.1；跨设备管理走 SSH 端口转发或 Tailscale，不直接开放公网。

## 4. 上游兼容原则与代码职责

保持 `upstream/nanobot` 作为可追溯的上游快照，Luna 自定义逻辑放在独立目录 `luna_home/`；需要触碰上游的 Hook / 通道注册点时，使用极小补丁、单独测试和变更记录，避免在上游 `runtime.py` 里堆砌大量业务逻辑。最终代码可采用一个 `LunaNapcatChannel` 子类或包装层，能否直接通过插件发现机制注册需在实现阶段验证；**此处是拟议目录，不代表已实现**。

拟议模块：

```text
luna_home/
  bridge/napcat_channel.py       # 私聊准入、消息标准化、OneBot I/O
  bridge/message_codec.py        # text/image/record <-> 内部消息
  media/downloader.py            # 入站资源检查、限速、大小、超时
  media/audio_codec.py           # FFmpeg/音频解码及格式转换
  media/asr.py                   # 语音识别后端抽象
  media/tts.py                   # 语音合成后端抽象
  memory/policy.py               # 可保存内容、授权、遗忘和清理规则
  security/allowlist.py          # 主 QQ ID、来源、群过滤
  operations/health.py           # 健康状态和可观测性
tests/luna_home/                 # 消息、安全和媒体契约测试
deploy/                          # Docker Compose / systemd / 运维脚本
```

## 5. 现有可用配置（不包含尚待开发的扩展字段）

在 **`~/.nanobot/config.json`** 合并如下片段。示例字段均在现有 NapCat 配置清单中存在；替换占位符；生产环境最好使用 `${NAPCAT_WS_TOKEN}` 环境变量引用，不存明文密钥：

```json
{
  "channels": {
    "napcat": {
      "enabled": true,
      "wsUrl": "ws://127.0.0.1:3001",
      "accessToken": "${NAPCAT_WS_TOKEN}",
      "allowFrom": ["YOUR_MAIN_QQ_NUMBER"],
      "groupPolicy": "mention",
      "welcomeNewMembers": false,
      "maxImageBytes": 10485760
    }
  },
  "agents": {
    "defaults": {
      "unifiedSession": false,
      "idleCompactAfterMinutes": 15
    }
  }
}
```

**说明**：上述配置可用来首次测试文字与图片；它**不能保证完全禁止群触发**，因为你的 QQ 主号在某个群中 @ Luna 时仍可触发。拟议新增 `privateOnly: true` 或在 Luna 适配器直接拒绝所有 `message_type=group`，应作为正式上线的前置验收项。

现阶段可在已有上游 Python 安装成功后执行：

```bash
nanobot plugins enable napcat
nanobot channels status
nanobot gateway
```

NapCat 部署依照官方 Docker 教程，容器需要持久化 QQ 登录与配置目录。首次扫码可能需要 SSH 端口转发打开管理页面。

## 6. 消息处理与授权

处理顺序（必要）：

1. 只接收格式正确、具有消息 ID 的 OneBot 消息，忽略机器人自己发出的内容。
2. **在媒体下载之前**：校验 `message_type == private` 且 `str(user_id) == OWNER_QQ`，其他消息不读媒体、不执行模型、不写会话；QQ 的历史好友列表并非授权依据。
3. 以 `(account_id, message_id)` 做持久化幂等；短时间重连重复推送不得重复回复。
4. 进行输入速率限制（起步参考：5 次/分钟、每分钟最多 1 个并发模型任务、队列有界）；过量请求明确反馈。
5. 按顺序解析 `text / image / record`；不支持的段降级为文字说明，不把未经验证的任意附件路径交给系统命令。
6. 形成内部标准事件：`user_id`、`session_id`、`msg_id`、`text`、`attachments[]`、`type`、`timestamp`。
7. 从会话及记忆构造有限上下文，调用模型；发送回复并记录成功/失败状态。

QQ 号码、NapCat access token、OpenAI Token 绝不打印在正常日志中。

## 7. 图片能力

### 接收

- 复用现有 OneBot `image` 解析与 `_download_image`，但把**早期发送者鉴权**作为第一步。
- 下载地址必须经过 SSRF 校验（私有地址、回环、DNS 解析重绑定风险需要检查）；只允许受控媒体来源，拒绝重定向、限制体积和超时；校验实际 MIME 和图像解码结果。
- 图片单张 10 MiB 上限（起步值），先生成缩略图/压缩分辨率，再发视觉模型，避免原图直接增加费用。
- 模型本身必须支持图片输入；纯文本模型只能告知“当前模型不支持看图”，绝不假称已看懂。
- 消息图片在有限期内删除原始文件（建议 24 小时），仅保留用户允许的描述性摘要。

### 发送

- 使用既有 outbound image segment；本地文件先限制在受控媒体目录，防止任意系统文件被读出并编码后发送。
- 测试 PNG/JPEG、QQ 长图、透明 PNG、超大文件拒绝、网络失败重试。

## 8. 语音能力（**要开发**）

### QQ 语音 → Luna 文本理解

```text
OneBot record segment
   -> 依 NapCat 当前版本使用 get_record /受控 file/url 解析
   -> 下载到隔离 temp 目录 + 限制时长、格式、大小
   -> FFmpeg/音频解码转换为 ASR 支持的格式
   -> ASR.transcribe()
   -> 用 [语音转写] 前缀写入与普通文本相同的 QQ 私聊会话
   -> nanobot agent 回答（默认文字）
```

- QQ record 的 `file` / `url` 在不同客户端与版本可能不同，**不能直接假定 `url` 必定是公网 HTTP 地址**。优先使用受身份认证的 OneBot 资源接口与可验证格式，禁止远程请求任意 file:// 路径。
- ASR 引擎：先用 nanobot 已提供的受支持转录后端；需要额外凭证/计费时明确展示。可按 CPU 能力实验本地语音转写，旧机器不保证实时。
- 起步限制：最长 60 秒、10 MiB、转码/转写任务最多 1 个并发、超时 60–120 秒；失败给清楚的文字提示，不能卡死聊天。
- 语音转写原文只作为短期会话；长期记忆保存其有价值的事实，而不是自动保存所有录音。

### Luna 回复语音（后续开启）

- 默认发文字；用户明确说“发语音”或配置 `replyMode=voice` 才调用 TTS。
- `TTS.synthesize(text, voice_id)` 先生成标准音频，再按 NapCat/OneBot 所需格式转换，发送 `record` 段。
- QQ 语音可能涉及 Silk/AMR 等编码，需要按 NapCat 实际接收格式实测，不能只把任意 MP3 路径传给 `record` 并当作成功。
- 合成失败应回退为文字，防止单次失败导致整个回复丢失。
- 中文声音可选独立 TTS API，或支持中文音色的本地 TTS。**Luna 文本模型本身不等同于 TTS 服务**。

## 9. 长期记忆：尽量复用 nanobot

纳入仓库的上游已有：

- 最近聊天：`~/.nanobot/sessions/<workspace-id>/sessions.sqlite3`。
- 历史压缩：`<workspace>/memory/history.jsonl`。
- 持久信息：`<workspace>/SOUL.md`、`USER.md`、`memory/MEMORY.md`。
- Dream：定期从历史摘要提炼稳定事实，并通过 GitStore 记录长期记忆文件变化。

推荐政策：

1. QQ 私聊唯一 `session_key`；`unifiedSession=false`，避免调试 WebUI 的临时内容混入私人聊天。
2. 近期对话只保留与本轮相关的少量轮次/Token；空闲 15 分钟允许上游自动 compaction。
3. Dream 定期或手动整理，不要求每条消息写入永久记忆；仅保存稳定喜好、正在进行的项目、明确要求记住的事实。
4. `SOUL.md` 设定 Luna 的语气和行为规则；`USER.md` 保留用户主动授权的偏好；`MEMORY.md` 保留关键项目与长期事项。
5. 增加 /memory 查看、/remember 明确保存、/forget 清理：*仅删除 MEMORY.md 不等于删除 SQLite 历史、归档和备份*。必须明确清理范围和备份保留策略。
6. 每晚备份 SQLite（先一致性快照）、记忆与 QQ 认证数据到访问受限的位置。设定保留周期，演练恢复。
7. 不把整份聊天历史、图片、录音或内存数据推送 GitHub；即便项目仓库公开也只提交模板和无秘密代码。

## 10. 模型与额度隔离

- **文本模型**：优先查询真实可用模型列表，再选择 Luna（如果该账户的授权接口确实提供）；不可把聊天软件的 QQ OAuth、nanobot 的 Codex OAuth 和 OpenAI SIWC OAuth 混为一谈。
- **SIWC Plus 授权**：需符合官方接入资格，按照自托管主机转移受保护凭证流程处理。现有 nanobot Codex 登录不能未经验证地当作等价 SIWC 实现。
- **图片**：需可用视觉模型；如果 SIWC 所选模型/请求能力不能处理图片，独立配置视觉提供商或有视觉能力的 API Key。
- **ASR/TTS**：单独配置计费/本地引擎，不要假设 Plus 自动包含语音转写和语音合成 API。
- **额度控制**：起步每天 50 次正常聊天的软目标，每 5 小时记账；独立统计 text tokens、vision 请求、ASR 时长、TTS 字符数。超限只停止模型处理，不影响 QQ 登录和健康检查。

## 11. Linux 24×7 部署

优先 Debian 13 Server / Ubuntu Server；纯文本 + 远程模型预期双核/4 GiB RAM/SSD 即可起步；本地转写可能需要更高 CPU/RAM，应先压测再决定。

- NapCat：参考官方 `NapNeko/NapCat-Docker` Docker Compose 示例，`restart: unless-stopped`，固定版本标签、保留 QQ/配置/插件目录；绑定 `127.0.0.1:6099:6099`、`127.0.0.1:3001:3001`，不要公网暴露。
- nanobot：可用隔离 Python venv + systemd 独立非 root 用户运行（或使用官方 Docker 镜像）；出错重启、设置合理重启间隔、日志滚动与机器开机自启。
- 管理：SSH/Tailscale 仅可信设备访问；Docker Socket、`sudo`、任意 Shell 工具默认不授权给模型。
- 确认服务器重启后 QQ 能否自动恢复登录；NapCat 可能要求重新人工扫码，不能承诺永不掉线。
- 监控：QQ 连接状态、WS 重连、模型 API 延迟、消息积压、SQLite 可写、磁盘剩余、语音失败率。避免保存完整私聊原文至常规日志。
- 安全：QQ 非官方桥接有平台风控/账号限制风险；优先用独立 QQ 小号，遵守平台条款，永远不把主 QQ 密码提交代码库。

## 12. 分阶段实施与验收

### Phase A / 普通聊天（代码已实现，需验证）
- [ ] NapCat Linux Docker 登录独立 QQ 号。
- [ ] 可从主 QQ 私聊收到并回复文字。
- [ ] 其他 QQ 号、群消息（包括主号在群里 @）全部拒绝，且不发生媒体下载/模型调用。
- [ ] 1 分钟内重复 WebSocket 消息不造成重复发言。

### Phase B / 图片（基础代码已存在，需视觉模型和实机验证）
- [ ] 私聊单图、多图、截图可解读（视觉模型确实支持）。
- [ ] 无视觉能力时准确告知，不编造图片内容。
- [ ] 超大图片/恶意 URL/下载超时/无效 MIME 安全失败。
- [ ] 入站原图能按 TTL 清理，出站仅受控路径。

### Phase C / QQ 语音（转写与 Piper 出站通路已实现，音色及实机未验收）
- [ ] 真机录制 QQ 短语音，验证 NapCat 当前 `record` 数据结构与取文件操作。
- [ ] QQ Silk/AMR/其他支持格式可转码成 ASR 可接受的格式。
- [ ] 语音识别转入相同私聊上下文，ASR 失败降级文字说明。
- [ ] 请求语音回复时能发送实际可播放的 QQ 语音消息；失败退回文字。

### Phase D / 记忆（复用上游；SOUL 人设需要和用户讨论）
- [ ] 重启服务后能接续最近对话。
- [ ] Dream 确实提炼长期记忆，而不是凭空声称“记住了”。
- [ ] /memory 可查看，/forget 对各存储层和备份策略说明真实清理范围。
- [ ] 可完成 SQLite / 长期记忆数据备份并恢复。

### Phase E / 运维（部署文件已写，待服务器联调）
- [ ] 电源重启后两服务自动拉起，QQ 重新连接（需要扫码则提示）。
- [ ] 不暴露公网管理端口，密钥权限 0600 / 环境变量安全。
- [ ] GitHub Actions 运行静态检查、单元测试、Mock OneBot 事件回放。
- [ ] 整机运行 24–72 小时后复核内存/CPU/磁盘/日志及 QQ 风控表现。

## 参考链接

- nanobot NapCat 聊天通道：<https://github.com/HKUDS/nanobot/blob/main/docs/chat-apps.md>
- nanobot 记忆系统：<https://github.com/HKUDS/nanobot/blob/main/docs/memory.md>
- NapCat Docker 部署：<https://github.com/NapNeko/NapCat-Docker>
- NapCat OneBot 网络：<https://napneko.github.io/onebot/network>
- OpenAI SIWC 自托管 VM：<https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms>
