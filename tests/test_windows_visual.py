import base64
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from assistant.windows_apps import WindowsApps, resume_automation, stop_automation, pause_automation
from assistant.windows_visual import VISUAL_TOOLS, key_codes, tool_message
from assistant.tools import EXTRA_TOOLS, WRITES, validate_call
from test_windows_apps import FakeBackend

JPEG = base64.b64encode(b'\xff\xd8\xff123456789').decode()

class VisualFake:
    def __init__(self):
        self.rect = (100, 200, 500, 500)
        self.valid = True
        self.actions = []
        self.captures = 0
        self.fail = False
    def list_windows(self, path):
        return [{'hwnd': 7, 'pid': 42, 'started': 123, 'title': 'Tunnel designer'}]
    def geometry(self, session):
        if not self.valid:raise PermissionError('Window changed')
        return self.rect
    def focus(self, session):return (42, 8)
    def capture(self, session):
        self.captures += 1
        return self.rect, JPEG
    def input(self, session, plan, check):
        check()
        self.actions.append(plan)
        if self.fail:raise RuntimeError('Partial input')

class VisualTest(unittest.TestCase):
    def setUp(self):
        resume_automation()
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'app.exe'
        self.path.write_bytes(b'fixture')
        self.cfg = {'windows_apps_enabled': True, 'windows_apps_allowed': [str(self.path)]}
        self.apps = WindowsApps(self.cfg, lambda *a:None, owner='test', backend=FakeBackend())
        self.backend = VisualFake()
        self.apps.visual.backend = self.backend
        row = self.run_tool('windows_list_windows', path=str(self.path))['windows'][0]
        self.selection = row['window']
        self.session = self.run_tool('windows_attach', path=str(self.path), window=self.selection)['session']
    def tearDown(self):
        resume_automation()
        self.tmp.cleanup()
    def run_tool(self, name, **args):return self.apps.commit(self.apps.prepare(name, args))
    def capture(self):return self.run_tool('windows_capture', session=self.session)
    def args(self, **extra):
        return dict(session=self.session, observation=self.capture()['observation'], operation='click', x=10, y=20, **extra)
    def test_attach_reuses_existing_window_without_launch(self):
        self.assertEqual(self.apps.backend.launches, [])
        self.assertEqual(self.backend.captures, 0)
    def test_click_returns_new_pixels_and_token(self):
        args = self.args()
        result = self.run_tool('windows_input', **args)
        self.assertEqual(result['_screenshot'], JPEG)
        self.assertTrue(result['verification_required'])
        self.assertNotEqual(result['observation'], args['observation'])
        self.assertEqual(self.backend.captures, 2)
        with self.assertRaises(PermissionError):self.run_tool('windows_input', **args)
    def test_no_input_without_observation(self):
        with self.assertRaises(PermissionError):
            self.run_tool('windows_input', session=self.session, observation='invented', operation='press_key', key='TAB')
        self.assertEqual(self.backend.actions, [])
    def test_moving_window_invalidates_prepared_click(self):
        plan = self.apps.prepare('windows_input', self.args())
        self.backend.rect = (0, 0, 400, 300)
        with self.assertRaises(PermissionError):self.apps.commit(plan)
        self.assertEqual(self.backend.actions, [])
    def test_changed_process_rejects_prepared_input(self):
        plan = self.apps.prepare('windows_input', self.args())
        self.backend.valid = False
        with self.assertRaises(PermissionError):self.apps.commit(plan)
        self.assertEqual(self.backend.actions, [])
    def test_partial_failure_cannot_replay(self):
        plan = self.apps.prepare('windows_input', self.args())
        self.backend.fail = True
        with self.assertRaises(RuntimeError):self.apps.commit(plan)
        with self.assertRaises(PermissionError):self.apps.commit(plan)
        self.assertEqual(len(self.backend.actions), 1)
    def test_outside_nonfinite_fractional_boolean_coordinates_rejected(self):
        for value in [-1, 400, float('inf'), float('nan'), 1.5, True, '12']:
            args = self.args();args['x'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):self.apps.prepare('windows_input', args)
        self.assertEqual(self.backend.actions, [])
    def test_text_literal_and_keys_validated(self):
        for operation, content in [('type_text', {'text':'Tiếng Việt + {ENTER}'}), ('press_key', {'key':'CTRL+A'})]:
            self.run_tool('windows_input', session=self.session, observation=self.capture()['observation'], operation=operation, **content)
        self.assertEqual(self.backend.actions[0]['text'], 'Tiếng Việt + {ENTER}')
        for key in ['WIN+R', 'ALT+TAB', 'ALT+F4', 'CTRL+ALT+DELETE', 'CTRL+ESC', 'A B', '{ENTER}', 'CTRL+CTRL+A']:
            with self.subTest(key=key), self.assertRaises(ValueError):key_codes(key)
        self.assertEqual(key_codes('CTRL+SHIFT+A'), [17, 16, 65])
        for text in ['x\ny', '\t', '\x00', 'a'*1001]:
            with self.assertRaises(ValueError):self.apps.prepare('windows_input', dict(session=self.session, observation=self.capture()['observation'], operation='type_text', text=text))
    def test_expired_observation_and_selection(self):
        args = self.args()
        with patch('assistant.windows_visual.time.monotonic', return_value=time.monotonic()+121):
            with self.assertRaises(PermissionError):self.apps.prepare('windows_input', args)
            with self.assertRaises(PermissionError):self.run_tool('windows_attach', path=str(self.path), window=self.selection)
    def test_owner_and_revoked_permission(self):
        other = WindowsApps(self.cfg, lambda *a:None, owner='other', backend=FakeBackend())
        with self.assertRaises(PermissionError):other.prepare('windows_attach', {'path':str(self.path), 'window':self.selection})
        with self.assertRaises(PermissionError):other.prepare('windows_capture', {'session':self.session})
        plan = self.apps.prepare('windows_input', self.args())
        self.cfg['windows_apps_allowed'] = []
        with self.assertRaises(PermissionError):self.apps.commit(plan)
    def test_stop_blocks_pending_input(self):
        plan = self.apps.prepare('windows_input', self.args())
        stop_automation()
        with self.assertRaises(PermissionError):self.apps.commit(plan)
        self.assertEqual(self.backend.actions, [])
    def test_pause_waits_and_stop_releases_waiter_without_input(self):
        plan = self.apps.prepare('windows_input', self.args())
        pause_automation()
        errors = []
        def run():
            try:self.apps.commit(plan)
            except PermissionError as exc:errors.append(str(exc))
        worker = threading.Thread(target=run)
        worker.start()
        try:
            time.sleep(.15)
            self.assertTrue(worker.is_alive())
            self.assertEqual(self.backend.actions, [])
            stop_automation()
            worker.join(1)
            self.assertFalse(worker.is_alive())
            self.assertEqual(len(errors), 1)
            self.assertEqual(self.backend.actions, [])
        finally:
            resume_automation();worker.join(1)
    def test_registry_and_plaxis_filter_expose_tools(self):
        from assistant.online_automation import _PLAXIS_TOOLSET
        specs = [s for module,s in EXTRA_TOOLS if module=='windows']
        self.assertTrue(VISUAL_TOOLS <= WRITES)
        self.assertTrue(VISUAL_TOOLS <= _PLAXIS_TOOLSET)
        validate_call('windows_input', self.args(), specs)
        with self.assertRaises(ValueError):validate_call('windows_input', dict(self.args(), shell='bad'), specs)
    def test_image_not_serialized_or_truncated_in_tool_text(self):
        result = self.capture()
        message = tool_message('windows_capture', result)
        self.assertEqual(message['images'], [JPEG])
        self.assertNotIn('_screenshot', json.loads(message['content']))
        self.assertIn('_screenshot', result)
    def test_online_planning_receives_latest_actual_image(self):
        from assistant.online_automation import planning_messages
        first = tool_message('windows_capture', self.capture())
        last = tool_message('windows_input', self.run_tool('windows_input', **self.args()))
        state = {'messages':[{'role':'user', 'content':'Dùng Tunnel_1'}, first, last]}
        messages = planning_messages(state, 'instructions')
        image_messages = [m for m in messages if isinstance(m['content'],list)]
        self.assertEqual(len(image_messages), 1)
        self.assertEqual(image_messages[0]['content'][1]['image_url']['url'], 'data:image/jpeg;base64,'+JPEG)
        self.assertIn('windows_input', image_messages[0]['content'][0]['text'])
    def test_historical_screenshot_not_sent_as_current_observation(self):
        from assistant.online_automation import planning_messages
        state = {'messages':[tool_message('windows_capture', self.capture()), {'role':'user','content':'Câu hỏi mới'}]}
        self.assertFalse(any(isinstance(m['content'],list) for m in planning_messages(state,'instructions')))



