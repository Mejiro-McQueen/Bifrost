from ait.core import log
import traceback
from colorama import Fore, Back, Style
import inspect


def with_loud_coroutine_exception(f):
    """
    Use this decorator to attempt to prevent coroutines and functions from silently failing
    """ 
    async def loud_async_exception_(*args, **kw):
        try:
            r = await f(*args, **kw)
            return r
        except Exception as e:
            self = args[0]
            log.error(f"{Back.RED}Got exception {e} running {self} {Back.RESET}")
            traceback.print_exc()
            # if coroutine:
            #     await self.publish(f'Bifrost.Messages.Errors.Panic', e) # Causes Exceptions elsewhere
            s = inspect.currentframe().f_back.f_code
            log.error(f"Called from: {s}")
            raise e
    return loud_async_exception_


def with_loud_exception(f):
    """
    Use this decorator to attempt to prevent coroutines and functions from silently failing
    """ 
    def loud_exception_(*args, **kw):
        try:
            r = f(*args, **kw)
            return r
        except Exception as e:
            self = args[0]
            log.error(f"{Back.RED}Got exception {e} running {self} {Back.RESET}")
            traceback.print_exc()
            s = inspect.currentframe().f_back.f_code
            log.error(f"Called from: {s}")
    return loud_exception_

