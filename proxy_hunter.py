#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, concurrent.futures as fut, ipaddress, random, re, socket, sys, time
from typing import List, Tuple, Optional, Dict
try:
    import requests
except Exception:
    print("Missing dependency 'requests'."); sys.exit(1)
try:
    import socks  # PySocks
except Exception:
    socks = None

DEFAULT_SOURCES = [
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=https&timeout=5000&country=all&ssl=all&anonymity=all",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=5000&country=all",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=5000&country=all",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks4.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
]
TEST_URLS_DEFAULT = ["https://api.ipify.org?format=json","https://httpbin.org/ip","https://ifconfig.me/ip"]
UA = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
      "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121 Safari/537.36",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/16.0 Safari/605.1.15"]
IP_PORT_RE = re.compile(r"^(?P<ip>(?:\d{1,3}\.){3}\d{1,3}):(?P<port>\d{2,5})$")
def is_ip_port(line:str)->Optional[Tuple[str,int]]:
    m=IP_PORT_RE.match(line.strip()); 
    if not m: return None
    ip=m.group("ip"); port=int(m.group("port"))
    try: ipaddress.ip_address(ip)
    except: return None
    if not (1<=port<=65535): return None
    return ip, port
def fetch_source(url:str, timeout:float)->List[str]:
    try:
        r=requests.get(url, timeout=timeout, headers={"User-Agent": random.choice(UA)}); r.raise_for_status()
        return [ln.strip() for ln in r.text.splitlines() if ln.strip()]
    except Exception: return []
def collect_proxies(sources:List[str], timeout:float, limit:int)->List[str]:
    pool=set()
    for url in sources:
        for ln in fetch_source(url, timeout):
            if is_ip_port(ln): pool.add(ln.strip())
        if len(pool)>=limit: break
    return list(pool)[:limit]
def build_requests_proxies(proto:str, hostport:str)->Dict[str,str]:
    p=proto.lower()
    if p in ("socks4","socks5"): sch="socks4" if p=="socks4" else "socks5"; return {"http":f"{sch}://{hostport}","https":f"{sch}://{hostport}"}
    return {"http":f"http://{hostport}","https":f"http://{hostport}"}
def test_single(hostport:str, proto:str, test_urls:List[str], timeout:float):
    url=random.choice(test_urls); proxies=build_requests_proxies(proto,hostport)
    try:
        t0=time.perf_counter(); r=requests.get(url, proxies=proxies, timeout=timeout, headers={"User-Agent": random.choice(UA)})
        dt=int((time.perf_counter()-t0)*1000)
        if r.status_code==200: return {"proxy":hostport,"protocol":proto,"latency_ms":dt,"test_url":url}
    except Exception: return None
def parse_protocols(arg:str)->List[str]:
    allowed={"http","https","socks4","socks5"}
    parts=[p.strip().lower() for p in arg.split(",") if p.strip()]
    out=[p for p in parts if p in allowed]
    return out or ["http","https","socks5"]
def main():
    import argparse, sys, time
    ap=argparse.ArgumentParser(description="Fetch and test public proxies; save working ones.")
    ap.add_argument("--protocols",type=str,default="http,https,socks5")
    ap.add_argument("--limit",type=int,default=300)
    ap.add_argument("--timeout",type=float,default=6.0)
    ap.add_argument("--concurrency",type=int,default=200)
    ap.add_argument("--sources-json",type=str,default="")
    ap.add_argument("--test-url",type=str,default="")
    ap.add_argument("--output",type=str,default="good_proxies.txt")
    args=ap.parse_args()
    if args.concurrency<1: args.concurrency=1
    protocols=parse_protocols(args.protocols)
    sources=list(DEFAULT_SOURCES)
    if args.sources_json:
        try:
            import json; extra=json.load(open(args.sources_json,"r",encoding="utf-8"))
            if isinstance(extra,list): sources.extend([str(u) for u in extra if isinstance(u,str)])
        except Exception as e: print("Warning: couldn't read sources-json:",e)
    print(f"Collecting from {len(sources)} sources (limit={args.limit}) ...")
    pool=collect_proxies(sources, timeout=args.timeout, limit=args.limit)
    print(f"Found {len(pool)} candidates.")
    if not pool: print("No candidates."); sys.exit(1)
    test_urls=[args.test_url] if args.test_url else TEST_URLS_DEFAULT
    work=[(hp,p) for hp in pool for p in protocols]
    print(f"Testing {len(work)} combos with concurrency={args.concurrency} ...")
    results=[]; tested=0; ok=0; t=time.time()
    def runner(item): return test_single(item[0], item[1], test_urls, args.timeout)
    with fut.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        for res in ex.map(runner, work):
            tested+=1
            if res: results.append(res); ok+=1
            if tested % 50 == 0:
                print(f" ... tested {tested}/{len(work)} — good: {ok} — elapsed {int(time.time()-t)}s")
    dedup={}
    for r in results:
        k=(r["proxy"], r["protocol"])
        if k not in dedup or r["latency_ms"]<dedup[k]["latency_ms"]: dedup[k]=r
    final=sorted(dedup.values(), key=lambda x:x["latency_ms"])
    if not final: print("No working proxies."); sys.exit(2)
    txt=args.output; csv=txt.rsplit(".",1)[0]+".csv"
    open(txt,"w",encoding="utf-8").write("\n".join([f'{r["protocol"]}://{r["proxy"]}  latency_ms={r["latency_ms"]}  test={r["test_url"]}' for r in final]))
    open(csv,"w",encoding="utf-8").write("protocol,proxy,latency_ms,test_url\n"+"\n".join([f'{r["protocol"]},{r["proxy"]},{r["latency_ms"]},{r["test_url"]}' for r in final]))
    print(f"Saved {len(final)} working proxies -> {txt} & {csv}")
if __name__=="__main__": main()
