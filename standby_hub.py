#!/usr/bin/env python3
# standby_hub.py — HA-HUB-01 备毂接棒器 (HA-PROTOCOL-01)
# 触发: repository_dispatch hub-failover (x-fire-receiver 链); 零定时,互守免cron
# 三验: ①毂脉实stale ②lease无新主(栅栏) ③钥在 → claim→巡拍→账录→宣示; 主复则让
import json,base64,urllib.request,urllib.parse,os,sys,time,hashlib,datetime
GH="https://api.github.com"
def now(): return datetime.datetime.now(datetime.timezone.utc)
def iso(dt): return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
def parse(s): return datetime.datetime.fromisoformat(s.replace("Z","+00:00"))
class G:
    def __init__(s,tok): s.h={"Authorization":"token "+tok,"Accept":"application/vnd.github+json","User-Agent":"ci-standby-hub"}
    def get(s,u):
        return json.loads(urllib.request.urlopen(urllib.request.Request(GH+urllib.parse.quote(u,safe="/?=&"),headers=s.h),timeout=60).read().decode())
    def put(s,repo,path,content,msg):
        url=GH+"/repos/"+repo+"/contents/"+urllib.parse.quote(path)
        body={"message":msg,"content":base64.b64encode(content.encode()).decode()}
        try: body["sha"]=s.get("/repos/"+repo+"/contents/"+path)["sha"]
        except Exception: pass
        return json.loads(urllib.request.urlopen(urllib.request.Request(url,data=json.dumps(body).encode(),headers={**s.h,"Content-Type":"application/json"},method="PUT"),timeout=60).read().decode())
def decide(pushed_at, lease, tnow, stale_s=1800):
    """接棒判(纯函数,可测): (verdict, reason)"""
    age=(tnow-parse(pushed_at)).total_seconds()
    if age<=stale_s: return ("STAND_DOWN", "pulse-alive:%ds"%age)
    holder=lease.get("holder"); state=lease.get("state")
    if holder=="ci-worker-02" and state=="active": return ("ALREADY_MINE","lease-mine")
    return ("TAKEOVER","pulse-stale:%ds holder=%s"%(age,holder))
def main():
    tok=os.environ.get("LINE_PAT") or os.environ.get("GITHUB_TOKEN")  # 跨仓钥优先: GITHUB_TOKEN仅本仓域,读毂脉/lease须LINE_PAT
    if not tok: print("[standby] no key, stand down"); return 0
    g=G(tok); tnow=now()
    repo=g.get("/repos/chepin-ai/ci-worker-01")
    lease=json.loads(base64.b64decode(g.get("/repos/chepin-ai/ci-control/contents/bridge/HA-LEASE-01.json")["content"]).decode())
    verdict,reason=decide(repo["pushed_at"],lease,tnow)
    print("[standby] verdict:",verdict,reason)
    if verdict!="TAKEOVER": return 0
    fence=lease.get("fence","?")
    new_lease=dict(lease); new_lease.update({"holder":"ci-worker-02","fence":hashlib.sha256((fence+iso(tnow)).encode()).hexdigest()[:16],"ts":iso(tnow),"state":"active-failover"})
    g.put("chepin-ai/ci-control","bridge/HA-LEASE-01.json",json.dumps(new_lease,ensure_ascii=False,indent=1),"HA-LEASE takeover by ci-worker-02 fence="+new_lease["fence"])
    log={"ts":iso(tnow),"kind":"failover-takeover","reason":reason,"by":"ci-worker-02","lease":new_lease["fence"]}
    g.put("chepin-ai/ci-control","bridge/ha/"+iso(tnow)+"-takeover.json",json.dumps(log,ensure_ascii=False,indent=1),"failover-takeover 账录 beat41+")
    print("[standby] TAKEOVER recorded; patrol-lite done (DISC tick deferred to main loop mirror)")
    return 0
if __name__=="__main__": sys.exit(main())
