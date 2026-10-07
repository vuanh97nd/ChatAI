"""Rà soát có điều kiện và câu hỏi tiếp theo không thêm lượt model."""
import json


def review_answer(client, model, question, draft, evidence, cfg):
    response=client.chat(model=model,stream=False,keep_alive='10m',messages=[
        {'role':'system','content': 'Kiểm tra sai sót thực tế trong bản nháp theo bằng chứng cung cấp và sửa nếu cần. Giữ cách diễn đạt tự nhiên của bản nháp, không áp dàn bài hay mẫu hỏi lại. Không bịa nguồn, số liệu hoặc kết quả thực thi. Chỉ trả câu trả lời.'},
        {'role':'user','content':json.dumps({'question':question[:1600],
            'draft':draft[:max(1600,min(5000,cfg['num_ctx']))],'evidence':evidence},ensure_ascii=False)}],
        options={'temperature':.2,'num_ctx':cfg['num_ctx'],'num_predict':cfg['num_predict']})
    message=response['message'] if isinstance(response,dict) else response.message
    result=message['content'] if isinstance(message,dict) else message.content
    if not isinstance(result,str) or not result.strip():raise ValueError('Rà soát trả nội dung rỗng.')
    return result.strip()


def followups(category,answer):
    if not answer.strip() or answer.startswith('Lỗi Ollama:'):return []
    variants={
        'coding':[('Thêm kiểm thử','Viết các kiểm thử hữu ích cho đoạn code vừa rồi.'),('Xử lý lỗi','Bổ sung xử lý lỗi cho đoạn code vừa rồi.'),('Giải thích code','Giải thích cách chạy và các phần chính của code vừa rồi.')],
        'calculation':[('Giải thích phép tính','Giải thích công thức, đơn vị và cách kiểm tra kết quả vừa tính.'),('Đổi dữ kiện','Tôi muốn tính lại bài trên với dữ kiện khác; hãy cho biết các dữ kiện cần thay.'),('Ứng dụng thực tế','Cho một ví dụ thực tế áp dụng phép tính vừa rồi.')],
        'writing_translation':[('Rút gọn','Rút gọn bản vừa viết nhưng giữ đầy đủ ý chính.'),('Đổi giọng văn','Viết lại bản trên với giọng văn tự nhiên, gần gũi hơn.'),('Bản trang trọng','Viết lại bản trên bằng giọng văn trang trọng.')],
        'personal_documents':[('Tóm tắt tài liệu','Tóm tắt các điểm quan trọng trong tài liệu vừa dùng.'),('Chỉ vị trí nguồn','Chỉ rõ phần nào trong tài liệu làm căn cứ cho câu trả lời trên.'),('Các việc cần làm','Rút ra các việc cần làm từ tài liệu vừa phân tích.')],
        'current_web':[('Đối chiếu nguồn','Đối chiếu các nguồn vừa tra, nêu điểm thống nhất và khác nhau.'),('Tóm tắt nhanh','Tóm tắt thông tin vừa tìm thành các ý chính.'),('Kiểm chứng thêm','Tìm thêm nguồn chính thức để kiểm chứng câu trả lời vừa rồi.')],
        'knowledge':[('Ví dụ thực tế','Cho ví dụ thực tế về nội dung vừa giải thích.'),('Giải thích kỹ hơn','Giải thích kỹ hơn điểm quan trọng nhất trong câu trả lời trên.'),('Áp dụng từng bước','Hướng dẫn từng bước cách áp dụng kiến thức vừa trình bày.')],
    }
    return [{'label':label,'prompt':prompt} for label,prompt in variants.get(category,[])][:3]
