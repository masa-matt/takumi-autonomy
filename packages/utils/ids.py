import uuid
from datetime import datetime


def generate_job_id() -> str:
    """Generate a unique job ID in the format: job-YYYYMMDD-XXXXXXXX."""
    date_str = datetime.utcnow().strftime("%Y%m%d")
    short_id = uuid.uuid4().hex[:8]
    return f"job-{date_str}-{short_id}"
