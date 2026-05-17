"""
Helper functions for the v1 API layer (normalization, header extraction, etc.)
"""

import uuid
from datetime import datetime

from fastapi import Header

from service.context import APP_CTX


# pylint: disable=C0103
def common_headers(
    header_x_trace_id: str = Header(
        ...,
        alias="x-trace-id",
        description="Unique identifier for the request trace.",
        example=uuid.uuid4(),
    ),
    header_x_request_time: str = Header(
        ...,
        alias="x-request-time",
        description="Request timestamp in ISO 8601 format.",
        example=str(datetime.now(tz=APP_CTX.get_pytz_timezone()).isoformat()),
    ),
    header_x_source_id: str = Header(
        ...,
        alias="x-source-name",
        description="Name of the calling system.",
        example="telegram",
    ),
    header_x_user_id: str = Header(
        ...,
        alias="x-user-id",
        description="User ID",
        example=uuid.uuid4(),
    ),
) -> dict:
    return {
        "x-trace-id": header_x_trace_id,
        "x-request-time": header_x_request_time,
        "x-source-id": header_x_source_id,
        "x-user-id": header_x_user_id,
    }
