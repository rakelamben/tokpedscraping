from bot import _parse_keyword_min_price


def test_angka_terakhir_tetap_menjadi_bagian_keyword():
    assert _parse_keyword_min_price(["iphone", "14"]) == ("iphone 14", None)
    assert _parse_keyword_min_price(["iphone", "14", "1jt"]) == ("iphone 14 1jt", None)


def test_filter_harga_minimum_dengan_satuan_rb_dan_jt():
    assert _parse_keyword_min_price(["iphone", "14", "min:500rb"]) == ("iphone 14", 500_000)
    assert _parse_keyword_min_price(["iphone", "14", "min:1,5jt"]) == ("iphone 14", 1_500_000)


def test_filter_harga_minimum_tanpa_satuan_dianggap_rupiah():
    assert _parse_keyword_min_price(["iphone", "14", "min:14000000"]) == ("iphone 14", 14_000_000)
