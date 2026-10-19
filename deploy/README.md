# Luna-Home：Debian Linux + QQ 好友部署指南

> 本指南对应 Luna 私聊功能的开发分支，**不是现成可保证零配置使用的部署包**。请在合并 PR 后，或者自行检出此分支执行。安装/测试不需要提供 QQ 号码给 GitHub。OpenAI 账号订阅额度的认证方式需单独配置并核验。

## 前提

- Debian 13 / Ubuntu Server、x86_64 或 ARM64，建议双核、至少 4 GiB RAM 和 SSD。
- Linux 命令行、SSH、Docker Engine + Docker Compose plugin、Python >=3.11。
- 一个专用 QQ 小号（登录 NapCat）和你的主 QQ 号（唯一允许聊天的用户）。
- 账号安全：NapCat 是非官方登录桥接，存在 QQ 风控、登录失效乃至账户限制风险。

## 1. 下载源码与系统准备

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip ffmpeg
# 按 Docker 官方手册安装 Docker Engine 和 docker compose plugin
sudo useradd --system --home-dir /var/lib/luna --create-home --shell /usr/sbin/nologin luna || true
sudo mkdir -p /opt /etc/luna-home
# 目标目录首次不存在时才能执行 git clone
sudo git clone https://github.com/Bluelgin/Luna-Home.git /opt/luna-home
# 若 PR 尚未合并，明确切到已提交实现的 PR 开发分支：
cd /opt/luna-home
sudo git fetch origin docs/qq-napcat-multimodal-memory-plan
sudo git switch -c luna-qq --track origin/docs/qq-napcat-multimodal-memory-plan
sudo python3 -m venv /opt/luna-home/.venv
sudo /opt/luna-home/.venv/bin/python -m pip install --upgrade pip
sudo /opt/luna-home/.venv/bin/python -m pip install -e /opt/luna-home/upstream/nanobot
sudo -u luna env HOME=/var/lib/luna /opt/luna-home/.venv/bin/nanobot plugins enable napcat
```

最后一条仅启用插件；如果这个 nanobot 版本的 CLI 要求初始化 Home 或通过 WebUI 才允许启用，请按上游 `docs/chat-apps.md`，以 `luna` 用户执行而非 root。安装时请确认插件已启用、状态显示正常。

## 2. 启动 NapCat（本地回环端口）

```bash
cd /opt/luna-home/deploy
sudo cp .env.example .env
sudo chmod 600 .env
sudoedit .env
sudo docker compose -f compose.napcat.yaml up -d
```

- 为 `NAPCAT_WEBUI_TOKEN` 生成长随机值，别用示例值。
- 如果已部署并验证版本稳定，`NAPCAT_IMAGE` 最好固定镜像 tag 或 digest；不要盲目追 `latest`。
- 在自己电脑上 SSH 转发：`ssh -L 6099:127.0.0.1:6099 your-ssh-user@server-ip`，然后访问 `http://127.0.0.1:6099/webui`。
- 扫码登录 **QQ 小号**，在 NapCat WebUI 的 **网络配置 → 新建 → WebSocket 服务器** 打开 Forward WebSocket，监听 3001 并设置独立的强 access token。
- `NAPCAT_WEBUI_TOKEN` 与 `NAPCAT_WS_TOKEN` 不是同一个；它们分别保护管理面板和 OneBot WebSocket。
- docker Compose 默认只将 6099/3001 绑定到 `127.0.0.1`，绝不直接把它们开放公网。

## 3. 配置独立 nanobot 服务账户

```bash
sudo mkdir -p /var/lib/luna/.nanobot
sudo cp /opt/luna-home/deploy/nanobot.config.example.json /var/lib/luna/.nanobot/config.json
sudo cp /opt/luna-home/deploy/luna.env.example /etc/luna-home/luna.env
sudo chmod 600 /var/lib/luna/.nanobot/config.json /etc/luna-home/luna.env
sudoedit /var/lib/luna/.nanobot/config.json
sudoedit /etc/luna-home/luna.env
sudo chown -R luna:luna /var/lib/luna
# 纳入图片/语音共享目录时，按最低权限开放读取，不要让 Luna 读任意宿主机文件。
```

- 在 `config.json` 中填写 `ownerQq`、`allowFrom`，两项必须是你**主 QQ 号**的字符串。
- `privateOnly: true` 对**群入站、群出站和其他账号**都生效；缺失 `ownerQq` 时启动必须拒绝。
- `accessToken` 引用 `${NAPCAT_WS_TOKEN}`，其真实值只写到权限为 0600 的 `/etc/luna-home/luna.env`。
- 需要单独设置一个模型提供方。**QQ OAuth、nanobot Codex OAuth 和 OpenAI SIWC OAuth 不等价**；不能保证 Plus 的模型列表有 GPT-6 Luna。请登录后检查实际授权模型再选，必要时用独立 API Key。
- 安全起步：先禁用任意 shell、浏览器自动控制、外部 MCP 和文件写工具；只让它回复消息。

