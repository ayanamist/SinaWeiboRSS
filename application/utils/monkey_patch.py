from __future__ import absolute_import

import inspect
import logging


def patch_logging():
    def logger_wrap(func):
        def logger_log(*args, **kwargs):
            caller_frame = inspect.currentframe().f_back
            caller_name = caller_frame.f_globals["__package__"]
            logger = logging.getLogger(caller_name)
            getattr(logger, func.__name__)(*args, **kwargs)

        return logger_log

    # Replace all direct function callings to logger methods.
    for func_name in ("critical", "error", "exception", "warn", "warning", "info", "debug", "log"):
        setattr(logging, func_name, logger_wrap(getattr(logging, func_name)))

    # Mute noisy logging.
    logging.getLogger("requests").setLevel(logging.ERROR)
    logging.getLogger("oauthlib").setLevel(logging.ERROR)


def patch_all():
    patch_logging()

