from .const import ATTR_MANUFACTURER, DOMAIN, CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR
from .const import WRITE_DATA_LOCAL, WRITE_MULTISINGLE_MODBUS, WRITE_SINGLE_MODBUS, TMPDATA_EXPIRY
from homeassistant.components.timme import PLATFORM_SCHEMA, TimeEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from typing import Any, Dict, Optional
from time import time
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities) -> None:
    if entry.data: # old style - remove soon
        hub_name = entry.data[CONF_NAME]
        modbus_addr = entry.data.get(CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR)
    else: # new style
        hub_name = entry.options[CONF_NAME]
        modbus_addr = entry.options.get(CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR)
    hub = hass.data[DOMAIN][hub_name]["hub"]
    device_info = {
        "identifiers": {(DOMAIN, hub_name)},
        "name": hub_name,
        "manufacturer": ATTR_MANUFACTURER,
    }
    plugin = hub.plugin #getPlugin(hub_name)
    entities = []
    for time_info in plugin.TIME_TYPES:
        readscale = 1
        if time_info.read_scale_exceptions:
            for (prefix, value,) in time_info.read_scale_exceptions: 
                if hub.seriesnumber.startswith(prefix): readscale = value
        if plugin.matchInverterWithMask(hub._invertertype,time_info.allowedtypes, hub.seriesnumber ,time_info.blacklist):
            number = SolaXModbusNumber( hub_name, hub, modbus_addr, device_info, time_info, readscale)
            if time_info.write_method==WRITE_DATA_LOCAL: 
                #if (time_info.initvalue) != None: hub.data[time_info.key] = time_info.initvalue
                hub.writeLocals[time_info.key] = time_info
            entities.append(number)
        
    async_add_entities(entities)
    return True

class SolaXModbusTime(TimeEntity):
    """Representation of an SolaX Modbus time."""

    def __init__(self,
                 platform_name,
                 hub,
                 modbus_addr,
                 device_info,
                 time_info,
    ) -> None:
        """Initialize the number."""
        self._platform_name = platform_name
        self._hub = hub
        self._modbus_addr = modbus_addr
        self._attr_device_info = device_info
        self._name = time_info.name
        self._key = time_info.key
        self._register = time_info.register
        self.entity_description = time_info
        self._attr_native_value = state
        self._state = time_info.state # not used AFAIK
        self.entity_description = time_info
        self._write_method = time_info.write_method

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._hub.async_add_solax_modbus_sensor(self._modbus_data_updated)

    async def async_will_remove_from_hass(self) -> None:
        self._hub.async_remove_solax_modbus_sensor(self._modbus_data_updated)

    @callback
    def _modbus_data_updated(self) -> None:
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self._platform_name} {self._name}"

    @property
    def unique_id(self) -> Optional[str]:
        return f"{self._platform_name}_{self._key}"

    async def async_set_native_value(self, value: float) -> None:
        """Change the time option."""
        payload = get_payload(self._attr_native_value, value)
        if self._write_method == WRITE_MULTISINGLE_MODBUS:
            _LOGGER.info(f"writing {self._platform_name} time register {self._register} value {payload}")
            self._hub.write_registers_single(unit=self._modbus_addr, address=self._register, payload=payload)
        elif self._write_method == WRITE_SINGLE_MODBUS:
            _LOGGER.info(f"writing {self._platform_name} time register {self._register} value {payload}")
            self._hub.write_register(unit=self._modbus_addr, address=self._register, payload=payload)
        elif self._write_method == WRITE_DATA_LOCAL:
            _LOGGER.info(f"*** local data written {self._key}: {payload}")
            self._hub.localsUpdated = True # mark to save permanently
        #self._hub.data[self._key] = option
        self.async_write_ha_state()