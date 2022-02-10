import argparse
import logging
import sys
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from importlib_metadata import version
import uvicorn
from pyxtermjs import __version__
from pyxtermjs import XtermjsRouter

def main():
    parser = argparse.ArgumentParser(
        description=(
            "A fully functional terminal in your browser. "
            "https://github.com/paulo-raca/pyxtermjs"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--port", default=8080, help="port to run server on")
    parser.add_argument("--host", default="127.0.0.1", help="host to run server on (use 0.0.0.0 to allow access from other hosts)")
    parser.add_argument("--debug", action="store_true", help="debug the server")
    parser.add_argument("--version", action="version", version=f'{__version__}', help="print version and exit")
    parser.add_argument("cmd", metavar='CMD', nargs='?', default="bash", help="Default command to run in the terminal")
    parser.add_argument("args", metavar='ARGS', nargs='*', help="Command arguments")
    args = parser.parse_args()

    # setup logging
    green = "\033[92m"
    end = "\033[0m"
    log_format = green + "pyxtermjs > " + end + "%(levelname)s (%(funcName)s:%(lineno)s) %(message)s"
    logging.basicConfig(
        format=log_format,
        stream=sys.stdout,
        level=logging.DEBUG if args.debug else logging.INFO,
    )

    # Decided the command to execute based on `cmd` query string, defaults to the cmd provided in the 
    def fastapi_cmd(cmd: str = None):
        ret = cmd or [args.cmd] + args.args
        return ret

    # Launch fastapp
    app = FastAPI()

    @app.get("/")
    def redirect_root():
        # XtermjsRouter cannot be mounter at the root directory, so we add a redirection instead
        return RedirectResponse("/xterm")

    app.include_router(XtermjsRouter(fastapi_cmd), prefix="/xterm")

    logging.info(f"serving on http://{args.host}:{args.port}/")
    uvicorn.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()
