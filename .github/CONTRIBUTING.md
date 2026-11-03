# 贡献指南

## 分支与提交

- 分支从 `main` 切出，命名 `feat/xxx`、`fix/xxx`、`chore/xxx`。
- 提交信息遵循 `type(scope): subject`，如 `fix(audio): 转码失败时回退原文件`。

## 提交前自检

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

钩子包含 black / isort / flake8 / mypy / pydocstyle 与若干文件卫生检查，
全部通过再提 PR。

## 代码约定

- 面向 Python 3.13+，不使用高版本专属语法。
- 发送语音前先判 `ffmpeg` 可用性，不可用时降级为原文件，不要直接抛错。
- 新增配置项必须同时更新 `_conf_schema.json` 与 `core/config.py` 的默认值。
