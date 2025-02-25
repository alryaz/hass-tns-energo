"""
Sensor for TNS Energo cabinet.
Retrieves indications regarding current state of accounts.
"""

import logging
import re
from abc import ABC
from datetime import datetime
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Final,
    Hashable,
    List,
    Mapping,
    Optional,
    Type,
    TypeVar,
    Union,
)

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OK,
    STATE_UNKNOWN,
)
from homeassistant.helpers.typing import ConfigType, StateType

from ._base import (
    SupportedServicesType,
    TNSEnergoEntity,
    make_common_async_setup_entry,
)
from ._encoders import (
    account_to_attrs,
    indication_to_attrs,
    meter_to_attrs,
    payment_to_attrs,
)
from ._util import with_auto_auth
from .const import (
    ATTR_ACCOUNT_CODE,
    ATTR_ADDRESS,
    ATTR_AMOUNT,
    ATTR_COMMENT,
    ATTR_END,
    ATTR_FULL_NAME,
    ATTR_IGNORE_INDICATIONS,
    ATTR_INCREMENTAL,
    ATTR_INDICATIONS,
    ATTR_LAST_INDICATIONS_DATE,
    ATTR_LIVING_AREA,
    ATTR_METER_CODE,
    ATTR_METER_MODEL,
    ATTR_PAID_AT,
    ATTR_RESULT,
    ATTR_SOURCE,
    ATTR_START,
    ATTR_SUCCESS,
    ATTR_SUM,
    ATTR_TOTAL_AREA,
    CONF_ACCOUNTS,
    CONF_LAST_PAYMENT,
    CONF_METERS,
    DOMAIN,
    FORMAT_VAR_ID,
    FORMAT_VAR_TYPE_EN,
    FORMAT_VAR_TYPE_RU,
)
from tns_energo_api import Account, Meter, Payment, process_start_end_arguments
from tns_energo_api.exceptions import TNSEnergoException

_LOGGER = logging.getLogger(__name__)

RE_HTML_TAGS = re.compile(r"<[^<]+?>")
RE_MULTI_SPACES = re.compile(r"\s{2,}")

INDICATIONS_MAPPING_SCHEMA = vol.Schema(
    {
        vol.Required(vol.Match(r"t\d+")): cv.positive_float,
    }
)

INDICATIONS_SEQUENCE_SCHEMA = vol.All(
    vol.Any(vol.All(cv.positive_float, cv.ensure_list), [cv.positive_float]),
    lambda x: dict(map(lambda y: ("t" + str(y[0]), y[1]), enumerate(x, start=1))),
)

CALCULATE_PUSH_INDICATIONS_SCHEMA = vol.All(
    cv.make_entity_service_schema(
        {
            vol.Required(ATTR_INDICATIONS): vol.Any(
                vol.All(
                    cv.string,
                    lambda x: list(map(str.strip, x.split(","))),
                    INDICATIONS_SEQUENCE_SCHEMA,
                ),
                INDICATIONS_MAPPING_SCHEMA,
                INDICATIONS_SEQUENCE_SCHEMA,
            ),
            vol.Optional(ATTR_IGNORE_INDICATIONS, default=False): cv.boolean,
            vol.Optional(ATTR_INCREMENTAL, default=False): cv.boolean,
            vol.Optional("notification"): lambda x: x,
        }
    ),
    cv.deprecated("notification"),
)

SERVICE_PUSH_INDICATIONS: Final = "push_indications"
SERVICE_PUSH_INDICATIONS_SCHEMA: Final = CALCULATE_PUSH_INDICATIONS_SCHEMA

SERVICE_CALCULATE_INDICATIONS: Final = "calculate_indications"
SERVICE_CALCULATE_INDICATIONS_SCHEMA: Final = CALCULATE_PUSH_INDICATIONS_SCHEMA

_SERVICE_SCHEMA_BASE_DATED: Final = {
    vol.Optional(ATTR_START, default=None): vol.Any(vol.Equal(None), cv.datetime),
    vol.Optional(ATTR_END, default=None): vol.Any(vol.Equal(None), cv.datetime),
}

SERVICE_SET_DESCRIPTION: Final = "set_description"
SERVICE_GET_PAYMENTS: Final = "get_payments"
SERVICE_GET_INDICATIONS: Final = "get_indications"

_TTNSEnergoEntity = TypeVar("_TTNSEnergoEntity", bound=TNSEnergoEntity)


def get_supported_features(
    from_services: SupportedServicesType, for_object: Any
) -> int:
    features = 0
    for type_feature, services in from_services.items():
        if type_feature is None:
            continue
        check_cls, feature = type_feature
        if isinstance(for_object, check_cls):
            features |= feature

    return features


ATTR_METER_CODES: Final = "meter_codes"


