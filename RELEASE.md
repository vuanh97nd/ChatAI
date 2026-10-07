# Phát hành bản cập nhật trên GitHub

Repo dùng cho cập nhật: https://github.com/vuanh97nd/ChatAI

1. Đưa mã dự án vào repo của bạn, giữ nguyên `config.json` mẫu; không đưa `.venv`, lịch sử SQLite, tài liệu, model tải về hoặc secrets.
2. Trước bản mới, cập nhật `CURRENT_VERSION` trong `assistant/updater.py`, phiên bản hiển thị trong `desktop_ui.py` và `app.py`, cùng `AppVersion` trong `Chat-AI-Setup.iss`. Ví dụ: `2.6.0`. Giữ nguyên AppId của Inno Setup để nâng cấp bản đang cài.
3. Ghi tính năng/lỗi sửa thực tế trong CHANGELOG.md. Chạy Build-Setup.bat trên Windows có Inno Setup6.
4. GitHub → Releases → Draft a new release → tag `v2.6.0`; ghi release notes bằng tiếng Việt. Đính kèm `Chat-AI-Setup-2.6.0.exe`, có thể thêm `Chat-AI-2.6.0.zip`. Không chỉ dùng ZIP mã nguồn tự tạo bởi GitHub: updater tìm asset có tên Chat-AI hoặc ChatAI và đuôi exe/zip.
5. Publish release chính thức (không draft/prerelease). Repo cần public để ứng dụng đọc mà không có token GitHub.
6. Người dùng vào Cài đặt → Cập nhật → Kiểm tra cập nhật; app đọc API releases/latest, so sánh tag với bản đang chạy, hiển thị ghi chú và hỏi trước khi tải.
7. File được tải vào `%LOCALAPPDATA%/ChatAI/updates`; app kiểm kích thước và đối chiếu SHA256 nếu GitHub có digest. Đóng Chat AI, chạy bộ cài vừa tải. Không tự chạy EXE, không tự thay mã đang chạy.

Bộ cài giữ config hiện có và dữ liệu tại thư mục cài. Bản chạy trực tiếp trong Google Drive có dữ liệu riêng; cài sang thư mục mới không tự chuyển lịch sử cũ. Với ZIP, chỉ cập nhật mã chương trình; giữ config.json, data, workspace và .venv. Chưa có cập nhật tự động schema/downgrade hoặc rollback toàn bộ ứng dụng.

`server /api/update` trả URL releases/latest theo repo này. Worker cloud phải được triển khai riêng khi thay đổi worker; bộ cài Windows không deploy Cloudflare. Phiên này đã chuẩn bị mã; chưa push repo hoặc tạo release trên GitHub.
