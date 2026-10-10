# 第三方来源

原创代码采用 MIT 许可。数据、论文与模型权重适用各自的来源许可。

| 来源 | 用途 | 许可 |
|---|---|---|
| [Pi SDK](https://github.com/earendil-works/pi) | Agent 会话编排 | MIT |
| [QASPER](https://huggingface.co/datasets/allenai/qasper/blob/main/README.md) | 论文文本与问答资料 | CC BY 4.0 |
| [BGE-M3](https://huggingface.co/BAAI/bge-m3) | 稠密向量检索 | MIT |
| [BGE-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) | Cross-Encoder 重排 | Apache-2.0 |
| FAISS、PyTorch、Transformers、rank-bm25 | 检索依赖 | 各上游包许可 |

依赖版本见 `package-lock.json` 与 `uv.lock`；论文来源见 `data/full-v1/manifests/corpus.json`，扩展原文来源见 `data/evaluation-v1/manifests/public-source-map.jsonl`。项目评测包含自行构建的对话与派生标注。

## 参考资料

- Dasigi, P., Lo, K., Beltagy, I., Cohan, A., Smith, N. A., & Gardner, M. (2021). [A Dataset of Information-Seeking Questions and Answers Anchored in Research Papers](https://aclanthology.org/2021.naacl-main.365/). NAACL-HLT.
- Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). [Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents](https://doi.org/10.48550/arXiv.2609.00065). 其中的 pi-agent 技能用于 SDK 开发参考。
