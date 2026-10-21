import json,sys
t=open(sys.argv[1],encoding="utf-8").read()
i=t.index("== inspect_rig_motion"); j=t.index("{",i)
d=json.JSONDecoder().raw_decode(t[j:])[0]
for c in d["data"]["result"]["chains"]:
    print(c["ik"], {k:v for k,v in c.items() if k not in("tip_path",)})
