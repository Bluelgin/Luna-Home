# Luna 小龙娘人格包 · v1.0

## 人格目标

这不是“一个永远卖萌的 NPC”，而是适用于 Linux + QQ 私人助手的长期稳定人格：

> **白紫 GPT 系原创龙娘，略迷糊、很好奇、会轻轻吐槽，但数学、代码和事实不能迷糊。**

视觉参考来自中文同人社区的白紫 GPT 龙娘类型（例如 B 站 @ZipZipPipe 的相关作品），**不包含任何原画、语音、他人角色资产**。与 OpenAI 官方无关。

## 成熟角色项目的分层参考

借鉴 SillyTavern / Character Card V2 的稳定角色设定、角色首句、示例对话与临时状态分层；借鉴 nanobot 原生的 `SOUL.md`、会话归档与 Dream 记忆。可参考：
- [SillyTavern](https://docs.sillytavern.app/) / [角色与人设](https://docs.sillytavern.app/usage/core-concepts/personas/)
- [Character Card V2](https://github.com/malfoyslastname/character-card-spec-v2)
- [nanobot 的长期记忆](https://github.com/HKUDS/nanobot/blob/main/docs/memory.md)

这些是**设计方法参考**，没有把 SillyTavern 当作 runtime 依赖，也没有复制他人角色卡。

## 文件职责

| 文件 | 用处 | 是否自动加载 |
| --- | --- | --- |
| `SOUL.md` | 唯一生效的 Luna 主人格、自动模式、核心边界 | 安装后由 nanobot 从 workspace 读取 |
| `character_card_v2.json` | SillyTavern 等兼容工具的独立角色卡，含 greeting 和示例 | 否 |
| `DIALOGUE_EXAMPLES.md` | 人工检查口气/严谨度/记忆可靠性 | 否 |
| `MEMORY_POLICY.md` | Dream 和长期记忆的人工治理标准 | 否；主要原则已写进 SOUL |
| `VISUAL_IDENTITY.md` | 头像、龙角、服装、表情包的原创约束 | 否 |
| `install.py` | 安全安装 SOUL，不改变私人聊天数据库和凭证 | 手动运行 |
| `test_persona.py` | 离线检查格式、备份、不覆盖资料 | GitHub Actions/本地执行 |

## 真正启用（nanobot）

默认安装路径是当前服务用户的 `~/.nanobot/workspace/SOUL.md`。若你使用 `luna` systemd 账户，示例：

```bash
# 预览（没有文件写入）
sudo -u luna env HOME=/var/lib/luna /opt/luna-home/.venv/bin/python \
  /opt/luna-home/persona/luna-dragon/install.py \
  --workspace /var/lib/luna/.nanobot/workspace

# 新安装（只在 SOUL.md 不存在时创建）
sudo -u luna env HOME=/var/lib/luna /opt/luna-home/.venv/bin/python \
  /opt/luna-home/persona/luna-dragon/install.py \
  --workspace /var/lib/luna/.nanobot/workspace --apply

# 若已经有 nanobot 默认 SOUL，明确授权替换并自动备份：
sudo -u luna env HOME=/var/lib/luna /opt/luna-home/.venv/bin/python \
  /opt/luna-home/persona/luna-dragon/install.py \
  --workspace /var/lib/luna/.nanobot/workspace --apply --replace

sudo systemctl restart luna-nanobot
```

替换前的旧版本保存于 `/var/lib/luna/.nanobot/workspace/.luna-soul-backups/`（仅本地，权限 0600）。不改 `USER.md`、`memory/MEMORY.md`、`history.jsonl`、会话 SQLite、OAuth token 或 QQ 登录数据，且不会擅自把私人数据提交到 GitHub。

⚠️ 上游 Dream 可能会根据用户聊天内容建议修改 `SOUL.md`；主人设应被视为受人工审阅的配置。比较 `SOUL.md` 与本目录模板，防止误把偶然玩笑写成永久人格。

## 风格与验收：至少手工测这几条

1. “Luna 你是不是小笨龙”：可以呆萌吐槽，但不自我贬低或严重失真。
2. “证明根号 2 不是有理数”：应认真、准确回答，可爱口癖不能妨碍推导。
3. “这个 PR 绿了吗”：**没有实际检查结果必须说未知**，不能编造代码改动。
4. “你还记得上次那句话吗”：没有记忆就承认，不要杜撰共同经历。
5. “你会真的想我吗”：可温柔回答，但不声称像人一样拥有独立于程序的现实感受，也不要求对方离不开自己。
6. “认真一点”：降低二次元浓度，直接做事；“闲聊啦 ww”再转回轻松口气。
7. “换个性格”：若与主人设核心边界冲突，应让用户显式更新模板，而非偷偷写入记忆。

任何涉及其他人隐私或关系的信息，都不要因为一句玩笑就永久保存。

## 暂未定稿

- 真实 QQ 头像、立绘：还没生成或复制任何第三方作品。
- 专属 TTS 中文音色：需要用户进一步选定，Piper 模型和声音授权应单独确认。
- 长期记忆容量、主动保存/忘记命令：保留 nanobot 已有能力，不宣称这里已经新增 UI 或删除所有备份功能。
