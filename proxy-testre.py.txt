import requests
import concurrent.futures
import socket
from time import time

PROXY_API = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=all&timeout=1000&country=all&ssl=all&anonymity=all"

def get_proxies():
    try:
        resp = requests.get(PROXY_API, timeout=10)
        proxies = resp.text.strip().split("\n")
        return [p.strip() for p in proxies if p.strip()]
    except Exception as e:
        print("❌ خطا در گرفتن لیست پروکسی‌ها:", e)
        return []

def test_proxy(proxy):
    try:
        start = time()
        ip, port = proxy.split(":")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((ip, int(port)))
        s.close()
        ping = int((time() - start) * 1000)
        return proxy, ping
    except:
        return None

if __name__ == "__main__":
    print("📡 دریافت لیست پروکسی‌ها...")
    proxies = get_proxies()
    print(f"🔹 تعداد پروکسی دریافتی: {len(proxies)}")

    print("⏳ در حال تست پروکسی‌ها، لطفاً صبر کنید...\n")
    good_proxies = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        for result in executor.map(test_proxy, proxies):
            if result:
                good_proxies.append(result)

    good_proxies.sort(key=lambda x: x[1])

    if good_proxies:
        with open("good_proxies.txt", "w") as f:
            for proxy, ping in good_proxies:
                line = f"{proxy} - Ping: {ping}ms"
                print("✅", line)
                f.write(line + "\n")
        print(f"\n💾 پروکسی‌های سالم در فایل good_proxies.txt ذخیره شدند.")
    else:
        print("❌ هیچ پروکسی سالمی پیدا نشد.")
