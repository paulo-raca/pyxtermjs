import asyncio
from dataclasses import dataclass
from fcntl import ioctl
import logging
from typing import Tuple, Union
import os
import pty
import struct
import termios
import re
import fcntl

logger = logging.getLogger(__name__)

@dataclass
class WindowSize:
    row: int = 24
    col: int = 80
    xpixel: int = 0
    ypixel: int = 0

    @staticmethod
    def from_str(value: str) -> "WindowSize":
        try:
            return WindowSize(*[int(arg) for arg in re.findall(r'\S+', value)])
        except:
            logger.warn(f"Failed to parse window size: {repr(value)}, expected 'row col xpixel ypixel'")


def set_winsize(fd: int, winsize: WindowSize):
    winsize = struct.pack("HHHH", winsize.row, winsize.col, winsize.xpixel, winsize.ypixel)
    ioctl(fd, termios.TIOCSWINSZ, winsize)


async def create_session(cmd: Union[str, list[str]], winsize: WindowSize = None) -> Tuple[int, asyncio.subprocess.Process]:
    master_pty, slave_pty = pty.openpty()
    if winsize:
        set_winsize(master_pty, winsize)
    if isinstance(cmd, str):
        subprocess = await asyncio.create_subprocess_shell(cmd, stdin=slave_pty, stdout=slave_pty, stderr=slave_pty, start_new_session=True)
    else:
        subprocess = await asyncio.create_subprocess_exec(*cmd, stdin=slave_pty, stdout=slave_pty, stderr=slave_pty, start_new_session=True)
    os.close(slave_pty)
    flag = fcntl.fcntl(master_pty, fcntl.F_GETFD)
    fcntl.fcntl(master_pty, fcntl.F_SETFD, flag | os.O_NONBLOCK)

    return master_pty, subprocess
