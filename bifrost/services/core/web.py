from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception

from bifrost.common.service import Service
import uvicorn
import pickle
import ait.core.tlm
import ait.core.cmd
from colorama import Fore


class Web_Server(Service):
    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.start()

    @with_loud_coroutine_exception
    async def start_server(self):
        config = uvicorn.Config(self.app, port=8000, host='0.0.0.0', log_level="error")
        server = uvicorn.Server(config)
        print(f"{Fore.CYAN}Bifrost Web Service Now serving on {config.host}:{config.port}{Fore.RESET}")
        await server.serve()

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        self.app = Starlette(debug=True,
                             routes=[
                                 Mount('/test', app=StaticFiles(directory=self.index, html=True), name='static'),
                                 WebSocketRoute("/telemetry", endpoint=self.ws_telemetry),
                                 WebSocketRoute("/command_loader", endpoint=self.ws_command_loader),
                                 WebSocketRoute('/variable_messages', endpoint=self.ws_variable_messages),
                                 WebSocketRoute('/monitors', endpoint=self.ws_monitors),
                                 WebSocketRoute('/downlink_updates', endpoint=self.ws_downlink_updates),
                                 Route('/', self.homepage),
                                 Route('/pubsub', self.pubsub),
                                 Route("/dict/{dict_type:str}", self.cmd_dict),
                                 Route("/sle/raf/{directive:str}", self.sle_raf_directive),
                                 Route("/sle/cltu/{directive:str}", self.sle_cltu_directive),
                                 Route("/config", self.config_request),
                             ])
        
        self.server_task = self.loop.create_task(self.start_server())

    @with_loud_coroutine_exception
    async def homepage(self, request):
        return JSONResponse(self.name)

    @with_loud_coroutine_exception
    async def pubsub(self, request):
        req = await request.body()
        sub = await self.nc.subscribe('Telemetry.AOS.VCID.1.TaggedPacket.>')
        async for msg in sub.messages:
            d = pickle.loads(msg.data)
            return JSONResponse(d)

    @with_loud_coroutine_exception
    async def ws_telemetry(self, websocket):
        try:
            await websocket.accept()
            if websocket.query_params.get('filter', {}):
                subscriptions = await websocket.receive_json()
            else:
                subscriptions = ait.core.tlm.getDefaultDict()
            sub = await self.nc.subscribe(self.telemetry_stream_pattern)
            async for msg in sub.messages:
                d = pickle.loads(msg.data)
                if d['packet_name'] in subscriptions:
                    await websocket.send_json(d)
        except WebSocketDisconnect:
            pass

    @with_loud_coroutine_exception
    async def tlm_dict(self, request):
        d = ait.core.tlm.getDefaultDict().toJSON()
        return JSONResponse(d)

    @with_loud_coroutine_exception
    async def cmd_dict(self, request):
        d = ait.core.cmd.getDefaultDict().toJSON()
        return JSONResponse(d)

    @with_loud_coroutine_exception
    async def dict(self, request):
        dict_type = request.path_params['dict_type']
        if dict_type == 'tlm':
            return await self.tlm_dict(request)
        elif dict_type == 'cmd':
            return await self.cmd_dict(request)
        else:
            return JSONResponse(f"{dict_type} is not <tlm|cmd>")

    @with_loud_coroutine_exception
    async def ws_command_loader(self, websocket):
        try:
            await websocket.accept()
            while True:
                req = await websocket.receive_json()
                cl_request = req['directive']
                payload = " ".join(req['payload'])
                directive = f'{cl_request}'
                data = await self.request(directive, payload)
                await websocket.send_json(data)
        except WebSocketDisconnect:
            pass
        
    @with_loud_coroutine_exception
    async def config_request(self, request):
        k = request.query_params.get('config_key', None)
        d = await self.request('Reconfiguration_Service.Request', k)
        return JSONResponse(d)

    @with_loud_coroutine_exception
    async def ws_variable_messages(self, websocket):
        try:
            await websocket.accept()
            while True:
                sub = await self.nc.subscribe('Bifrost.Messages.>')
                async for msg in sub.messages:
                    d = pickle.loads(msg.data)
                    m = {'subject': msg.subject,
                         'message': d}
                    await websocket.send_json(m)
        except WebSocketDisconnect:
            pass
        except TypeError:
            print(f'{m} is not JSONable')

    @with_loud_coroutine_exception
    async def ws_monitors(self, websocket):
        try:
            await websocket.accept()
            while True:
                sub = await self.nc.subscribe('Bifrost.Monitors.>')
                async for msg in sub.messages:
                    d = pickle.loads(msg.data)
                    m = {'subject': msg.subject,
                         'message': d}
                    await websocket.send_json(m)
        except WebSocketDisconnect:
            pass
        except TypeError:
            print(f'{m} is not JSONable')

    @with_loud_coroutine_exception
    async def sle_raf_directive(self, request):
        directive = request.path_params['directive'].capitalize()
        directive = f'Bifrost.Directive.SLE.RAF.{directive}'
        await self.publish(directive, None)
        return JSONResponse(f"OK, {directive}")

    @with_loud_coroutine_exception
    async def sle_cltu_directive(self, request):
        directive = request.path_params['directive'].capitalize()
        directive = f'Bifrost.Directive.SLE.CLTU.{directive}'
        await self.publish(directive, None)
        return JSONResponse(f"OK, {directive}")

    @with_loud_coroutine_exception
    async def ws_downlink_updates(self, websocket):
        try:
            await websocket.accept()
            while True:
                sub = await self.nc.subscribe(self.downlink_update_pattern)
                async for msg in sub.messages:
                    d = pickle.loads(msg.data)
                    m = {'subject': msg.subject,
                         'message': d}
                    await websocket.send_json(m)
        except WebSocketDisconnect:
            pass
        except TypeError:
            print(f'{m} is not JSONable')
