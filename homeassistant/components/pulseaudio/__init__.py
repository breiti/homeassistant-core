"""The PulseAudio integration."""
import asyncio
import threading

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, CONF_SERVER

from pulsectl import Pulse, PulseError, PulseVolumeInfo, _pulsectl
import queue
from threading import Thread

UNDO_UPDATE_LISTENER = "undo_update_listener"
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["media_player"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the PulseAudio component."""
    return True


class PulseAudioInterface:

    _queue = queue.Queue()
    _connected = False
    _sink_list = None
    _source_list = None
    _module_list = None

    def __init__(self, server: str):
        def pulse_thread(q: queue.Queue, server: str):
            pulse = Pulse(server=server)
            while True:
                try:
                    try:
                        (f, ev) = q.get(block=True, timeout=2)

                        if (f, ev) == (None, None):
                            return

                        f(pulse)
                        ev.set()

                    except queue.Empty:
                        None

                    self._connected = pulse.connected
                    if not self._connected:
                        pulse.connect()

                    self._module_list = pulse.module_list()
                    self._sink_list = pulse.sink_list()
                    self._source_list = pulse.source_list()

                except (PulseError, _pulsectl.LibPulse.CallError):
                    self._connected = False
                    pulse.disconnect()


        self._thread = Thread(
            target=pulse_thread, name="PulseAudio_" + server, args=(self._queue, server)
        )

        self._thread.start()

    def stop(self):
        self._queue.put((None, None))

    async def async_pulse_call(self, f):
        ev = asyncio.Event()
        self._queue.put((f, ev))
        await ev.wait()

    async def async_sink_volume_set(self, sink, volume: float):
        await self.async_pulse_call(
            lambda pulse, sink=sink, volume=volume: pulse.sink_volume_set(
                sink.index, PulseVolumeInfo(volume, len(sink.volume.values))
            )
        )

    async def async_sink_mute(self, sink, mute):
        await self.async_pulse_call(
            lambda pulse, index=sink.index, mute=mute: pulse.sink_mute(index, mute)
        )

    def _get_module_idx(self, sink_name, source_name):
        for module in self._module_list:
            if not module.name == "module-loopback":
                continue

            if f"sink={sink_name}" not in module.argument:
                continue

            if f"source={source_name}" not in module.argument:
                continue

            return module.index

        return None

    async def async_connect_source(self, sink, source_name, sources):
        for s in sources:
            idx = self._get_module_idx(sink.name, s)
            if s == source_name:
                if not idx:
                    await self.async_pulse_call(
                        lambda pulse, sink=sink.name, source=s: pulse.module_load(
                            "module-loopback", args=f"sink={sink} source={source}"
                        )
                    )
            else:
                if not idx:
                    continue

                await self.async_pulse_call(
                    lambda pulse, idx=idx: pulse.module_unload(idx)
                )

    def get_connected_source(self, sink, sources):
        if sink:
            for s in sources:
                idx = self._get_module_idx(sink.name, s)
                if idx:
                    return s
        return None

    def get_sink_by_name(self, name):
        if not self._sink_list:
            return None

        return [s for s in self._sink_list if s.name == name][0]

    @property
    def connected(self):
        """Return true when connected to server."""
        return self._connected


interfaces = {}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the denonavr components from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    server = entry.data[CONF_SERVER]

    undo_listener = entry.add_update_listener(async_update_listener)

    if not server in interfaces:
        interfaces[server] = PulseAudioInterface(server)

    hass.data[DOMAIN][entry.entry_id] = {
        "pulse_interface": interfaces[server],
        CONF_SERVER: server,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )

    hass.data[DOMAIN][config_entry.entry_id][UNDO_UPDATE_LISTENER]()

    entity_registry = await er.async_get_registry(hass)
    entries = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    for entry in entries:
        entity_registry.async_remove(entry.entity_id)

    if unload_ok:
        data = hass.data[DOMAIN].pop(config_entry.entry_id)
        interfaces.pop(data[CONF_SERVER]).stop()

    return unload_ok


async def async_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
