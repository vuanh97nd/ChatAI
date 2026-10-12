# Ngữ cảnh gọn khi tính PLAXIS

Bản này dựa trên commit `0b2081d` (merge lúc 19:19 ngày 12/10/2026,
giờ Việt Nam). Giữ nguyên các thay đổi bộ nhớ dài hạn của bản đó.

Chỉ bật khi đang làm PLAXIS; tác vụ nghiên cứu web hoặc ứng dụng khác giữ
luồng cũ. Áp dụng cho các nhà cung cấp trong quy trình PLAXIS, gồm DeepSeek,
NVIDIA và OpenRouter.

- Gửi một bộ hướng dẫn ngắn thay các đoạn hướng dẫn ứng dụng không liên quan.
  Giữ chính sách manual, kiểm chứng vùng đào và hình học.
- Giữ nguyên toàn bộ schema tham số, enum, required và additionalProperties;
  mô tả công cụ được rút gọn. `version`, `target`, `commands` vẫn bắt buộc.
- Giữ yêu cầu mới nhất đầy đủ, yêu cầu gốc và hai yêu cầu trước để nối tiếp.
  Không đưa JSON lời gọi cũ vào lịch sử làm mẫu cho LLM.
- Gửi tối đa sáu kết quả gần nhất và ảnh công cụ mới nhất của lượt hiện tại.
  Kết quả mới nhất có ngân sách 10.000 ký tự, kết quả cũ 1.400 ký tự.
  Kết quả dài giữ đầu/cuối và đánh dấu rõ chưa đầy đủ. Không được suy ra
  giá trị, Active hay xác minh từ phần bị lược bỏ.
- Bộ nhớ tài liệu liên quan: tối đa 8.000 ký tự mỗi lượt; bộ nhớ quy trình
  tối đa 3.000; cú pháp đã thành công tối đa 4.000. Các trang đã đọc và
  bảng kiểm tutorial vẫn có trong ngữ cảnh. Khi thiếu dữ kiện, đọc đúng
  mục/đối tượng, không OCR lại toàn bộ manual.

Full state, kết quả gốc, bộ nhớ lưu trữ, quyền thao tác, chống lặp và guard
trước đổi Active/calculate không bị chỉnh sửa hoặc bỏ qua.

Nhật ký `automation_plaxis_context` ghi profile `plaxis-compact-1`, provider,
text_chars, số message và độ dài lịch sử gốc. `ai_usage` của server mới là
số liệu token thực tế; không quy đổi ký tự thành token hoặc tiền theo tỉ lệ cố định.

Kiểm tra đã chạy: 103 kiểm tra context, automation, staged guard và case memory.
Schema công cụ giảm 24.884 → 13.639 ký tự (45,2%). Trên dữ liệu thử 100 vòng,
lịch sử gửi lại giảm 14.815 → 8.085 ký tự so với context NVIDIA cũ.
Các số này chưa đo trên bài PLAXIS thật, chưa chứng minh giảm tương ứng thời gian,
chi phí hoặc số token. Chưa thử giao diện Windows/PLAXIS trực tiếp.

Cập nhật PC bằng nhánh `optimize-plaxis-token-context`:

```powershell
git fetch origin optimize-plaxis-token-context
git switch --detach FETCH_HEAD
```

Đóng Chat AI trước khi chuyển mã, mở lại sau khi cập nhật. Nếu có sửa local,
cất vào stash trước; không tự áp stash cũ lên bản này. Không cần deploy Worker
để áp dụng tối ưu ngữ cảnh ở desktop.
