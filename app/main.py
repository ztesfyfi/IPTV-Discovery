import os, time, json, asyncio
from pathlib import Path
from urllib.parse import urlparse
import yaml, httpx
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel
from .db import connect, init_db
from .parsers import parse_playlist, normalize_name
from .security import validate_public_http_url

DATA=Path(os.getenv("DATA_DIR","/data")); CONFIG=Path(os.getenv("CONFIG_DIR","/app/config"))
IMPORTS=DATA/"imports"; MAX_BYTES=int(os.getenv("MAX_IMPORT_BYTES","5242880"))
TIMEOUT=float(os.getenv("REQUEST_TIMEOUT","8")); CONCURRENCY=max(1,int(os.getenv("MAX_CONCURRENCY","4")))
DEEP_CONCURRENCY=max(1,int(os.getenv("DEEP_CONCURRENCY","1"))); TOKEN=os.getenv("ADMIN_TOKEN","")
app=FastAPI(title="IPTV Discovery",version="0.1.0")

class LocalImport(BaseModel):
    filename:str
    source_name:str="local-import"
class RemoteImport(BaseModel):
    url:str
    source_name:str="remote-import"

def auth(token):
    if TOKEN and token!=TOKEN: raise HTTPException(401,"缺少或错误的 X-Admin-Token")

def seed_channels():
    p=CONFIG/"channels.yaml"
    if not p.exists(): return
    data=yaml.safe_load(p.read_text("utf-8")) or {}
    with connect() as c:
        for ch in data.get("channels",[]):
            c.execute("INSERT OR REPLACE INTO channels VALUES(?,?,?)",(ch["id"],ch["name"],ch.get("group","其他")))
            for a in ch.get("aliases",[]): c.execute("INSERT OR REPLACE INTO aliases VALUES(?,?)",(normalize_name(a),ch["id"]))

def match_channel(name):
    n=normalize_name(name)
    with connect() as c:
        r=c.execute("SELECT channel_id FROM aliases WHERE alias=?",(n,)).fetchone()
        return r["channel_id"] if r else None

def save_rows(rows,source_name,source_type,source_url=None):
    with connect() as c:
        c.execute("INSERT OR IGNORE INTO sources(name,source_type,source_url) VALUES(?,?,?)",(source_name,source_type,source_url))
        sid=c.execute("SELECT id FROM sources WHERE name=?",(source_name,)).fetchone()["id"]
        added=0
        for x in rows:
            u=x["url"].strip()
            if not u.startswith(("http://","https://")): continue
            cur=c.execute("INSERT OR IGNORE INTO candidates(channel_id,name_raw,url,source_id,protocol) VALUES(?,?,?,?,?)",
                (match_channel(x["name"]),x["name"].strip() or "未命名频道",u,sid,urlparse(u).scheme))
            added+=cur.rowcount
    return added

@app.on_event("startup")
def startup():
    for p in (IMPORTS,DATA/"database",DATA/"output"): p.mkdir(parents=True,exist_ok=True)
    init_db(); seed_channels()

@app.get("/health")
def health():
    with connect() as c: n=c.execute("SELECT COUNT(*) n FROM candidates").fetchone()["n"]
    return {"status":"ok","version":"0.1.0","candidates":n}

@app.get("/api/channels")
def channels():
    with connect() as c:
        return [dict(r) for r in c.execute("""SELECT ch.id,ch.name,ch.group_name,COUNT(ca.id) candidate_count,
        SUM(CASE WHEN ca.status='online' THEN 1 ELSE 0 END) online_count FROM channels ch
        LEFT JOIN candidates ca ON ca.channel_id=ch.id GROUP BY ch.id ORDER BY ch.group_name,ch.name""")]

@app.get("/api/candidates")
def candidates(status:str|None=None,limit:int=Query(500,ge=1,le=5000)):
    with connect() as c:
        q="SELECT * FROM candidates"; args=()
        if status: q+=" WHERE status=?"; args=(status,)
        q+=" ORDER BY id DESC LIMIT ?"; args=args+(limit,)
        return [dict(r) for r in c.execute(q,args)]

@app.get("/api/sources")
def sources():
    with connect() as c: return [dict(r) for r in c.execute("SELECT * FROM sources ORDER BY id DESC")]

@app.post("/api/imports/local")
def import_local(body:LocalImport,x_admin_token:str|None=Header(default=None)):
    auth(x_admin_token)
    if Path(body.filename).name!=body.filename: raise HTTPException(400,"非法文件名")
    p=IMPORTS/body.filename
    if not p.is_file(): raise HTTPException(404,"请先把文件放入 data/imports/")
    raw=p.read_bytes()
    if len(raw)>MAX_BYTES: raise HTTPException(413,"文件过大")
    rows=parse_playlist(raw.decode("utf-8",errors="replace"))
    return {"parsed":len(rows),"added":save_rows(rows,body.source_name,"local")}