class TNSEnergoSensor(TNSEnergoEntity, SensorEntity, ABC):
    pass


class TNSEnergoAccount(TNSEnergoSensor):
    """The class for this sensor"""

    config_key: ClassVar[str] = CONF_ACCOUNTS

    _attr_unit_of_measurement = "руб."
    _attr_icon = "mdi:lightning-bolt-circle"
    _attr_device_class = DOMAIN + "_account"

    _supported_services: ClassVar[SupportedServicesType] = {
        None: {
            SERVICE_GET_PAYMENTS: _SERVICE_SCHEMA_BASE_DATED,
        },
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, *kwargs)

        self.entity_id: Optional[str] = "sensor." + self.entity_id_prefix + "_account"

    @property
    def code(self) -> str:
        return self._account.code

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor"""
        acc = self._account
        return f"{acc.api.__class__.__name__}_account_{acc.code}"

    @property
    def state(self) -> Union[float, str]:
        balance = self._account.balance
        if balance is None:
            return STATE_UNKNOWN
        if balance == 0.0:
            return 0.0
        return balance

    @property
    def sensor_related_attributes(self) -> Optional[Mapping[str, Any]]:
        account = self._account

        attributes = account_to_attrs(account)

        self._handle_dev_presentation(
            attributes,
            (),
            (
                ATTR_FULL_NAME,
                ATTR_ADDRESS,
                ATTR_LIVING_AREA,
                ATTR_TOTAL_AREA,
                ATTR_METER_MODEL,
                ATTR_METER_CODE,
            ),
        )

        return attributes

    @property
    def name_format_values(self) -> Mapping[str, Any]:
        """Return the name of the sensor"""
        account = self._account
        return {
            FORMAT_VAR_ID: str(account.code),
            FORMAT_VAR_TYPE_EN: "account",
            FORMAT_VAR_TYPE_RU: "лицевой счёт",
        }

    #################################################################################
    # Functional implementation of inherent class
    #################################################################################

    @classmethod
    async def async_refresh_accounts(
        cls,
        entities: Dict[Hashable, "TNSEnergoAccount"],
        account: "Account",
        config_entry: ConfigEntry,
        account_config: ConfigType,
        async_add_entities: Callable[[List["TNSEnergoAccount"], bool], Any],
    ) -> None:
        entity_key = account.code
        try:
            entity = entities[entity_key]
        except KeyError:
            entity = cls(account, account_config)
            entities[entity_key] = entity

            async_add_entities([entity], False)
        else:
            if entity.enabled:
                entity.async_schedule_update_ha_state(force_refresh=True)

    async def async_update_internal(self) -> None:
        account = self._account
        account_code = account.code
        accounts = await account.api.async_get_accounts_list(account_code)

        for account in accounts:
            if account.code == account_code:
                self._account = account
                break

        self.register_supported_services(account)

    #################################################################################
    # Services callbacks
    #################################################################################

    @property
    def supported_features(self) -> int:
        return get_supported_features(
            self._supported_services,
            self._account,
        )

    async def async_service_get_payments(self, **call_data):
        account = self._account

        _LOGGER.info(self.log_prefix + "Begin handling payments retrieval")

        dt_start: Optional["datetime"] = call_data[ATTR_START]
        dt_end: Optional["datetime"] = call_data[ATTR_END]

        dt_start, dt_end = process_start_end_arguments(dt_start, dt_end)
        results = []

        event_data = {
            ATTR_ENTITY_ID: self.entity_id,
            ATTR_ACCOUNT_CODE: account.code,
            ATTR_SUCCESS: False,
            ATTR_START: dt_start.isoformat(),
            ATTR_END: dt_end.isoformat(),
            ATTR_RESULT: results,
            ATTR_COMMENT: None,
            ATTR_SUM: 0.0,
        }

        try:
            payments = await with_auto_auth(
                account.api,
                account.async_get_payments,
                dt_start,
                dt_end,
            )

            for payment in payments:
                event_data[ATTR_SUM] += payment.amount
                results.append(payment_to_attrs(payment))

        except BaseException as e:
            event_data[ATTR_COMMENT] = "Unknown error: %r" % e
            _LOGGER.exception(event_data[ATTR_COMMENT])
            raise
        else:
            event_data[ATTR_SUCCESS] = True

        finally:
            _LOGGER.debug(
                self.log_prefix + "Payments retrieval event: " + str(event_data)
            )
            self.hass.bus.async_fire(
                event_type=DOMAIN + "_" + SERVICE_GET_PAYMENTS,
                event_data=event_data,
            )

            _LOGGER.info(self.log_prefix + "Finish handling payments retrieval")


class TNSEnergoMeter(TNSEnergoSensor):
    """The class for this sensor"""

    config_key: ClassVar[str] = CONF_METERS

    _attr_icon = "mdi:counter"
    _attr_device_class = DOMAIN + "_meter"

    _supported_services: ClassVar[SupportedServicesType] = {
        None: {
            SERVICE_PUSH_INDICATIONS: SERVICE_PUSH_INDICATIONS_SCHEMA,
            SERVICE_CALCULATE_INDICATIONS: SERVICE_PUSH_INDICATIONS_SCHEMA,
            SERVICE_GET_INDICATIONS: _SERVICE_SCHEMA_BASE_DATED,
        },
    }

    def __init__(self, *args, meter: "Meter", **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._meter = meter

        self.entity_id: Optional[str] = (
            "sensor." + self.entity_id_prefix + "_meter_" + meter.code
        )

    #################################################################################
    # Implementation base of inherent class
    #################################################################################

    @classmethod
    async def async_refresh_accounts(
        cls,
        entities: Dict[Hashable, Optional[_TTNSEnergoEntity]],
        account: "Account",
        config_entry: ConfigEntry,
        account_config: ConfigType,
        async_add_entities: Callable[[List[_TTNSEnergoEntity], bool], Any],
    ):
        new_meter_entities = []
        meters = await account.async_get_meters()

        for meter_code, meter in meters.items():
            entity_key = (account.code, meter_code)
            try:
                entity = entities[entity_key]
            except KeyError:
                entity = cls(
                    account,
                    account_config,
                    meter=meter,
                )
                entities[entity_key] = entity
                new_meter_entities.append(entity)
            else:
                if entity.enabled:
                    entity.async_schedule_update_ha_state(force_refresh=True)

        if new_meter_entities:
            async_add_entities(new_meter_entities, False)

    async def async_update_internal(self) -> None:
        meters = await self._account.async_get_meters()
        meter = meters.get(self._meter.code)

        if meter is None:
            self.hass.async_create_task(self.async_remove())
        else:
            self.register_supported_services(meter)
            self._meter = meter

    #################################################################################
    # Data-oriented implementation of inherent class
    #################################################################################

    @property
    def code(self) -> str:
        return self._meter.code

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor"""
        met = self._meter
        acc = met.account
        return f"{acc.api.__class__.__name__}_meter_{acc.code}_{met.code}"

    @property
    def state(self) -> str:
        return self._meter.status or STATE_OK

    @property
    def sensor_related_attributes(self) -> Optional[Mapping[str, Any]]:
        meter = self._meter

        attributes = meter_to_attrs(meter)

        self._handle_dev_presentation(
            attributes,
            (),
            (
                ATTR_METER_CODE,
                ATTR_LAST_INDICATIONS_DATE,
                *filter(lambda x: x.startswith("zone_"), attributes.keys()),
            ),
        )

        return attributes

    @property
    def name_format_values(self) -> Mapping[str, Any]:
        meter = self._meter
        return {
            FORMAT_VAR_ID: meter.code or "<unknown>",
            FORMAT_VAR_TYPE_EN: "meter",
            FORMAT_VAR_TYPE_RU: "счётчик",
        }

    #################################################################################
    # Additional functionality
    #################################################################################

    def _get_real_indications(
        self, call_data: Mapping
    ) -> Mapping[str, Union[int, float]]:
        indications: Mapping[str, Union[int, float]] = call_data[ATTR_INDICATIONS]
        meter_zones = self._meter.zones

        for zone_id, new_value in indications.items():
            if zone_id not in meter_zones:
                raise ValueError(f"meter zone {zone_id} does not exist")

        if call_data[ATTR_INCREMENTAL]:
            return {
                zone_id: ((meter_zones[zone_id].last_indication or 0) + new_value)
                for zone_id, new_value in indications.items()
            }

        return indications

    async def async_service_push_indications(self, **call_data):
        """
        Push indications entity service.
        :param call_data: Parameters for service call
        :return:
        """
        _LOGGER.info(self.log_prefix + "Begin handling indications submission")

        meter = self._meter

        if meter is None:
            raise Exception("Meter is unavailable")

        meter_code = meter.code

        event_data = {
            ATTR_ENTITY_ID: self.entity_id,
            ATTR_METER_CODE: meter_code,
            ATTR_SUCCESS: False,
            ATTR_INDICATIONS: None,
            ATTR_COMMENT: None,
        }

        try:
            indications = self._get_real_indications(call_data)

            event_data[ATTR_INDICATIONS] = indications

            await with_auto_auth(
                meter.account.api,
                meter.async_send_indications,
                **indications,
                ignore_values=call_data.get(ATTR_IGNORE_INDICATIONS, False),
            )

        except TNSEnergoException as e:
            event_data[ATTR_COMMENT] = "API error: %s" % e
            raise

        except BaseException as e:
            event_data[ATTR_COMMENT] = "Unknown error: %r" % e
            _LOGGER.error(event_data[ATTR_COMMENT])
            raise

        else:
            event_data[ATTR_COMMENT] = "Indications submitted successfully"
            event_data[ATTR_SUCCESS] = True
            self.async_schedule_update_ha_state(force_refresh=True)

        finally:
            _LOGGER.debug(
                self.log_prefix + "Indications push event: " + str(event_data)
            )
            self.hass.bus.async_fire(
                event_type=DOMAIN + "_" + SERVICE_PUSH_INDICATIONS,
                event_data=event_data,
            )

            _LOGGER.info(self.log_prefix + "End handling indications submission")

    async def async_service_get_indications(self, **call_data):
        account = self._account
        meter = self._meter

        _LOGGER.info(self.log_prefix + "Begin handling indications retrieval")

        dt_start: Optional["datetime"] = call_data[ATTR_START]
        dt_end: Optional["datetime"] = call_data[ATTR_END]

        dt_start, dt_end = process_start_end_arguments(dt_start, dt_end)
        results = []

        event_data = {
            ATTR_ENTITY_ID: self.entity_id,
            ATTR_ACCOUNT_CODE: account.code,
            ATTR_METER_CODE: meter.code,
            ATTR_SUCCESS: False,
            ATTR_START: dt_start.isoformat(),
            ATTR_END: dt_end.isoformat(),
            ATTR_RESULT: results,
            ATTR_COMMENT: None,
        }

        try:
            indications = await with_auto_auth(
                account.api,
                meter.async_get_indications,
                dt_start,
                dt_end,
            )

            for indication in indications:
                results.append(indication_to_attrs(indication))

        except BaseException as e:
            event_data[ATTR_COMMENT] = "Unknown error: %r" % e
            _LOGGER.exception(event_data[ATTR_COMMENT])
            raise
        else:
            event_data[ATTR_SUCCESS] = True

        finally:
            _LOGGER.debug(
                self.log_prefix + "Indications retrieval event: " + str(event_data)
            )
            self.hass.bus.async_fire(
                event_type=DOMAIN + "_" + SERVICE_GET_INDICATIONS,
                event_data=event_data,
            )

            _LOGGER.info(self.log_prefix + "Finish handling indications retrieval")


