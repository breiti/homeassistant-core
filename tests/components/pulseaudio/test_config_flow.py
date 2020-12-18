"""Test the PulseAudio config flow."""
import pytest
from homeassistant.core import HomeAssistant
from homeassistant import config_entries, data_entry_flow
from homeassistant.components.pulseaudio.const import (
    CONF_SERVER,
    CONF_MEDIAPLAYER_SINKS,
    CONF_MEDIAPLAYER_SOURCES,
    DOMAIN,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry

TEST_SERVER = "localhost"
TEST_UNIQUE_ID = f"{DOMAIN}-{TEST_SERVER}"


@pytest.fixture(name="pulseaudio_connect", autouse=True)
def pulseaudio_connect_fixture():
    """Mock PulseAudio connection."""

    class PulseItemMock:
        def __init__(self, name: str):
            self.name = name

    with patch(
        "homeassistant.components.pulseaudio.config_flow._verify_server",
        return_value=True,
    ), patch(
        "homeassistant.components.pulseaudio.config_flow.validate_input",
        return_value={
            "sinks": [PulseItemMock("sink1"), PulseItemMock("sink1")],
            "sources": [
                PulseItemMock("source1"),
                PulseItemMock("source2"),
            ],
        },
    ), patch(
        "homeassistant.components.pulseaudio.async_setup", return_value=True
    ), patch(
        "homeassistant.components.pulseaudio.async_setup_entry",
        return_value=True,
    ):
        yield


async def test_config_flow_connect_success(hass: HomeAssistant):
    """
    Successful flow manually initialized by the user.

    Host specified.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SERVER: "localhost"},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "localhost"
    assert result["data"] == {
        CONF_SERVER: "localhost",
    }


async def test_config_flow_options(hass: HomeAssistant):
    """Test options config flow"""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_UNIQUE_ID,
        data={
            CONF_SERVER: TEST_SERVER,
            CONF_MEDIAPLAYER_SINKS: [],
            CONF_MEDIAPLAYER_SOURCES: [],
        },
        title=TEST_SERVER,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MEDIAPLAYER_SINKS: ["sink1"],
            CONF_MEDIAPLAYER_SOURCES: ["source2"],
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        CONF_MEDIAPLAYER_SINKS: ["sink1"],
        CONF_MEDIAPLAYER_SOURCES: ["source2"],
    }