class NativeInputTest(unittest.TestCase):
    """Exercise the production encoder with fake OS functions, never a real window."""
    def setUp(self):
        from contextlib import nullcontext
        from types import SimpleNamespace
        from unittest.mock import Mock
        from assistant.windows_visual import VisualBackend
        self.sent = []
        self.after_send = lambda:None
        def send(count, events, size):
            self.sent.append([(e.type, e.ki.wVk, e.ki.wScan, e.ki.dwFlags) if e.type==1 else (e.type,e.mi.dx,e.mi.dy,e.mi.dwFlags) for e in events])
            self.after_send()
            return count
        self.user = SimpleNamespace(SendInput=Mock(side_effect=send))
        self.gui = SimpleNamespace(SetForegroundWindow=Mock(), GetForegroundWindow=lambda:7,
                                   WindowFromPoint=lambda point:7, GetAncestor=lambda hwnd,flag:7)
        self.api = SimpleNamespace(GetSystemMetrics=lambda index:{76:-100,77:0,78:1000,79:800}[index])
        patches = [patch('assistant.windows_visual.physical_pixels', side_effect=nullcontext),
                   patch('ctypes.WinDLL', return_value=self.user, create=True),
                   patch.dict('sys.modules', {'win32gui':self.gui, 'win32api':self.api})]
        for item in patches:item.start();self.addCleanup(item.stop)
        self.backend = VisualBackend()
        self.backend.geometry = lambda session:(100,200,500,500)
        self.backend.focus = lambda session:(42,8)
        self.session = {'hwnd':7,'pid':42}
        self.base = {'rect':(100,200,500,500),'focus':(42,8)}
        resume_automation();self.addCleanup(resume_automation)
    def test_literal_unicode_not_interpreted_as_hotkeys(self):
        text='Việt {ENTER}+'
        self.backend.input(self.session,dict(self.base,operation='type_text',text=text),lambda:None)
        down=[events[0] for events in self.sent]
        decoded=b''.join(event[2].to_bytes(2,'little') for event in down).decode('utf-16-le')
        self.assertEqual(decoded,text)
        self.assertTrue(all(event[1]==0 and event[3]==4 for event in down))
        self.assertTrue(all(events[1][3]==6 for events in self.sent))
    def test_stop_between_characters_drops_remaining_text(self):
        def check():
            from assistant.windows_apps import _STOP
            if _STOP.is_set():raise PermissionError('stopped')
        self.after_send=stop_automation
        with self.assertRaises(PermissionError):
            self.backend.input(self.session,dict(self.base,operation='type_text',text='abc'),check)
        self.assertEqual(len(self.sent),1)
    def test_focus_change_does_not_type(self):
        self.backend.focus=lambda session:(42,99)
        with self.assertRaises(PermissionError):
            self.backend.input(self.session,dict(self.base,operation='type_text',text='10.4'),lambda:None)
        self.assertEqual(self.sent,[])
    def test_other_foreground_window_does_not_receive_keys(self):
        self.gui.GetForegroundWindow=lambda:99
        with self.assertRaises(PermissionError):
            self.backend.input(self.session,dict(self.base,operation='press_key',key='ENTER'),lambda:None)
        self.assertEqual(self.sent,[])
    def test_occluded_click_rejected(self):
        self.gui.GetAncestor=lambda hwnd,flag:99
        with self.assertRaises(PermissionError):
            self.backend.input(self.session,dict(self.base,operation='click',x=20,y=30),lambda:None)
        self.assertEqual(self.sent,[])
    def test_mouse_move_down_up_single_batch(self):
        self.backend.input(self.session,dict(self.base,operation='click',x=20,y=30),lambda:None)
        self.assertEqual(len(self.sent),1)
        self.assertEqual([e[3] for e in self.sent[0]],[0xC001,2,4])
        self.assertEqual(self.sent[0][0][1],round(220*65535/999))
    def test_partial_chord_releases_modifiers_without_replaying(self):
        self.user.SendInput.side_effect=[1,2]
        with self.assertRaises(RuntimeError):
            self.backend.input(self.session,dict(self.base,operation='press_key',key='CTRL+A'),lambda:None)
        self.assertEqual(self.user.SendInput.call_count,2)
        release=self.user.SendInput.call_args.args[1]
        self.assertTrue(all(e.ki.dwFlags==2 for e in release))

    def test_win32_focus_fallback_and_native_password_block(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from assistant.windows_visual import VisualBackend
        def info(thread, pointer):
            pointer._obj.hwndFocus=8
            return 1
        self.user.GetGUIThreadInfo=Mock(side_effect=info)
        self.gui.GetClassName=lambda hwnd:'CustomCanvas'
        self.gui.GetWindowLong=lambda hwnd,index:0
        process=SimpleNamespace(GetWindowThreadProcessId=lambda hwnd:(9,42))
        uia=SimpleNamespace(IUIA=Mock(side_effect=RuntimeError('No UIA')))
        with patch.dict('sys.modules', {'win32process':process, 'pywinauto.uia_defines':uia}):
            backend=VisualBackend()
            self.assertEqual(backend.focus(self.session),(8,))
            self.gui.GetClassName=lambda hwnd:'Edit'
            self.gui.GetWindowLong=lambda hwnd,index:0x20
            self.assertIsNone(backend.focus(self.session))

if __name__ == '__main__':unittest.main()