class TNSEnergoLastPayment(TNSEnergoSensor):
    config_key: ClassVar[str] = CONF_LAST_PAYMENT

    _attr_unit_of_measurement = "руб."
    _attr_icon = "mdi:cash-multiple"
    _attr_device_class = DOMAIN + "_payment"

    def __init__(self, *args, last_payment: Optional[Payment] = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._last_payment = last_payment
        self.entity_id: Optional[str] = (
            "sensor." + self.entity_id_prefix + "_last_payment"
        )

    #################################################################################
    # Implementation base of inherent class
    #################################################################################

    @classmethod
    async def async_refresh_accounts(
        cls: Type[_TTNSEnergoEntity],
        entities: Dict[Hashable, _TTNSEnergoEntity],
        account: "Account",
        config_entry: ConfigEntry,
        account_config: ConfigType,
        async_add_entities: Callable[[List[_TTNSEnergoEntity], bool], Any],
    ) -> None:
        entity_key = account.code

        try:
            entity = entities[entity_key]
        except KeyError:
            entity = cls(account, account_config)
            entities[entity_key] = entity
            async_add_entities([entity], True)

        else:
            if entity.enabled:
                await entity.async_update_ha_state(force_refresh=True)

    async def async_update_internal(self) -> None:
        self._last_payment = await self._account.async_get_last_payment()

    #################################################################################
    # Data-oriented implementation of inherent class
    #################################################################################

    @property
    def code(self) -> str:
        return self._account.code

    @property
    def state(self) -> StateType:
        data = self._last_payment

        if data is None:
            return STATE_UNKNOWN

        return self._last_payment.amount

    @property
    def sensor_related_attributes(self) -> Optional[Mapping[str, Any]]:
        payment = self._last_payment

        if payment is None:
            attributes = {}

        else:
            attributes = payment_to_attrs(payment)

            self._handle_dev_presentation(
                attributes,
                (ATTR_PAID_AT,),
                (ATTR_AMOUNT, ATTR_SOURCE),
            )

        return attributes

    @property
    def name_format_values(self) -> Mapping[str, Any]:
        last_payment = self._last_payment
        return {
            FORMAT_VAR_ID: last_payment.transaction_id if last_payment else "<?>",
            FORMAT_VAR_TYPE_EN: "last payment",
            FORMAT_VAR_TYPE_RU: "последний платёж",
        }

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor"""
        acc = self._account
        return f"{acc.api.__class__.__name__}_lastpayment_{acc.code}"


async_setup_entry = make_common_async_setup_entry(
    TNSEnergoAccount,
    TNSEnergoMeter,
    TNSEnergoLastPayment,
)
