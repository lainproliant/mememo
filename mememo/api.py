# --------------------------------------------------------------------
# api.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Thursday July 25, 2024
# --------------------------------------------------------------------

import asyncio
import ssl
import sys

import uvicorn
from bivalve.agent import BivalveAgent
from elcamino.config import Config
from elcamino.weather import WeatherReport
from fastapi import FastAPI, Request
from xeno import AsyncInjector, provide


# --------------------------------------------------------------------
class MememoAPIModule:
    @provide
    def fastapi_app(self) -> FastAPI:
        app = FastAPI()

        @app.get("/weather")
        def weather(request: Request) -> WeatherReport:
            return WeatherReport.get(Config.get().weather)

        return app

    @provide
    def uvicorn_config(self, fastapi_app: FastAPI) -> uvicorn.Config:
        return uvicorn.Config(fastapi_app)

    @provide
    def uvicorn_server(self, uvicorn_config: uvicorn.Config) -> uvicorn.Server:
        return uvicorn.Server(uvicorn_config)

    @provide
    async def mememo_agent(self) -> BivalveAgent:
        config = Config.get()
        agent = BivalveAgent()
        await agent.connect(
            host=config.mememo.hostname,
            port=config.mememo.port,
            ssl=ssl.create_default_context() if config.mememo.ssl else None,
        )
        return agent

    @provide
    async def main(
        self, mememo_agent: BivalveAgent, uvicorn_server: uvicorn.Server
    ) -> int:
        asyncio.create_task(mememo_agent.run())
        await uvicorn_server.serve()
        return 0


# --------------------------------------------------------------------
if __name__ == "__main__":
    injector = AsyncInjector(MememoAPIModule())
    sys.exit(injector.require("main"))
