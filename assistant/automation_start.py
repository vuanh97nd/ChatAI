"""Start desktop automation without passing unused image arguments to older modules."""
from inspect import signature


def start_automation(agent, state, prompt, model, owner, image=None):
    if image is None:
        return agent.start(state, prompt, model, owner)
    parameters = signature(agent.start).parameters
    if 'image' not in parameters:
        raise RuntimeError(
            'Module điều khiển ứng dụng đang chạy chưa hỗ trợ ảnh đính kèm. '
            'Hãy cập nhật toàn bộ ChatAI và đóng/mở lại ứng dụng. '
            'Chưa gửi tin nhắn hoặc thực hiện thao tác; ảnh không bị bỏ qua.')
    return agent.start(state, prompt, model, owner, image=image)
