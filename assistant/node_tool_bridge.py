"""Explain Chat AI's local tool executor to a chat-only API planner."""
import re


def planning_contract(schemas):
    names = [spec['function']['name'] for spec in schemas]
    text = (
        '\nCHAT AI LOCAL TOOL EXECUTOR: You are planning for an external Windows application. '
        'The functions in the supplied schemas are real tools executed by Chat AI on the user machine; '
        'they do not need to appear as native tools in your ChatGPT session. '
        'Return the requested JSON plan with tool and arguments. Chat AI validates it, executes '
        'the selected function under the existing permissions, and returns its result next turn. '
        'Existing task authorization applies equally to this API model. Do not ask to enable permissions '
        'already granted or claim no tools merely because your native ChatGPT tool list is empty. '
        'Do not invent tools or completed actions. A failed connection is different from an absent tool. '
        'Choose only a function in the actual schemas; ask only for genuinely missing project data. '
        'Available function names: ' + ', '.join(names)
    )
    return text, names


def unsupported_denial(answer, names):
    if not re.search(r'không\s+có\s+(?:công cụ|tool|tích hợp)|chưa\s+(?:tích hợp|có)\s+(?:công cụ|tool)|không\s+thể\s+tự\s+gắn', answer, re.I):
        return None
    if re.search(r'plaxis', answer, re.I) and 'plaxis_commands' in names:
        return 'plaxis_commands'
    if re.search(r'geostudio|geoslope|\bgsi\b', answer, re.I) and 'geostudio_python' in names:
        return 'geostudio_python'
    return None
