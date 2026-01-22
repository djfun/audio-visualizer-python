import numpy
from avp.toolkit.frame import BlankFrame, FloodFrame


def test_blank_frame():
    """BlankFrame creates a frame of all zeros"""
    assert numpy.asarray(BlankFrame(1920, 1080), dtype="int32").sum() == 0


def test_flood_frame():
    """FloodFrame given (1, 1, 1, 1) creates a frame of sum 1920 * 1080 * 4"""
    assert numpy.asarray(FloodFrame(1920, 1080, (1, 1, 1, 1)), dtype="int32").sum() == (
        1920 * 1080 * 4
    )
