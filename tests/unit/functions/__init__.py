"""Just somewhere for me to put the `flatten_dict` I/O combos for now."""
from __future__ import annotations

from json import load
from os import listdir
from os.path import isfile
from pathlib import Path

INPUT_OUTPUT_COMBOS = [
    ({}, {}),
    (
        {
            "one": 1,
            "two": {
                "three": 3,
                "four": 4,
            },
            "five": {"six": 6},
        },
        {"one": 1, "two.three": 3, "two.four": 4, "five.six": 6},
    ),
    (
        {
            "one": 1,
            "two": {
                3: 3,
                "four": 4,
            },
            "five": {"two": {"six": 6}},
        },
        {"one": 1, "two.3": 3, "two.four": 4, "five.two.six": 6},
    ),
    (
        {
            "one": {
                "two": {
                    "three": {
                        "four": {"five": {"six": {"seven": 7, "eight": 8, "nine": 9}}}
                    }
                }
            }
        },
        {
            "one.two.three.four.five.six.seven": 7,
            "one.two.three.four.five.six.eight": 8,
            "one.two.three.four.five.six.nine": 9,
        },
    ),
]


# It's easier to store large objects in flat files, so...
file: str
for file in listdir(json_dir := Path(__file__).parents[2] / "flat_files" / "json"):
    if file.endswith("_flattened.json"):
        continue

    if file.endswith(".json") and isfile(
        flattened_path := json_dir / file.replace(".json", "_flattened.json")
    ):
        with open(json_dir / file, encoding="utf-8") as fin:
            _original_payload = load(fin)

        # I used this JSFiddle to create the flat JSON: https://jsfiddle.net/S2hsS
        with open(flattened_path, encoding="utf-8") as _fin:
            _flattened_payload = load(_fin)

        INPUT_OUTPUT_COMBOS.append((_original_payload, _flattened_payload))

__all__ = ["INPUT_OUTPUT_COMBOS"]
