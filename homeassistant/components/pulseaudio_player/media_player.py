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

_LOGGER = logging.getLogger(__name__)

CONF_SINK_NAME = "sink_name"
CONF_SOURCES = "sources"
CONF_SOURCE_NAME = "source_name"

DEFAULT_NAME = "PULSE"
DEFAULT_PORT = 6600

PLAYLIST_UPDATE_INTERVAL = timedelta(seconds=120)

SUPPORT_Pulse = (
    SUPPORT_PAUSE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PLAY
    | SUPPORT_CLEAR_PLAYLIST
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_SEEK
    | SUPPORT_STOP
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
)

SOURCES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SOURCE_NAME): cv.string,
        vol.Required(CONF_NAME, default=None): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_SINK_NAME): cv.string,
        vol.Required(CONF_SOURCES): [SOURCES_SCHEMA],
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Pulse platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    sources = config.get(CONF_SOURCES)
    sink_name = config.get(CONF_SINK_NAME)

    device = PulseDevice(host, port, name, sink_name, sources)
    add_entities([device], True)


class PulseDevice(MediaPlayerDevice):
    """Representation of a Pulse server."""

    # pylint: disable=no-member
    def __init__(self, server, port, name, sink_name, sources):
        """Initialize the Pulse device."""
        self.server = server
        self.port = port
        self._name = name
        self.sink_name = sink_name
        self._sources = sources
        self._source_names = [s["name"] for s in self._sources]

        self._status = None
        self._is_connected = True

    @property
    def available(self):
        """Return true if Pulse is available and connected."""
        return self._is_connected

    def update(self):
        """Get the latest data and update the state."""
        None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the media state."""
        return STATE_PLAYING

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
        )

    @property
    def source_list(self):
        """Return the list of available input sources."""
        return self._source_names

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
