"""Bounded LangGraph reasoning loop using Ollama native function calling."""
import asyncio
import json
from typing import Annotated, Any, TypedDict
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from .tools import MODELS, schemas
from .utils import logger


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    steps: int
    halted: bool


SYSTEM = '''Bạn là agent PLAXIS của Chat AI. Chỉ dùng tools được cung cấp, không viết Python,
không gọi API tự do. Inspect trước khi ghi. Không đổi dự án hay chuyển 2D thành 3D.
Các công cụ hiện chỉ hỗ trợ inspect, vật liệu MC, thêm lớp 2D và verify/calculate;
nếu thiếu công cụ hình học, tải hoặc phase, báo cụ thể thay vì giả vờ đã làm.
Không tự đoán số liệu manual; yêu cầu nguồn hoặc dữ liệu kỹ thuật còn thiếu.
Không lặp thao tác ghi; uncertain thì dừng. Tool ok không chứng minh đúng cả bài.
Không báo bài hoàn tất khi chưa có kiểm chứng mô hình, trạng thái solver và kết quả Output.
Chỉ xử lý sản phẩm PLAXIS được người dùng chọn trong yêu cầu hệ thống.'''


def build_graph(model: Any, runtime: Any, version: str, max_steps: int,
                stop: asyncio.Event, events: list[dict[str, Any]]) -> Any:
    llm = model.bind_tools(schemas())

    async def reason(state: State) -> dict[str, Any]:
        if stop.is_set():
            return {'halted': True}
        # The model transport has its own HTTP timeout as well as this task bound.
        reply = await asyncio.wait_for(llm.ainvoke(state['messages']), timeout=180)
        logger.info('plan step=%s tool_calls=%s', state['steps'], len(reply.tool_calls))
        return {'messages': [reply]}

    async def tools(state: State) -> dict[str, Any]:
        messages: list[ToolMessage] = []
        steps = state['steps']
        inspected = any(event.get('tool') == 'plaxis_safe_inspect' and event.get('result', {}).get('ok')
                        for event in events)
        for call in state['messages'][-1].tool_calls:
            if stop.is_set() or steps >= max_steps:
                return {'messages': messages, 'steps': steps, 'halted': True}
            name, arguments = call['name'], call['args']
            steps += 1
            if name not in MODELS or not isinstance(arguments, dict):
                result = {'ok': False, 'not_executed': True, 'error': 'Tool/arguments không hợp lệ.'}
            elif arguments.get('version') != version:
                result = {'ok': False, 'not_executed': True, 'error': 'Tool khác sản phẩm PLAXIS của công việc.'}
            elif name != 'plaxis_safe_inspect' and not inspected:
                result = {'ok': False, 'not_executed': True, 'error': 'Cần inspect thành công trước khi ghi.'}
            else:
                result = await runtime.call(name, arguments)
            events.append({'step': steps, 'tool': name, 'result': result})
            messages.append(ToolMessage(content=json.dumps(result, ensure_ascii=False, default=str),
                                        tool_call_id=call['id'], name=name))
            if not result.get('ok'):
                return {'messages': messages, 'steps': steps, 'halted': True}
            if name == 'plaxis_safe_inspect':
                inspected = True
        return {'messages': messages, 'steps': steps, 'halted': False}

    def route(state: State) -> str:
        if state['halted'] or stop.is_set() or state['steps'] >= max_steps:
            return END
        return 'tools' if getattr(state['messages'][-1], 'tool_calls', []) else END

    graph = StateGraph(State)
    graph.add_node('reason', reason)
    graph.add_node('tools', tools)
    graph.add_edge(START, 'reason')
    graph.add_conditional_edges('reason', route)
    graph.add_conditional_edges('tools', lambda state: END if state['halted'] or stop.is_set() or state['steps'] >= max_steps else 'reason')
    return graph.compile()


async def run_agent(model: Any, runtime: Any, prompt: str, version: str, max_steps: int,
                    stop: asyncio.Event, events: list[dict[str, Any]]) -> dict[str, Any]:
    graph = build_graph(model, runtime, version, max_steps, stop, events)
    state = await graph.ainvoke({'messages': [SystemMessage(content=SYSTEM + '\nSản phẩm: ' + version),
                                HumanMessage(content=prompt)], 'steps': 0, 'halted': False},
                               config={'recursion_limit': max_steps * 2 + 4})
    message = state['messages'][-1]
    last = events[-1]['result'] if events else {}
    answer = message.content if not isinstance(message, ToolMessage) else last.get('error', 'Đã dừng tại giới hạn bước.')
    return {'answer': answer, 'steps': state['steps'], 'halted': state['halted'],
            'limit_reached': state['steps'] >= max_steps, 'model_completion_verified': False,
            'note': 'API chưa có bộ kiểm chứng trọn bài/đọc Output; finished chỉ là agent đã kết thúc.'}
