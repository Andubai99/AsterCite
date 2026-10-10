# 按指标复现

最快的入口是 npm run reproduce：不调用模型、不启动检索 worker，核对公开文件哈希后，从保存的逐题记录复算。它能复核计分和表格，不是再次运行语言模型，也不是重新进行语义评审。目录与分母见 registry.json；完整结果在 docs/results.md。

| 指标 | 题集 / 视图 | 记录与评分 |
|---|---|---|
| 检索 Span Recall@5 | retrieval47/cases.jsonl，原47题，旧2450 chunk索引 | top5.jsonl 共188条；每题多个 Gold 备选组，要求完整 Unicode 跨度覆盖，逐题取最高备选组召回，再平均 |
| 五分类 | agent295/views.json 的 intent，各100题 | original.jsonl 的原始模型标签与宿主接受标签分别计分，缺失计错 |
| Query 改写 | views.json 的 rewrite，各100题 | query-rewrite100/packets.json 与200条显式语义判定，失败/缺失保留分母 |
| 主任务 / 流程完成 | agent295/cases.jsonl，295题；test177单列 | 保存的最终答案、可见证据、请求usage、语义判定；任务正确与工程完成分开 |
| 边界 / 拒答 | boundary55，拒答15，证据不足7 | 真实输出的动作判定；各自的case范围，不混为一个“拒答准确率” |
| 引用支持 / 完全正确 | 逐条引用 / 需引证的242题 | 可见chunk存在性与逐条语义支持；引用数量因配置不同而不同 |
| 端到端 | e2e70 | 主实验的重叠视图，单独给任务与流程指标 |
| 压缩 / 恢复 / token | 30组 × 4轮，t3/t4各30 | compression/native_off记录，固定168次欠费/依赖失败补跑；配对完成且usage完整的对话才纳入token均值 |

这些视图有重叠，不能相加。295题开发118/测试177；源问题及论文关联使它们不是295个独立样本。公开包有1605条计分位置记录（主集885 + 两种对话对照各360）和168条固定补跑，原实验1617中12条接入预检不纳入效果表。

## 证据与判定关系

original.jsonl / credit-recovery.jsonl 是原始文件的公开安全投影：最终答案、结构化动作、可见source identity、usage、压缩/恢复信息和判定。source_outcome_sha256 绑定本地保存的完整原始文件，公开文件自身的字节哈希登记在 manifest.json。隐藏思考、完整 provider stream、个人配置与密钥不导出。

scoring.py 保留历史语义判定的计分规则。run.py 重新检查每个必答子问题、动作、约束、来源可见性、引用支持和记忆一致性，再聚合；不是直接读取 expected.json 当成绩。expected 是独立校验目标。开发者 AI 是 Gold 和语义判定的复核者，不标为独立人工盲评。

压缩补跑只替换固定选定的42条欠费失败及126条依赖失败；不选优、不替换原先成功的位置、不修改主295题表。历史 /low 模型身份保留在本地留档；服务端权重 revision 和实际费用 unknown。当前98题检索结果不进入默认表，仍保存在本地 AC 实验分支。

## 重新运行原47题检索

先按 README 恢复旧语料、两份固定权重及旧 CUDA 索引。查看计划：

```powershell
python reproduce/rerun_retrieval47.py
```

执行完整四配置比较（最多188次本地查询，生成 API 调用0）：

```powershell
python reproduce/rerun_retrieval47.py --execute --run-id original47-local-001
```

仅接入检查可加 --limit 1，得到每配置1题、共4次查询。部分运行明确标成 partial/full_original47=false，不写入正式表。新记录进入 .local/retrieval47/<run-id>/；目录已存在会拒绝启动，不覆盖历史。CPU 必须填写另建的索引路径与 --device cpu，属于新索引对照。

## 恢复295题历史语料并运行新基准

295题使用另一份语料，不改变原47题基线：

```powershell
python scripts/restore_corpus.py --download --dataset agent295
.venv\Scripts\python.exe -m retriever.p2 build --full --corpus-dir data/abc295-v3/corpus --models-dir .cache/models --artifacts-dir artifacts/abc295-v3 --device cuda
```

该语料在旧48篇原段落后追加固定公开来源节与 PDF 页转录；增量和终态语料逐文件核验哈希，原 PDF 下载不分发。原命名中的 abc295-v3 是冻结来源身份，保留便于核验，与本地分支改名无关。

另复制模型模板为被忽略的 configs/agent295.local.json，填写自己的模型配置，将 retrieval.corpus_dir 改为 data/abc295-v3/corpus，index_dir 改为构建输出的3801 chunk索引目录。不要将日常旧索引配置替换成它来展示47题成绩。

```powershell
node reproduce/run_agent.ts --arm C-no-reflect --role main --limit 4 --run-id integration-001 --config configs/agent295.local.json
node reproduce/run_agent.ts --arm C-no-reflect --role main --limit 4 --run-id integration-001 --config configs/agent295.local.json --execute
```

第一条仅打印计划；第二条明确调用使用者的模型账户。执行必须给新 run-id 和有限 limit。A、C、C-no-reflect可分别运行；role=main完整295题，native_off和compression各120轮。完整基准分别设置limit295/120；压缩对照执行真实t3压缩、t4快照恢复。启动前预留整张有限矩阵，每轮 ≤12请求，失败不退款；不自动重跑已有 run-id。任一实际前置轮失败，其后依赖轮保留为失败，不代入理想答案。

run-plan.json 仅提供问题、会话顺序与公开声明范围；检索 worker只读 corpus。包含对话依赖的模块视图需先运行完整 main，再在独立评分中取对应视图，不能丢掉前置轮为省钱而宣称正式复现。subset limit只用于新接入/有限子集验证，不能写成完整295成绩。

新结果保存在 .local/benchmarks/，语义评分状态为 pending。可以用 score_new.py 生成评审模板、填入显式判定后再计分；它不自动让同一模型当裁判。不同使用者模型、服务端权重变化或新源码身份，不保证复刻原成绩。在线基准入口未在本次公开整理中发起付费运行。
