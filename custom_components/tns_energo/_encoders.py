from typing import TYPE_CHECKING

from homeassistant.const import ATTR_CODE

from .const import (
    ATTR_ACCOUNT_CODE,
    ATTR_ADDRESS,
    ATTR_AMOUNT,
    ATTR_CHECKUP_DATE,
    ATTR_CHECKUP_STATUS,
    ATTR_CHECKUP_URL,
    ATTR_CONTROLLED_BY_CODE,
    ATTR_DIGITAL_INVOICES_EMAIL,
    ATTR_DIGITAL_INVOICES_EMAIL_COMMENT,
    ATTR_DIGITAL_INVOICES_ENABLED,
    ATTR_DIGITAL_INVOICES_IGNORED,
    ATTR_EMAIL,
    ATTR_INSTALL_LOCATION,
    ATTR_IS_CONTROLLED,
    ATTR_IS_CONTROLLING,
    ATTR_LAST_CHECKUP_DATE,
    ATTR_LAST_INDICATIONS_DATE,
    ATTR_METER_CODE,
    ATTR_METER_ID,
    ATTR_MODEL,
    ATTR_PAID_AT,
    ATTR_PRECISION,
    ATTR_SERVICE_NAME,
    ATTR_SERVICE_TYPE,
    ATTR_SOURCE,
    ATTR_STATUS,
    ATTR_TAKEN_ON,
    ATTR_TRANSACTION_ID,
    ATTR_TRANSMISSION_COEFFICIENT,
    ATTR_TYPE,
    ATTR_ZONES,
)

if TYPE_CHECKING:
    from tns_energo_api import Account, Indication, Meter, Payment


def payment_to_attrs(payment: "Payment"):
    return {
        ATTR_AMOUNT: payment.amount,
        ATTR_PAID_AT: payment.paid_at.isoformat(),
        ATTR_TRANSACTION_ID: payment.transaction_id,
        ATTR_SOURCE: payment.source,
    }


def account_to_attrs(account: "Account"):
    attributes = {
        ATTR_ADDRESS: account.address,
        ATTR_CODE: account.code,
        ATTR_EMAIL: account.email,
        ATTR_IS_CONTROLLED: account.is_controlled,
        ATTR_IS_CONTROLLING: account.is_controlling,
        ATTR_DIGITAL_INVOICES_IGNORED: account.digital_invoices_ignored,
        ATTR_DIGITAL_INVOICES_EMAIL: account.digital_invoices_email,
        ATTR_DIGITAL_INVOICES_ENABLED: account.digital_invoices_enabled,
        ATTR_DIGITAL_INVOICES_EMAIL_COMMENT: account.digital_invoices_email_comment,
    }

    if account.is_controlled:
        attributes[ATTR_CONTROLLED_BY_CODE] = account.controlled_by_code

    return attributes


def meter_to_attrs(meter: "Meter"):
    last_checkup_date = meter.last_checkup_date
    if last_checkup_date is not None:
        last_checkup_date = last_checkup_date.isoformat()

    checkup_date = meter.checkup_date
    if checkup_date is not None:
        checkup_date = checkup_date.isoformat()

    attributes = {
        ATTR_METER_CODE: meter.code,
        ATTR_ACCOUNT_CODE: meter.account.code,
        ATTR_LAST_INDICATIONS_DATE: meter.last_indications_date,
        ATTR_MODEL: meter.model,
        ATTR_SERVICE_NAME: meter.service_name,
        ATTR_SERVICE_TYPE: meter.service_number,
        ATTR_STATUS: meter.status,
        ATTR_TRANSMISSION_COEFFICIENT: meter.transmission_coefficient,
        ATTR_INSTALL_LOCATION: meter.install_location,
        ATTR_PRECISION: meter.precision,
        ATTR_CHECKUP_STATUS: meter.checkup_status,
        ATTR_CHECKUP_DATE: checkup_date,
        ATTR_LAST_CHECKUP_DATE: last_checkup_date,
        ATTR_CHECKUP_URL: meter.checkup_url,
        ATTR_TYPE: meter.type,
    }

    # Installation date attribute

    last_indications_date = meter.last_indications_date
    attributes[ATTR_LAST_INDICATIONS_DATE] = (
        None if last_indications_date is None else last_indications_date.isoformat()
    )

    # Add zone information
    for zone_id, zone_def in meter.zones.items():
        iterator = [
            ("name", zone_def.name),
            ("label", zone_def.label),
            ("last_indication", zone_def.last_indication or 0),
            ("max_difference", zone_def.max_indication_difference),
            ("identifier", zone_def.identifier),
        ]

        for attribute, value in iterator:
            attributes[f"zone_{zone_id}_{attribute}"] = value

    return attributes


def indication_to_attrs(indication: "Indication"):
    return {
        ATTR_METER_ID: indication.meter_identifier,
        ATTR_TAKEN_ON: indication.taken_on.isoformat(),
        ATTR_METER_CODE: indication.meter_code,
        ATTR_STATUS: indication.status,
        ATTR_ZONES: indication.zones,
    }
