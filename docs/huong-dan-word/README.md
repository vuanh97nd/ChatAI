# Hướng dẫn sử dụng ChatAI

[Tải bộ 6 tài liệu sử dụng chung](https://github.com/vuanh97nd/ChatAI/raw/refs/heads/main/docs/huong-dan-word/Bo_huong_dan_ChatAI_2026-10-11.zip).

[Tải 3 tài liệu kỹ thuật riêng](https://github.com/vuanh97nd/ChatAI/raw/refs/heads/main/docs/huong-dan-word/Ba_huong_dan_PLAXIS_GeoStudio.zip):

- [PLAXIS 2D 2024.2](07_PLAXIS_2D_2024_2.docx): dữ liệu, Remote Scripting, hình học/tunnel, vật liệu, lưới, pha, tính toán và Output.
- [PLAXIS 3D 2024](08_PLAXIS_3D_2024.docx): tọa độ X/Y/Z, hình học 3D, cấu kiện, vật liệu, lưới, pha và kết quả.
- [GeoStudio 2025.1.1 / SLOPE/W](09_GeoStudio_2025_1_1.docx): BTH, SLTT, DXF, địa tầng, vật liệu, nước/tải, miền tìm trượt và Fs mới.

Ba tài liệu kỹ thuật hướng dẫn giao việc và kiểm tra kết quả với ChatAI. Hình trong tài liệu là logo và sơ đồ minh họa có chú thích, chưa phải ảnh chụp giao diện phần mềm. Cần bổ sung manual/ảnh thực tế đúng phiên bản để hoàn thiện hướng dẫn bấm từng nút. Không dùng các sơ đồ khái niệm làm dữ liệu công trình.

Tạo lại tài liệu bằng Python có `python-docx`, `Pillow` và `matplotlib`:

```bash
python docs/huong-dan-word/build_guides.py
python docs/huong-dan-word/build_technical_guides.py
```

Các file Word đã được kiểm tra cấu trúc DOCX, bảng và hình nhúng; chưa kiểm tra dàn trang bằng Microsoft Word trong môi trường Windows.
