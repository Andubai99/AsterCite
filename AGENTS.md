# AsterCite 开发约定

项目是固定论文库上的单 Agent CLI；Pi SDK 固定 1.0.4。先维护 docs/specs/ 与 docs/plans/，再实现并验证，阶段提交使用 docs:/feat:/test:/chore: 加中文摘要。

只向模型暴露 search_papers、retrieve_chunks，禁用个人资源、默认 shell/文件工具、MCP、目录联网和自动重试。生成密钥只来自 PIPAPER_API_KEY、只注入内存，配置/错误/日志/快照不得保存密钥或隐藏思考。Gold 仅供 reproduce/ 的独立评测过程，不进入 corpus、工具结果或系统提示。

产品默认 NLU + 混合检索 + 重排 + 引用生成 + Memory，关闭 Reflect。每用户轮请求尝试 ≤12，search ≤2，retrieve ≤4；失败、中断、压缩都计数，持久化预留不可退款。在线基准须以显式执行参数、固定计划与有限上限启动；不根据结果删题或改 Gold。

reproduce/retrieval47/ 只对应原47题与旧2450 chunk索引，其他指标按 registry.json 的范围分别评分。保存的语义判定必须标明开发者 AI 关系，不能冒充独立人工评审；模型 revision/实际费用未知写 unknown。产品改动不回写冻结复现包的成绩。

只暂存明确路径，不使用 add-all、强制推送或破坏性清理。变更前后核对密钥隔离、针对性测试、类型检查和离线复算。原实验留档分支保持只读。
