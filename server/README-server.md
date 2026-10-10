# Chat AI Server 2.5

Worker Cloudflare viết lại từ `worker.js` bạn cung cấp. Đây là server cloud tùy chọn, không thay thế Ollama trên máy Windows. Ứng dụng desktop hiện vẫn dùng Ollama; desktop đã có form Tạo tài khoản mới trong Cài đặt khi bạn nhập URL HTTPS; chat AI cloud và desktop đã có đăng nhập bắt buộc, ghi nhớ DPAPI và bộ nhớ riêng dùng với Ollama; provider suy luận cloud còn là API riêng.

## Các tính năng

- Tài khoản đăng ký/đăng nhập, đổi mật khẩu, hạn dùng trial/pro/oem; theo dõi thiết bị và heartbeat.
- Quản trị tài khoản, trạng thái online, broadcast, hàng đợi thông báo email cho bridge bên ngoài. Email xác minh tài khoản và đặt lại mật khẩu được gửi qua Resend; xem [cấu hình email](../docs/email-setup.md).
- Chat hỗ trợ giữa người dùng và admin; tin nhắn, ảnh JPEG, file, đánh dấu đọc/chưa đọc, trạng thái đang gõ, gửi chống trùng client_id.
- Trợ lý tiếng Việt: Cloudflare Workers AI, Gemini, DeepSeek API, OpenAI, Groq, NVIDIA; provider không cấu hình trả lỗi rõ. Tên model và quyền truy cập phụ thuộc tài khoản nhà cung cấp; sửa các biến model nếu model cũ không còn khả dụng.
- Tra web Brave Search độc lập với model, có URL nguồn; chỉ lấy trích đoạn tìm kiếm, không tự đọc toàn văn.
- Phân tích ảnh/tài liệu qua `/api/chat/ai`; desktop phải gửi văn bản đã trích từ Office, không gửi binary DOCX/XLSX để Worker tự phân tích.
- Streaming SSE ở `/api/chat/stream` cho chat văn bản: Cloudflare, OpenAI, Groq, DeepSeek, NVIDIA. Gemini dùng endpoint JSON. SSE chuẩn hóa thành meta/delta/done/error.
- Lịch sử chat AI riêng theo tài khoản ở `/api/conversations/*`; API riêng với chat hỗ trợ. Xóa là ẩn mềm, giữ dữ liệu để khôi phục, không xóa vĩnh viễn.
- Agent lập kế hoạch JSON từ `agent_schema`, chưa thực thi tool. Desktop cần kiểm tra whitelist, xác nhận, backup, audit và chạy vòng lặp. Server không chạy Python, sửa Excel, tạo PNG/video hoặc truy cập file Windows.
- Trích dữ liệu chung: `extraction_kind: "document"`. Hai contract geology/boreholes và mapping địa kỹ thuật giữ lại để tương thích tính năng file gốc; không bắt buộc cho trợ lý cá nhân.
- Bộ nhớ chung knowledge/mapping, cursor đồng bộ, công bố/thu hồi có nhật ký. Chỉ Admin được ghi/công bố; tài khoản trả phí đọc đồng bộ. Đây không phải Chroma RAG: RAG cá nhân vẫn ở desktop.
- CORS theo danh sách origin; giới hạn kích thước thực của body, kiểm tra JSON, rate limit theo phút, PBKDF2 cho mật khẩu mới/được Admin đặt lại, không trả mật khẩu trong danh sách Admin. Logout cần xác thực.

## Cài server bằng Wrangler

1. Cài Node.js LTS, mở Terminal trong thư mục `server`.
2. Chạy:

```powershell
npm install
npx wrangler login
npx wrangler d1 create chat-ai-db
```

3. Sao chép `database_id` được trả về vào `wrangler.jsonc`. Dùng D1 riêng cho Chat AI; không trỏ vào cơ sở dữ liệu đang chạy của ứng dụng khác.
4. Tạo secret Admin (mật khẩu dài, ngẫu nhiên):

```powershell
npx wrangler secret put ADMIN_KEY
```

