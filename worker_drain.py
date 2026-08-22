#!/usr/bin/env python3
"""CI-WORKER-DRAIN — 公域空仓认领器（零 secret 铁律）。
匿名读公域权威队 vci-inbox/spool-public/queue/，执行 public-safe 件（probe/report），
结果落本仓 results/（at-least-once，幂等件专用）；对账由 cisvr/guard 收卡。
"""
import json, os, urllib.request, base64, datetime, sys

QAPI = "https://api.github.com/repos/chepin-ai/vci-inbox/contents/spool-public/queue"
RAW = "https://raw.githubusercontent.com/chepin-ai/vci-inbox/main/spool-public/queue/"
WORKER = os.environ.get("WORKER_NAME", "ci-worker-?")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ci-worker-drain/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.read().decode("utf-8", "replace")


def main():
    os.makedirs("results", exist_ok=True)
    try:
        _, listing = fetch(QAPI)
        files = [f["name"] for f in json.loads(listing) if f["name"].endswith(".json")]
    except Exception as e:
        print("queue 拉取失败:", str(e)[:120]); files = []
    done = 0
    for fn in files:
        jid = fn[:-5]
        if os.path.exists("results/%s.json" % jid):
            continue
        try:
            _, raw = fetch(RAW + fn)
            job = json.loads(raw)
        except Exception:
            continue
        if job.get("state") != "queued" or job.get("runner_class") != "public-safe":
            continue
        res = {"job_id": jid, "worker": WORKER, "runner": "github-hosted ubuntu-latest",
               "finished_ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        try:
            if job.get("type") == "probe":
                out = {}
                for u in job.get("payload", {}).get("urls", []):
                    try:
                        c, _ = fetch(u); out[u] = c
                    except Exception as e:
                        out[u] = str(e)[:80]
                res["result"] = out or {"note": job.get("payload", {}).get("note", "")}
            else:
                res["result"] = {"note": job.get("payload", {}).get("note", ""), "type": job.get("type")}
            res["ok"] = True
        except Exception as e:
            res.update({"ok": False, "error": str(e)[:200]})
        json.dump(res, open("results/%s.json" % jid, "w"), ensure_ascii=False, indent=1)
        done += 1
    with open("pulse.log", "a") as f:
        f.write("%s %s drained=%d\n" % (res["finished_ts"] if done else datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), WORKER, done))
    print("drained", done)


if __name__ == "__main__":
    main()
