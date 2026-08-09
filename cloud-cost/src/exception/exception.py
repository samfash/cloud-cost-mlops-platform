#!/usr/bin/env python3
"""Project-wide exception type.

CustomException must be raised only from an active except block because
__init__ reads sys.exc_info() for file/line context:

    try:
        ...
    except Exception as e:
        raise CustomException(e, sys) from e

Do not raise CustomException("message", sys) at top level — that yields
AttributeError when no traceback is active.
"""
import sys


class CustomException(Exception):
    def __init__(self, error_message, error_details: sys):
        self.error_message = error_message
        _, _, exc_tb = error_details.exc_info()

        self.lineno = exc_tb.tb_lineno
        self.file_name = exc_tb.tb_frame.f_code.co_filename

    def __str__(self):
        return (
            "Error occured in python script name "
            f"[{self.file_name}] line number [{self.lineno}] "
            f"error message [{self.error_message!s}]"
        )
