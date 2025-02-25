"""TNS Energo integration config and option flow handlers"""

import asyncio
import logging
from collections import OrderedDict
from datetime import timedelta
from typing import (
    Any,
    ClassVar,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    TYPE_CHECKING,
)

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import (
    CONF_DEFAULT,
    CONF_ENTITIES,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ACCOUNTS,
    CONF_LAST_INVOICE,
    CONF_METERS,
    CONF_NAME_FORMAT,
    DATA_API_OBJECTS,
    DATA_ENTITIES,
    DOMAIN,
)
from tns_energo_api import Account, TNSEnergoAPI, Meter
from tns_energo_api.exceptions import TNSEnergoException

if TYPE_CHECKING:
    from ._base import TNSEnergoEntity

_LOGGER = logging.getLogger(__name__)

CONF_DISABLE_ENTITIES = "disable_entities"


def _flatten(conf: Any):
    if isinstance(conf, timedelta):
        return conf.total_seconds()
    if isinstance(conf, Mapping):
        return dict(zip(conf.keys(), map(_flatten, conf.values())))
    if isinstance(conf, (list, tuple)):
        return list(map(_flatten, conf))
    return conf


class TNSEnergoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TNS Energo config entries."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    CACHED_API_TYPE_NAMES: ClassVar[Optional[Dict[str, Any]]] = {}

    def __init__(self):
        """Instantiate config flow."""
        self._current_type = None
        self._current_config: Optional[ConfigType] = None
        self._devices_info = None
        self._accounts: Optional[Mapping[int, "Account"]] = None

        self.schema_user = None

    async def _check_entry_exists(self, username: str):
        current_entries = self._async_current_entries()

        for config_entry in current_entries:
            if config_entry.data[CONF_USERNAME] == username:
                return True

        return False

    # Initial step for user interaction
    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow start."""
        if self.schema_user is None:
            schema_user = OrderedDict()
            schema_user[vol.Required(CONF_USERNAME)] = str
            schema_user[vol.Required(CONF_PASSWORD)] = str
            self.schema_user = vol.Schema(schema_user)

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=self.schema_user)

        username = user_input[CONF_USERNAME]

        if await self._check_entry_exists(username):
            return self.async_abort(reason="already_configured_service")

        async with TNSEnergoAPI(
            username=username,
            password=user_input[CONF_PASSWORD],
        ) as api:
            try:
                await api.async_authenticate()

            except TNSEnergoException as e:
                _LOGGER.error(f"Authentication error: {repr(e)}")
                return self.async_show_form(
                    step_id="user",
                    data_schema=self.schema_user,
                    errors={"base": "authentication_error"},
                )

            try:
                self._accounts = await api.async_get_accounts_list()

            except TNSEnergoException as e:
                _LOGGER.error(f"Request error: {repr(e)}")
                return self.async_show_form(
                    step_id="user",
                    data_schema=self.schema_user,
                    errors={"base": "update_accounts_error"},
                )

        self._current_config = user_input

        return await self.async_step_select()

    async def async_step_select(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        accounts, current_config = self._accounts, self._current_config
        if user_input is None:
            if accounts is None or current_config is None:
                return await self.async_step_user()

            return self.async_show_form(
                step_id="select",
                data_schema=vol.Schema(
                    {
                        vol.Optional(CONF_ACCOUNTS): cv.multi_select(
                            {account.code: account.code for account in self._accounts}
                        )
                    }
                ),
            )

        if user_input.get(CONF_ACCOUNTS):
            current_config[CONF_DEFAULT] = False
            current_config[CONF_ACCOUNTS] = dict.fromkeys(
                user_input[CONF_ACCOUNTS], True
            )

        return self.async_create_entry(
            title=current_config[CONF_USERNAME],
            data=_flatten(current_config),
        )

    async def async_step_import(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        _LOGGER.debug("Executing import step: %s", user_input)

        if user_input is None:
            return self.async_abort(reason="unknown_error")

        username = user_input[CONF_USERNAME]

        if await self._check_entry_exists(username):
            return self.async_abort(reason="already_exists")

        return self.async_create_entry(
            title=username,
            data={CONF_USERNAME: username},
        )


CONF_DISABLE_ACCOUNTS = "disable_" + CONF_ACCOUNTS
CONF_DISABLE_METERS = "disable_" + CONF_METERS
CONF_DISABLE_INVOICES = "disable_" + CONF_LAST_INVOICE
CONF_USE_TEXT_FIELDS = "use_text_fields"


class TNSEnergoOptionsFlow(OptionsFlow):
    """Handler for TNS Energo options"""

    def __init__(self, config_entry: ConfigEntry):
        self.config_entry = config_entry
        self.use_text_fields = False
        self.config_codes: Optional[Dict[str, List[str]]] = None

    async def async_fetch_config_codes(self):
        api: "TNSEnergoAPI" = self.hass.data[DATA_API_OBJECTS][
            self.config_entry.entry_id
        ]
        accounts = await api.async_get_accounts_list()
        account_codes = {
            account.code for account in accounts.values() if account.code is not None
        }

        aws = (account.async_get_meters() for account in accounts)

        meters_maps: Iterable[Mapping[str, "Meter"]] = await asyncio.gather(*aws)
        meter_codes = set()

        for meters_map in meters_maps:
            meter_codes.update(
                [meter.code for meter in meters_map.values() if meter.code is not None]
            )

        return {
            CONF_ACCOUNTS: sorted(account_codes),
            CONF_LAST_INVOICE: sorted(account_codes),
            CONF_METERS: sorted(meter_codes),
        }

    async def async_get_options_multiselect(self, config_key: str) -> Dict[str, str]:
        if self.config_codes is None:
            try:
                self.config_codes = await self.async_fetch_config_codes()
                config_codes = self.config_codes
            except TNSEnergoException:
                self.use_text_fields = True
                config_codes = {}

        else:
            config_codes = self.config_codes

        options = OrderedDict()

        entities: List["TNSEnergoEntity"] = (
            self.hass.data.get(DATA_ENTITIES, {})
            .get(self.config_entry.entry_id, {})
            .get(config_key, [])
        )

        for code in sorted(config_codes.get(config_key, [])):
            text = code

            for entity in entities:
                if entity.code == code:
                    text += " (" + entity.entity_id + ")"
                    break

            options[code] = text

        return options

    async def async_generate_schema_dict(
        self, user_input: Optional[ConfigType] = None
    ) -> OrderedDict:
        user_input = user_input or {}

        schema_dict = OrderedDict()

        all_cfg = {**self.config_entry.data}

        if self.config_entry.options:
            all_cfg.update(self.config_entry.options)

        # Entity filtering
        # try:
        #     option_entities = ENTITY_CONF_VALIDATORS[CONF_ENTITIES](all_cfg.get(CONF_ENTITIES, {}))
        # except vol.Invalid:
        #     option_entities = ENTITY_CONF_VALIDATORS[CONF_ENTITIES]({})
        # @todo включить валидатор
        option_entities = all_cfg.get(CONF_ENTITIES, {})

        async def _add_filter(config_key_: str):
            filter_key = CONF_ENTITIES + "_" + config_key_
            blacklist_key = filter_key + "_blacklist"

            default_value = vol.UNDEFINED
            blacklisted = True

            if filter_key in user_input:
                default_value = user_input[filter_key]

            else:
                options_value = option_entities.get(config_key_)

                if options_value:
                    blacklisted = options_value[CONF_DEFAULT]

                    default_value = [
                        key
                        for key, value in options_value.items()
                        if key != CONF_DEFAULT and value is not blacklisted
                    ]

            if self.use_text_fields:
                # Validate text for text fields
                validator = cv.string

                if default_value is not vol.UNDEFINED and isinstance(
                    default_value, list
                ):
                    default_value = ",".join(default_value)
            else:
                # Validate options for multi-select fields
                select_options = await self.async_get_options_multiselect(config_key_)

                if default_value is not vol.UNDEFINED:
                    if isinstance(default_value, str):
                        default_value = list(map(str.strip, default_value.split(",")))

                    for value in default_value:
                        if value not in select_options:
                            select_options[value] = value

                validator = cv.multi_select(select_options)

            schema_dict[vol.Optional(filter_key, default=default_value)] = validator
            schema_dict[vol.Optional(blacklist_key, default=blacklisted)] = cv.boolean

        # Scan intervals
        # try:
        #     option_scan_interval = ENTITY_CONF_VALIDATORS[CONF_SCAN_INTERVAL](
        #         all_cfg.get(CONF_SCAN_INTERVAL, {})
        #     )
        # except vol.Invalid:
        #     option_scan_interval = ENTITY_CONF_VALIDATORS[CONF_SCAN_INTERVAL]({})
        # @todo вернуть валидацию
        option_scan_interval = all_cfg.get(CONF_SCAN_INTERVAL, {})

        async def _add_scan_interval(config_key_: str):
            scan_interval_key = CONF_SCAN_INTERVAL + "_" + config_key_

            if scan_interval_key in user_input:
                default_value = user_input[scan_interval_key]

            else:
                default_value = option_scan_interval[config_key_][CONF_DEFAULT]

            if isinstance(default_value, timedelta):
                default_value = default_value.total_seconds()

            default_value = {
                "seconds": default_value % 60,
                "minutes": default_value % (60 * 60) // 60,
                "hours": default_value % (60 * 60 * 24) // (60 * 60),
            }

            schema_dict[vol.Optional(scan_interval_key, default=default_value)] = (
                cv.positive_time_period_dict
            )

        # Name formats
        # try:
        #     option_name_format = ENTITY_CONF_VALIDATORS[CONF_NAME_FORMAT](
        #         all_cfg.get(CONF_NAME_FORMAT, {})
        #     )
        # except vol.Invalid:
        #     option_name_format = ENTITY_CONF_VALIDATORS[CONF_NAME_FORMAT]({})
        # @todo вернуть валидацию
        option_name_format = all_cfg.get(CONF_NAME_FORMAT, {})

        async def _add_name_format(config_key_: str):
            name_format_key = CONF_NAME_FORMAT + "_" + config_key_
            name_format_value = user_input.get(name_format_key)

            if name_format_value is None:
                name_format_value = option_name_format[config_key_][CONF_DEFAULT]

            schema_dict[vol.Optional(name_format_key, default=name_format_value)] = (
                cv.string
            )

        # @todo вернуть валидацию
        # for config_key in ENTITY_CODES_VALIDATORS.keys():
        #     await _add_filter(config_key)
        #     await _add_scan_interval(config_key)
        #     await _add_name_format(config_key)
        await _add_filter(option_entities)
        await _add_scan_interval(option_scan_interval)
        await _add_name_format(option_name_format)

        schema_dict[
            vol.Optional(CONF_USE_TEXT_FIELDS, default=self.use_text_fields)
        ] = cv.boolean

        return schema_dict

    async def async_step_init(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        if self.config_entry.source == config_entries.SOURCE_IMPORT:
            return self.async_abort(reason="yaml_not_supported")

        errors = {}
        if user_input:
            use_text_fields = user_input.get(CONF_USE_TEXT_FIELDS, self.use_text_fields)
            if use_text_fields == self.use_text_fields:
                new_options = {}

                def _save_filter(config_key_: str):
                    filter_key = CONF_ENTITIES + "_" + config_key_
                    blacklist_key = filter_key + "_blacklist"

                    value = user_input.get(filter_key)

                    if value is None:
                        value = []
                    elif isinstance(value, str):
                        value = list(filter(bool, map(str.strip, value.split(","))))

                    if CONF_DEFAULT in value:
                        errors[filter_key] = "value_default_not_valid"
                        return

                    blacklisted = user_input[blacklist_key]

                    try:
                        # codes = list(map(validator, value))
                        # @todo добавить валидацию
                        codes = value

                    except vol.Invalid as e:
                        _LOGGER.error("Error parsing options: %s", e)
                        errors[config_key_] = "invalid_code_format"
                        return

                    else:
                        entities_options = new_options.setdefault(CONF_ENTITIES, {})
                        entities_options[config_key_] = dict.fromkeys(
                            codes, not blacklisted
                        )
                        entities_options[config_key_][CONF_DEFAULT] = blacklisted

                def _save_scan_interval(config_key_: str):
                    scan_interval_key = CONF_SCAN_INTERVAL + "_" + config_key_
                    scan_interval_value = user_input.get(scan_interval_key)

                    if scan_interval_value is not None:
                        scan_interval_options = new_options.setdefault(
                            CONF_SCAN_INTERVAL, {}
                        )
                        scan_interval_options[config_key_] = int(
                            scan_interval_value.total_seconds()
                        )

                def _save_name_format(config_key_: str):
                    name_format_key = CONF_NAME_FORMAT + "_" + config_key_
                    name_format_value = user_input.get(name_format_key)

                    if name_format_value is not None:
                        name_format_options = new_options.setdefault(
                            CONF_NAME_FORMAT, {}
                        )
                        name_format_options[config_key_] = str(
                            name_format_value
                        ).strip()

                # for config_key, validator in ENTITY_CODES_VALIDATORS.items():
                #     _save_filter(config_key)
                #     _save_scan_interval(config_key)
                #     _save_name_format(config_key)
                # @todo вернуть валидацию
                _save_filter(CONF_ENTITIES)
                _save_scan_interval(CONF_SCAN_INTERVAL)
                _save_name_format(CONF_NAME_FORMAT)

                if not errors:
                    _LOGGER.debug("Saving options: %s", new_options)
                    return self.async_create_entry(title="", data=new_options)

            else:
                self.use_text_fields = use_text_fields

        schema_dict = await self.async_generate_schema_dict(user_input)

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema_dict), errors=errors or None
        )
