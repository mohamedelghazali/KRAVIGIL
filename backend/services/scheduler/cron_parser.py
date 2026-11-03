from datetime import datetime
from typing import Optional
from croniter import croniter

class CronParser:
    @staticmethod
    def get_next_run(cron_expression: str, base_time: Optional[datetime] = None) -> datetime:
        base = base_time or datetime.utcnow()
        if not croniter.is_valid(cron_expression):
            raise ValueError(f"Invalid cron expression: {cron_expression}")
        return croniter(cron_expression, base).get_next(datetime)
