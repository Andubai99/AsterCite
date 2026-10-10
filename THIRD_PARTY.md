# 第三方来源与许可

项目原创代码采用 MIT。论文、评测数据及下载的权重按各自来源许可使用，代码许可不重新授权论文内容。

| 来源 | 本项目使用方式 | 许可 / 来源 |
|---|---|---|
| Pi SDK 1.0.4 | 锁定的 npm 依赖；不复制或修改上游源码 | MIT；[Pi 仓库](https://github.com/earendil-works/pi) |
| QASPER v0.3 | 固定48篇论文的公开文本、原问题及派生标注；原下载不提交 | CC BY 4.0；[官方数据卡](https://huggingface.co/datasets/allenai/qasper/blob/main/README.md)、[论文](https://aclanthology.org/2021.naacl-main.365/) |
| BAAI/bge-m3 | 固定 revision 本地 dense embedding | MIT；[模型卡](https://huggingface.co/BAAI/bge-m3) |
| BAAI/bge-reranker-v2-m3 | 固定 revision 本地 cross-encoder 重排 | Apache-2.0；[模型卡](https://huggingface.co/BAAI/bge-reranker-v2-m3) |
| FAISS、Torch、Transformers、rank-bm25 等 | 精确版本依赖，不在仓库内分发依赖本体 | 遵从各上游包许可；版本在 package-lock.json / uv.lock |

QASPER 引用：Dasigi, P., Lo, K., Beltagy, I., Cohan, A., Smith, N. A., & Gardner, M. (2021). A Dataset of Information-Seeking Questions and Answers Anchored in Research Papers. NAACL-HLT. https://aclanthology.org/2021.naacl-main.365/

论文级标题、arXiv 来源地址与原文哈希见 data/full-v1/manifests/corpus.json。用于历史295题的 PDF 页转录与分块来源见 data/abc295-v3/manifests/public-source-map.jsonl；节选保留作者来源，完整 PDF 不在本仓库内分发。派生问答、对话、Gold 与评分规则是项目评测设计，不能标成原始 QASPER 官方 benchmark 成绩。

本次 SDK 接入查阅了 Scientific Agent Skills 的 pi-agent 技能；技能属于开发参考，未进入模型运行时。参考：Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*. https://doi.org/10.48550/arXiv.2609.00065

权重与第三方依赖的下载明确由使用者触发。生成模型使用使用者自己的服务与账户，其费用、额度和条款由该服务决定；本仓库不提供共享 API key。
