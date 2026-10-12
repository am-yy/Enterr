from datetime import timedelta, datetime, timezone
from typing import Optional
from pydantic import BaseModel, field_validator
from dataAccess.database.database import Website
from utils.utils import to_utc_time
from endpoints.decorators.request_validator import (
    GetRequestBaseModel,
    PostRequestBaseModel,
)
from endpoints.models.action_interval_model import (
    AddActionInterval,
    GetActionInterval,
    EditActionInterval,
)
from utils.totp import is_valid_secret, normalize_secret
from utils.utils import timedelta_to_parts


def _validate_totp_secret(value: Optional[str]) -> Optional[str]:
    if not value or not value.strip():
        return None
    if not is_valid_secret(value):
        raise ValueError("totp_secret must be a base32 secret or otpauth:// URI")
    return normalize_secret(value)


class DateTime(BaseModel):
    day: Optional[int] = None
    month: Optional[int] = None
    year: Optional[int] = None
    hour: Optional[int] = None
    minute: Optional[int] = None

    @staticmethod
    def from_datetime(dt: datetime) -> "DateTime":
        return DateTime(
            day=dt.day, month=dt.month, year=dt.year, hour=dt.hour, minute=dt.minute
        )


class AddWebsite(PostRequestBaseModel):
    url: str
    success_url: str
    name: str
    username: str
    password: str
    take_screenshot: bool
    paused: Optional[bool] = None
    expiration_interval_minutes: Optional[int] = None
    custom_login_script: Optional[str] = None
    totp_secret: Optional[str] = None
    action_interval: AddActionInterval

    _check_totp_secret = field_validator("totp_secret")(_validate_totp_secret)

    def to_sql_model(self) -> Website:
        expiration_interval = None
        if self.expiration_interval_minutes is not None:
            expiration_interval = timedelta(minutes=self.expiration_interval_minutes)
        website = Website(
            url=self.url,
            success_url=self.success_url,
            name=self.name,
            username=self.username,
            password=self.password,
            custom_login_script=self.custom_login_script,
            totp_secret=self.totp_secret,
            take_screenshot=self.take_screenshot,
            paused=self.paused if self.paused is not None else False,
            added_at=datetime.now(timezone.utc),
            expiration_interval=expiration_interval,
        )

        website.action_interval = self.action_interval.to_sql_model()
        return website


class EditWebsite(BaseModel):
    url: Optional[str] = None
    success_url: Optional[str] = None
    name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    take_screenshot: Optional[bool] = None
    paused: Optional[bool] = None
    expiration_interval_minutes: Optional[int] = None
    custom_login_script: Optional[str] = None
    totp_secret: Optional[str] = None
    action_interval: Optional[EditActionInterval] = None

    _check_totp_secret = field_validator("totp_secret")(_validate_totp_secret)

    def edit_existing_model(self, existing_website: Website) -> Website:
        if self.url is not None:
            existing_website.url = self.url
        if self.success_url is not None:
            existing_website.success_url = self.success_url
        if self.name is not None:
            existing_website.name = self.name
        if self.username is not None:
            existing_website.username = self.username
        if self.password is not None:
            existing_website.password = self.password
        if self.take_screenshot is not None:
            existing_website.take_screenshot = self.take_screenshot
        if self.paused is not None:
            existing_website.paused = self.paused
        # These three can be cleared with an explicit null, so only touch them when the
        # request contains them (pause/resume sends just {"paused": ...}).
        if "expiration_interval_minutes" in self.model_fields_set:
            existing_website.expiration_interval = (
                None
                if self.expiration_interval_minutes is None
                else timedelta(minutes=self.expiration_interval_minutes)
            )
        if "custom_login_script" in self.model_fields_set:
            existing_website.custom_login_script = self.custom_login_script
        if "totp_secret" in self.model_fields_set:
            existing_website.totp_secret = self.totp_secret
        if self.action_interval is not None:
            existing_website.action_interval = self.action_interval.edit_existing_model(
                existing_website.action_interval
            )

        if existing_website.paused:
            existing_website.next_schedule = None
        else:
            existing_website.next_schedule = (
                existing_website.action_interval.get_random_action_datetime()
            )

        return existing_website


class GetWebsite(GetRequestBaseModel):
    id: int
    url: str
    success_url: str
    name: str
    username: str
    password: str
    take_screenshot: bool
    paused: bool
    expiration_interval_minutes: Optional[int] = None
    custom_login_script: Optional[str] = None
    totp_secret: Optional[str] = None
    action_interval: Optional[GetActionInterval] = None
    next_schedule: Optional[datetime] = None
    last_login_attempt: Optional[datetime] = None
    status: Optional[str] = None

    @staticmethod
    def from_sql_model(
        website: Website,
        last_login_attempt: datetime = None,
        status=None,
    ) -> "GetWebsite":
        if website.expiration_interval is None:
            expiration_interval_minutes = None
        else:
            expiration_interval_parts = timedelta_to_parts(website.expiration_interval)
            expiration_interval_minutes = (
                expiration_interval_parts.days * 24 * 60
                + expiration_interval_parts.hours * 60
                + expiration_interval_parts.minutes
            )

        return GetWebsite(
            id=website.id,
            url=website.url,
            success_url=website.success_url,
            name=website.name,
            username=website.username,
            password=website.password,
            take_screenshot=website.take_screenshot,
            paused=website.paused,
            expiration_interval_minutes=expiration_interval_minutes,
            custom_login_script=website.custom_login_script,
            totp_secret=website.totp_secret,
            action_interval=(
                GetActionInterval.from_sql_model(website.action_interval)
                if website.action_interval
                else None
            ),
            next_schedule=to_utc_time(website.next_schedule),
            last_login_attempt=to_utc_time(last_login_attempt),
            status=status.value if status else None,
        )


class CheckCustomLoginScript(BaseModel):
    script: str


class CheckCustomLoginScriptResponse(BaseModel):
    error: str | None
