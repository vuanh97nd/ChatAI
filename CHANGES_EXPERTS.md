# Các file hoàn chỉnh trong bản cập nhật

Các file đã sửa trực tiếp trong dự án. Nội dung là toàn bộ file, không phải patch rời.

| File | Trạng thái |
|---|---|
| [assistant/document_intent.py](assistant/document_intent.py) | Mới |
| [assistant/documents.py](assistant/documents.py) | Mới |
| [assistant/document_pipeline.py](assistant/document_pipeline.py) | Mới |
| [assistant/orchestrator.py](assistant/orchestrator.py) | Mới |
| [experts.yaml](experts.yaml) | Mới |
| [glossary.json](glossary.json) | Mới |
| [run_document_benchmark.py](run_document_benchmark.py) | Mới |
| [tests/document_cases.json](tests/document_cases.json) | Mới |
| [tests/orchestrator_cases.json](tests/orchestrator_cases.json) | Mới |
| [tests/test_document_workflow.py](tests/test_document_workflow.py) | Mới |
| [tests/test_orchestrator.py](tests/test_orchestrator.py) | Mới |
| [ORCHESTRATOR.md](ORCHESTRATOR.md) | Mới |
| [DOCUMENT_WORKFLOW.md](DOCUMENT_WORKFLOW.md) | Mới |
| [desktop_ui.py](desktop_ui.py) | Sửa |
| [assistant/agent.py](assistant/agent.py) | Sửa |
| [assistant/routing.py](assistant/routing.py) | Sửa |
| [assistant/prompts.py](assistant/prompts.py) | Sửa |
| [assistant/web.py](assistant/web.py) | Sửa |
| [assistant/context.py](assistant/context.py) | Sửa |
| [assistant/answer_policy.py](assistant/answer_policy.py) | Sửa |
| [assistant/quality.py](assistant/quality.py) | Sửa |
| [assistant/rag.py](assistant/rag.py) | Sửa |
| [assistant/trial.py](assistant/trial.py) | Sửa |
| [assistant/ollama_setup.py](assistant/ollama_setup.py) | Sửa |
| [requirements.txt](requirements.txt) | Sửa |
| [requirements-bundled.txt](requirements-bundled.txt) | Sửa |
| [Chat-AI-Setup.iss](Chat-AI-Setup.iss) | Sửa |
| [tests/test_collaboration.py](tests/test_collaboration.py) | Sửa |
| [tests/test_web_quality.py](tests/test_web_quality.py) | Sửa |
| [tests/test_pipeline_quality.py](tests/test_pipeline_quality.py) | Sửa |

Kiểm thử trước điều chỉnh tự nhiên: 146 test qua. Sau yêu cầu bỏ bộ hướng dẫn, không chạy lại kiểm thử theo yêu cầu người dùng. Chưa triển khai Worker hoặc build EXE.

| File bổ sung sửa | Trạng thái |
|---|---|
| [work.js](work.js) | Sửa |
| [server/worker.js](server/worker.js) | Sửa |
| [tests/test_experience.py](tests/test_experience.py) | Sửa |

| File công cụ | Trạng thái |
|---|---|
| assistant/tools.py | Sửa |
| assistant/capabilities.py | Sửa |
| assistant/runner.py | Sửa |
| assistant/modules.py | Sửa |
| config.json | Sửa: auto_python=true |
| Dockerfile.python-tools | Mới |

Điều chỉnh cuối: prompt trả lời chỉ còn tên Chat AI và tiếng Việt. Không nạp thẻ kinh nghiệm/few-shot, không rà soát viết lại theo checklist, không áp thứ tự kết luận/giải thích hoặc cách hỏi lại. Quyền và xác nhận công cụ vẫn do mã nguồn kiểm soát. Chưa chạy lại kiểm thử theo yêu cầu.
