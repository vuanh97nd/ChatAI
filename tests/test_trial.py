import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from assistant.storage import Store
from assistant.trial import GuestTrial, GUEST_OWNER, TrialLimitError


class FakeAgent:
    def __init__(self, store, cid):
        self.store, self.cid = store, cid

    def save(self, state):
        self.store.save(self.cid, state)

    def start(self, state, prompt, model, images=None):
        if not prompt.strip():
            raise ValueError('Empty prompt')
        state['messages'].append({'role': 'user', 'content': prompt})
        state['running'] = True
        self.save(state)


class TrialTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'history.sqlite3'
        self.store = Store(self.path)
        self.trial = GuestTrial(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def ask(self, text='Hello'):
        cid = self.store.create()
        state = self.store.load(cid)
        self.trial.start(FakeAgent(self.store, cid), state, text, 'qwen2.5:7b')
        return cid, state

    def test_three_turns_then_login_and_restart(self):
        for remaining in (2, 1, 0):
            self.ask()
            self.assertEqual(self.trial.remaining(), remaining)
        with self.assertRaises(TrialLimitError):
            self.ask()
        self.assertEqual(GuestTrial(Store(self.path)).remaining(), 0)

    def test_invalid_input_not_counted(self):
        with self.assertRaises(ValueError):
            self.ask(' ')
        self.assertEqual(self.trial.remaining(), 3)

    def test_resume_last_turn_and_idempotency(self):
        self.ask(); self.ask()
        cid, state = self.ask()
        self.assertTrue(self.trial.can_continue(cid, state))
        self.assertFalse(self.trial.can_continue('other', state))
        self.trial.consume(cid, state)
        self.assertEqual(self.trial.remaining(), 0)
        state['account_username'] = 'other-account'
        self.assertFalse(self.trial.can_continue(cid, state))

    def test_login_adopts_only_guest_history_without_resetting_quota(self):
        cid, state = self.ask()
        other = self.store.create()
        other_state = self.store.load(other)
        other_state['account_username'] = 'bob'
        self.store.save(other, other_state)
        self.trial.adopt('alice')
        self.assertEqual(self.store.load(cid)['account_username'], 'alice')
        self.assertEqual(self.store.load(other)['account_username'], 'bob')
        self.assertEqual(self.trial.remaining(), 2)

    def test_account_history_cannot_use_guest_trial(self):
        cid = self.store.create()
        state = self.store.load(cid)
        state['account_username'] = 'alice'
        with self.assertRaises(PermissionError):
            self.trial.start(FakeAgent(self.store, cid), state, 'Hello', 'qwen2.5:7b')
        self.assertEqual(self.trial.remaining(), 3)

    def test_last_slot_is_atomic_across_connections(self):
        self.ask(); self.ask()
        def reserve(token):
            cid = self.store.create()
            state = self.store.load(cid)
            state.update(account_username=GUEST_OWNER, guest_trial_token=token)
            try:
                GuestTrial(Store(self.path)).consume(cid, state)
                return True
            except TrialLimitError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, ['a', 'b']))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(self.trial.remaining(), 0)
