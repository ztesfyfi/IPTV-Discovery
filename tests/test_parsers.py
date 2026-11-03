from app.parsers import parse_playlist, normalize_name


def test_m3u():
    x = parse_playlist('#EXTM3U\n#EXTINF:-1,CCTV-1\nhttps://example.org/a.m3u8')
    assert x[0]["name"] == "CCTV-1"
    assert x[0]["url"] == "https://example.org/a.m3u8"


def test_txt():
    x = parse_playlist("湖南卫视,https://example.org/a.m3u8")
    assert x[0]["name"] == "湖南卫视"


def test_alias_normalization():
    assert normalize_name("CCTV-1") == "CCTV1"


def test_utf8_bom_and_spaces():
    x = parse_playlist("\ufeff#EXTM3U\n#EXTINF:-1, CCTV-1 \nhttps://example.org/a.m3u8")
    assert x[0]["name"] == "CCTV-1"
