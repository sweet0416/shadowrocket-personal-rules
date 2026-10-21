# Shadowrocket personal rules

完整保留 [Moshel / Johnshall 上游项目](https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever) 的 `sr_top500_banlist_ad.conf` 成品，只在唯一 `[Rule]` 段开头插入个人规则托管块。上游 URL 唯一维护位置是 `scripts/build_config.py` 的 `UPSTREAM_URL`；不使用其他配置变体。

## 下载与维护

- 仓库：https://github.com/sweet0416/shadowrocket-personal-rules
- **填进原快捷指令**：https://raw.githubusercontent.com/sweet0416/shadowrocket-personal-rules/main/dist/shadowrocket_personal.conf
- [网页编辑 custom_rules.txt](https://github.com/sweet0416/shadowrocket-personal-rules/edit/main/custom_rules.txt)
- [Actions](https://github.com/sweet0416/shadowrocket-personal-rules/actions/workflows/update.yml)

`custom_rules.txt` 是个人域名维护入口。支持空行、整行 `#` / `;` 注释和完全重复项去重，只接受三字段 `DOMAIN` / `DOMAIN-SUFFIX`、合法 ASCII 域名、`PROXY`。当前只有：

```text
DOMAIN-SUFFIX,metaaivm.com,PROXY
DOMAIN-SUFFIX,meta.ai,PROXY
DOMAIN-SUFFIX,ai.meta.com,PROXY
```

`metaaivm.com` 是此前实际排障确认的关键域名；另外两条是原有保留项，不声称都已证明是 Muse 必需接口。不扩展其他 Meta/Facebook 域名。

## 构建约束

Python 3 标准库，无第三方包。运行：

```sh
python -m unittest discover -s tests -v
python scripts/build_config.py
```

HTTPS 下载（含重定向约束），30 秒超时，最多三次尝试，间隔 1/2 秒，20 MiB 上限；校验 HTTP 200、UTF-8、非空、非 HTML、General、唯一 Rule 和唯一末尾 FINAL。验证全部完成后同目录临时文件原子替换 `dist/shadowrocket_personal.conf`，失败不覆盖有效产物。

只插入 `# BEGIN PERSONAL RULES` 至 `# END PERSONAL RULES` 块，沿用 Rule 段头换行。保留所有上游原始字节、BOM、其他配置段、顺序、FINAL、末尾换行。即使上游已有相同规则，托管块仍保留。删除插入块后必须精确恢复本次上游；每次重新下载，不累积。已有本项目标记时失败。相同输入输出确定，无本项目动态时间戳（上游自己的时间注释原样保留）。Git 对产物禁用文本换行转换。

本次上游没有配置自身更新指令；顶部来源注释不是更新指令。**改写白名单为空，实际改写零项**。未来发现 `#!` 元数据或 URL/update 类配置指令会安全失败，需人工审查后再修改程序，避免更新回不含个人规则的上游。此检查是静态保护，不等于手机解析验收。

上游已有 `[URL Rewrite]`、`[MITM]` 和外部 RULE-SET 引用，全部原样保留；本项目不增加解密、证书安装要求，不改变默认策略。生成输入仅为公开上游和上述个人规则，不读取手机配置、下载目录、iCloud 或私有订阅。不要向本仓库提交节点、订阅、密码、UUID、密钥、Token、Cookie 或设备日志。

## 自动更新

默认分支 `main` 的工作流支持手动 `workflow_dispatch`；个人规则、脚本、测试或工作流变更也触发。计划 `17 */6 * * *` 使用 UTC，即北京时间每日 08:17、14:17、20:17、次日 02:17。

默认权限 `contents: read`，仅发布任务 `contents: write`，使用内置 `GITHUB_TOKEN`。无 `pull_request_target`。官方 checkout v6 / setup-python v7 固定完整提交 SHA，已从官方仓库 tag 和 commit API 核实。单组并发、10 分钟超时，先测试后构建；只暂存产物，变化才提交。产物提交不匹配触发路径，避免循环。推送冲突直接失败，不 force push；查看失败步骤、更新 main 后重新运行，不能强推旧输入结果。Summary 提供来源、字节/哈希验证、更新状态；失败原因见失败步骤与 Summary，最后远程有效产物保留。

[GitHub 官方 schedule 文档](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule) 说明高负载可能延迟甚至丢弃排队任务，不能保证到点。[官方启停文档](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows) 说明公开仓库 60 天无活动可能自动停用计划。恢复时到 Actions → 本工作流 → Enable workflow，再 Run workflow 验证，也可运行 `gh workflow enable update.yml`。不承诺永久免维护。

## 手机迁移与回退

1. 保留旧配置和原快捷指令。
2. 复制快捷指令，只替换下载 URL 为上面的 main Raw URL。保留现有可工作的 Shadowrocket 导入链接构造方式，不发明 URL Scheme，不重复编码。
3. 手动运行副本，导入后首次选中 `shadowrocket_personal.conf`；检查 `metaaivm.com` 规则、测试 Muse 对话，并查看实际 `PROXY` 命中日志。
4. 通过后才修改原每天 12 点正式任务的 URL，不同时运行两个互相覆盖的更新任务。失败时选回旧配置并恢复旧 URL。固定提交 Raw 可回退本项目已验证版本，但不替代旧配置备份。

“规则已更新”提示不是成功回执，可改为“已发起配置更新”。本项目不操作手机配置或重建自动化。静态顺序不能证明 Shadowrocket 解析或实际网络命中。此前候选配置可让 Muse 对话，但缺少新 `metaaivm.com` 完整 PROXY 日志，不据此宣称本版本运行通过。手机界面旧约 15.3 MB / 候选约 10.3 MB 原因未知，不能等同原始文本字节。

## 许可与修改说明

上游作者 Moshel / Johnshall；来源见首段及产物原始署名。已复核 [release 分支 LICENSE](https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever/blob/release/LICENSE)，原文保存在 `LICENSE-UPSTREAM`，为 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)。派生配置继续采用 CC BY-SA 4.0；本仓库脚本、测试、工作流和文档也采用相同许可。修改仅为上述个人托管块；不暗示上游作者认可本项目。

## 实际验收

本地真实上游验证：3,434,325 → 3,434,462 字节，净增 137 字节；89,856 → 89,859 条规则；移除块逐字节还原上游，零其他改写。

- 上游 SHA-256：`c9f7f4e2adbe38433e904f72d010a6d08a84e451ef5b9722183940c68240cabd`
- 产物 SHA-256：`19111b518f282996c4d4f7d50e21ce34c982f946df21156bce0aa8f2bf458814`

远程发布验收将在首次实际 Actions 与匿名下载完成后写入。

| 验收项 | 状态 |
| --- | --- |
| BUILD_AND_TESTS | PASS（本地 unittest，包括格式组合和下载失败保护） |
| UPSTREAM_PRESERVATION | PASS（真实上游，精确字节恢复） |
| GITHUB_ACTIONS_RUN | PENDING |
| PUBLIC_RAW_DOWNLOAD | PENDING |
| SHADOWROCKET_IMPORT | PENDING_USER_CHECK |
| MUSE_RUNTIME | PENDING_USER_CHECK |
