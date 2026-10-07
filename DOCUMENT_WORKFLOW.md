# Quy trình tài liệu tổng quát

Bản này dùng chung cho luật, tiêu chuẩn, báo cáo, bài báo, sách và chủ đề; không viết cứng một số hiệu tài liệu. Đã tích hợp vào Agent hiện tại, giữ nút web và quyền công cụ.

1. Một lời gọi phân loại sinh intent: task, target, target_type, identifiers (codes/years/issuers/authors), need_web, need_fulltext, câu độc lập và giả định. Truyền tối đa 10 lượt gần nhất trong ngân sách; câu nối tiếp dựa vào lịch sử. Lỗi JSON có fallback. Chuỗi mã định danh model thêm được kiểm tra có trong dữ liệu hội thoại; không coi dự đoán model là bằng chứng.
2. Tạo 2–3 biến thể từ đối tượng/định danh, bỏ động từ yêu cầu. Có thể kèm pdf hoặc toàn văn. Nhiều tài liệu có truy vấn riêng theo mã. glossary.json được đọc lại khi chạy, không cần đổi code; từ điển là dữ liệu người dùng, không tự chứng minh tên gọi chính thức.
3. File đính kèm/RAG ưu tiên trước web. Nếu cần đọc đủ tài liệu riêng, retrieval tìm file rồi đọc lại qua whitelist/hash. Khi nút web tắt thì chỉ dùng dữ liệu sẵn có; không dùng Python tìm lách quyền.
4. Bing có sẵn trong app, chấm liên quan theo tiêu đề/snippet, mã/năm, tên miền. Nguồn chính thống được cộng điểm sau khi đáp ứng liên quan; không chọn nguồn chỉ vì tên miền. Không có kết quả phù hợp thì thử truy vấn khác và báo chưa tìm được, không chế tên/mã/cơ quan.
5. Đọc 2–3 trang phù hợp; HTML lấy phần nội dung chính, PDF toàn bộ phần chữ có thể trích, DOCX phần chữ body/bảng/header/footer/chú thích. Có giới hạn 20 MiB, 1 triệu ký tự và 1500 trang; vượt giới hạn/scan/không giải mã thì có nhãn partial. HTML đọc hết trang không đồng nghĩa đã đọc toàn bộ một cuốn sách nằm ở liên kết khác. PDF scan chưa có OCR trang tự động trong reader.
6. Tài liệu dài chia phần, map từng phần rồi reduce phân cấp. Trích dẫn map phải có nguyên văn trong phần thật; ghi số phần thành công/lỗi. Không chỉ lấy vài phần đầu rồi gọi toàn văn. Chỉ gửi bản tổng hợp có nguồn/nhãn phạm vi vào model trả lời; context rút gọn không sửa snapshot gốc.
7. Theo yêu cầu mới, đã bỏ thẻ kinh nghiệm, few-shot và bộ hướng dẫn bố cục khỏi ngữ cảnh trả lời. Giữ prompt tối thiểu, metadata tài liệu, glossary và kết quả công cụ; AI tự chọn cách diễn đạt.
8. Chỉ thêm nguồn nếu câu trả lời sử dụng ID hoặc URL thật; mỗi nguồn một dòng tên trang - tiêu đề - URL đầy đủ. File có tên + vị trí trang/đoạn thực. Xóa ID không tồn tại. Không ép in footer ở mọi câu và không có câu “đã đọc phần nội dung bị cắt” cố định.

## Giới hạn bằng chứng

Chấm liên quan không phải xác minh pháp lý hay ngữ nghĩa hoàn hảo. Mã/năm từ URL/title/snippet vẫn cần đối chiếu bản gốc; các trường chưa xác minh được nêu rõ. Trích dẫn tồn tại nguyên văn không chứng minh summary diễn giải đúng; câu khó/cần chính xác cao có lượt rà soát, người dùng cần kiểm chứng nội dung quan trọng. Đọc trọn phần chữ khác với đọc tất cả hình, scan, liên kết và phụ lục riêng.

Dịch tài liệu ngắn có thể đưa nguyên văn vào context. Với tài liệu dài đã map-reduce, không nhận bản dịch ghi chú là bản dịch đầy đủ: cần xử lý bản dịch theo từng phần. DOCX không tạo số trang giả vì phân trang phụ thuộc Word/máy in. RAG vẫn giới hạn index 100000 ký tự theo cơ chế hiện tại; file lớn cần chia khi index, reader có giới hạn riêng.

## Kiểm thử

`tests/document_cases.json`: 20 câu đa lĩnh vực gồm viết tắt, thiếu thông tin, câu nối tiếp, tài liệu không tồn tại và file đính kèm. `tests/test_document_workflow.py`: kiểm tra truy vấn sạch, context/glossary, liên quan, tải toàn văn, PDF scan, DOCX, map-reduce, nguồn dùng có điều kiện và quyền web.

```bat
runtime\python\python.exe -m unittest discover -s tests -q
runtime\python\python.exe run_document_benchmark.py --case 5
runtime\python\python.exe run_document_benchmark.py --case 5 --web
```

`--web` là hành động chủ động của người chạy benchmark, tương đương bật nút Tìm kiếm mạng. Không có tham số này thì tắt toàn bộ web. Có thể dùng `--attachment path\file.pdf` cho các case file. Kết quả benchmark lưu trong data, gồm kiểm tra cơ học và ô chấm nội dung bằng người; không coi kiểm tra từ khóa là đã đánh giá chất lượng model.

Chấm mỗi câu 0–2 cho: đúng ý/không hỏi thừa; không bịa; truy vấn đúng đối tượng; nguồn hỗ trợ kết luận; bao phủ phạm vi đọc. Lỗi bịa nội dung/nguồn hoặc tìm khi tắt web là không đạt dù tổng điểm cao. Khi nguồn không tồn tại hoặc chỉ có snippet, câu đạt phải nói đúng giới hạn thay vì ép đưa bản tóm tắt. Lưu phản hồi 👎 là dữ liệu để phân tích và sửa prompt/công cụ, không phải model tự học hay đã huấn luyện lại.

## Điều chỉnh theo yêu cầu mới

Đã rút gọn cả prompt local và CHAT_AI_PROMPT ở work.js/server/worker.js. File ví dụ trước đây chỉ còn phục vụ tham khảo, không được nạp vào câu trả lời. Worker trực tuyến cần triển khai lại work.js trên Cloudflare để có hiệu lực. Không chạy lại kiểm thử sau lần điều chỉnh này theo yêu cầu người dùng.

Điều chỉnh cuối: prompt trả lời chỉ còn tên Chat AI và tiếng Việt. Không nạp thẻ kinh nghiệm/few-shot, không rà soát viết lại theo checklist, không áp thứ tự kết luận/giải thích hoặc cách hỏi lại. Quyền và xác nhận công cụ vẫn do mã nguồn kiểm soát. Chưa chạy lại kiểm thử theo yêu cầu.
