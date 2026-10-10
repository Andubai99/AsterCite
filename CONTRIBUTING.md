# 贡献与验证

先阅读 AGENTS.md。功能设计保存到 docs/specs/，实施计划保存到 docs/plans/。运行 npm run check、npm test、npm run test:reproduce、npm run audit；新增确定性边界配套测试。

修改产品源码可以产生新的运行身份，不修改冻结 Gold 或从输出中删失败题。新题集/索引另起版本，结果说明包含分母、失败项、模型参数、usage未知情况和判定者关系。不得上传 model.local.json、.env、.local会话或个人凭据。

提交使用英文类型前缀和中文摘要。发布只包含经过审查的源码、来源manifest和脱敏复现资料。发现凭据泄漏请先私下联系仓库维护者，并立即在服务端吊销凭据；不在公开 issue 粘贴密钥。
