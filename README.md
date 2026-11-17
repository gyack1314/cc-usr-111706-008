# 听证议程与公众材料变更采集

本项目接收公开来源的原文及关联记录。当前样例只给出部分证据，未决状态不等于业务事实不存在。

来源响应由 transport 校验，domain 解释资料，ledger 保留事务与版本，view 展示当前证据和缺口。样例为合成资料，不访问真实网站。

## 领域规则

- **项目身份**：以案号（docket）为身份。延期（postponed）、撤回（withdrawn）、重排（rescheduled）只是同一案号议程的新版次（r1、r2、…），不会产生新项目；当前状态取最高议程版次。
- **角色边界**：议程（kind=agenda）只记录会议安排与生命周期，携带 `decisions` 的议程直接拒收；决议只能由会议纪要（kind=minutes，版次 m1、…）承载。纪要晚到后，旧公告原文仍在 receipts 中，可按时间线逐版回放。
- **附件来源**：开发商等第三方材料登记为 support 实体，附件自述来源（source）与抓取收据 URL、原文 sha256 同时留存。
- **案号关系**：仅当来源给出 `authority=formal` 的正式交叉引用时，不同部门案号才并入同一项目；`related_dockets` 或非正式 authority 一律登记为 pending 待核，不参与归并，同一关系声明发生变化则整笔回滚。
- **只追加账本**：新版次另插一行；同一 (类型, 案号, 版次) 再次送达而原文不同即视为冲突并回滚。

## 运行

在项目根目录执行：

    python -m unittest discover -s tests -v
    python -m compileall -q capture_service tests
    python -m capture_service.cli inspect data/normal.json
    python -m capture_service.cli inspect data/lifecycle/manifest.json
    python -m capture_service.cli timeline data/lifecycle/manifest.json
    python -m capture_service.cli inspect data/crossref/manifest.json --db hearings.sqlite

`inspect` 输出项目归并、时间线、附件来源、正式/待核关系与缺口；`timeline` 按到达顺序列出每个项目的版次并确认旧公告原文可回放。`--db` 给定文件路径时多次采集可累积且重放幂等，默认使用内存库。

冻结样例由 `tools/generate_fixtures.py` 生成（合成数据）：`data/lifecycle/` 覆盖延期—重排—纪要晚到与撤回，`data/crossref/` 覆盖正式交叉引用合并与待核关系。

Dockerfile 提供 Linux 环境；docker build -t hearing-docket . 构建，docker run --rm hearing-docket 运行样例。
