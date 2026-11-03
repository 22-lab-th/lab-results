"""Run the 40-task tool-calling suite against any OpenAI-compatible server you already started.

Example (llama.cpp):
  llama-server -m model.gguf --jinja -c 8192 --port 8080
  python3 try_suite.py --url http://127.0.0.1:8080 --repeats 3
Only the Python standard library is needed. Tool calls are simulated; nothing is executed.
"""
import argparse,json,re,time,urllib.request
from pathlib import Path
from score import score
P=Path(__file__).resolve().parent
ASK=r"[?？]|please|provide|specify|which|what|ขอ|ระบุ|กรุณา|อะไร|เท่า|ไหน"
def api(url,payload):
 req=urllib.request.Request(url.rstrip("/")+"/v1/chat/completions",data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"})
 with urllib.request.urlopen(req,timeout=300) as r:return json.load(r)
def step_score(t,step,response):
 s=score({**t,"expected":step["expected"]},response)
 if step.get("clarification_patterns"):
  content=response["choices"][0]["message"].get("content") or ""
  s["clarification_ok"]=all(re.search(p,content,re.I) for p in step["clarification_patterns"]) and bool(re.search(ASK,content,re.I))
  s["pass"]=s["pass"] and s["clarification_ok"]
 return s
def run_task(url,model,system,t):
 payload={"model":model,"messages":[{"role":"system","content":system},{"role":"user","content":t["prompt"]}],"tools":t["tools"],"tool_choice":"auto","parallel_tool_calls":True,"temperature":0,"top_k":1,"seed":42,"max_tokens":512,"cache_prompt":False,"chat_template_kwargs":{"enable_thinking":False}}
 turns=[]
 for i,step in enumerate(t["steps"]):
  response=api(url,payload);s=step_score(t,step,response);turns.append({"response":response,"score":s})
  if i+1<len(t["steps"]):
   msg=response["choices"][0]["message"];payload["messages"].append(msg)
   for call in msg.get("tool_calls") or []:
    try:matched={"name":call["function"]["name"],"arguments":json.loads(call["function"]["arguments"])} in step["expected"]
    except (KeyError,ValueError):matched=False
    result=step["result"] if matched else {"error":"No matching fixture; lookup failed"}
    payload["messages"].append({"role":"tool","tool_call_id":call["id"],"content":json.dumps(result,ensure_ascii=False)})
   if not msg.get("tool_calls"):payload["messages"].append({"role":"user","content":"Continue the original request if possible."})
 return {"pass":all(x["score"]["pass"] for x in turns),"format_slip":any(x["score"]["format_slip"] for x in turns),"turns":turns}
if __name__=="__main__":
 ap=argparse.ArgumentParser();ap.add_argument("--url",default="http://127.0.0.1:8080");ap.add_argument("--model",default="local")
 ap.add_argument("--repeats",type=int,default=1);ap.add_argument("--limit",type=int);ap.add_argument("--out",default="my-results.jsonl");a=ap.parse_args()
 tasks=json.loads((P/"tasks-hard.json").read_text())[:a.limit];system=(P/"system-hard.txt").read_text()
 rows=[]
 with open(a.out,"w") as out:
  for rep in range(1,a.repeats+1):
   for t in tasks:
    t0=time.perf_counter()
    try:r=run_task(a.url,a.model,system,t)
    except Exception as e:r={"pass":False,"format_slip":False,"error":repr(e),"turns":[]}
    r.update(task_id=t["id"],category=t["category"],language=t["language"],repeat=rep,wall_seconds=round(time.perf_counter()-t0,2))
    rows.append(r);out.write(json.dumps(r,ensure_ascii=False)+"\n");out.flush()
    print(rep,t["id"],"PASS" if r["pass"] else "fail",r["wall_seconds"],flush=True)
 def pct(xs):return f"{sum(x['pass'] for x in xs)}/{len(xs)} ({100*sum(x['pass'] for x in xs)/len(xs):.1f}%)" if xs else "-"
 print("\noverall",pct(rows))
 for c in sorted({r["category"] for r in rows}):print(f"  {c:16}",pct([r for r in rows if r["category"]==c]))
 print("  thai            ",pct([r for r in rows if r["language"]=="th"]))
 print("format slips",sum(r["format_slip"] for r in rows),"· saved",a.out)