5. Cloudflare Workers AI dùng binding `AI` có sẵn trong cấu hình. Muốn provider khác, thêm secret tương ứng; chỉ thêm những dịch vụ cần dùng:

```powershell
npx wrangler secret put GEMINI_API_KEY
npx wrangler secret put DEEPSEEK_API_KEY
npx wrangler secret put OPENAI_API_KEY
npx wrangler secret put GROQ_API_KEY
npx wrangler secret put NVIDIA_API_KEY
# Bing RSS mặc định: không cần secret tìm kiếm.
```

6. Điền `ALLOWED_ORIGINS` nếu có web client, ví dụ `https://chat.example.com,http://localhost:5173`. Để rỗng thì chỉ nhận request không có Origin (Python desktop/cURL); Origin từ trình duyệt bị từ chối. Không dùng dấu `*`.
7. File lớn nên có KV: chạy `npx wrangler kv namespace create CHAT_AI_KV`, thêm binding `CHAT_AI_KV` và ID vào `kv_namespaces` trong cấu hình. Nếu không có KV, file lớn vượt giới hạn D1 của file gốc bị từ chối.
8. Triển khai khi bạn sẵn sàng:

```powershell
npm run deploy
```

Các bảng D1 được tạo/migrate lần yêu cầu đầu. Cron dọn rate limit, heartbeat, typing và thống kê AI cũ; không dọn lịch sử chat. Không có quota câu hỏi theo ngày do worker áp đặt, nhưng vẫn có rate limit theo phút và hạn mức/tính phí nhà cung cấp.

Có thể dán toàn bộ `worker.js` vào Dashboard và tạo bindings/secrets thủ công thay cho Wrangler. Chưa triển khai vào tài khoản Cloudflare của bạn trong phiên này.

## Biến cấu hình

| Biến/binding | Công dụng |
|---|---|
| DB | D1 bắt buộc |
| AI | Workers AI cho provider cloudflare |
| CHAT_AI_KV hoặc KV | Tùy chọn lưu file/ảnh lớn |
| ADMIN_KEY | Secret quản trị; không nhúng vào ứng dụng người dùng |
| ALLOWED_ORIGINS | Danh sách origin chính xác, phân tách dấu phẩy |
| CHAT_AI_AI_MODEL | Gemini: `auto` quét model Flash từ ListModels, hoặc tên model cụ thể |
| CLOUDFLARE_AI_MODEL / CLOUDFLARE_AI_VISION_MODEL | Model văn bản/ảnh Cloudflare |
| OPENAI_MODEL / OPENAI_VISION_MODEL | Model OpenAI |
| GROQ_MODEL / GROQ_VISION_MODEL | Model Groq |
| DEEPSEEK_MODEL | Model API DeepSeek; khác với tag Ollama `deepseek-r1:8b` |
| NVIDIA_MODEL / NVIDIA_VISION_MODEL | Model NVIDIA |
| CHAT_AI_DOWNLOAD_URL | URL tải bản desktop của bạn; mặc định rỗng |
| CHAT_AI_RELEASE_NOTES | Thông tin cập nhật |

## API và dữ liệu mẫu

API tài khoản nhận POST JSON. Xác thực hiện dùng `username` + `key` trong mỗi yêu cầu HTTPS; `key` là mật khẩu, không phải token phiên. Không lưu/log mật khẩu trong client. Admin API dùng header `admin-key`. Chưa có JWT/token refresh.

