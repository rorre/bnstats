import binascii
import os
import time

MODES = {"osu": 0, "taiko": 1, "catch": 2, "mania": 3}


def format_time(total: int) -> str:
    minutes = total // 60
    seconds = total % 60
    if seconds < 10:
        seconds = f"0{seconds}"  # type: ignore
    return f"{minutes}:{seconds}"


# https://github.com/mxr/random-object-id/blob/master/random_object_id.py#L9-L12
def generate_mongo_id() -> str:
    timestamp = "{:x}".format(int(time.time()))
    rest = binascii.b2a_hex(os.urandom(8)).decode("ascii")
    return timestamp + rest


def mode_to_db(mode_str: str) -> int:
    return MODES[mode_str]
