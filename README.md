# Luna Home 🌙

一个基于 [HKUDS/nanobot](https://github.com/HKUDS/nanobot) 的个人自托管 AI 助手实验项目，计划在旧 Linux 主机上 24/7 运行。

> 本仓库已更名为 **Luna-Home**。QQ 接入代码与新龙娘人设目前通过独立 PR 逐步验证，部署前请检查 PR 合并情况。

## 上游项目

- 项目：[`HKUDS/nanobot`](https://github.com/HKUDS/nanobot)
- 许可证：[MIT](https://github.com/HKUDS/nanobot/blob/main/LICENSE)
- 源代码位置：`upstream/nanobot/`（由仓库的 GitHub Actions 首次导入）
- 上游版本：参见 `UPSTREAM.md`（导入后生成）

本仓库保留了上游版权及许可证，不代表与 HKUDS 官方存在从属关系。更新上游代码前，请先复核代码、依赖及 breaking changes。

## 部署（Debian / Ubuntu）

第一次使用时，在 GitHub 仓库 **Actions** 页面确认 **Import nanobot source** 已成功运行；如果没有运行，可手动点击该 workflow 的 **Run workflow**。完成后，仓库应当包含 `upstream/nanobot/`。

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
git clone https://github.com/Bluelgin/Luna-Home.git
cd Luna-Home/upstream/nanobot
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
nanobot webui
```

> 部分最新源码构建 UI/TUI 还需要 Bun；具体以 `upstream/nanobot/docs/quick-start.md` 为准。私人 QQ 小号部署见 [`deploy/README.md`](deploy/README.md)。

OpenAI Codex OAuth（与 OpenAI 新版 Sign in with ChatGPT / SIWC 是**两套不同接入机制**）：

```bash
nanobot provider login openai-codex --set-main
```

在浏览器/终端完成官方登录，然后从在线模型目录选择账号实际可用的模型。**不要假定一定有 `gpt-6-luna`；应以实际模型目录为准。** 若后续要实现 SIWC，需要额外开发独立的授权适配器，不能直接复用 Codex OAuth 当作 SIWC。

## Luna 小龙娘人设

- 角色：**白紫色的小龙娘，呆萌但不迷糊地办事**。QQ 日常聊天自然亲近，代码、学习场景认真可靠。
- 正式可执行角色模板：[`persona/luna-dragon/SOUL.md`](persona/luna-dragon/SOUL.md)。
- 角色卡、视觉规范、交互示例和安全安装工具：[`persona/luna-dragon/README.md`](persona/luna-dragon/README.md)。
- 角色模板只在明确运行安装器后进入 nanobot workspace；不会自动上传私人聊天、覆盖现有记忆或指定声音。

## 安全边界

1. 初次部署优先只监听 `127.0.0.1`，通过 SSH / Tailscale 访问；不要将管理面板直接暴露公网。
2. OAuth 登录令牌、API Key、`~/.nanobot` 数据目录、聊天记录、数据库、日志不能提交到 GitHub。
3. 旧主机不需要 GPU；先使用最少工具权限，避免授予机器人不必要的 root、Docker Socket 或任意 shell 操作能力。
4. 用 systemd 管理进程、独立的非 root 服务账户和定期备份来实现常驻运行。不要在尚未配置/测试时直接作为 root 启动。

## 开发计划

- [x] 从上游导入完整源代码并保留 MIT 授权
- [ ] 在 Linux 本地验证 WebUI 和 Codex OAuth
- [ ] 验证账号能否通过模型列表调用 Luna
- [ ] 按需开发官方 Sign in with ChatGPT（SIWC）支持
- [ ] 增加登录保护、systemd 服务、记忆数据持久化及 GitHub CI
