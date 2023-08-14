import time

import schedule
from loguru import logger

from utils.config import config
from utils.teams import Teams

EMAIL = config.get("ALWAYSGREEN_EMAIL", False)
PASSWORD = config.get("ALWAYSGREEN_PASSWORD", False)


def set_teams_activity():
    teams = Teams(email=EMAIL, password=PASSWORD)
    set_activity = teams.set_activity(activity="Available", availability="Available")
    logger.info("Activity updated.")


logger.add("app.log", rotation="1 day")

set_teams_activity()
schedule.every(90).seconds.do(set_teams_activity)

while True:
    schedule.run_pending()
    time.sleep(1)
