# 模型与运行配置

configs/model.example.json 是无服务地址、无模型名、无密钥的结构模板。复制到被忽略的 configs/model.local.json，填入使用者自己的服务信息。CLI 不接受 api_key、headers、任意附加参数或 URL 中的用户名/密码、查询串及片段。

model.base_url 应为 Chat Completions 服务根地址，例如自己的服务文档规定的 /v1 入口；不能填完整 /chat/completions 端点。HTTP 仅允许 localhost，其余服务使用 HTTPS。model_id 必须是使用者账户可调用的模型，并支持工具调用。context_window 填服务真实容量，max_output_tokens 是每次生成/辅助请求的上限；压缩请求保留 Pi 原生分配，但总请求次数仍被拦截。

thinking_level 不在宿主偷偷升档：普通生成和辅助阶段使用同一配置。off 时禁用推理；reasoning=false 必须配 off。服务支持推理时可设置 reasoning=true、thinking_level=low、compat.supportsReasoningEffort=true；实际参数由 Pi SDK 兼容实现投影。模型的服务端权重 revision 无法核实，记录 unknown。

允许的兼容布尔字段：supportsStore、supportsDeveloperRole、supportsReasoningEffort、supportsUsageInStreaming、supportsFinishReason、requiresToolResultName、requiresAssistantAfterToolResult、zaiToolStream。maxTokensField 仅接受 max_tokens / max_completion_tokens；thinkingFormat 仅接受 Pi 1.0.4 的内置格式，如 openai、zai、qwen。供应商要求特定格式时照其官方文档填，不由项目猜测。

session.max_turns 是每个日常会话的有限轮数上限，默认20，配置范围1..1000；每轮固定12次请求尝试、search2次、retrieve4次。两种时间上限分别限制单请求与整轮。主流程关闭 Reflect，保留 NLU、结构化记忆、证据校验与可选原生压缩；不加载 Pi 的个人模型目录、扩展、技能、MCP 或默认系统工具。

会话目录 .local/sessions/<name>/ 包含追加式预算 ledger、脱敏后的最终答案/动作/usage和快照。快照删除隐藏思考，保留 Pi 原生 compaction entry、对话、用户约束及最终回答。恢复需同时匹配配置、源代码与索引身份。session.lock 防止两个进程使用同一会话；异常退出后先确认进程已终止，再手工移除该会话的旧 lock。中断的已预留轮与请求保留计数，不能自动补跑收费请求。

CLI 保存的文本可能含你自己的问题或论文内容，应按个人数据管理；这些文件默认不会被 Git 跟踪。更换模型、改代码或索引后使用新的会话名。配置文件中不写 key；只通过 PIPAPER_API_KEY 注入内存，worker 子进程不继承该变量。
