import re
from urllib.parse import urlparse

def parse_playlist(text):
    rows=[]; pending=None
    for raw in text.replace("\ufeff","").splitlines():
        line=raw.strip()
        if not line: continue
        if line.startswith("#EXTINF"):
            name=line.split(",",1)[1].strip() if "," in line else "未命名频道"
            pending={"name":name}
        elif not line.startswith("#") and line.lower().startswith(("http://","https://")):
            rows.append({"name":(pending or {}).get("name","未命名频道"),"url":line}); pending=None
    if not rows:
        for line in text.splitlines():
            s=line.strip()
            if not s or s.startswith("#"): continue
            if "," in s:
                name,url=s.split(",",1)
                if url.strip().startswith(("http://","https://")): rows.append({"name":name.strip(),"url":url.strip()})
            elif s.startswith(("http://","https://")): rows.append({"name":urlparse(s).hostname or "未命名频道","url":s})
    return rows

def normalize_name(name):
    return re.sub(r"[\s_（）()【】\[\]-]+","",name).upper()
