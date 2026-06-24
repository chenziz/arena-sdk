import json,os,subprocess,sys,time,urllib.request,tempfile
BASE="https://b-arena.dev.fun/api/arena"
KEY=json.load(open(os.path.expanduser("~/.arena-credentials")))["apiKey"]
COMP=sys.argv[1]
FLAG=sys.argv[2] if len(sys.argv)>2 else "--pve"
MAX=int(sys.argv[3]) if len(sys.argv)>3 else 99
# fast-fail / reject bots FIRST; hang-risk (bad-amount) LAST so a hang can't block the others
ORDER=[
 ("00_valid",'def act(t):\n a=t["allowedActions"]["availableActions"]\n return "check" if "check" in a else ("call" if "call" in a else "fold")\n'),
 ("01_illegal_action",'def act(t):\n return {"action":"teleport"}\n'),
 ("02_crash",'def act(t):\n raise RuntimeError("boom")\n'),
 ("03_bad_return",'def act(t):\n return 42\n'),
 ("04_none_return",'def act(t):\n return None\n'),
 ("05_no_entrypoint",'def foo(t):\n return "fold"\n'),
 ("06_syntax_error",'def act(t):\n return (\n'),
 ("07_bad_amount",'def act(t):\n return {"action":"raise","amount":"lots"}\n'),
 ("08_huge_amount",'def act(t):\n return {"action":"raise","amount":10**12}\n'),
]
def api(p):
    r=urllib.request.Request(BASE+p,headers={"x-arena-api-key":KEY})
    try:return json.load(urllib.request.urlopen(r,timeout=25))
    except Exception as e:return {"err":str(e)}
results=[]
for name,code in ORDER[:MAX]:
    d=tempfile.mkdtemp();p=os.path.join(d,"strategy.py");open(p,"w").write(code)
    out=subprocess.run(["./poker","submit","--strategy",p,"--competition",COMP,FLAG,"--no-watch"],
                       capture_output=True,text=True,env={**os.environ,"ARENA_ENDPOINT":BASE})
    txt=out.stdout+out.stderr
    sid=None
    for ln in txt.splitlines():
        if "id=" in ln and "accepted" in ln.lower(): sid=ln.split("id=")[1].split()[0];break
    if not sid:
        m=[l for l in txt.splitlines() if "bundle invalid" in l or "HTTP" in l or "error" in l.lower()]
        print(f"{name}: REJECTED_AT_SUBMIT | {(m[-1] if m else txt.strip()[-160:])[:200]}",flush=True)
        results.append({"name":name,"outcome":"rejected_at_submit","detail":txt.strip()[-200:]});continue
    final=None
    for _ in range(30):  # ~5 min cap
        s=api(f"/submissions/{sid}");st=s.get("status")
        if st in ("Succeeded","Failed","TimedOut"):
            final={"status":st,"code":s.get("errorCode") or s.get("code"),"error":(s.get("error") or s.get("message") or "")[:240]};break
        time.sleep(10)
    if not final: final={"status":"STILL_RUNNING"}
    print(f"{name}: {final.get('status')} | code={final.get('code')} | {final.get('error','')}",flush=True)
    results.append({"name":name,"sid":sid,**final})
print("=== DONE ===",flush=True)
