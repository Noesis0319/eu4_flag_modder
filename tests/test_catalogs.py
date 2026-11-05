from src import countries, event_pictures


def test_country_tags_unique_and_flattened():
    tags = countries.all_tags()
    assert len(tags) == sum(len(v) for v in countries.COUNTRIES.values())
    assert len({t for t, _n, _r in tags}) == len(tags)
    assert ("FRA", "프랑스", "서유럽 - 프랑스권") in tags


def test_country_find():
    assert countries.find("FRA") == ("프랑스", "서유럽 - 프랑스권")
    assert countries.find("fra") == (None, None)
    assert countries.find("ZZZZ") == (None, None)


def test_event_picture_keys_unique_and_known_folders():
    keys = [k for k, _f in event_pictures.EVENT_PICTURES]
    assert len(set(keys)) == len(keys)
    assert all(k.endswith("_eventPicture") for k in keys)
    folders = {f for _k, f in event_pictures.EVENT_PICTURES}
    assert folders <= set(event_pictures.CATEGORY_LABELS)


def test_event_picture_grouped():
    groups = event_pictures.grouped()
    assert sum(len(v) for v in groups.values()) == len(event_pictures.EVENT_PICTURES)
    flat = dict(item for items in groups.values() for item in items)
    assert flat["BATTLE_eventPicture"] == "전투 (BATTLE_eventPicture)"
    unnamed = next(k for k, _f in event_pictures.EVENT_PICTURES
                   if k not in event_pictures.KOREAN_ALIASES)
    assert flat[unnamed] == unnamed


def test_event_picture_folder_for():
    assert event_pictures.folder_for("NOBLE_ESTATE_eventPicture") == "event_pictures_estates"
    assert event_pictures.folder_for("missing_eventPicture") is None
