# Luna-Home / 周末接入硬件验收清单

软件所在仓库：[Bluelgin/Luna-Home](https://github.com/Bluelgin/Luna-Home)。本项目按顺序合并 #1 (QQ 底座) → #2 (人设) → #3 (QQ 节奏)。请确认最终 main 包含三个 PR 的完整改动，再开始以下操作。

## 主板还没到时：已能完成的事项

- [ ] GitHub Actions 的 QQ 测试、角色卡、备份测试、语法自检都通过，没有取消/跳过的必需检查。
- [ ] 在本地克隆最终 main 并运行 `python3 deploy/preflight.py`。
- [ ] 先决定 QQ 账号（只在服务器本地填入，不要上传仓库）。
- [ ] 提前确认 QQ 小号的正常登录可用，开启双重验证。NapCat 为非官方服务，有账号风险，重要 QQ 不要使用。
- [ ] 在本地做好 `NAPCAT_WEBUI_TOKEN` 和 `NAPCAT_WS_TOKEN` 两份彼此不同的随机密钥，密钥仅放服务器。
- [ ] 确认 Plus 账号可用的模型与接入路径：上游 nanobot 自带 `openai-codex` 授权，并不等同于 OpenAI SIWC。不能先假设 Luna 模型必然出现在帐号可用模型列表中。
- [ ] Luna 人设在 `persona/luna-dragon/SOUL.md`，中文 Piper 音色和正式立绘可以之后再选；目前文字聊天不依赖它们。

## Debian 初次启动

1. BIOS：设置断电恢复来电自动开机（主板支持时），关闭无用外设，接有线网/SSD。
2. 安装 Debian 13 Server（无桌面），创建普通用户，开启 SSH、系统更新、正确时区；SSH 限可信来源和公钥。
3. 安装 `git`, Python 3.11+, `ffmpeg`, Docker Engine / Compose；确认 Docker 可以拉取官方 NapCat 镜像。
4. 按 `deploy/README.md` 从 GitHub main 拉取到 `/opt/luna-home`，以 `luna` 低权限用户运行 Python 网关；不要以 root 运行 nanobot。
5. 配置 `deploy/.env`（WEBUI_TOKEN）与 `/etc/luna-home/luna.env`（WS Token）；只有 QQ 小号进行 NapCat 扫码。
6. 在 NapCat WebUI（通过 SSH 端口转发）打开本地 Forward WS 3001，Token 与 nanobot 一致；不要开放 6099/3001 到公网。
7. 在 `/var/lib/luna/.nanobot/config.json` 填 `privateOnly=true`, `ownerQq=主号`, `allowFrom=[主号]`，检查模型 provider 与实际可用模型。
8. 运行 `python3 deploy/preflight.py --host --config /var/lib/luna/.nanobot/config.json`，排除硬件/配置上的红色项。
9. 以 luna 用户执行 persona 安装器（先 dry-run，再 --apply --replace 安全备份默认 SOUL），启动 systemd，监测日志。
10. 确认原始聊天成功后再测试分句、文字延迟、插话打断、图片、ASR、TTS。语音默认不启用；TTS 没有指定合法中文音色时不发送语音。

## QQ 实机回归测试

| 步骤 | 从主 QQ 发送 | 必须观察到 |
| --- | --- | --- |
| 1 | `在吗 ww` | 单次 AI 回复，可能拆为 1–3 条；不出现重复整段 |
| 2 | `用三句话说说你的龙角` | 有语义分句与 0.7–2s 的气泡间隔 |
| 3 | 回复的第一条消息刚出现时插话 | 旧回答剩余气泡停止发送，处理新问题 |
| 4 | `请检查一个代码块/链接` | 整块代码或网址未被分句器割裂 |
| 5 | 测试账号/群里 @ Luna | 零模型调用、零回复、零提前下载图片 |
| 6 | 从主 QQ 发一张截图 | 有视觉能力模型实际描述截图；文本模型不谎称看懂 |
| 7 | 发 10 秒语音 | 已配置 ASR 时得到有效转写，否则告知不可用 |
| 8 | 配置合法 TTS 音色后 `/voice on` | 返回可播放语音，失败回落文字；`/voice off` 停止 |
| 9 | 设置定时提醒 | nanobot Cron 绑定此 QQ 私聊后在指定时间送达 |
| 10 | 开启主动问候且长时间没有消息 | 仅允许窗口内、每日最多一次；默认关闭时完全不主动发 |
| 11 | 重启 systemd 和 Docker | 不重复消息；如 QQ 扫码失效需手动重新登录 |
| 12 | 备份+恢复一份测试数据库 | SQLite 会话和持久记忆能恢复，绝不恢复/上传 OAuth 密钥 |

## 验收完成条件

- 系统连续 24 小时运行无重启风暴/日志持续增长，不能承诺非官方 QQ 永不掉线。
- 只有配置的主 QQ 可以通过 NapCat 呼叫 AI。
- OpenAI 授权登录、模型、额度经过该账户的实际测试，按需启用单独 API 付费 fallback。
- SSH/Tailscale 管理，WebUI/WS 无公网开放；QQ/模型凭证只有服务器文件持有。
- `/voice on/off` 与语音识别需要实体 QQ 实机验证，不因 CI 绿灯就默认完成。

## 回滚

部署更新前记录 git commit 和 SQLite 一致性备份；有问题时先停网关，`git switch --detach <verified_commit>` 恢复已测过的版本，重新 pip install -e 并启动服务。**不要**运行 `git reset --hard` 清理含私人数据的目录（私人数据库根本不应该保存在 Git 工作区）。

### 相关入口

- [Debian 详细部署文档](../deploy/README.md)
- [Luna 龙娘人设](../persona/luna-dragon/README.md)
- [NapCat Docker 官方指南](https://github.com/NapNeko/NapCat-Docker)
- [nanobot 自动化](https://github.com/HKUDS/nanobot/blob/main/docs/automations.md)
