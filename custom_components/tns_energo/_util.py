import datetime
import re
from datetime import timedelta
from typing import Any, Callable, Coroutine, Optional, TypeVar, Union

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import EntityPlatform

from .const import DOMAIN
from tns_energo_api import TNSEnergoAPI
from tns_energo_api.exceptions import EmptyResultException, TNSEnergoException


def _make_log_prefix(
    config_entry: Union[Any, ConfigEntry], domain: Union[Any, EntityPlatform], *args
):
    join_args = [
        (
            config_entry.entry_id[-6:]
            if isinstance(config_entry, ConfigEntry)
            else str(config_entry)
        ),
        (domain.domain if isinstance(domain, EntityPlatform) else str(domain)),
    ]
    if args:
        join_args.extend(map(str, args))

    return "[" + "][".join(join_args) + "] "


@callback
def _find_existing_entry(
    hass: HomeAssistant, username: str
) -> Optional[config_entries.ConfigEntry]:
    existing_entries = hass.config_entries.async_entries(DOMAIN)
    for config_entry in existing_entries:
        if config_entry.data[CONF_USERNAME] == username:
            return config_entry


_RE_USERNAME_MASK = re.compile(r"^(\W*)(.).*(.)$")


def mask_username(username: str):
    parts = username.split("@")
    return "@".join(map(lambda x: _RE_USERNAME_MASK.sub(r"\1\2***\3", x), parts))


LOCAL_TIMEZONE = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo

# Kaliningrad is excluded as it is not supported
IS_IN_RUSSIA = (
    timedelta(hours=3) <= LOCAL_TIMEZONE.utcoffset(None) <= timedelta(hours=12)
)


_T = TypeVar("_T")
_RT = TypeVar("_RT")


async def with_auto_auth(
    api: "TNSEnergoAPI",
    async_getter: Callable[..., Coroutine[Any, Any, _RT]],
    *args,
    **kwargs,
) -> _RT:
    try:
        return await async_getter(*args, **kwargs)
    except EmptyResultException:
        # Attempt once more
        return await async_getter(*args, **kwargs)
    except TNSEnergoException:
        await api.async_authenticate()
        return await async_getter(*args, **kwargs)
