import time
import unittest
from unittest.mock import patch
from assistant import billing_client
from assistant.accounts import request_account, AccountAPIError


class DirectBillingTests(unittest.TestCase):
    def setUp(self):
        billing_client._cache.clear()
        self.calls = []
        self.body = {'username': 'alice', 'key': 'private-main-session'}

    def transport(self, endpoint, path, body, timeout=12):
        self.calls.append((endpoint, path, dict(body)))
        if path == '/api/account/billing-session':
            self.assertEqual(endpoint, billing_client.PRIMARY)
            return {'success': True, 'billing_endpoint': billing_client.AUTHORITY,
                    'billing_session': 'signed-short-session', 'expires_at': (time.time()+300)*1000}
        if endpoint == billing_client.AUTHORITY:
            self.assertNotIn('key', body)
            self.assertNotIn('username', body)
            self.assertEqual(body['billing_session'], 'signed-short-session')
            return {'success': True, 'wallet': {'balance': 1000}, 'totals': {'alice': {'balance_vnd': 1}}}
        if path == '/api/admin/accounts/list':
            self.assertTrue(body['billing_direct'])
            return {'success': True, 'users': [{'username': 'alice', 'account_status': 'active'}]}
        return {'success': True}

    def test_polls_and_orders_go_to_authority_with_one_cached_identity_request(self):
        with patch('assistant.accounts._request_account', side_effect=self.transport):
            for path in ['/api/billing/status', '/api/billing/order', '/api/billing/order/status']:
                request_account(billing_client.PRIMARY, path, self.body)
            request_account(billing_client.PRIMARY, '/api/provider/model', self.body)
        self.assertEqual([c[1] for c in self.calls if c[0] == billing_client.PRIMARY],
                         ['/api/account/billing-session', '/api/provider/model'])

    def test_admin_list_gets_billing_directly_and_survives_outage(self):
        with patch('assistant.accounts._request_account', side_effect=self.transport):
            result = request_account(billing_client.PRIMARY, '/api/admin/accounts/list', self.body)
        self.assertEqual(result['users'][0]['billing']['balance_vnd'], 1)
        def offline(endpoint, path, body, timeout=12):
            if endpoint == billing_client.AUTHORITY:
                raise RuntimeError('offline')
            return self.transport(endpoint, path, body, timeout)
        with patch('assistant.accounts._request_account', side_effect=offline):
            result = request_account(billing_client.PRIMARY, '/api/admin/accounts/list', self.body)
        self.assertTrue(result['users'][0]['billing']['billing_unavailable'])

    def test_ambiguous_payment_never_falls_back_or_retries(self):
        def ambiguous(endpoint, path, body, timeout=12):
            result = self.transport(endpoint, path, body, timeout)
            if endpoint == billing_client.AUTHORITY:
                raise RuntimeError('connection lost after credit')
            return result
        with patch('assistant.accounts._request_account', side_effect=ambiguous):
            with self.assertRaises(RuntimeError):
                request_account(billing_client.PRIMARY, '/api/admin/billing/credit', self.body)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.calls[-1][0], billing_client.AUTHORITY)

    def test_changed_login_or_target_gets_separate_session(self):
        with patch('assistant.accounts._request_account', side_effect=self.transport):
            for body in [self.body, {**self.body, 'key': 'new-session'}, {**self.body, 'target': 'bob'}]:
                request_account(billing_client.PRIMARY, '/api/billing/status', body)
        self.assertEqual(sum(c[1] == '/api/account/billing-session' for c in self.calls), 3)

    def test_expired_ticket_evicted_without_retrying_mutation(self):
        def expired(endpoint, path, body, timeout=12):
            result = self.transport(endpoint, path, body, timeout)
            if endpoint == billing_client.AUTHORITY:
                raise AccountAPIError('expired', 401, code='BILLING_SESSION_EXPIRED')
            return result
        with patch('assistant.accounts._request_account', side_effect=expired):
            with self.assertRaises(AccountAPIError):
                request_account(billing_client.PRIMARY, '/api/billing/order', self.body)
        self.assertEqual(len(self.calls), 2)
        self.assertFalse(billing_client._cache)

    def test_untrusted_destination_rejected_before_credentials_can_leak(self):
        def malicious(endpoint, path, body, timeout=12):
            result = self.transport(endpoint, path, body, timeout)
            result['billing_endpoint'] = 'https://untrusted.example'
            return result
        with patch('assistant.accounts._request_account', side_effect=malicious):
            with self.assertRaises(RuntimeError):
                request_account(billing_client.PRIMARY, '/api/billing/status', self.body)
        self.assertEqual(len(self.calls), 1)

    def test_maintenance_checks_stay_on_primary(self):
        with patch('assistant.accounts._request_account', side_effect=self.transport):
            request_account(billing_client.PRIMARY, '/api/admin/billing/central-check', self.body)
        self.assertEqual(self.calls[0][0], billing_client.PRIMARY)
        self.assertEqual(len(self.calls), 1)


if __name__ == '__main__':
    unittest.main()