| API | Phương thức | Nội dung |
|---|---|---|
| /api/health, /api/update | GET | Trạng thái, bản cập nhật |
| /api/register | POST | username,password,fullname,email bắt buộc |
| /api/login | POST | username,key,device_id |
| /api/logout | POST | username,key |
| /api/change_password | POST | username,old_key,new_key |
| /api/models | POST | username,key; danh sách dịch vụ đã cấu hình |
| /api/chat/ai, /api/ai/consult | POST | username,key,provider,text,history; image/document/context tùy chọn |
| /api/chat/stream | POST | username,key,provider,text,history |
| /api/chat/search | POST | username,key,text; từ khóa <=600 ký tự/75 từ |
| /api/conversations/list | POST | username,key,offset tùy chọn |
| /api/conversations/create | POST | username,key,title |
| /api/conversations/get | POST | username,key,conversation_id,after_id tùy chọn |
| /api/conversations/append | POST | username,key,conversation_id,role,content,client_id |
| /api/conversations/delete | POST | username,key,conversation_id,confirm:true |
| /api/chat/send, list, read, typing, unread, conversations, file, image, delete, admin-status | POST | Giao thức chat hỗ trợ của file gốc; peer/id tùy endpoint |
| /api/activity/heartbeat, logout | POST | username,key,session_id; heartbeat có device_id,sequence,active_seconds |
| /api/admin/users | GET/POST/DELETE | Header admin-key; POST tạo/sửa, DELETE dùng username trong query |
| /api/admin/broadcast | POST | Header admin-key; text,client_id |
| /api/admin/email/pending, ack | GET/POST | Bridge ngoài đọc hàng đợi rồi xác nhận id |
| /api/memory/shared/sync, pending, review | POST | username,key và payload theo schema file gốc |

Ví dụ chat:

```json
{"username":"alice","key":"YOUR_PASSWORD","provider":"cloudflare","text":"Chào Chat AI","history":[]}
```

Ví dụ tài liệu (văn bản do desktop đọc):

```json
{"username":"alice","key":"YOUR_PASSWORD","provider":"cloudflare","text":"Tóm tắt tài liệu này","document":{"name":"bao-cao.docx","text":"Nội dung đã trích..."}}
```

Ví dụ SSE:

```text
event: delta
data: {"text":"Xin chào"}

event: done
data: {"success":true,"characters":8}
```

`/api/chat/ai` và streaming không tự lưu lịch sử. Client gọi create/append để lưu message, get để lấy lịch sử rồi gửi history vào AI. client_id dùng UUID cho từng message; retry gửi lại cùng client_id không tạo bản sao. Phân trang get tối đa100 message, dùng next_after_id. Xóa giữ lại dữ liệu trên server; đây chưa phải công cụ xóa dữ liệu vĩnh viễn.

Lỗi server trả `{success:false,message}`. SSE đã mở thì lỗi trả event:error; client giữ phần nhận được, không đánh dấu hoàn tất. Model Qwen/DeepSeek trong danh sách local chạy bằng Ollama trên desktop; Cloudflare không gọi được `127.0.0.1:11434` của máy bạn.

## Kiểm tra đã thực hiện

`node --check worker.js`; 12 kiểm tra Node về CORS, JSON, xác thực, logout, streaming, công cụ và extraction. Các test dùng D1/AI giả lập; chưa thử trực tiếp D1, provider thật hoặc deploy Cloudflare.

Tài liệu cấu hình chính thức:
- https://developers.cloudflare.com/workers/wrangler/configuration/
- https://developers.cloudflare.com/workers-ai/configuration/bindings/
- https://developers.cloudflare.com/d1/get-started/

Đăng ký mở mặc định; `OPEN_REGISTRATION=false` để tạm đóng. Ba trường bắt buộc là fullname (Họ và tên), username (Tên đăng nhập), password (Mật khẩu). Email không bắt buộc.


## Bộ nhớ riêng theo tài khoản (server)

Mỗi tài khoản đã xác thực có KV riêng theo namespace; tài khoản A không đọc/sửa/xóa bộ nhớ của B. Không có API admin đọc toàn bộ bộ nhớ cá nhân. Worker tự nạp tối đa12 ghi nhớ mới nhất (tóm lược400 ký tự/mục) vào chat/stream của đúng tài khoản, trừ khi `use_memory:false`. Desktop cũng đọc profile trước lượt Ollama; không lưu profile đó trong state SQLite. Mục ghi nhớ được lưu khi người dùng xác nhận trong Cài đặt, không tự biến tất cả chat thành dữ liệu ghi nhớ.

Tạo KV bằng `npx wrangler kv namespace create MEMORY_KV`, thêm binding MEMORY_KV và ID vào kv_namespaces (có thể cùng binding CHAT_AI_KV/KV nếu đã dùng). Thêm secret MEMORY_ENCRYPTION_KEY: base64 của32 byte ngẫu nhiên. Có thể tạo trên Windows:

