from pathlib import Path
from asyncio.subprocess import Process
from fastapi import APIRouter, Depends
from starlette.websockets import WebSocket
from starlette.responses import HTMLResponse, Response

from .asyncfd import async_read, async_write_fully
from .pty import WindowSize, set_winsize, create_session

import asyncio
import os
import logging
import json

from typing import Callable, Optional, Union

__version__ = "0.6.0.0"

logger = logging.getLogger(__name__)

class XtermjsRouter(APIRouter):
    def __init__(self, cmd: Union[str, list[str], Callable[[], Union[str, list[str]]]], **kwargs) -> None:
        # CMD may either be a string, a list [cmd, arg, arg, arg], or a FastAPI callback that can provide these
        self.cmd = cmd if callable(cmd) else lambda: cmd
        super().__init__(**kwargs)

        @self.get("")
        def get_endpoint() -> Response:
            path = Path(__file__).parent / "index.html"
            with open(path) as f:
                return HTMLResponse(f.read())

        @self.websocket("")
        async def websocket_endpoint(ws: WebSocket, winsize: Optional[str] = None, cmd = Depends(self.cmd)):
            print(cmd)
            await ws.accept()
            logger.info(f"Starting websocket shell for {cmd}")

            # Try to read terminal size from query arguments
            try:
                if winsize is not None:
                    winsize = WindowSize.from_str(winsize)
            except:
                logger.warn(f"Failed to parse window size")
                winsize = None
            finally:
                logger.info(f"Window Size: {winsize}")
            
            fd, subprocess = await create_session(cmd, winsize=winsize)
            task_pty2ws = asyncio.create_task(pty2ws(fd, ws, subprocess), name="xterm.js:pty->ws")
            task_ws2pty = asyncio.create_task(ws2pty(ws, fd, subprocess), name="xterm.js:ws->pty")
            
            exitcode = await wait_subprocess(subprocess)
            logger.info(f"Subprocess completed: {exitcode}")

            try:
                await ws.send_json({"exitcode": exitcode})
            except:
                pass

            task_pty2ws.cancel()
            task_ws2pty.cancel()
            await asyncio.wait([task_pty2ws, task_ws2pty])
            os.close(fd)
            logger.info(f"Websocket shell session completed for {cmd}")

# Transfer shell process output to Websocket
async def pty2ws(fd: int, ws: WebSocket, subprocess: Process):
    try:
        while True:
            data = await async_read(fd)
            if not data:
                break
            await asyncio.shield(ws.send_bytes(data))
    except asyncio.CancelledError:
        # Try to flush whatever data hasn't been read from the buffer
        while True:
            try:
                data = os.read(fd, 1024)
                if not data:
                    break
                await asyncio.shield(ws.send_bytes(data))
            except:
                break
    except:
        pass


# Transfer Websocket input to shell process
async def ws2pty(ws: WebSocket, fd: int, subprocess: Process):
    try:
        while True:
            data = await ws.receive()
            print(repr(data))
            if data.get("bytes") is not None: 
                # Raw terminal data
                await async_write_fully(fd, data["bytes"])
            if data.get("text") is not None:
                # JSON-encoded control message
                data = json.loads(data["text"])                       
                if "resize" in data:
                    try:
                        set_winsize(fd, WindowSize(**data["resize"]))
                    except:
                        logger.warning("Failed to set window size", exc_info=True)
    except:
        pass
    finally:
        logger.warn('Lost connection to websocket, killing subprocess')
        try:
            await kill_subprocess(subprocess)
        except:
            logger.exception("kill_subprocess failed")


async def kill_subprocess(subprocess: Process, kill_timeout=5):
    # Send a SIGTERM and wait a bit
    try:
        subprocess.terminate()
    except ProcessLookupError:
        # logger.warning("Cannot send SIGTERM: ProcessLookupError")
        return

    if await wait_subprocess(subprocess, kill_timeout):
        return

    # Send a KILL
    try:
        logger.warning("Sending KILL")
        subprocess.kill()
    except ProcessLookupError:
        # logger.warning("Cannot send SIGKILL: ProcessLookupError")
        return


async def wait_subprocess(subprocess: Process, timeout: Optional[float] = None) -> Optional[int]:
    try:
        return await asyncio.wait_for(subprocess.wait(), timeout=timeout) or subprocess.returncode or -1
    except asyncio.TimeoutError:
        return None
