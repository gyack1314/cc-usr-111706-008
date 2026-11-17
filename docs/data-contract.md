# 听证议程与公众材料变更采集资料约定

原文、解释记录和可见状态需要一致，不能用合成资料推断现实设施或排放。

## 来源原文形态

每个冻结响应是一份 JSON 原文，必含 `docket`（案号）与 `revision`（版次）。版次前缀区分角色：`rN` 为议程，`mN` 为会议纪要。

- 议程（`kind=agenda`，缺省值）：`status` 取 scheduled/postponed/withdrawn/rescheduled 之一，可含 `meeting`（YYYY-MM-DD）、`location`、`attachments`；不得出现 `decisions`。
- 纪要（`kind=minutes`）：可含 `meeting` 与 `decisions`；不得出现议程生命周期 `status`。
- 附件原文含 `attachment` 标识与所属 `docket`，可含 `kind` 与自述 `source`（开发商等附件来源）。
- 交叉引用：`cross_references[].authority=formal` 为正式交叉引用，可触发案号合并；其他 authority 以及 `related_dockets` 只登记待核关系。交叉引用不得指向本案号。

## 账本与状态约定

- receipts 保存每次送达的原始字节与 sha256，只追加；任何历史版次都能取回旧公告原文。
- entities 以 (collection, 类型, 案号, 版次) 为主键：新版次新增行，同版次原文不同即冲突回滚。
- links 以 (collection, 源案号, 目标案号, state) 为主键：state=confirmed 仅来自正式交叉引用，state=pending 保留待核；同键声明变化即冲突回滚。
- 项目当前状态、会议日期、地点取最高议程版次；时间线按原文到达顺序排列，纪要晚到不覆盖旧公告。
- 纪要及决议未发布属于证据缺口（publishable=false），不等于业务事实不存在。
