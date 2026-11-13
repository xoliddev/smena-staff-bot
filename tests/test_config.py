"""Tests for the white-label RESTAURANT_NAME setting and report file naming."""
import importlib

import pytest

import config


@pytest.fixture
def reload_config(monkeypatch):
    """Re-import config with a given RESTAURANT_NAME (None = unset); restores the module afterwards."""
    # Keep a local .env from leaking into these tests
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)

    def _reload(value):
        if value is None:
            monkeypatch.delenv("RESTAURANT_NAME", raising=False)
        else:
            monkeypatch.setenv("RESTAURANT_NAME", value)
        return importlib.reload(config)

    yield _reload
    monkeypatch.undo()
    importlib.reload(config)


def test_default_restaurant_name_is_smena(reload_config):
    cfg = reload_config(None)
    assert cfg.RESTAURANT_NAME == "Smena"
    assert cfg.RESTAURANT_SLUG == "Smena"


@pytest.mark.parametrize("raw", ["", "   ", "\t\n"])
def test_blank_restaurant_name_falls_back_to_default(reload_config, raw):
    assert reload_config(raw).RESTAURANT_NAME == "Smena"


def test_custom_restaurant_name_is_trimmed_and_collapsed(reload_config):
    cfg = reload_config("  Mening   Oshxonam ")
    assert cfg.RESTAURANT_NAME == "Mening Oshxonam"
    assert cfg.RESTAURANT_SLUG == "Mening_Oshxonam"


@pytest.mark.parametrize("name, expected", [
    ("Smena", "Smena"),
    ("Grill & Co", "Grill_&_Co"),
    ("Café/Bar: \"Night\"", "CaféBar_Night"),
    ("Choyxona O'rda", "Choyxona_Orda"),
    ("Кафе Лагман", "Кафе_Лагман"),
    ("///", "Smena"),
])
def test_make_file_slug(name, expected):
    assert config.make_file_slug(name) == expected


def test_monthly_report_filename_uses_restaurant_name(reload_config):
    cfg = reload_config("Grill House")
    assert cfg.monthly_report_filename("Mart", 2026) == "Grill_House_Mart_2026_Hisoboti.xlsx"


def test_monthly_report_filename_explicit_name():
    assert config.monthly_report_filename("Yanvar", 2027, "Smena") == "Smena_Yanvar_2027_Hisoboti.xlsx"