```powershell
py -3.12 -c "import base64,secrets;print(base64.b64encode(secrets.token_bytes(32)).decode())"
npx wrangler secret put MEMORY_ENCRYPTION_KEY
```

Giữ nguyên secret này qua các lần deploy; đổi/mất khóa sẽ không giải mã được giá trị cũ. Mã hóa AES-GCM ở server, không phải mã hóa đầu-cuối: server có khóa giải mã để dùng profile khi suy luận.

D1 có bảng personal_memory_index chỉ lưu owner/id/revision; nội dung nằm trong KV mã hóa. Mỗi sửa tạo key revision mới để tránh ghi cùng key quá thường xuyên. Xóa đánh dấu D1 trước khi xóa giá trị KV, nên các lượt đọc theo index bỏ mục đã xóa dù KV còn cache cũ ở vùng khác. KV vẫn có thể chưa trả revision vừa tạo ngay ở vùng khác: list có thể tạm thiếu mục mới; thử lại sau khi đồng bộ. Không dùng KV làm bằng chứng xác thực.

| API POST | Dữ liệu thêm ngoài username/key |
|---|---|
| /api/memory/personal/list | Không cần |
| /api/memory/personal/put | title,text,confirm:true; id nếu sửa |
| /api/memory/personal/delete | id,confirm:true |

Tối đa100 mục/tài khoản, title120 ký tự, text4000 ký tự. Bật bộ nhớ cần cả KV và MEMORY_ENCRYPTION_KEY; các API khác vẫn hoạt động nếu chưa cấu hình bộ nhớ.

## Tìm kiếm kết hợp suy luận

`/api/chat/ai` hoặc `/api/chat/stream` nhận `web_search:true` và `search_query` tùy chọn. Worker gọi Bing RSS, đưa trích đoạn/nguồn vào model được chọn, yêu cầu tổng hợp có dẫn URL. Bing RSS không cần API key; nếu Bing chặn truy cập, trả lỗi rõ ràng, không tự chuyển dịch vụ. Nếu không có search_query, dùng câu hỏi văn bản, không lấy nội dung document/context làm truy vấn. Tối đa600 ký tự/75 từ. Tool Python thực thi ở desktop/Docker, Worker không chạy Python hoặc lệnh Windows.

`work.js` ở thư mục gốc là bản sao đồng bộ của server/worker.js, dùng để copy lên Cloudflare Dashboard. Chỉ triển khai một bản.


### Cập nhật sửa thời gian đăng nhập

Khi cập nhật thủ công: lấy toàn bộ `server/worker.js` của nhánh main, mở Worker hiện có trong Cloudflare Dashboard → Edit code, thay nội dung và Deploy. Giữ nguyên binding DB và các secrets hiện có. Pull ứng dụng trên Windows không tự cập nhật Worker. Không tạo Worker/database mới để áp dụng bản sửa.

Worker lưu phiên bản cấu trúc dữ liệu trong `chat_ai_runtime_schema`; lần đầu cập nhật chạy migration, các cold start sau đọc một dòng phiên bản thay vì lặp DDL/PRAGMA. Khi sửa `ensureSchema` hoặc `ensureAdminSchema`, tăng `RUNTIME_SCHEMA_VERSION`. Chỉ ghi phiên bản sau khi mọi migration thành công; lỗi migration không được đánh dấu sẵn sàng. Token, khóa thiết bị và chào lần đầu được ghi theo một D1 batch; mật khẩu, trạng thái, hạn tài khoản và session epoch vẫn được kiểm tra. Các bảng dữ liệu khác tiếp tục migration riêng khi cần.

Đăng nhập admin sau migration dùng tối đa 4 câu SQL ở cold start theo kiểm tra SQLite; đây là số truy vấn, không phải cam kết độ trễ mạng thực tế. Chạy `npm test` để kiểm tra schema lạnh, phục hồi migration, xác thực và thu hồi phiên.

### Ba cấu hình DeepSeek dùng một key

