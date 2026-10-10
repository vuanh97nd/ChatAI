"""Regression tests: repeated PDF reads, memory overwrite, sync poison pills, context clipping."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from assistant.accounts import AccountAPIError
from assistant.conversation_context import conversation_context
from assistant.document_memory import DocumentMemory
from assistant.history_sync import HistorySync
from assistant.online_automation import mark_repeated_read, pdf_read_map
from assistant.procedure_memory import ProcedureMemory
from assistant.procedure_sync import ProcedureSync
from assistant.storage import Store
from tests.test_history_sync import Backend as HistoryBackend
from tests.test_procedure_sync import Backend as LessonBackend


def pdf_result(start, end, pages, content='x'):
    return {'ok': True, 'path': 'C:/w/manual.pdf', 'content': content, 'range_start': start, 'range_end': end,
            'locations': ['trang %d' % p for p in pages], 'characters_total': 100000, 'truncated': True}


def tool(result):
    return {'role': 'tool', 'tool_name': 'pdf_read', 'content': json.dumps(result, ensure_ascii=False)}


class DocumentMemoryRereadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.memory = DocumentMemory(Store(Path(self.tmp.name) / 'a.db'))

    def test_reading_page_one_again_keeps_later_excerpts(self):
        first = {'path': 'C:/w/manual.pdf', 'content': 'Mục lục ' * 100, 'range_start': 0, 'coverage': 'partial'}
        self.memory.remember('alice', [first])
        self.memory.remember('alice', [{'path': 'C:/w/manual.pdf', 'content': 'Tutorial 1: E = 30000 kPa', 'range_start': 50000, 'coverage': 'partial'}])
        self.memory.remember('alice', [first])
        text = self.memory.records('alice')[0]['text']
        self.assertIn('E = 30000 kPa', text); self.assertIn('Mục lục', text)

    def test_changed_file_replaces_old_text(self):
        self.memory.remember('alice', [{'path': 'C:/w/a.pdf', 'content': 'Bản cũ', 'range_start': 0, 'coverage': 'partial'}])
        self.memory.remember('alice', [{'path': 'C:/w/a.pdf', 'content': 'Bản mới hoàn toàn', 'range_start': 0, 'coverage': 'partial'}])
        self.assertEqual(self.memory.records('alice')[0]['text'], 'Bản mới hoàn toàn')


class DocumentRangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        units = [{'location': 'trang 1', 'text': 'Contents\nTutorial 1 Settlement of a footing ........ 9'},
                 {'location': 'trang 2', 'text': 'Introduction'},
                 {'location': 'trang 9', 'text': 'Tutorial 1 Settlement of a footing\nE = 13000 kN/m2'}]
        self.document = {'text': '\n\n'.join('[' + u['location'] + ']\n' + u['text'] for u in units), 'units': units,
                         'full_text': True, 'coverage_note': 'Đã trích xuất hết phần văn bản có thể đọc từ tệp.'}
        self.file = Path(self.tmp.name) / 'manual.pdf'; self.file.write_bytes(b'%PDF')
        self.files = type('Files', (), {'path': lambda _self, p: Path(p)})()

    def read(self, **kwargs):
        from assistant import documents
        documents._RANGE_CACHE.clear()
        with patch.object(documents, 'read_local', return_value=self.document):
            return documents.read_document_range(self.files, str(self.file), limit=80, **kwargs)

    def test_query_skips_table_of_contents(self):
        result = self.read(query='tutorial 1')
        self.assertIn('trang 9', result['locations']); self.assertIn('E = 13000', result['content'])
        self.assertEqual(result['matches'], ['trang 1', 'trang 9'])

    def test_page_jump_and_partial_note_is_not_misleading(self):
        result = self.read(page=9)
        self.assertTrue(result['content'].startswith('[trang 9]'))
        self.assertNotIn('Đã trích xuất hết', result['note']); self.assertIn('CHƯA đọc', result['note'])


class RepeatedReadTests(unittest.TestCase):
    def test_visible_repeat_returns_no_content(self):
        messages = [{'role': 'user', 'content': 'làm bài 1'}, tool(pdf_result(0, 8000, [1, 2, 3], 'MỤC LỤC'))]
        result = mark_repeated_read(messages, pdf_result(0, 8000, [1, 2, 3], 'MỤC LỤC'))
        self.assertTrue(result['already_read']); self.assertEqual(result['content'], '')

    def test_repeat_outside_window_is_resent_once(self):
        messages = [{'role': 'user', 'content': 'làm bài 1'}, tool(pdf_result(0, 8000, [1], 'MỤC LỤC'))] + [{'role': 'assistant', 'content': 'x'}] * 25
        result = mark_repeated_read(messages, pdf_result(0, 8000, [1], 'MỤC LỤC'))
        self.assertTrue(result['already_read']); self.assertEqual(result['content'], 'MỤC LỤC')

    def test_read_map_lists_pages(self):
        text = pdf_read_map([tool(pdf_result(0, 8000, [1, 2, 3])), tool(pdf_result(8000, 16000, [3, 4])), tool(pdf_result(60000, 68000, [20]))])
        self.assertIn('manual.pdf', text); self.assertIn('1-4, 20', text)


class ContextTests(unittest.TestCase):
    def test_long_answer_keeps_conclusion_and_no_double_user_turn(self):
        rows = []
        for i in range(30):
            rows += [{'role': 'user', 'content': 'hỏi %d' % i}, {'role': 'assistant', 'content': 'mở đầu ' + 'a' * 20000 + ' KẾT LUẬN %d' % i}]
        rows.append({'role': 'user', 'content': 'tiếp'})
        result = conversation_context(rows)
        self.assertIn('KẾT LUẬN 29', ''.join(m['content'] for m in result))
        self.assertTrue(all(a['role'] != b['role'] or a['role'] != 'user' for a, b in zip(result, result[1:])))


class HistoryPoisonPillTests(unittest.TestCase):
    def test_rejected_conversation_does_not_block_others(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        store = Store(Path(tmp.name) / 'a.db'); backend = HistoryBackend()
        ids = []
        for text in ('một', 'hai'):
            cid = store.create(False)
            store.save(cid, {'messages': [{'role': 'user', 'content': text}], 'account_username': 'alice', 'queue': [], 'pending': None, 'running': False})
            ids.append(cid)
        bad = min(ids)

        def request(path, body):
            if path.endswith('/put') and body['conversation_id'] == bad:
                raise AccountAPIError('Hội thoại quá lớn để đồng bộ một lần.', 413)
            return backend(path, body)
        sync = HistorySync(store, {'username': 'alice', 'key': 'k', 'endpoint': 'https://example.org'}, request)
        sync.cycle()
        self.assertIn(('alice', max(ids)), backend.rows); self.assertEqual([c for c, _ in sync.failures], [bad])


class LessonPoisonPillTests(unittest.TestCase):
    def test_rejected_lesson_is_parked_and_download_still_runs(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        store = Store(Path(tmp.name) / 'a.db'); memory = ProcedureMemory(store); backend = LessonBackend()
        for i in range(3):
            memory.remember('alice', {'messages': [{'role': 'user', 'content': 'PLAXIS'}]},
                            {'function': {'name': 'plaxis_commands', 'arguments': {'index': i}}}, {'ok': True})
        bad = sorted(r['id'] for r in memory.records('alice'))[0]

        def request(path, body):
            if path.endswith('/put') and any(r['id'] == bad for r in body['records']):
                raise AccountAPIError('Bài học không hợp lệ.', 400)
            return backend(path, body)
        session = {'username': 'alice', 'key': 'k', 'endpoint': 'https://example.org'}
        sync = ProcedureSync(store, session, request); sync.cycle()
        self.assertEqual(len(backend.rows), 2); self.assertEqual([i for i, _ in sync.rejected], [bad])
        sync.cycle()  # parked record is not retried forever
        self.assertEqual(len(backend.rows), 2)


if __name__ == '__main__':
    unittest.main()


class PlanParsingTests(unittest.TestCase):
    """Replays of plan replies the model actually produced on 2026-10-10."""
    def parse(self, raw):
        from assistant.online_automation import parse_plan
        from assistant.tools import EXTRA_TOOLS
        return parse_plan(raw, [s for _, s in EXTRA_TOOLS])

    def test_duplicated_identical_plan_is_accepted(self):
        one = '[{"function": {"name": "pdf_read", "arguments": {"path": "a.pdf", "start": "24000"}}}]'
        self.assertEqual(self.parse(one + '\n\n' + one + '\n]')['arguments']['start'], '24000')

    def test_misplaced_closing_brackets_are_rebalanced(self):
        self.assertEqual(self.parse('[{"function": {"name": "pdf_read", "arguments": {"path": "a.pdf", "start": "20000"}}}}]')['tool'], 'pdf_read')
        self.assertEqual(self.parse('[{"function": {"name": "pdf_read", "arguments": {"path": "a.pdf"}}]}')['tool'], 'pdf_read')

    def test_different_or_truncated_plans_stay_rejected(self):
        with self.assertRaises(ValueError):
            self.parse('[{"function": {"name": "pdf_read", "arguments": {"path": "a.pdf"}}}] [{"function": {"name": "windows_list_apps", "arguments": {}}}]')
        with self.assertRaises(ValueError):
            self.parse('[{"function": {"name": "pdf_read", "arguments": {"path": "a.p')

    def test_history_shows_calls_in_plan_format(self):
        from assistant.online_automation import planning_messages
        state = {'messages': [{'role': 'user', 'content': 'đọc'}, {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {'name': 'pdf_read', 'arguments': {'path': 'a.pdf'}}}]}]}
        rendered = json.loads(planning_messages(state, 'x')[-1]['content'])
        self.assertEqual(rendered, {'answer': '', 'tool': 'pdf_read', 'arguments': {'path': 'a.pdf'}})


class PlaxisPortTests(unittest.TestCase):
    def test_port_comes_from_plaxis_title_not_default(self):
        from assistant.plaxis_remote import detect_ports
        titles = ['Chat AI', 'PLAXIS 2D Ultimate: (Untitled) --- SERVER ACTIVE on port 10001 (UNSECURED)',
                  'PLAXIS 3D Output --- SERVER ACTIVE on port 10011']
        self.assertEqual(detect_ports('2d', titles), {'input': 10001})
        self.assertEqual(detect_ports('3d', titles), {'output': 10011})

    def test_output_never_falls_back_onto_input_port(self):
        from assistant import plaxis_remote
        with patch.object(plaxis_remote, 'detect_ports', return_value={'input': 10001}):
            self.assertEqual(plaxis_remote.resolve_port('2d', 'output'), (None, False))
            self.assertEqual(plaxis_remote.resolve_port('2d', 'input'), (10001, True))
        with self.assertRaises(RuntimeError):
            plaxis_remote._connect(None, 'PLAXIS 2D Output')


class StopTests(unittest.TestCase):
    def test_stop_returns_while_plaxis_call_hangs(self):
        import threading, time
        from assistant import plaxis_remote, windows_apps
        release = threading.Event(); self.addCleanup(release.set); self.addCleanup(windows_apps.resume_automation)
        windows_apps.resume_automation()
        threading.Timer(0.3, windows_apps.stop_automation).start()
        started = time.monotonic()
        with self.assertRaises(plaxis_remote.PlaxisStopped):
            plaxis_remote._until_stopped(release.wait)
        self.assertLess(time.monotonic() - started, 2)

    def test_errors_and_values_pass_through(self):
        from assistant import plaxis_remote, windows_apps
        windows_apps.resume_automation()
        self.assertEqual(plaxis_remote._until_stopped(lambda x: x + 1, 1), 2)
        with self.assertRaises(ValueError):
            plaxis_remote._until_stopped(int, 'x')


class PlaxisObjectMethodTests(unittest.TestCase):
    class Proxy:
        """Mimics plxscripting: a missing member raises a non-AttributeError."""
        def __init__(self, **members): self.__dict__.update(members)
        def __getattr__(self, name): raise RuntimeError(f"Requested attribute '{name}' is not present")

    def run_rows(self, rows):
        from unittest.mock import Mock
        from assistant.plaxis_commands import execute_commands
        from assistant import windows_apps
        windows_apps.resume_automation()
        contour = Mock(name='SoilContour')
        g = self.Proxy(SoilContour=contour, soillayer=Mock(return_value='layer'))
        return execute_commands(Mock(), g, rows), contour

    def test_method_called_on_object_given_as_first_argument(self):
        result, contour = self.run_rows([{'command': 'initializerectangular', 'args': [{'ref': 'g.SoilContour'}, 0, 0, 5, 4]}])
        self.assertTrue(result['ok']); contour.initializerectangular.assert_called_once_with(0, 0, 5, 4)

    def test_bare_initializerectangular_targets_soil_contour(self):
        result, contour = self.run_rows([{'command': 'initializerectangular', 'args': [0, 0, 5, 4]}])
        self.assertTrue(result['ok']); contour.initializerectangular.assert_called_once_with(0, 0, 5, 4)

    def test_unknown_command_explains_object_syntax_without_running(self):
        result, _ = self.run_rows([{'command': 'nosuchcommand', 'args': [1]}])
        self.assertFalse(result['ok']); self.assertTrue(result['not_executed']); self.assertIn('signature', result['error'])


class PlaxisSessionTests(unittest.TestCase):
    class Proxy:
        def __init__(self, **members): self.__dict__.update(members)
        def __getattr__(self, name): raise RuntimeError(f"Requested attribute '{name}' is not present")

    def setUp(self):
        from unittest.mock import Mock
        from assistant import plaxis_commands, windows_apps
        windows_apps.resume_automation(); plaxis_commands._SESSIONS.clear()
        self.boreholes = []
        def borehole(head):
            item = Mock(name='bh'); item.Name.value = 'Borehole_%d' % (len(self.boreholes) + 1); self.boreholes.append(item); return item
        self.soillayer = Mock(return_value='layer')
        self.g = self.Proxy(Project='<Project {A}>', borehole=borehole, soillayer=self.soillayer, Boreholes=self.boreholes)
        self.run = lambda rows: plaxis_commands.run_batch(Mock(), self.g, rows, port=10001)

    def test_names_survive_between_calls_and_retry_does_not_duplicate(self):
        self.assertTrue(self.run([{'command': 'borehole', 'args': [2.0], 'result': 'bh'}])['ok'])
        second = self.run([{'command': 'borehole', 'args': [2.0], 'result': 'bh'}, {'command': 'soillayer', 'args': [{'ref': 'bh'}, 4.0]}])
        self.assertTrue(second['ok']); self.assertEqual(len(self.boreholes), 1)
        self.assertIn('skipped', second['results'][0]); self.soillayer.assert_called_once_with(self.boreholes[0], 4.0)
        self.assertIn('Boreholes: 1 (Borehole_1)', second['model_state'])

    def test_unknown_name_is_explained_not_sent(self):
        result = self.run([{'command': 'soillayer', 'args': [{'ref': 'bh'}, 4.0]}])
        self.assertFalse(result['ok']); self.assertTrue(result['not_executed'])
        self.assertIn("'bh' chưa được định nghĩa", result['error']); self.soillayer.assert_not_called()


class RepeatAndManualTests(unittest.TestCase):
    def test_identical_plaxis_call_blocked_right_after_failure(self):
        from assistant.experience import repeated_failure
        call = {'function': {'name': 'plaxis_commands', 'arguments': {'commands': '[1]'}}}
        state = {'messages': [{'role': 'user', 'content': 'làm'}, {'role': 'assistant', 'content': '', 'tool_calls': [call]},
                              {'role': 'tool', 'tool_name': 'plaxis_commands', 'content': json.dumps({'ok': False, 'error': 'Unrecognized token'})}]}
        self.assertIn('vừa thất bại', repeated_failure(state, call))

    def test_question_for_data_requires_manual_lookup(self):
        from assistant.online_automation import check_confirmation
        state = {'messages': [tool(pdf_result(0, 8000, [1])), {'role': 'user', 'content': 'Tiếp tục'}]}
        with self.assertRaises(ValueError):
            check_confirmation({'tool': '', 'answer': 'Bạn cho biết tọa độ điểm đặt và cao độ lớp đất?'}, state, {'windows_apps_auto_execute': True})


class PlaxisCommandRepairTests(unittest.TestCase):
    def test_wrong_closing_bracket_in_commands_is_repaired(self):
        from assistant.plaxis_commands import commands_from_json
        rows = commands_from_json('[{"command":"soilmat","args":[],"result":"mat"},{"command":"setproperties","args":[{"ref":"sl"},"Material","mat"}]}]')
        self.assertEqual(rows[-1]['args'][-1], 'mat')

    def test_unrepairable_json_error_shows_location(self):
        from assistant.plaxis_commands import commands_from_json
        with self.assertRaises(ValueError) as caught:
            commands_from_json('[{"command":"soilmat" "args":[]}]')
        self.assertIn('gần:', str(caught.exception))

    def test_invalid_parameters_returns_signature_and_not_uncertain(self):
        from unittest.mock import Mock
        from assistant.plaxis_commands import execute_commands
        from assistant import windows_apps
        windows_apps.resume_automation()
        g = Mock(); g.soillayer.side_effect = RuntimeError('Unsuccessful command:\nInvalid parameters.')
        g.commands.return_value = 'soillayer (sl)\n  Borehole NumberWithUnitLength\'\n  NumberWithUnitLength\'\nsoilmat (sm)'
        result = execute_commands(Mock(), g, [{'command': 'soillayer', 'args': [1, 2, 3]}])
        self.assertFalse(result['uncertain']); self.assertIn('Borehole NumberWithUnitLength', result['signature'])


class ManualRetrievalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.memory = DocumentMemory(Store(Path(tmp.name) / 'a.db'))
        toc = '[trang 1]\nContents\n' + ''.join('%d.%d Section ........ %d\n' % (i, j, i * 10) for i in range(9) for j in range(9))
        filler = ''.join('[trang %d]\nGeneral explanation of the user interface and menus.\n' % p + 'x ' * 1200 for p in range(2, 14))
        table = '[trang 16]\nTable 1–1: Material properties of the sand layer\nUnsaturated unit weight γunsat 17 kN/m3\nYoung\'s modulus E\'ref 13 · 103 kN/m2\nFriction angle φ\' 30 °\n'
        text = toc + filler + table
        for name in ('manual.pdf', 'manual-copy.pdf'):
            self.memory.remember('alice', [{'file': 'C:/w/' + name, 'content': text, 'coverage': 'partial'}])
        self.messages = [{'role': 'user', 'content': 'Đọc manual Plaxis và làm bài 1'}, {'role': 'user', 'content': 'thử lại với bài 1'}]

    def test_vietnamese_follow_up_still_gets_parameter_table_once(self):
        context = self.memory.context('alice', 'thử lại với bài 1', messages=self.messages)
        self.assertIn('Table 1–1', context); self.assertIn('13·10^3', context)
        self.assertEqual(context.count('[TÀI LIỆU ĐÃ ĐỌC'), 1)


class PlanRepairMoreTests(unittest.TestCase):
    def test_missing_closing_quote_of_commands_string(self):
        from assistant.online_automation import plan_json
        raw = '{"answer": "", "tool": "plaxis_commands", "arguments": {"version": "2d", "commands": "[{\\"command\\":\\"signature\\",\\"args\\":[\\"soillayer\\"]}]}}'
        self.assertEqual(json.loads(plan_json(raw, 't')['arguments']['commands'])[0]['command'], 'signature')

    def test_manual_reminder_only_once_per_turn(self):
        from assistant.online_automation import check_confirmation
        state = {'messages': [tool(pdf_result(0, 8000, [1])), {'role': 'user', 'content': 'Tiếp tục'}]}
        output = {'tool': '', 'answer': 'Bạn cho biết tọa độ điểm đặt?'}
        with self.assertRaises(ValueError):
            check_confirmation(output, state, {'windows_apps_auto_execute': True})
        check_confirmation(output, state, {'windows_apps_auto_execute': True})

    def test_argument_count_hint(self):
        from unittest.mock import Mock
        from assistant.plaxis_commands import execute_commands
        from assistant import windows_apps
        windows_apps.resume_automation()
        g = Mock(); g.soillayer.side_effect = RuntimeError('Unsuccessful command:\nInvalid parameters.')
        g.commands.return_value = "soillayer (sl)\n  Borehole NumberWithUnitLength'\n  NumberWithUnitLength'\nsoilmat"
        result = execute_commands(Mock(), g, [{'command': 'soillayer', 'args': [1, 4.0, 0.0]}])
        self.assertIn('3 tham số', result['arguments_hint']); self.assertIn('1 hoặc 2', result['arguments_hint'])


class OpenOutputTests(unittest.TestCase):
    def test_output_opened_from_input_and_new_port_detected(self):
        from unittest.mock import Mock
        from assistant import plaxis_remote
        done = Mock(); done.CalculationResult.value = 1
        fresh = Mock(); fresh.CalculationResult.value = 0
        g_in = Mock(); g_in.Phases = [done, fresh]
        ports = iter([{'input': 10001}, {'input': 10001}, {'input': 10001, 'output': 10002}])
        with patch.object(plaxis_remote, 'detect_ports', side_effect=lambda v: next(ports)), \
             patch.object(plaxis_remote, '_connect', return_value=(Mock(), g_in)), \
             patch.object(plaxis_remote, 'port_open', return_value=True), patch('time.sleep'):
            self.assertEqual(plaxis_remote.open_output('2d'), 10002)
        g_in.view.assert_called_once_with(done)

    def test_no_calculated_phase_is_reported(self):
        from unittest.mock import Mock
        from assistant import plaxis_remote
        g_in = Mock(); g_in.Phases = []
        with patch.object(plaxis_remote, 'detect_ports', return_value={'input': 10001}), \
             patch.object(plaxis_remote, '_connect', return_value=(Mock(), g_in)):
            with self.assertRaises(RuntimeError):
                plaxis_remote.open_output('2d')


TOC = ('[trang 2]\n1 Settlement of a circular footing on sand..................................10\n'
       '2 Drained and undrained stability of an embankment.................40\n'
       '3 Submerged construction of an excavation............................. 52\n')


class TutorialResolutionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.store = Store(Path(tmp.name) / 'a.db'); self.memory = DocumentMemory(self.store)
        self.memory.remember('alice', [{'file': 'C:/w/manual.pdf', 'content': TOC + '[trang 41]\nEmbankment geometry', 'coverage': 'partial'}])

    def test_number_maps_to_title_in_this_manual_not_remembered_version(self):
        messages = [{'role': 'user', 'content': 'Hãy thử tính toán bài 2 với bộ số liệu y hệt Plaxis manual'}, {'role': 'user', 'content': 'new project nhé'}]
        info = self.memory.tutorial('alice', messages)
        self.assertEqual((info['number'], info['title'], info['page'], info['end']), (2, 'Drained and undrained stability of an embankment', 40, 51))

    def test_topic_change_stops_lookup(self):
        from assistant.document_memory import requested_tutorial
        self.assertIsNone(requested_tutorial([{'role': 'user', 'content': 'bài 2'}, {'role': 'user', 'content': 'viết email cho sếp'}]))

    def test_building_blocked_until_tutorial_page_read(self):
        from assistant.online_automation import tutorial_unread
        state = {'account_username': 'bob', 'messages': [], 'tutorial': {'number': 2, 'title': 'Embankment', 'page': 40, 'end': 51, 'file': 'manual.pdf'}}
        build = {'commands': json.dumps([{'command': 'soilmat', 'args': []}])}
        self.assertIn('Chưa đọc trang', tutorial_unread(state, build, self.store))
        self.assertIsNone(tutorial_unread(state, {'commands': json.dumps([{'command': 'read', 'args': [{'ref': 'g.Phases'}]}])}, self.store))
        state['messages'] = [tool(pdf_result(0, 8000, [41, 42]))]
        self.assertIsNone(tutorial_unread(state, build, self.store))


class CompletionGateTests(unittest.TestCase):
    def state(self, verified):
        build = {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {'name': 'plaxis_commands', 'arguments': {'commands': json.dumps([{'command': 'soilmat', 'args': []}])}}}]}
        msgs = [{'role': 'user', 'content': 'làm bài 1'}, build, {'role': 'tool', 'tool_name': 'plaxis_commands', 'content': json.dumps({'ok': True})}]
        if verified:
            msgs.append({'role': 'tool', 'tool_name': 'plaxis_commands', 'content': json.dumps({'ok': True, 'model_verified': True})})
        return {'messages': msgs}

    def test_claim_without_verification_is_challenged_once_then_flagged(self):
        from assistant.online_automation import check_confirmation
        state = self.state(False); output = {'tool': '', 'answer': 'Đã hoàn tất mô hình theo đúng manual.'}
        with self.assertRaises(ValueError):
            check_confirmation(output, state, {})
        check_confirmation(output, state, {})
        self.assertTrue(output['answer'].startswith('⚠ Chưa kiểm chứng'))

    def test_verified_claim_passes(self):
        from assistant.online_automation import check_confirmation
        output = {'tool': '', 'answer': 'Đã hoàn tất mô hình theo đúng manual.'}
        check_confirmation(output, self.state(True), {}); self.assertFalse(output['answer'].startswith('⚠'))


class ModelWarningTests(unittest.TestCase):
    def test_plane_strain_for_circular_footing_and_duplicates(self):
        from assistant.online_automation import model_warnings
        warnings = model_warnings('Project: ModelType=Plane strain (0); LineDisplacements: 2 (A, B)', {'title': 'Settlement of a circular footing on sand'})
        self.assertEqual(len(warnings), 2)

    def test_snapshot_reports_model_type(self):
        from unittest.mock import Mock
        from assistant.plaxis_commands import model_snapshot
        g = Mock(); g.Project.ModelType.value = 1
        for attr in ('Boreholes', 'Soillayers', 'Materials', 'Points', 'Lines', 'Polygons', 'Plates', 'Interfaces', 'LineLoads', 'PointLoads',
                     'LineDisplacements', 'PointDisplacements', 'NodeToNodeAnchors', 'EmbeddedBeams', 'Phases'):
            setattr(g, attr, [])
        self.assertIn('ModelType=Axisymmetric', model_snapshot(g))


class RoutingTests(unittest.TestCase):
    def test_manual_question_stays_in_plaxis_task(self):
        from assistant.online_automation import use_automation
        state = {'online_automation': False, 'messages': [{'role': 'tool', 'tool_name': 'plaxis_commands', 'content': '{}'}]}
        self.assertTrue(use_automation('tìm trong manual pdf ấy', {'windows_apps_enabled': True}, state))
        self.assertFalse(use_automation('viết email', {'windows_apps_enabled': True}, {'messages': []}))


class StagedConstructionTests(unittest.TestCase):
    def plaxis_failure(self, command, error):
        return {'role': 'tool', 'tool_name': 'plaxis_commands', 'content': json.dumps({'ok': False, 'failed_command': command, 'error': error})}

    def test_phase_hint_on_staged_material_failure(self):
        from unittest.mock import Mock
        from assistant.plaxis_commands import execute_commands
        from assistant import windows_apps
        windows_apps.resume_automation()
        g = Mock(); g.setmaterial.side_effect = RuntimeError('Unsuccessful command:\nTried executing, but failed')
        result = execute_commands(Mock(), g, [{'command': 'setmaterial', 'args': [1, 2]}])
        self.assertIn('g.InitialPhase', result['phase_hint'])

    def test_mesh_blocked_while_a_soil_has_no_material(self):
        from unittest.mock import Mock
        from assistant.plaxis_commands import execute_commands
        from assistant import windows_apps
        windows_apps.resume_automation()
        bare = Mock(); bare.Material.value = None; bare.Name.value = 'Soil_2_Soil_3_1'
        done = Mock(); done.Material.value = 'Clay'; done.Name.value = 'Soil_1_1'
        g = Mock(); g.Soils = [bare, done]
        result = execute_commands(Mock(), g, [{'command': 'mesh', 'args': [0.06]}])
        self.assertTrue(result['not_executed']); self.assertIn('Soil_2_Soil_3_1', result['error']); g.mesh.assert_not_called()

    def test_tutorial_kept_through_follow_ups(self):
        from assistant.online_automation import new_unrelated_task
        self.assertFalse(new_unrelated_task('tra mạng đi'))
        self.assertFalse(new_unrelated_task('không biết thì tìm trên mạng đã nhé'))
        self.assertTrue(new_unrelated_task('Viết giúp mình email gửi khách hàng về lịch họp tuần sau'))

    def test_fourth_identical_failure_is_stopped(self):
        from assistant.online_automation import stuck_command
        error = 'Unsuccessful command:\nTried executing, but failed'
        state = {'messages': [{'role': 'user', 'content': 'làm'}] + [self.plaxis_failure('setmaterial', error)] * 3}
        self.assertIn('3 lần', stuck_command(state, {'commands': json.dumps([{'command': 'setmaterial', 'args': []}])}))
        self.assertIsNone(stuck_command(state, {'commands': json.dumps([{'command': 'read', 'args': []}])}))

    def test_working_form_after_failure_is_remembered(self):
        from assistant.online_automation import remember_working_forms
        state = {'messages': [self.plaxis_failure('setmaterial', 'Invalid parameters')]}
        call = {'function': {'arguments': {'commands': json.dumps([{'command': 'setmaterial', 'args': [{'ref': 'g.Polygon_2.Soil'}, {'ref': 'emb'}]}])}}}
        remember_working_forms(state, call, {'ok': True, 'results': [{'step': 1, 'command': 'setmaterial', 'value': 'OK'}]})
        self.assertIn('g.Polygon_2.Soil', state['plaxis_learned'][0])


class SecondPassBai2Tests(unittest.TestCase):
    def test_gotomesh_blocked_while_soil_has_no_material(self):
        from unittest.mock import Mock
        from assistant.plaxis_commands import execute_commands
        from assistant import windows_apps
        windows_apps.resume_automation()
        bare = Mock(); bare.Material.value = None; bare.Name.value = 'Soil_2'
        g = Mock(); g.Soils = [bare]
        result = execute_commands(Mock(), g, [{'command': 'gotomesh', 'args': []}])
        self.assertTrue(result['not_executed']); g.gotomesh.assert_not_called(); self.assertIn('gotostructures', result['error'])

    def test_assignment_to_wrong_region_is_flagged(self):
        from unittest.mock import Mock
        from assistant import plaxis_commands, windows_apps
        windows_apps.resume_automation(); plaxis_commands._SESSIONS.clear()
        bare = Mock(); bare.Material.value = None; bare.Name.value = 'Soil_2'
        other = Mock(); other.Material.value = 'Clay'; other.Name.value = 'Soil_1'
        g = Mock(); g.Soils = [other, bare]; g.setmaterial.return_value = 'OK'
        result = plaxis_commands.run_batch(Mock(), g, [{'command': 'setmaterial', 'args': [{'ref': 'g.Soils', 'index': 0}, 1]}], port=1)
        self.assertIn('Soil_2', result['material_warning'])

    def test_property_writes_are_not_learned(self):
        from assistant.online_automation import remember_working_forms
        state = {'messages': [{'role': 'tool', 'tool_name': 'plaxis_commands', 'content': json.dumps({'ok': False, 'failed_command': 'setproperties', 'error': 'x'})}]}
        call = {'function': {'arguments': {'commands': json.dumps([{'command': 'setproperties', 'args': [{'ref': 'm'}, 'phi', 30]}])}}}
        remember_working_forms(state, call, {'ok': True, 'results': [{'step': 1}]})
        self.assertEqual(state.get('plaxis_learned', []), [])

    def test_hung_browser_read_returns_on_stop(self):
        import threading, time
        from assistant import browser, windows_apps
        windows_apps.resume_automation(); self.addCleanup(windows_apps.resume_automation)
        b = browser.BrowserTools.__new__(browser.BrowserTools)
        release = threading.Event(); self.addCleanup(release.set)
        b._commit = lambda plan: release.wait()
        threading.Timer(0.3, windows_apps.stop_automation).start()
        started = time.monotonic(); result = b.commit({})
        self.assertFalse(result['ok']); self.assertLess(time.monotonic() - started, 2)


class DataAnswerGuardTests(unittest.TestCase):
    def test_answer_listing_manual_data_is_not_blocked(self):
        from assistant.online_automation import check_confirmation
        state = {'messages': [{'role': 'user', 'content': 'đọc bài 2 và cung cấp số liệu'}, tool(pdf_result(0, 8000, [40]))]}
        answer = ('| Tham số | Giá trị |\n| Contour | 0..50 x -6..4 |\nVật liệu Embankment: E50 = 2000 kN/m2, φ = 30°. '
                  'Bạn có muốn tôi dựng mô hình với các thông số này không?')
        check_confirmation({'tool': '', 'answer': answer}, state, {'windows_apps_auto_execute': True})

    def test_asking_user_for_data_after_reading_manual_this_turn_is_allowed(self):
        from assistant.online_automation import check_confirmation
        state = {'messages': [{'role': 'user', 'content': 'làm bài 2'}, tool(pdf_result(0, 8000, [40]))]}
        check_confirmation({'tool': '', 'answer': 'Bạn cho biết cao độ mực nước ngầm?'}, state, {'windows_apps_auto_execute': True})


class CompletionWordingTests(unittest.TestCase):
    def test_ran_through_wording_is_gated(self):
        from assistant.online_automation import unverified_completion
        state = CompletionGateTests().state(False)
        self.assertIsNotNone(unverified_completion('Đã chạy xong Bài 2 (theo mục lục manual).', state))
        self.assertIsNotNone(unverified_completion('Đã tính xong hai phase.', state))
        self.assertIsNone(unverified_completion('Đang chờ PLAXIS tính phase 2.', state))


class Bai3Tests(unittest.TestCase):
    def staged_model(self, changed):
        from unittest.mock import MagicMock
        def phase(name, prev=None, pending=True):
            p = MagicMock(); p.Name.value = name; p.DeformCalcType.value = 4; p.ShouldCalculate.value = pending
            p.PreviousPhase.value = prev; return p
        initial = phase('InitialPhase', pending=False); p1 = phase('Phase_1', initial)
        wall = MagicMock(); wall.Name.value = 'Plate_1'
        wall.Active.__getitem__.side_effect = lambda ph: MagicMock(value=(changed and ph is p1))
        g = MagicMock(); g.Phases = [initial, p1]; g.Plates = [wall]
        for attr in ('Soils', 'NodeToNodeAnchors', 'FixedEndAnchors', 'LineLoads', 'PointLoads', 'LineDisplacements',
                     'PointDisplacements', 'Interfaces', 'EmbeddedBeams', 'Geogrids'):
            setattr(g, attr, [])
        return g

    def test_calculate_blocked_once_for_empty_phase(self):
        from unittest.mock import Mock
        from assistant.plaxis_commands import execute_commands
        from assistant import windows_apps
        windows_apps.resume_automation()
        g = self.staged_model(False); session = {'aliases': {}, 'created': {}}
        first = execute_commands(Mock(), g, [{'command': 'calculate', 'args': []}], session=session)
        self.assertFalse(first['ok']); self.assertIn('Phase_1', first['error']); g.calculate.assert_not_called()
        second = execute_commands(Mock(), g, [{'command': 'calculate', 'args': []}], session=session)
        self.assertTrue(second['ok'])

    def test_phase_with_activation_is_not_empty(self):
        from assistant.plaxis_commands import _empty_phases
        self.assertEqual(_empty_phases(self.staged_model(True)), [])

    def test_steps_and_exponents(self):
        from assistant.document_memory import tutorial_steps, normalize_exponents
        text = 'mode. 3.4.1 To define the diaphragm wall: draw. 3.6.2 Phase 1: External load\n1. Click. 3.6 Define and perform the calculation .......... 61'
        self.assertEqual(tutorial_steps(text, 3), ['3.4.1 To define the diaphragm wall:', '3.6.2 Phase 1: External load'])
        self.assertIn('7.5·10^6', normalize_exponents('EA1 7.5 · 10 6 kN/m'))
        self.assertIn('1·10^-3', normalize_exponents('kx 1 · 10-3 m/day'))


class Bai3SecondPassTests(unittest.TestCase):
    def test_identical_and_unchained_phases_are_reported(self):
        from unittest.mock import patch
        from assistant import plaxis_commands
        rows = [{'phase': f'Phase_{i}', 'previous': 'InitialPhase', 'kind': 4, 'pending': True, 'on': ['Plate_1'], 'off': [], 'materials': [], 'state': (('Plate_1', (True, None)),)} for i in range(1, 6)]
        with patch.object(plaxis_commands, 'phase_changes', return_value=rows):
            problems = plaxis_commands._empty_phases(object())
        self.assertTrue(any('giống hệt' in p for p in problems)); self.assertTrue(any('nối tiếp' in p for p in problems))

    def test_two_branches_from_initial_like_tutorial_2_are_fine(self):
        from unittest.mock import patch
        from assistant import plaxis_commands
        rows = [{'phase': 'Phase_1', 'previous': 'InitialPhase', 'kind': 4, 'pending': True, 'on': ['Soil_2'], 'off': [], 'materials': [], 'state': (('a', 1),)},
                {'phase': 'Phase_2', 'previous': 'InitialPhase', 'kind': 4, 'pending': True, 'on': ['Soil_2'], 'off': [], 'materials': ['Soil_1'], 'state': (('a', 2),)}]
        with patch.object(plaxis_commands, 'phase_changes', return_value=rows):
            self.assertEqual(plaxis_commands._empty_phases(object()), [])

    def test_wall_drawn_off_manual_coordinates_is_flagged(self):
        from assistant.online_automation import geometry_off_manual
        state = {'tutorial': {'coords': [[50, 20], [50, -10], [43, 20], [48, 20], [50, 19]]}}
        call = {'function': {'arguments': {'commands': json.dumps([{'command': 'plate', 'args': [50, 20, 50, 0]}])}}}
        warning = geometry_off_manual(state, call, {'results': [{'step': 1}]})
        self.assertIn('plate (50 0)', warning); self.assertNotIn('(50 20)', warning)

    def test_manual_coordinates_extracted_from_tutorial_pages_only(self):
        from assistant.document_memory import tutorial_coordinates
        text = '[trang 10]\nfooting (0 4)\n[trang 57]\nMove to (50 20) and (50 -10).\n[trang 80]\nrock (1 1)'
        self.assertEqual(tutorial_coordinates(text, 52, 71), {(50.0, 20.0), (50.0, -10.0)})

    def test_checklist_blocks_calculate_once(self):
        from assistant.online_automation import checklist_gaps
        model = {'role': 'tool', 'tool_name': 'plaxis_commands', 'content': json.dumps({'ok': True, 'model_state': 'Soils: 3 (a, b, c); Plates: 1 (Plate_1)'})}
        state = {'tutorial': {'steps': ['3.4.2 To define the interfaces:', '3.4.3 To define the excavation levels:', '3.4.4 To define the strut:']},
                 'messages': [{'role': 'user', 'content': 'tính bài 3'}, model]}
        calc = {'commands': json.dumps([{'command': 'calculate', 'args': []}])}
        gaps = checklist_gaps(state, calc)
        self.assertIn('Interfaces', gaps); self.assertIn('cao độ đào', gaps); self.assertIn('neo', gaps)
        self.assertIsNone(checklist_gaps(state, calc))

    def test_provider_balance_error_is_explained(self):
        from assistant.online_automation import provider_problem
        text = provider_problem('Dịch vụ DEEPSEEK HTTP 402. Chưa xử lý được yêu cầu. Chi tiết: Insufficient Balance')
        self.assertIn('DEEPSEEK', text); self.assertIn('hết tiền', text)
        self.assertIsNone(provider_problem('Phản hồi kế hoạch không phải JSON'))


class ProviderParityTests(unittest.TestCase):
    def test_local_textual_tool_call_is_executed(self):
        from assistant.agent import _textual_tool_call
        schemas = [{'type': 'function', 'function': {'name': 'file_read'}}]
        call = _textual_tool_call('```json\n{"name": "file_read", "arguments": {"path": "a.txt"}}\n```', schemas)
        self.assertEqual(call, {'function': {'name': 'file_read', 'arguments': {'path': 'a.txt'}}})
        self.assertIsNone(_textual_tool_call('Đây là câu trả lời {"name": "file_read"}', schemas))
        self.assertIsNone(_textual_tool_call('{"name": "rm_rf", "arguments": {}}', schemas))

    def test_commands_object_without_tool_name_is_wrapped(self):
        from assistant.online_automation import parse_plan
        from assistant.tools import EXTRA_TOOLS
        raw = json.dumps({'commands': json.dumps([{'command': 'gotostructures', 'args': []}])})
        plan = parse_plan(raw, [s for _, s in EXTRA_TOOLS])
        self.assertEqual(plan['tool'], 'plaxis_commands')

    def test_vision_from_ollama_capabilities(self):
        from assistant import vision_support
        vision_support._CACHE.clear()
        with patch.object(vision_support, '_show', return_value={'capabilities': ['completion', 'vision']}):
            self.assertTrue(vision_support.local_supports_vision('http://h', 'llava-new:7b'))
        with patch.object(vision_support, '_show', return_value={'capabilities': ['completion', 'tools']}):
            self.assertFalse(vision_support.local_supports_vision('http://h', 'qwen2.5:3b'))

    def test_provider_account_error_message(self):
        from assistant.online_automation import provider_problem
        self.assertIn('Khóa API', provider_problem('Dịch vụ NVIDIA HTTP 401 unauthorized'))


class MidStringBracketTests(unittest.TestCase):
    def test_swapped_closers_inside_commands_are_fixed(self):
        from assistant.plaxis_commands import commands_from_json
        raw = ('[{"command":"platemat","args":[],"result":"wall_mat"},'
               '{"command":"setproperties","args":[{"ref":"wall_mat"},"Identification","Wall"}],'
               '{"command":"setmaterial","args":[{"ref":"g.Plates","index":0},{"ref":"wall_mat"}]}]')
        rows = commands_from_json(raw)
        self.assertEqual([r['command'] for r in rows], ['platemat', 'setproperties', 'setmaterial'])
        self.assertEqual(rows[1]['args'][-1], 'Wall')

    def test_brackets_inside_strings_are_not_touched(self):
        from assistant.online_automation import fix_mismatched_closers
        self.assertEqual(fix_mismatched_closers('{"a":["x}]y"}]'), {'a': ['x}]y']})
        self.assertIsNone(fix_mismatched_closers('{"a":[1]}'))  # nothing to fix

    def test_material_on_geometry_line_gets_object_hint(self):
        from unittest.mock import Mock
        from assistant.plaxis_commands import execute_commands
        from assistant import windows_apps
        windows_apps.resume_automation()
        line = Mock(); line.__str__ = lambda self: 'Line_1 <Line {ABC}>'; line.Name.value = 'Line_1'
        g = Mock(); g.Line_1 = line; g.setmaterial.side_effect = RuntimeError('Unsuccessful command:\nInvalid parameters.')
        g.commands.return_value = "setmaterial (sm)\n  <{1,...}: Feature'>' Material'"
        result = execute_commands(Mock(), g, [{'command': 'setmaterial', 'args': [{'ref': 'Line_1'}, 1]}])
        self.assertIn('g.Plates', result['object_hint'])