@app.post("/api/imports/remote")
async def import_remote(body:RemoteImport,x_admin_token:str|None=Header(default=None)):
    auth(x_admin_token)
    try: validate_public_http_url(body.url)
    except ValueError as e: raise HTTPException(400,str(e))
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT,follow_redirects=False) as client:
            async with client.stream("GET",body.url,headers={"Range":f"bytes=0-{MAX_BYTES - 1}"}) as r:
                if r.is_redirect: raise HTTPException(400,"订阅重定向暂不自动跟随，请填写最终 URL")
                r.raise_for_status()
                chunks=[]; total=0
                async for chunk in r.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_BYTES: raise HTTPException(413,"订阅文件过大")
                    chunks.append(chunk)
                raw=b"".join(chunks)
    except httpx.HTTPError as e: raise HTTPException(502,f"获取失败：{e}")
    rows=parse_playlist(raw.decode("utf-8",errors="replace"))
    return {"parsed":len(rows),"added":save_rows(rows,body.source_name,"remote",body.url)}

async def probe(row,deep):
    start=time.perf_counter(); status=None; ok=False; detail=""; meta={}
    try:
        validate_public_http_url(row["url"])
        async with httpx.AsyncClient(timeout=TIMEOUT,follow_redirects=False) as client:
            async with client.stream("GET",row["url"],headers={"Range":"bytes=0-1023"}) as r:
                status=r.status_code; ok=status in (200,206)
                detail="HTTP 可达" if ok else f"HTTP {status}"
                if ok:
                    async for _chunk in r.aiter_bytes():
                        break
        latency=round((time.perf_counter()-start)*1000,2)
        if deep and ok:
            p=await asyncio.create_subprocess_exec("ffprobe","-v","error","-rw_timeout","5000000","-i",row["url"],
                "-select_streams","v:0","-show_entries","stream=width,height,avg_frame_rate,bit_rate,codec_name",
                "-of","json","-read_intervals","%+8",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            out,_=await asyncio.wait_for(p.communicate(),timeout=15)
            if p.returncode==0:
                ss=json.loads(out.decode()).get("streams",[])
                if ss:
                    s=ss[0]; f=s.get("avg_frame_rate","0/1").split("/")
                    meta={"width":s.get("width"),"height":s.get("height"),
                          "fps":round(float(f[0])/float(f[1]),2) if len(f)==2 and float(f[1]) else None,
                          "bitrate":int(s["bit_rate"]) if str(s.get("bit_rate","")).isdigit() else None,"codec":s.get("codec_name")}
                    detail+="; FFprobe 元数据成功"
    except Exception as e:
        latency=round((time.perf_counter()-start)*1000,2); detail=str(e)[:250]
    return {"id":row["id"],"ok":ok,"status":status,"latency":latency,"detail":detail,"meta":meta}

@app.post("/api/checks/run")
async def checks_run(deep:bool=False,x_admin_token:str|None=Header(default=None)):
    auth(x_admin_token)
    with connect() as c: rows=c.execute("SELECT * FROM candidates WHERE status IN ('pending','online','offline') ORDER BY id LIMIT 500").fetchall()
    sem=asyncio.Semaphore(DEEP_CONCURRENCY if deep else CONCURRENCY)
    async def task(r):
        async with sem: return await probe(dict(r),deep)
    results=await asyncio.gather(*(task(r) for r in rows))
    with connect() as c:
        for x in results:
            m=x["meta"]
            c.execute("""UPDATE candidates SET status=?,last_status_code=?,latency_ms=?,width=?,height=?,fps=?,bitrate=?,codec=?,last_checked=CURRENT_TIMESTAMP WHERE id=?""",
                ("online" if x["ok"] else "offline",x["status"],x["latency"],m.get("width"),m.get("height"),m.get("fps"),m.get("bitrate"),m.get("codec"),x["id"]))
            c.execute("INSERT INTO checks(candidate_id,ok,status_code,latency_ms,detail) VALUES(?,?,?,?,?)",
                (x["id"],int(x["ok"]),x["status"],x["latency"],x["detail"]))
    return {"checked":len(results),"online":sum(x["ok"] for x in results),"offline":sum(not x["ok"] for x in results),"deep":deep}

@app.get("/api/checks/recent")
def recent(limit:int=Query(100,ge=1,le=1000)):
    with connect() as c: return [dict(r) for r in c.execute("SELECT * FROM checks ORDER BY id DESC LIMIT ?",(limit,))]

def export_rows():
    with connect() as c:
        return [dict(r) for r in c.execute("""SELECT ca.*,ch.name channel_name,ch.group_name FROM candidates ca
        LEFT JOIN channels ch ON ch.id=ca.channel_id WHERE ca.status='online'
        ORDER BY COALESCE(ch.group_name,'未分类'),COALESCE(ch.name,ca.name_raw),ca.latency_ms""")]

@app.get("/exports/result.m3u")
def export_m3u():
    lines=["#EXTM3U"]
    for r in export_rows():
        name=r["channel_name"] or r["name_raw"]; group=r["group_name"] or "未分类"
        lines.extend([f'#EXTINF:-1 tvg-id="{r["channel_id"] or ""}" group-title="{group}",{name}',r["url"]])
    return PlainTextResponse("\n".join(lines)+"\n",media_type="audio/x-mpegurl")

@app.get("/exports/result.txt")
def export_txt():
    return PlainTextResponse("\n".join(f'{r["channel_name"] or r["name_raw"]},{r["url"]}' for r in export_rows())+"\n")

@app.get("/exports/result.json")
def export_json(): return JSONResponse(export_rows())
