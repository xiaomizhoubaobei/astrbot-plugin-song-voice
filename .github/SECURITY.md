# 安全策略

## 报告漏洞

请**不要**通过公开 Issue 报告安全问题，改用以下任一渠道：

1. 仓库 **Security → Advisories → Report a vulnerability**（推荐，支持私密协作）；
2. 直接联系维护者（见 `metadata.yaml` 的 `author` 字段）。

我们会在 7 天内初步回应，并在修复发布后致谢。

## 协调披露

修复发布前，请勿在公开渠道披露细节。`ai-audit` 自动创建的 Issue 只会包含
告警编号与安全等级，规则名、文件路径与复现细节保留在 Code Scanning 面板中。

## 支持的版本

只对 `main` 上的最新版本与最近一个 Release 提供安全修复。
