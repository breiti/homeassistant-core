"""Support to interact with a Music Player Daemon."""
from datetime import timedelta
import logging
import os

import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_SELECT_SOURCE,
    SUPPORT_VOLUME_STEP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    STATE_ON,
    STATE_OFF,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

from pulsectl import Pulse, PulseError, PulseVolumeInfo

from .const import DOMAIN, CONF_SERVER

_LOGGER = logging.getLogger(__name__)

CONF_SINK_NAME = "sink_name"
CONF_SOURCE_NAME = "source_name"
CONF_SINK_NAME = "sink_name"
CONF_SOURCES = "sources"

DEFAULT_NAME = "paloopback"
DEFAULT_PORT = 4713

PLAYLIST_UPDATE_INTERVAL = timedelta(seconds=120)

SOURCES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SOURCE_NAME): cv.string,
        vol.Required(CONF_NAME, default=None): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_SINK_NAME): cv.string,
        vol.Required(CONF_SOURCES): [SOURCES_SCHEMA],
    }
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the DenonAVR receiver from a config entry."""
    entities = []

    sinks = config_entry.options.get("mediaplayer_sinks")
    sources = config_entry.options.get("mediaplayer_sources")
    server = hass.data[DOMAIN][config_entry.entry_id][CONF_SERVER]
    interface = hass.data[DOMAIN][config_entry.entry_id]["pulse_interface"]

    if sinks:
        for sink in sinks:
            entities.append(PulseDevice(server, interface, sink, sink, sources))

        async_add_entities(entities)


class PulseDevice(MediaPlayerEntity):
    """Representation of a Pulse server."""

    # pylint: disable=no-member
    def __init__(self, server, interface, name, sink_name, sources):
        """Initialize the Pulse device."""
        self._server = server
        self._name = name
        self._sink = None
        self._sink_name = sink_name
        self._source_names = sources
        self._status = None
        self._current_source = None
        self._last_source = None
        self._interface = interface
        self._volume = 0.0
        self._muted = False

    @property
    def unique_id(self):
        """Return the unique id of the zone."""
        return f"{self._server}-{self._sink_name}"

    @property
    def available(self):
        """Return true when connected to server."""
        return self._sink and self._interface.connected

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._current_source:
            return STATE_ON
        else:
            return STATE_OFF

    @property
    def volume_level(self):
        """Return the volume level."""
        return self._volume

    @property
    def supported_features(self):
        """Flag media player features that are supported."""

        return (
            SUPPORT_VOLUME_SET
            | SUPPORT_VOLUME_STEP
            | SUPPORT_VOLUME_MUTE
            | SUPPORT_SELECT_SOURCE
            | SUPPORT_TURN_OFF
            | SUPPORT_TURN_ON
        )

    @property
    def media_title(self):
        """Return the content ID of current playing media."""
        return self._current_source

    @property
    def source(self):
        """Name of the current input source."""
        return self._current_source

    @property
    def source_list(self):
        """Return the list of available input sources."""
        return self._source_names

    async def async_select_source(self, source):
        """Choose a different available playlist and play it."""
        self._current_source = source
        self.async_schedule_update_ha_state()
        await self._interface.async_connect_source(
            self._sink, source, self._source_names
        )

    async def async_set_volume_level(self, volume):
        """Set volume of media player."""
        self._volume = volume
        await self._interface.async_sink_volume_set(self._sink, volume)
        self.async_schedule_update_ha_state()

    async def async_mute_volume(self, mute):
        """Mute."""
        self._muted = True
        await self._interface.async_sink_mute(self._sink, mute)
        self.async_schedule_update_ha_state()

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    async def async_turn_off(self):
        """Service to send the Pulse the command to stop playing."""
        await self._interface.async_connect_source(self._sink, None, self._source_names)

    async def async_turn_on(self):
        """Service to send the Pulse the command to start playing."""

        if self._current_source != None:
            return

        if self._last_source:
            source = self._last_source
        else:
            source = self._source_names[0]

        await self._interface.async_connect_source(
            self._sink, source, self._source_names
        )

    async def async_update(self):
        self._sink = self._interface.get_sink_by_name(self._sink_name)

        if self._sink:
            self._current_source = self._interface.get_connected_source(
                self._sink, self._source_names
            )
            if self._current_source:
                self._last_source = self._current_source

            self._volume = self._sink.volume.value_flat
            self._muted = self._sink.mute == 1