## 4. 开启 24x7

```bash
sudo install -m 0644 deploy/luna-nanobot.service /etc/systemd/system/luna-nanobot.service
sudo install -m 0644 deploy/luna-media-cleanup.service /etc/systemd/system/luna-media-cleanup.service
sudo install -m 0644 deploy/luna-media-cleanup.timer /etc/systemd/system/luna-media-cleanup.timer
sudo install -m 0644 deploy/luna-backup.service /etc/systemd/system/luna-backup.service
sudo install -m 0644 deploy/luna-backup.timer /etc/systemd/system/luna-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now luna-nanobot.service luna-media-cleanup.timer luna-backup.timer
sudo systemctl status luna-nanobot.service
sudo journalctl -u luna-nanobot.service -f
```

服务按非 root `luna` 身份启动；缓存清理每天删除 24 小时前的 NapCat 临时图片/音频，不涉及 SQLite 会话与 Dream 长期记忆。系统恢复后 NapCat 登录状态仍可能要求你重新扫码。

## 5. 图片

发送 QQ 截图给 Luna。上游 NapCat 通道可以下载图片并交给支持视觉的模型；**文本模型无法读图时必须告知**。限制默认 10 MiB。临时图片 24 小时后由 timer 清理。模型视觉调用可能需要独立费用。

## 6. QQ 语音转写

`enableVoiceInput: false` 默认不处理 record 消息。正式启用时：

1. 在 `config.json` 内设置 `enableVoiceInput: true`，并在全局 `transcription` 配置有合法 ASR 提供商凭据。此功能**可能需要额外 API 费用**。
2. OneBot `get_record` 请求 MP3 格式；若返回 base64 或 HTTPS URL，自动使用；若返回 Docker 容器本地路径，则需要设置共享路径映射：
   - `sharedRecordRemoteRoot: "/app/.config/QQ"`
   - `sharedRecordDir: "/opt/luna-home/deploy/data/qq"`
   - 将宿主目录对 `luna` 设为只读可访问权限；若实际路径不在 QQ 配置卷，请调整 NapCat 的音频路径映射（不宜开放整个容器文件系统）。
3. 重启 `sudo systemctl restart luna-nanobot`。
4. 语音无法获取、文件不在允许目录、格式不兼容、ASR 不可用时，会文字告知，绝不假装理解了录音。

## 7. Luna 回语音：选择音色后再开启

本次先提供**可用的可选 Piper TTS 接口**，不替你决定女声/男声、年龄感、口癖或角色人设。

1. 以后选定经授权可用的 Piper 中文音色模型 `.onnx` 及配套 `.onnx.json`，下载至服务器上只有 luna 用户可读的位置。
2. 安装 Piper CLI；在 `ttsModelPath` 配置完整 `.onnx` 路径，`ttsExecutable` 配 CLI 的固定执行路径。
3. 在自己的 QQ 私聊发送 `/voice on`，机器人会使用本地 Piper 生成 WAV 并通过 OneBot `record` 发送。发送 `/voice off` 可恢复文字。
4. 如果语音模型未安装、长文本超过 500 字、超时或编码失败，则自动回退文字；旧主机需要实测速度。
5. 语音开关目前是**当前进程会话内状态**，服务器重启后恢复文字，这是故意的安全默认值。

## 8. 记忆

上游已具备：
- SQLite 会话历史（持久化）；
- `memory/history.jsonl` 自动摘要；
- `SOUL.md` / `USER.md` / `memory/MEMORY.md` 与 Dream 的 Git 版本记录。

本阶段**不预设 Luna 的 SOUL.md 人设**。请先讨论性格、身份边界、昵称、表达风格与“什么值得记住”。可以先用 `/compact`、`/dream`、`/dream-log` 验证上游记忆可用；主动遗忘时要同时注意原始 SQLite 记录、历史摘要、备份与日志，并不能只删 MEMORY.md。

已提供 `deploy/backup_luna.py` 与每天执行的 systemd timer，保存 `SOUL.md`、`USER.md`、`MEMORY.md`、压缩历史及 sessions 下 SQLite 的一致性快照，默认保留 7 份，写入 `/var/lib/luna/backups`，文件权限 0600；**此备份不包括 OAuth 令牌、NapCat QQ 登录状态和所有临时媒体文件**。备份自身仍包含私人聊天内容，复制到其他机器前请使用 age / GPG 等工具加密，定期做恢复演练。

记忆、图片原件、QQ 凭证及 API 凭证绝不上传 GitHub。

## 9. 回归验证

```bash
cd /opt/luna-home
/opt/luna-home/.venv/bin/python -m pip install -e './upstream/nanobot[dev]'
/opt/luna-home/.venv/bin/python -m pytest -q upstream/nanobot/nanobot/channels/napcat/tests
```

