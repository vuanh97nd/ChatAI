"""Local proxy retirement; remote provider APIs remain available."""
from ipaddress import ip_address
from urllib.parse import urlparse


def local_proxy(profile):
    host = (urlparse(str(profile.get('url', ''))).hostname or '').lower()
    if host == 'localhost':
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False
