"""Switch logic for loading/unloading pulseaudio loopback modules."""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
import homeassistant.helpers.config_validation as cv

from .pulse import get_pa_server

_LOGGER = logging.getLogger(__name__)

CONF_BUFFER_SIZE = "buffer_size"
CONF_SINK_NAME = "sink_name"
CONF_SOURCE_NAME = "source_name"
CONF_TCP_TIMEOUT = "tcp_timeout"

DEFAULT_BUFFER_SIZE = 1024
DEFAULT_HOST = "localhost"
DEFAULT_NAME = "paloopback"
DEFAULT_PORT = 4712
DEFAULT_TCP_TIMEOUT = 3

IGNORED_SWITCH_WARN = "Switch is already in the desired state. Ignoring."

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SINK_NAME): cv.string,
        vol.Required(CONF_SOURCE_NAME): cv.string,
        vol.Optional(CONF_BUFFER_SIZE, default=DEFAULT_BUFFER_SIZE): cv.positive_int,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_TCP_TIMEOUT, default=DEFAULT_TCP_TIMEOUT): cv.positive_int,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Read in all of our configuration, and initialize the loopback switch."""
    name = config.get(CONF_NAME)
    sink_name = config.get(CONF_SINK_NAME)
    source_name = config.get(CONF_SOURCE_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    buffer_size = config.get(CONF_BUFFER_SIZE)
    tcp_timeout = config.get(CONF_TCP_TIMEOUT)

    server = get_pa_server(host, port, buffer_size, tcp_timeout)

    add_entities([PALoopbackSwitch(hass, name, server, sink_name, source_name)])


class PALoopbackSwitch(SwitchDevice):
    """Representation the presence or absence of a PA loopback module."""

    def __init__(self, hass, name, pa_server, sink_name, source_name):
        """Initialize the Pulseaudio switch."""
        self._module_idx = -1
        self._hass = hass
        self._name = name
        self._sink_name = sink_name
        self._source_name = source_name
        self._pa_svr = pa_server

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._module_idx > 0

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if not self.is_on:
            self._pa_svr.turn_on(self._sink_name, self._source_name)
            self._pa_svr.update_module_state(no_throttle=True)
            self._module_idx = self._pa_svr.get_module_idx(
                self._sink_name, self._source_name
            )
            self.schedule_update_ha_state()
        else:
            _LOGGER.warning(IGNORED_SWITCH_WARN)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if self.is_on:
            self._pa_svr.turn_off(self._module_idx)
            self._pa_svr.update_module_state(no_throttle=True)
            self._module_idx = self._pa_svr.get_module_idx(
                self._sink_name, self._source_name
            )
            self.schedule_update_ha_state()
        else:
            _LOGGER.warning(IGNORED_SWITCH_WARN)

    def update(self):
        """Refresh state in case an alternate process modified this data."""
        self._pa_svr.update_module_state()
        self._module_idx = self._pa_svr.get_module_idx(
            self._sink_name, self._source_name
        )
