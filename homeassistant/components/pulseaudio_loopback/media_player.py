"""Support to interact with a Music Player Daemon."""
from datetime import timedelta
import logging
import os

import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerDevice
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

from .pulse import get_pa_server

_LOGGER = logging.getLogger(__name__)

CONF_BUFFER_SIZE = "buffer_size"
CONF_SINK_NAME = "sink_name"
CONF_SOURCE_NAME = "source_name"
CONF_TCP_TIMEOUT = "tcp_timeout"
CONF_SINK_NAME = "sink_name"
CONF_SOURCES = "sources"

DEFAULT_BUFFER_SIZE = 1024
DEFAULT_HOST = "localhost"
DEFAULT_NAME = "pulseaudio"
DEFAULT_PORT = 4712
DEFAULT_TCP_TIMEOUT = 3

PLAYLIST_UPDATE_INTERVAL = timedelta(seconds=120)

SOURCES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SOURCE_NAME): cv.string,
        vol.Required(CONF_NAME, default=None): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_BUFFER_SIZE, default=DEFAULT_BUFFER_SIZE): cv.positive_int,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_TCP_TIMEOUT, default=DEFAULT_TCP_TIMEOUT): cv.positive_int,
        vol.Required(CONF_SINK_NAME): cv.string,
        vol.Required(CONF_SOURCES): [SOURCES_SCHEMA],
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Pulse platform."""
    name = config.get(CONF_NAME)
    sources = config.get(CONF_SOURCES)
    sink_name = config.get(CONF_SINK_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    buffer_size = config.get(CONF_BUFFER_SIZE)
    tcp_timeout = config.get(CONF_TCP_TIMEOUT)

    server = get_pa_server(host, port, buffer_size, tcp_timeout)

    device = PulseDevice(server, name, sink_name, sources)
    add_entities([device], True)


class PulseDevice(MediaPlayerDevice):
    """Representation of a Pulse server."""

    # pylint: disable=no-member
    def __init__(self, pa_server, name, sink_name, sources):
        """Initialize the Pulse device."""
        self._pa_svr = pa_server
        self._name = name
        self._sink_name = sink_name
        self._sources = sources
        self._source_names = [s["name"] for s in self._sources]
        self._status = None
        self._is_connected = True
        self._current_source = None
        self._state = STATE_PAUSED

    @property
    def available(self):
        """Return true if Pulse is available and connected."""
        return self._is_connected

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the media state."""
        return self._state

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return False

    @property
    def volume_level(self):
        """Return the volume level."""
        return 50

    @property
    def supported_features(self):
        """Flag media player features that are supported."""

        return (
            SUPPORT_VOLUME_SET
            | SUPPORT_VOLUME_STEP
            | SUPPORT_VOLUME_MUTE
            | SUPPORT_VOLUME_MUTE
            | SUPPORT_SELECT_SOURCE
            | SUPPORT_PAUSE
        )

    @property
    def source(self):
        """Name of the current input source."""
        return self._current_source

    @property
    def source_list(self):
        """Return the list of available input sources."""
        return self._source_names

    def select_source(self, source):
        """Choose a different available playlist and play it."""
        self.connect_source(source)

    def set_volume_level(self, volume):
        """Set volume of media player."""
        None

    def volume_up(self):
        """Service to send the Pulse the command for volume up."""
        if "volume" in self._status:
            current_volume = int(self._status["volume"])

            if current_volume <= 100:
                self._client.setvol(current_volume + 5)

    def volume_down(self):
        """Service to send the Pulse the command for volume down."""
        None

    def media_play(self):
        """Service to send the Pulse the command for play/pause."""
        None

    def media_pause(self):
        """Service to send the Pulse the command for play/pause."""
        None

    def media_stop(self):
        """Service to send the Pulse the command for stop."""
        None

    def mute_volume(self, mute):
        """Mute. Emulated with set_volume_level."""
        None

    def turn_off(self):
        """Service to send the Pulse the command to stop playing."""
        None

    def turn_on(self):
        """Service to send the Pulse the command to start playing."""
        None

    def update(self):
        """Refresh state in case an alternate process modified this data."""
        self._pa_svr.update_module_state()

        current_source = None
        state = STATE_PAUSED

        for s in self._sources:
            idx = self._pa_svr.get_module_idx(self._sink_name, s["source_name"])

            if idx != -1:
                current_source = s["name"]
                state = STATE_PLAYING
                break

        self._current_source = current_source
        self._state = state

    def connect_source(self, source):
        src = next(filter(lambda s: s["name"] == source, self._sources))["source_name"]

        self._pa_svr.turn_on(self._sink_name, src)
        # TODO: Turn off other sources!
        self.update()
