import ipaddress, socket
from urllib.parse import urlparse

def validate_public_http_url(url):
    p=urlparse(url)
    if p.scheme not in ("http","https") or not p.hostname: raise ValueError("仅允许完整 HTTP/HTTPS URL")
    host=p.hostname.lower()
    if host=="localhost" or host.endswith((".localhost",".local")): raise ValueError("拒绝本地或局域网主机")
    try: ips={ipaddress.ip_address(host)}
    except ValueError:
        try: ips={ipaddress.ip_address(x[4][0]) for x in socket.getaddrinfo(host,p.port or (443 if p.scheme=="https" else 80))}
        except socket.gaierror as e: raise ValueError(f"域名解析失败：{e}")
    if any(not ip.is_global for ip in ips): raise ValueError("拒绝私有、环回、链路本地或保留 IP")
    return url
