import argparse, time, asyncio, aiohttp, sys

async def shoot(session, url, qps, seconds):
    interval = 1.0 / qps if qps > 0 else 0
    end = time.time() + seconds
    sent = ok = 0
    while time.time() < end:
        start = time.time()
        try:
            async with session.get(url) as r:
                if r.status == 200:
                    ok += 1
        except Exception:
            pass
        sent += 1
        sleep_for = interval - (time.time() - start)
        if sleep_for > 0:
            await asyncio.sleep(sleep_for)
    return sent, ok

async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="http://localhost:8080")
    p.add_argument("--path", default="/infer")
    p.add_argument("--qps", type=float, default=20)
    p.add_argument("--seconds", type=int, default=120)
    args = p.parse_args()
    url = args.host.rstrip("/") + args.path
    async with aiohttp.ClientSession() as s:
        sent, ok = await shoot(s, url, args.qps, args.seconds)
    print(f"Sent={sent} OK={ok} SuccessRate={ok/max(1,sent):.2f}")

if __name__ == "__main__":
    try:
        import aiohttp  # noqa
    except ImportError:
        print("Install dependency first: pip install aiohttp", file=sys.stderr)
        sys.exit(1)
    asyncio.run(main())
