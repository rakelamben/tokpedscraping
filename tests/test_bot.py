import config
import pytest

from bot import _parse_keyword_min_price, _parse_scrape_args


def test_angka_terakhir_tetap_menjadi_bagian_keyword():
    assert _parse_keyword_min_price(["iphone", "14"]) == ("iphone 14", None)
    assert _parse_keyword_min_price(["iphone", "14", "1jt"]) == ("iphone 14 1jt", None)


def test_filter_harga_minimum_dengan_satuan_rb_dan_jt():
    assert _parse_keyword_min_price(["iphone", "14", "min:500rb"]) == ("iphone 14", 500_000)
    assert _parse_keyword_min_price(["iphone", "14", "min:1,5jt"]) == ("iphone 14", 1_500_000)


def test_filter_harga_minimum_tanpa_satuan_dianggap_rupiah():
    assert _parse_keyword_min_price(["iphone", "14", "min:14000000"]) == ("iphone 14", 14_000_000)


def test_scrape_scroll_default_saat_tidak_ditentukan():
    assert _parse_scrape_args(["iphone", "14"]) == ("iphone 14", None, config.DEFAULT_PAGES)


def test_scrape_scroll_dan_filter_harga_bisa_dalam_urutan_berbeda():
    assert _parse_scrape_args(["iphone", "14", "scroll:3", "min:500rb"]) == (
        "iphone 14",
        500_000,
        3,
    )
    assert _parse_scrape_args(["iphone", "14", "min:500rb", "scroll:3"]) == (
        "iphone 14",
        500_000,
        3,
    )


@pytest.mark.parametrize("scroll_arg", ["scroll:0", "scroll:abc"])
def test_scrape_menolak_jumlah_scroll_tidak_valid(scroll_arg):
    with pytest.raises(ValueError, match="scroll:n"):
        _parse_scrape_args(["iphone", "14", scroll_arg])
