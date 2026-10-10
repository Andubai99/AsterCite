# 固定环境与索引恢复

完整检索的已验证平台：Windows x64，Node24.11.1、Python3.12.7、uv0.10.12。Pi npm 三个核心包1.0.4，来源基线7c10bd4337495ee613f2224843ecdf349b80d1df。package-lock.json 和 uv.lock 锁定传递依赖；uv.lock 只限定 Windows AMD64，当前不声称 Linux/GPU 跨平台复刻。

| 本地检索依赖 | 版本 |
|---|---|
| torch | 2.9.1 / cu128 |
| transformers | 4.57.3 |
| numpy | 2.3.5 |
| faiss-cpu | 1.15.1 |
| rank-bm25 | 0.2.2 |

BGE-M3 revision5617a9f61b028005a4858fdac845db406aefb181；reranker revision953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e；逐文件大小及哈希见 data/manifests/p2-models.json。权重约4.6GB，另需环境、语料与索引空间。本项目顺序装载 GPU 模型；缺 CUDA 或 OOM 明确失败，不静默换 CPU。已有硬件不足时，重新构建完整 CPU 索引并改配置；那是新身份。

恢复步骤见 README。旧源语料恢复后 SHA-256 为 e360ee218d8cc14751343ec90bc49c32c90a43d352f7472378dd4c23311f1654，共48篇。构建采用原段落内512 token窗口、64 token重叠、同时2000 codepoint可见上限；BGE-M3归一化CLS、FAISS IndexFlatIP、BM25；两路各20候选、RRF k=60，再由固定 cross-encoder 重排取5。recipe、dtype、device、依赖和模型文件进入索引身份。

原47题的历史 CUDA 索引身份为 pipaper-full-index-v1-e7699c38391f1315，共2450 chunk。295题历史主实验使用独立的扩展 PDF 语料和3801 chunk索引 pipaper-full-index-v1-64b1aa77167d5715；不要混用配置或将扩展索引的分数写成原47题基线。恢复第二份语料和在线基准步骤见 reproduce/README.md。

npm run doctor 只检查状态，不输出密钥，不发生成请求。尚未配置模型或尚未下载资产时返回缺失状态；这不会妨碍 demo、离线复算和纯契约测试。

常见问题：MISSING_KEY 表示当前终端未设置变量；INVALID_INDEX 表示源文件、配方或模型/依赖与索引不一致；SESSION_LOCKED 表示会话正使用或保留中断 lock；INVALID_SNAPSHOT 表示绑定或来源校验失败。遇到文件哈希不一致保留原文件核查，工具不会用新文件覆盖它。
