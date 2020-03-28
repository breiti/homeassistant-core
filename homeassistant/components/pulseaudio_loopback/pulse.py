from datetime import timedelta, datetime
import re
import socket
import select
import logging
from homeassistant import util

_LOGGER = logging.getLogger(__name__)

_PULSEAUDIO_SERVERS = {}

LOAD_CMD = "load-module module-loopback sink={0} source={1}"

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MOD_REGEX = (
    r"index: ([0-9]+)\s+name: <module-loopback>"
    r"\s+argument: (?=<.*sink={0}.*>)(?=<.*source={1}.*>)"
)

UNLOAD_CMD = "unload-module {0}"


def get_pa_server(host, port, buffer_size, tcp_timeout):
    server_id = str.format("{0}:{1}", host, port)

    if server_id in _PULSEAUDIO_SERVERS:
        server = _PULSEAUDIO_SERVERS[server_id]
    else:
        server = PAServer(host, port, buffer_size, tcp_timeout)
        _PULSEAUDIO_SERVERS[server_id] = server

    return server


class PAServer:
    """Representation of a Pulseaudio server."""

    _current_module_state = ""

    def __init__(self, host, port, buff_sz, tcp_timeout):
        """Initialize PulseAudio server."""
        self._pa_host = host
        self._pa_port = int(port)
        self._buffer_size = int(buff_sz)
        self._tcp_timeout = int(tcp_timeout)

    def _send_command(self, cmd, response_expected):
        """Send a command to the pa server using a socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self._tcp_timeout)
        try:
            sock.connect((self._pa_host, self._pa_port))
            _LOGGER.info("Calling pulseaudio: %s", cmd)
            sock.send((cmd + "\n").encode("utf-8"))
            if response_expected:
                return_data = self._get_full_response(sock)
                _LOGGER.debug("Data received from pulseaudio: %s", return_data)
            else:
                return_data = ""
        finally:
            sock.close()
        return return_data

    def _get_full_response(self, sock):
        """Get the full response back from pulseaudio."""
        result = ""

        t1 = datetime.now()
        sock.setblocking(0)

        while (datetime.now() - t1).seconds < self._tcp_timeout:
            ready = select.select([sock], [], [], 0.2)
            if ready[0]:
                rcv_buffer = sock.recv(self._buffer_size)
                result += rcv_buffer.decode("utf-8")
            else:
                break

        return result

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_module_state(self):
        """Refresh state in case an alternate process modified this data."""
        self._current_module_state = self._send_command("list-modules", True)

    def turn_on(self, sink_name, source_name):
        """Send a command to pulseaudio to turn on the loopback."""
        self._send_command(str.format(LOAD_CMD, sink_name, source_name), False)

    def turn_off(self, module_idx):
        """Send a command to pulseaudio to turn off the loopback."""
        self._send_command(str.format(UNLOAD_CMD, module_idx), False)

    def get_module_idx(self, sink_name, source_name):
        """For a sink/source, return its module id in our cache, if found."""
        result = re.search(
            str.format(MOD_REGEX, re.escape(sink_name), re.escape(source_name)),
            self._current_module_state,
        )
        if result and result.group(1).isdigit():
            return int(result.group(1))
        return -1
