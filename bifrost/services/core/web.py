from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosed
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from bifrost.common.loud_exception import with_loud_coroutine_exception, with_loud_exception

from bifrost.common.service import Service
import uvicorn
import msgpack
import ait.core.tlm
import ait.core.cmd
import ait.core.log as log
from colorama import Fore


class Web_Server(Service):
    @with_loud_exception
    def __init__(self):
        super().__init__()
        self.index = './gjallarhorn/simple_web_prototype/'
        self.start()

    @with_loud_coroutine_exception
    async def start_server(self):
        config = uvicorn.Config(self.app, port=8000, host='bifrost', log_level="error")
        server = uvicorn.Server(config)
        log.info(f"{Fore.CYAN}Bifrost Web Service Now serving on {config.host}:{config.port}{Fore.RESET}")
        await server.serve()

    @with_loud_coroutine_exception
    async def reconfigure(self, topic, message, reply):
        await super().reconfigure(topic, message, reply)
        self.middleware = [Middleware(CORSMiddleware, allow_origins=['*'])] # Don't do this!
        self.app = Starlette(debug=True,
                             routes=[
                                 WebSocketRoute("/telemetry", endpoint=self.ws_telemetry),
                                 WebSocketRoute("/command_loader", endpoint=self.ws_command_loader),
                                 WebSocketRoute('/variable_messages', endpoint=self.ws_variable_messages),
                                 WebSocketRoute('/monitors', endpoint=self.ws_monitors),
                                 WebSocketRoute('/downlink_updates', endpoint=self.ws_downlink_updates),
                                 WebSocketRoute('/subscribe', endpoint=self.ws_subscribe),
                                 WebSocketRoute("/service_directive", self.ws_service_directive),
                                 Route("/dict/{dict_type:str}", self.dict),
                                 Route("/sle/raf/{directive:str}", self.sle_raf_directive),
                                 Route("/sle/cltu/{directive:str}", self.sle_cltu_directive),
                                 Route("/config", self.config_request),
                                 Route("/status", self.status),
                                 Mount('/', app=StaticFiles(directory=self.index, html=True), name='static'),
                             ],
                             middleware=self.middleware)
        self.server_task = self.loop.create_task(self.start_server())

    @with_loud_coroutine_exception
    async def status(self, request):
        return JSONResponse(self.name)

    @with_loud_coroutine_exception
    async def ws_subscribe(self, websocket):
        try:
            await websocket.accept()
            while True:
                req = await websocket.receive_json()
                topic_request = req['topic']
                sub = await self.nc.subscribe(topic_request)
                async for msg in sub.messages:
                    d = msgpack.unpackb(msg.data)
                    m = {'subject': msg.subject,
                         'message': d}
                    await websocket.send_json(m)
        except WebSocketDisconnect:
            pass
        except TypeError:
            print(f'{m} is not JSONable')
        except ConnectionClosed:
            log.info("Websocket Connection closed.")
        except Exception as e:
            log.error(e)

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
                d = msgpack.unpackb(msg.data)
                if d['packet_name'] in subscriptions:
                    await websocket.send_json(d)
        except WebSocketDisconnect:
            pass
        except ConnectionClosed:
            log.info("Websocket Connection closed.")
        except Exception as e:
            log.error(e)

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
                topic = req['topic']
                message = req['message']
                data = await self.request(topic, message)
                m = {'topic': 'Command_Loader.Receipt',
                     'message': data}
                await websocket.send_json(m)
        except WebSocketDisconnect:
            pass
        except ConnectionClosed:
            log.info("Websocket Connection closed.")
        except Exception as e:
            log.error(e)

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
                    d = msgpack.unpackb(msg.data)
                    m = {'topic': msg.subject,
                         'message': d}
                    await websocket.send_json(m)
        except WebSocketDisconnect:
            pass
        except TypeError:
            print(f'{m} is not JSONable')
        except ConnectionClosed:
            log.info("Websocket Connection closed.")
        except Exception as e:
            log.error(e)

    @with_loud_coroutine_exception
    async def ws_monitors(self, websocket):
        try:
            await websocket.accept()
            while True:
                sub = await self.nc.subscribe('Bifrost.Monitors.>')
                async for msg in sub.messages:
                    d = msgpack.unpackb(msg.data)
                    m = {'topic': msg.subject,
                         'message': d}
                    await websocket.send_json(m)
        except WebSocketDisconnect:
            pass
        except TypeError:
            print(f'{m} is not JSONable')
        except ConnectionClosed:
            log.info("Websocket Connection closed.")
        except Exception as e:
            log.error(e)

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
    async def ws_service_directive(self, websocket):
        try:
            await websocket.accept()
            m = await websocket.receive_json()
            directive = m['topic']
            message = m['message']
            data = await self.request(directive, message)
            d = {'topic': f'{directive}.Receipt',
                 'message': data}
            await websocket.send_json(d)
        except WebSocketDisconnect:
            pass

    @with_loud_coroutine_exception
    async def ws_downlink_updates(self, websocket):
        try:
            await websocket.accept()
            while True:
                sub = await self.nc.subscribe(self.downlink_update_pattern)
                async for msg in sub.messages:
                    d = msgpack.unpackb(msg.data)
                    m = {'topic': msg.subject,
                         'message': d}
                    await websocket.send_json(m)
        except WebSocketDisconnect:
            pass
        except TypeError:
            print(f'{m} is not JSONable')


# TODO: This is all junk, rewrite in golang.
