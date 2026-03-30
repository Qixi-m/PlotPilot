from aitext.story.jsonutil import parse_json_loose, parse_model
from aitext.story.models import BibleOutlineBundle, Bible, Outline, OutlineChapter


def test_parse_json_loose_raw_object():
    data = parse_json_loose('  {"a": 1}  ')
    assert data == {"a": 1}


def test_parse_json_loose_fence():
    text = """```json
{"x": 2}
```"""
    assert parse_json_loose(text) == {"x": 2}


def test_parse_model_bundle():
    raw = """
Here's your JSON:
{
  "bible": {
    "characters": [{"name": "甲", "role": "主角", "traits": "", "arc_note": ""}],
    "locations": [{"name": "城", "description": ""}],
    "timeline_notes": [],
    "style_notes": ""
  },
  "outline": {
    "chapters": [{"id": 1, "title": "起", "one_liner": "开始"}]
  }
}
"""
    m = parse_model(raw, BibleOutlineBundle)
    assert m is not None
    assert m.bible.characters[0].name == "甲"
    assert m.outline.chapters[0].id == 1


def test_parse_model_invalid():
    assert parse_model("not json", BibleOutlineBundle) is None
