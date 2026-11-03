import json,re
from collections import Counter
def valid(v,s):
 t=s.get("type")
 if t=="object":return isinstance(v,dict) and all(k in v for k in s.get("required",[])) and (s.get("additionalProperties",True) or set(v)<=set(s["properties"])) and all(valid(x,s["properties"][k]) for k,x in v.items() if k in s["properties"])
 if t=="array":return isinstance(v,list) and all(valid(x,s["items"]) for x in v)
 if t=="string":return isinstance(v,str) and ("enum" not in s or v in s["enum"])
 if t=="integer":return isinstance(v,int) and not isinstance(v,bool)
 if t=="number":return isinstance(v,(int,float)) and not isinstance(v,bool)
 return False
def normalize(x):
 if isinstance(x,bool): return x
 if isinstance(x,(int,float)): return float(x)
 if isinstance(x,list):return [normalize(v) for v in x]
 if isinstance(x,dict):return {k:normalize(v) for k,v in x.items()}
 return x
def canon(calls):return Counter(json.dumps(normalize(c),sort_keys=True,ensure_ascii=False) for c in calls)
def score(task,response):
 try:
  choice=response["choices"][0];m=choice["message"];content=m.get("content") or "";calls=[];errors=[]
  schema={x["function"]["name"]:x["function"]["parameters"] for x in task["tools"]}
  for tc in m.get("tool_calls") or []:
   try:
    f=tc["function"];args=json.loads(f["arguments"]);name=f["name"]
    calls.append({"name":name,"arguments":args})
    if name not in schema or not valid(args,schema[name]):errors.append("schema")
   except (KeyError,TypeError,ValueError):errors.append("malformed_call")
  if re.search(r"<tool_call|</tool_call|<function=|<parameter=|\"arguments\"\s*:",content):errors.append("leaked_tool_syntax")
  if choice.get("finish_reason")=="length":errors.append("truncated")
  ok=not errors and canon(calls)==canon(task["expected"])
  if not task["expected"] and not content.strip():ok=False
  return {"pass":ok,"format_slip":bool(errors),"format_errors":errors,"parsed_calls":calls}
 except (KeyError,IndexError,TypeError):return {"pass":False,"format_slip":True,"format_errors":["invalid_response"],"parsed_calls":[]}
