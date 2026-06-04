#!/usr/bin/env python3
"""Generate the checked-in SVG symbol sprite from assets/icons/*.svg."""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def symbol_id(path: Path) -> str:
    value = path.stem.lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", value):
        raise ValueError(f"Invalid icon filename for symbol id: {path.name}")
    return value


def load_symbol(path: Path) -> ET.Element:
    root = ET.parse(path).getroot()
    if local_name(root.tag) != "svg":
        raise ValueError(f"Expected SVG root in {path}")

    view_box = root.attrib.get("viewBox")
    if not view_box:
        raise ValueError(f"Missing viewBox in {path}")

    symbol = ET.Element("symbol", {"id": symbol_id(path), "viewBox": view_box})
    for child in list(root):
        if local_name(child.tag) in {"title", "desc", "metadata"}:
            continue
        symbol.append(child)
    return symbol


def indent(element: ET.Element, level: int = 0) -> None:
    padding = "\n" + level * "  "
    child_padding = "\n" + (level + 1) * "  "
    if len(element):
        if not element.text or not element.text.strip():
            element.text = child_padding
        for child in element:
            indent(child, level + 1)
        if not element[-1].tail or not element[-1].tail.strip():
            element[-1].tail = padding
    if level and (not element.tail or not element.tail.strip()):
        element.tail = padding


def build_sprite(source_dir: Path) -> ET.Element:
    sources = sorted(source_dir.glob("*.svg"))
    if not sources:
        raise ValueError(f"No SVG icons found in {source_dir}")

    sprite = ET.Element(f"{{{SVG_NS}}}svg")
    for path in sources:
        sprite.append(load_symbol(path))
    indent(sprite)
    return sprite


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("assets/icons"))
    parser.add_argument("--output", type=Path, default=Path("plan/static/icons.svg"))
    args = parser.parse_args(argv)

    sprite = build_sprite(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        ET.tostring(sprite, encoding="unicode", short_empty_elements=True) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
