# 复现指南

## 查看评测结果

```powershell
npm run reproduce
```

根据仓库附带的测试记录重新统计结果，输出保存在 `.local/reproduction/`。

| 目录 | 内容 |
|---|---|
| `retrieval/` | 检索问题、证据跨度与各配置的召回记录 |
| `pipeline/` | 问答、引用及多轮记忆评测资料 |
| `intent/` | 意图分类结果 |
| `query-rewrite/` | Query 改写测试资料 |

各项指标使用的测试数据见 `registry.json`。检索和问答分别使用配套的语料与索引。

## 运行检索评测

完成 [本地检索环境](../docs/environment.md) 的安装后，查看运行计划：

```powershell
python reproduce/run_retrieval.py
```

执行 Dense、BM25、RRF 与重排的比较：

```powershell
python reproduce/run_retrieval.py --execute --run-id retrieval-demo
```

可用 `--limit` 控制范围，或通过 `--index-dir`、`--device` 指定索引和设备。新结果保存至 `.local/retrieval/<run-id>/`。

## 运行问答评测

准备评测用扩展语料：

```powershell
python scripts/restore_corpus.py --download --dataset pipeline
.venv\Scripts\python.exe -m retriever.p2 build --full --corpus-dir data/evaluation-v1/corpus --models-dir .cache/models --artifacts-dir artifacts/evaluation-v1 --device cuda
```

复制模型模板至 `configs/benchmark.local.json`，填写模型参数，将 `retrieval.corpus_dir` 设为 `data/evaluation-v1/corpus`，`retrieval.index_dir` 设为构建输出目录。

```powershell
node reproduce/run_agent.ts --arm C-no-reflect --role main --limit 4 --run-id qa-demo --config configs/benchmark.local.json
node reproduce/run_agent.ts --arm C-no-reflect --role main --limit 4 --run-id qa-demo --config configs/benchmark.local.json --execute
```

第一条查看计划，添加 `--execute` 后调用配置的模型服务。`--limit` 指定运行上限；`--run-id` 使用新名称。对话按顺序执行，保留真实上下文。

| 参数 | 选择 |
|---|---|
| `--arm` | `A` 基础流程；`C-no-reflect` 默认流程；`C` 反思消融 |
| `--role` | `main` 问答；`native_off` 无压缩；`compression` 压缩与恢复 |
| `--view` | `all`、`intent`、`rewrite`、`boundary`、`e2e` |

包含多轮依赖的指标使用完整对话运行，再按视图评分。结果保存至 `.local/benchmarks/`；`score_new.py` 用于整理评分记录和计算结果，参数见 `python reproduce/score_new.py --help`。

评测结果见 [结果页](../docs/results.md)。
