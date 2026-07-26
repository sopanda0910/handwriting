"""Observation branch tests: features respond directionally on synthetic
pages, reversal shapes classify correctly, and pixel provenance is enforced.
"""

from __future__ import annotations

import pytest

from hwportfolio.models import Observation
from hwportfolio.observe.features import line_drift, spacing_ratio, xheight_consistency
from hwportfolio.observe.geometry import extract_glyphs, estimate_xheight
from hwportfolio.observe.reversals import classify_glyph, detect_reversal_candidates
from hwportfolio.pipeline.segment import LineBox, detect_ruled_lines, find_text_lines, segment

from .synth import add_rules, blank_page, draw_bowl_stem_glyph, gray, write_lines


def test_ruled_line_detection():
    page = blank_page()
    ys = add_rules(page)
    detected = detect_ruled_lines(gray(page))
    assert len(detected) == len(ys)
    for expected, got in zip(ys, detected):
        assert abs(expected - got) <= 3


def test_text_line_detection():
    page = blank_page()
    write_lines(page, ["hello world", "second line", "third line"])
    lines = find_text_lines(gray(page))
    assert len(lines) == 3


def test_segment_groups_lines_into_region():
    page = blank_page()
    write_lines(page, ["one two three", "four five six"])
    seg = segment(gray(page))
    assert len(seg.regions) == 1
    assert seg.ruled is False


def test_line_drift_detects_slope():
    flat = blank_page()
    write_lines(flat, ["a steady line of words here"])
    drifting = blank_page()
    write_lines(drifting, ["a steady line of words here"], drift_per_char=1.5)

    def drift_of(page):
        g = gray(page)
        lines = find_text_lines(g)
        assert lines
        merged = LineBox(
            x=min(l.x for l in lines),
            y=min(l.y for l in lines),
            w=max(l.x + l.w for l in lines) - min(l.x for l in lines),
            h=max(l.y + l.h for l in lines) - min(l.y for l in lines),
        )
        obs = line_drift(g, [merged], ruled=False)
        assert obs
        return obs[0].magnitude

    assert drift_of(drifting) > drift_of(flat) + 1.0


def test_spacing_ratio_present_and_sane():
    page = blank_page()
    write_lines(page, ["word word word word"])
    g = gray(page)
    lines = find_text_lines(g)
    obs = spacing_ratio(g, lines)
    assert obs
    assert obs[0].magnitude > 1.0  # word gaps larger than letter gaps
    assert obs[0].w > 0 and obs[0].h > 0


def test_xheight_consistency_worse_for_mixed_sizes():
    uniform = blank_page()
    write_lines(uniform, ["mmmm mmmm mmmm mmmm"])
    mixed = blank_page()
    write_lines(mixed, ["mm mm"], start_y=290, scale=1.0)
    write_lines(mixed, ["mm mm"], start_y=390, scale=2.6)

    def cv_of(page):
        g = gray(page)
        lines = find_text_lines(g)
        obs = xheight_consistency(g, lines)
        assert obs
        return obs[0].magnitude

    assert cv_of(mixed) > cv_of(uniform)


@pytest.mark.parametrize("shape", ["b", "d", "p", "q"])
def test_reversal_shape_classification(shape):
    page = blank_page()
    # Body glyphs establish x-height; the target glyph is taller.
    write_lines(page, ["nnnn nnnn"], start_y=340, scale=1.2, thickness=3)
    draw_bowl_stem_glyph(page, x=620, y=280, shape=shape, stem_h=70, bowl_r=16)
    g = gray(page)
    lines = find_text_lines(g)
    candidates = detect_reversal_candidates(g, lines)
    shapes = [c.details["shape"] for c in candidates]
    assert shape in shapes, f"Expected a {shape!r}-shaped candidate, got {shapes}"
    match = next(c for c in candidates if c.details["shape"] == shape)
    assert match.w > 0 and match.h > 0  # pixel provenance


def test_round_glyph_is_not_a_reversal_candidate():
    page = blank_page()
    write_lines(page, ["oooo oooo"], start_y=340, scale=1.2, thickness=3)
    g = gray(page)
    lines = find_text_lines(g)
    assert detect_reversal_candidates(g, lines) == []


def test_observation_without_bbox_is_rejected():
    """No pixel provenance, no record (GOALS §5.3) — enforced at the model."""
    with pytest.raises(ValueError):
        Observation(
            artifact_id="x", type="baseline_adherence", magnitude=1.0,
            unit="xheight_rms", x=0, y=0, w=0, h=10, model_version="v",
        )
    with pytest.raises(ValueError):
        Observation(
            artifact_id="x", type="baseline_adherence", magnitude=1.0,
            unit="xheight_rms", x=0, y=0, w=10, h=-5, model_version="v",
        )