功能验收清单：
- 主 QQ 私聊文字正常，图片在视觉模型下正常；
- 其他 QQ / 群聊 (包括主人在群里 @) 不能触发下载、调用或回复；
- ws 重连后重复 message_id 不会重新生成回答；
- 图片下载失败、ASR 未配置、TTS 失败均回退而非卡死；
- 系统重启后 QQ 重新连接；缓存清理不删除记忆；
- NapCat 管理面板、OneBot websocket 不暴露公网。

## 10. 已知边界

- NapCat 是 QQ 非官方桥接，平台风控不可避免；24/7 无人值守不等于 QQ 永不掉线。
- `get_record` 返回的音频文件位置依版本而异，需要你的 NapCat 真机回放测试。Piper 音色未选择前不能端到端验收发送语音。
- 本地代码测试、GitHub CI、Docker 实机测试是不同的验证层级；CI 通过不代表 QQ 平台实际协议或 OpenAI OAuth 必定成功。
- 未来更新上游 nanobot 需手工审阅差异，避免覆盖 Luna 特有的安全/音频补丁。

## 11. Luna 白紫小龙娘人设（明确安装才生效）

已提供 [`persona/luna-dragon/`](../persona/luna-dragon/README.md) 中的正式 `SOUL.md`、SillyTavern V2 角色卡和对话样例。该角色是**呆萌、好奇、亲近、严谨**的 GPT 系二次元龙娘，同人灵感不等于 OpenAI 官方角色。**本次不定稿专属配音，也不以“呆萌”为由产生错误答案。**

```bash
# 先预览，不修改既有 nanobot 记忆
sudo -u luna env HOME=/var/lib/luna /opt/luna-home/.venv/bin/python \
  /opt/luna-home/persona/luna-dragon/install.py \
  --workspace /var/lib/luna/.nanobot/workspace

# 如果 nanobot 已初始化自己的 SOUL.md，想采用 Luna 时显式备份并替换
sudo -u luna env HOME=/var/lib/luna /opt/luna-home/.venv/bin/python \
  /opt/luna-home/persona/luna-dragon/install.py \
  --workspace /var/lib/luna/.nanobot/workspace --apply --replace

sudo systemctl restart luna-nanobot
```

安装器仅触及 `SOUL.md`，绝不改写 `USER.md`、`memory/MEMORY.md`、历史 SQLite、授权凭据。旧 SOUL 备份在 workspace 下的 `.luna-soul-backups/`，这不是 GitHub 备份路径。若你希望修改人格，请在 GitHub 上改版本模板，再运行安装器进行显式替换。


## 12. QQ 自然回复与插话打断

Luna 在 privateOnly 模式下，一次模型生成的回答可拆成 1–3 条 QQ 小气泡，**不会每拆一条就多调用模型**。

- `naturalChatEnabled=true`：只拆闲聊句；代码块、网址、列表、图、语音和事件消息保持完整。
- `replyDelayMinSeconds=0.8` / `replyDelayMaxSeconds=2.5`：先抵扣已经等待模型的时间，避免长时间额外等待。
- `chunkDelayMinSeconds=0.7` / `chunkDelayMaxSeconds=2.0`：拆分的消息之间产生有限随机间隔。
- `maxChatChunks=3`：最多三条。若你在其中插话，后续旧气泡会被取消（已经发送的不会撤回）。
- 若一段已成功发送、下一段失败，停止本次剩余发送，不请求重试整条，以免重复。

### 主动问候：需要你主动开启

`proactiveCheckinsEnabled=false` 是默认值。改为 `true` 才启用。
在完整 config.json 的 channels.napcat 里配置 `proactiveTimezone`、`proactiveStartHour=11`、`proactiveEndHour=20`、`proactiveMinIdleMinutes=180`、`proactiveProbability=0.35`。

仅在你授权的本地时间窗口与已经超过 3 小时没有 QQ 消息时尝试；每天最多一条，并以固定每日概率约 35% 决定是否发送，当日记录持久化以防重启重复。发出的只是预写的轻量龙娘问候，**不调用模型、不消耗 Plus 额度**。不会假装她现实生活中经历了什么。若要固定时间提醒或条件事件通知，使用 nanobot 原生 Cron/Heartbeat 并让你确认；不拿随机问候代替明确提醒。

随时把 `proactiveCheckinsEnabled` 调回 false 后重启网关。不要高频骚扰 QQ；NapCat 仍有非官方账号风控风险。

## 13. 主板到手前的软件检查

无需 QQ 或 Plus 登录便可用 Python 检查：

```bash
python3 deploy/preflight.py
python3 -m unittest discover -s persona/luna-dragon -p 'test_persona.py' -v
python3 deploy/test_backup.py
```

拿到 Debian 主机并创建真正的私有配置后检查环境：

```bash
python3 deploy/preflight.py --host --config /var/lib/luna/.nanobot/config.json
```

检查器不会登录账号、不会打印任何 Token。仍需真实 Linux 主机的 Docker/NapCat、QQ 扫码、Plus 可用模型和音频后端验证。CI 没有通过之前，不能视为已完成生产验收。
