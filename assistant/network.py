"""HTTP transport for AI/account APIs on networks with broken IPv6 routes."""
import socket
from http.client import HTTPConnection, HTTPSConnection
from urllib.request import HTTPHandler, HTTPSHandler, build_opener


def connect_ipv4_first(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    host, port = address
    addresses = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    addresses.sort(key=lambda row: row[0] != socket.AF_INET)
    last_error = None
    for family, kind, protocol, _, destination in addresses:
        connection = None
        try:
            connection = socket.socket(family, kind, protocol)
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                connection.settimeout(timeout)
            if source_address:
                connection.bind(source_address)
            connection.connect(destination)
            return connection
        except OSError as error:
            last_error = error
            if connection is not None:
                connection.close()
    if last_error is not None:
        raise last_error
    raise OSError('getaddrinfo returns an empty list')


class _HTTPConnection(HTTPConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = connect_ipv4_first


class _HTTPSConnection(HTTPSConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = connect_ipv4_first


class _HTTPHandler(HTTPHandler):
    def http_open(self, request):
        return self.do_open(_HTTPConnection, request)


class _HTTPSHandler(HTTPSHandler):
    def https_open(self, request):
        return self.do_open(_HTTPSConnection, request, context=self._context)


def urlopen(url, data=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
    # Keep urllib's proxy, redirect, error and TLS verification behavior.
    # Hostnames stay intact for certificate validation and TLS SNI.
    opener = build_opener(_HTTPHandler(), _HTTPSHandler())
    return opener.open(url, data=data, timeout=timeout)
