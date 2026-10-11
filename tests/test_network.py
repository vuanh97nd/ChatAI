import socket
import ssl
import unittest
from unittest.mock import Mock, patch

from assistant.network import connect_ipv4_first, _HTTPSConnection


IPV6 = (socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('::1', 443, 0, 0))
IPV4 = (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))


class NetworkTests(unittest.TestCase):
    def test_broken_ipv6_is_not_attempted_when_ipv4_connects(self):
        connection = Mock()
        with patch('assistant.network.socket.getaddrinfo', return_value=[IPV6, IPV6, IPV4]), \
                patch('assistant.network.socket.socket', return_value=connection) as create:
            self.assertIs(connect_ipv4_first(('api.example', 443), timeout=12), connection)
        create.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM, 6)
        connection.connect.assert_called_once_with(IPV4[4])
        connection.settimeout.assert_called_once_with(12)

    def test_ipv6_fallback_still_works_when_ipv4_fails(self):
        failed, connected = Mock(), Mock()
        failed.connect.side_effect = OSError('IPv4 unavailable')
        with patch('assistant.network.socket.getaddrinfo', return_value=[IPV6, IPV4]), \
                patch('assistant.network.socket.socket', side_effect=[failed, connected]):
            self.assertIs(connect_ipv4_first(('api.example', 443), 5), connected)
        failed.close.assert_called_once()
        connected.connect.assert_called_once_with(IPV6[4])

    def test_ipv6_only_hosts_and_source_address(self):
        connection = Mock()
        with patch('assistant.network.socket.getaddrinfo', return_value=[IPV6]), \
                patch('assistant.network.socket.socket', return_value=connection):
            connect_ipv4_first(('api.example', 443), 5, ('::', 0))
        connection.bind.assert_called_once_with(('::', 0))
        connection.connect.assert_called_once_with(IPV6[4])

    def test_failed_sockets_are_closed_and_error_is_preserved(self):
        connection = Mock()
        error = TimeoutError('connection timed out')
        connection.connect.side_effect = error
        with patch('assistant.network.socket.getaddrinfo', return_value=[IPV4]), \
                patch('assistant.network.socket.socket', return_value=connection):
            with self.assertRaises(TimeoutError) as caught:
                connect_ipv4_first(('api.example', 443), 5)
        self.assertIs(caught.exception, error)
        connection.close.assert_called_once()

    def test_https_keeps_hostname_and_certificate_verification(self):
        connection = _HTTPSConnection('api.example', timeout=5)
        self.assertEqual(connection.host, 'api.example')
        self.assertTrue(connection._context.check_hostname)
        self.assertEqual(connection._context.verify_mode, ssl.CERT_REQUIRED)
        self.assertIs(connection._create_connection, connect_ipv4_first)


if __name__ == '__main__':
    unittest.main()
