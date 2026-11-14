from main import simpan_raw_html


def test_simpan_raw_html_menyimpan_semua_halaman_dengan_keyword_aman(tmp_path):
    html_halaman = ["<html>halaman 1</html>", "<html>halaman 2</html>"]

    file_html = simpan_raw_html("iphone 15/pro", html_halaman, tmp_path)

    assert len(file_html) == 2
    assert file_html[0].name.startswith("raw_iphone_15_pro_")
    assert file_html[0].name.endswith("_hal_1.html")
    assert file_html[1].name.endswith("_hal_2.html")
    assert [path.read_text(encoding="utf-8") for path in file_html] == html_halaman
