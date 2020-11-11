import httpx
import logging
import warnings
from tortoise import Tortoise, run_async
from typing import List
from starlette.config import Config

from bnstats.routine import (
    update_nomination_db,
    update_users_db,
    update_maps_db,
    update_user_details,
)
from bnstats.score import get_system
from bnstats.bnsite import request
from bnstats.models import User

config = Config(".env")
DB_URL = config("DB_URL")
SITE_SESSION = config("BNSITE_SESSION")
API_KEY = config("API_KEY")
WEBHOOK_URL = config("WEBHOOK_URL", default="")

CALC_SYSTEM = get_system(config("CALC_SYSTEM"))()
print(f"> Using calculator: {CALC_SYSTEM.name}")

logger = logging.getLogger("bnstats")
logger.setLevel(logging.DEBUG)


def send_webhook(msg):
    if not WEBHOOK_URL:
        return
    hook = {"embeds": [{"title": "BNStats Populator", "description": msg}]}
    httpx.post(WEBHOOK_URL, json=hook)


async def run_calculate():
    await Tortoise.init(db_url=DB_URL, modules={"models": ["bnstats.models"]})
    await Tortoise.generate_schemas()

    users = await User.get_users()
    c = len(users)
    for i, u in enumerate(users):
        print(f">>> Calculating score for user: {u.username} ({i+1}/{c})")
        await CALC_SYSTEM.calculate_user(u)


async def run(days):
    send_webhook("Population starts.")
    try:
        request.setup_session(SITE_SESSION, API_KEY)
        await Tortoise.init(db_url=DB_URL, modules={"models": ["bnstats.models"]})
        await Tortoise.generate_schemas()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            print("> Populating users...")
            users: List[User] = await update_users_db()

            c = len(users)
            for i, u in enumerate(users):
                print(f">> Populating data for user: {u.username} ({i+1}/{c})")
                nominations = await update_nomination_db(u, days)

                print(f">>> Populating maps for user: {u.username}")
                c_maps = len(nominations)
                for i, nom in enumerate(nominations):
                    print(f">>> Fetching: {nom.beatmapsetId} ({i+1}/{c_maps})")
                    await update_maps_db(nom)

                user_maps = []
                all_noms = await u.get_nomination_activity()
                for nom in all_noms:
                    m = await nom.get_map()
                    user_maps.append(m)

                if user_maps:
                    print(f">>> Updating details for user: {u.username}")
                    await update_user_details(u, user_maps)

                print(f">>> Calculating score for user: {u.username}")
                await CALC_SYSTEM.calculate_user(u)

            if len(w):
                e_msg = "\r\n".join(list(map(lambda x: str(x.message), w)))
                send_webhook(f"Warnings: \r\n```\r\n{e_msg}```")
    except BaseException as e:
        send_webhook(f"An exception occured during population: \r\n```\r\n{str(e)}```")
        raise e

    await request.s.aclose()
    send_webhook("Population ends.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d", "--days", type=int, default=999, help="Number of days to fetch."
    )
    parser.add_argument(
        "--only-recalculate", help="Only recalculate users.", action="store_true"
    )

    args = parser.parse_args()
    if args.only_recalculate:
        run_async(run_calculate())
    else:
        run_async(run(args.days))
