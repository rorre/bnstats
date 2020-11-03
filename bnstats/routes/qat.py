from typing import Any, Awaitable, Callable, Dict, List

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Router
from starlette.config import Config

from bnstats.models import User, Nomination, Reset
from dateutil.parser import parse

router = Router()

conf = Config(".env")
DEFAULT_KEY = "absolutelyunsafekey"
DEBUG: bool = conf("DEBUG", cast=bool, default=False)
QAT_KEY: str = conf("QAT_KEY", default=DEFAULT_KEY)

if DEFAULT_KEY == QAT_KEY and not DEBUG:
    raise ValueError("Cannot use default key in non-debug mode.")


async def nomination_update(event: Dict[str, Any]) -> JSONResponse:
    db_event = await Nomination.get_or_none(
        beatmapsetId=event["beatmapsetId"],
        userId=event["userId"],
    )
    event["timestamp"] = parse(event["timestamp"], ignoretz=True)
    event["user"] = await User.get_or_none(osuId=event["userId"])

    if not db_event:
        db_event = await Nomination.create(**event)
    else:
        db_event.update_from_dict(event)
        await db_event.save()


async def reset_update(event: Dict[str, Any]) -> JSONResponse:
    event["timestamp"] = parse(event["timestamp"], ignoretz=True)
    db_event = await Reset.get_or_none(id=event["id"])
    if not db_event:
        db_event = await Reset.create(**event)
    else:
        db_event.update_from_dict(event)
        await db_event.save()


classes = {
    "nominate": nomination_update,
    "nomination_reset": reset_update,
    "disqualify": reset_update,
}


@router.route("/aiess", methods=["POST"])
async def new_entry(request: Request):
    if (
        "Authorization" not in request.headers
        or request.headers["Authorization"] != QAT_KEY
    ):
        return JSONResponse({"status": 401, "message": "Unauthorized."}, 401)

    req_data: List[Dict[str, Any]] = await request.json()

    for event in req_data:
        data_type: str = event["type"]
        if data_type not in classes.keys():
            return JSONResponse({"status": 400, "message": "Invalid type."}, 400)

        func: Callable[[Dict[str, Any]], Awaitable] = classes[data_type]
        try:
            await func(event)
        except:
            return JSONResponse(
                {"status": 500, "message": "An exception occured."}, 500
            )
    return JSONResponse({"status": 200, "message": "OK"})