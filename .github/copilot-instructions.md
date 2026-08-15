# Copilot 使用说明

- Python 3.11 Flask 后端；路由在 `app/apis/urls.py`，实现位于 `app/apis/`。
- 配置由 `app/config.py` 从环境变量读取；不得提交真实密钥，测试使用 `.env.test.sample`。
- API 修改应同步验证 `tests/api/`；运行 `ruff check .`、`ruff format --diff .` 和 `pytest`。
- 项目导入的服务器文件仅允许来自 `MOEFLOW_IMPORT_DIRECTORY`，不得接受客户端提供的任意路径。