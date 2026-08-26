import os

from aiohttp import web

web_runner = None


async def health(request):
    return web.Response(text="OK")


async def start_web_server():
    global web_runner

    if web_runner is not None:
        return

    app = web.Application()
    app.router.add_get("/", health)

    web_runner = web.AppRunner(app)
    await web_runner.setup()

    port = int(os.getenv("PORT", 8080))

    site = web.TCPSite(
        web_runner,
        "0.0.0.0",
        port
    )

    await site.start()

    print(f"Web server đã start tại port {port}", flush=True)