Sau khi pull ứng dụng, thay toàn bộ code của Worker hiện có bằng `work.js`
(hoặc `server/worker.js`) và Deploy, giữ nguyên DB, ADMIN_KEY và các key.
Trong ChatAI, admin chọn Cài đặt → Key AI trực tuyến →
**Cấu hình 3 AI DeepSeek dùng chung key**. Endpoint quản trị
`/api/admin/providers/deepseek-presets` dùng key DeepSeek chung đã lưu trong D1
hoặc secret DEEPSEEK_API_KEY; không sao chép key vào từng model.

- DeepSeek Flash: `deepseek-flash`, tắt suy luận.
- DeepSeek V4 Pro: `deepseek-v4-pro`, bật suy luận.
- DeepSeek Suy luận: `deepseek-flash`, bật suy luận (không gọi model R1 cũ).

Bấm lại cập nhật cùng ID thay vì tạo bản trùng. Mục “DeepSeek R1 Suy luận”
cũ được chuyển sang “DeepSeek Suy luận”. Chế độ suy luận được lưu trên server
và áp dụng cho cả người dùng thường. Key riêng của các mục được cập nhật sẽ
được thay bằng liên kết tới key chung; key chung và các AI khác được giữ nguyên.
Các mã model cần được dịch vụ DeepSeek cấp quyền; kiểm thử giả lập không chứng
minh tài khoản API thật có quyền dùng model.

Chat DeepSeek thông thường qua key chung hỗ trợ `stream:true` tại
`/api/provider/model`: desktop hiển thị từng đoạn nội dung ngay khi API gửi về.
Không hiển thị reasoning_content. Agent/JSON vẫn dùng phản hồi đầy đủ; bật
Phân tích sâu vẫn có lượt kiểm tra bổ sung. Để chat nhanh chọn DeepSeek Flash,
tắt Phân tích sâu và Tìm web khi không cần. Pro/Suy luận có thể mất lâu hơn
trước token trả lời đầu tiên. Không đảm bảo thời gian 1–2 giây của API thật.

## Tự động triển khai work.js từ GitHub

Workflow `.github/workflows/deploy-worker.yml` chạy khi `main` thay đổi `work.js`,
server, hoặc cấu hình triển khai; có thể chạy thủ công trong GitHub Actions.
Nó kiểm thử trước, rồi tải **work.js ở thư mục gốc** lên Worker hiện có.
Script đọc cấu hình Worker trước khi cập nhật, giữ các loại bindings (DB, KV, AI,
biến và secrets), compatibility flags và cấu hình observability/limits nếu có.
Không dùng database ID mẫu trong `server/wrangler.jsonc`, không tạo Worker/database
mới và không thay cron. Key DeepSeek và ADMIN_KEY không cần đưa vào GitHub.

Thiết lập một lần tại GitHub → Settings → Secrets and variables → Actions:

- Repository secret `CF_API_TOKEN`: Cloudflare API token có quyền Account →
  Workers Scripts → Edit, giới hạn vào tài khoản chứa Worker.
- Repository secret `CF_ACCOUNT_ID`: Account ID của tài khoản Cloudflare đó.
- Repository variable `CF_WORKER_NAME`: tên Worker hiện có, mặc định `chatai`
  (Worker phục vụ `chatai.anhvn53.workers.dev`). Nếu dùng tên khác, đặt đúng tên.

Tạo token tại Cloudflare → My Profile → API Tokens → Create Token → Custom token.
Không dán token vào hội thoại hay commit vào mã nguồn. Khi đã lưu hai secrets,
vào GitHub → Actions → Deploy Cloudflare Worker → Run workflow → main để triển
khai bản hiện tại. Những cập nhật Worker tiếp theo trên main sẽ tự triển khai.
Workflow báo lỗi rõ nếu thiếu secrets hoặc không truy cập được Worker; chỉ coi
đã triển khai khi bước Deploy thành công. Thay đổi chỉ ở desktop không kích hoạt
triển khai server. Nếu Worker đang được quản lý bằng Workers Builds, dùng một
luồng triển khai để tránh hai hệ thống ghi đè nhau.
