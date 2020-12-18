"""Config flow for PulseAudio integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import CONF_SERVER, CONF_MEDIAPLAYER_SINKS, CONF_MEDIAPLAYER_SOURCES
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_SERVER, default="nuc:4713"): str})


def _verify_server(server: str) -> (bool, set, set):
    """Verify PulseAudio connection."""
    from pulsectl import Pulse, PulseError

    try:
        pulse = Pulse(server=server)
        if pulse.connected:
            return (True, pulse.sink_list(), pulse.source_list())
    except PulseError:
        None

    return (False, None, None)


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host):
        """Initialize."""
        self.host = host

    async def authenticate(self, username, password) -> bool:
        """Test if we can authenticate with the host."""
        return True


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # TODO validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data["username"], data["password"]
    # )
    result, sinks, sources = await hass.async_add_executor_job(
        _verify_server, data["server"]
    )

    if not result:
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"server": data["server"], "sinks": sinks, "sources": sources}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PulseAudio."""

    VERSION = 1
    # TODO pick one of the available connection classes in homeassistant/config_entries.py
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
            self.server = info["server"]
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=self.server, data=user_input)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for PulseAudio."""

    server = ""
    sinks = set()
    sources = set()

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize PulseAudio options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        info = await validate_input(self.hass, self.config_entry.data)
        self.server = self.config_entry.options.get("server")
        self.sinks = info["sinks"]
        self.sources = info["sources"]

        sink_names = []
        for sink in self.sinks:
            sink_names.append(sink.name)

        source_names = []
        for source in self.sources:
            source_names.append(source.name)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MEDIAPLAYER_SINKS,
                        default=self.config_entry.options.get(CONF_MEDIAPLAYER_SINKS),
                    ): cv.multi_select(sink_names),
                    vol.Required(
                        CONF_MEDIAPLAYER_SOURCES,
                        default=self.config_entry.options.get(CONF_MEDIAPLAYER_SOURCES),
                    ): cv.multi_select(source_names),
                }
            ),
        )
