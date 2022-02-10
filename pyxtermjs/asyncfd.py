import asyncio
import os


async def async_read(fd: int, n: int = 1024):
    loop = asyncio.get_running_loop()
    fut = loop.create_future()

    def __check_for_read():
        try:
            r = os.read(fd, n)
        except Exception as e:
            loop.remove_reader(fd)
            fut.set_exception(e)
        else:
            loop.remove_reader(fd)
            fut.set_result(r)

    loop.add_reader(fd, __check_for_read)
    return await fut


async def async_write(fd: int, data: bytes):
    loop = asyncio.get_running_loop()
    fut = loop.create_future()

    def __check_for_write():
        try:
            r = os.write(fd, data)
        except Exception as e:
            loop.remove_writer(fd)
            fut.set_exception(e)
        else:
            loop.remove_writer(fd)
            fut.set_result(r)

    loop.add_writer(fd, __check_for_write)
    return await fut


async def async_write_fully(fd: int, data: bytes):
    ret = 0
    while data:
        n = await async_write(fd, data)
        ret += n
        data = data[n:]
    return ret
