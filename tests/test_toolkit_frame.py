import numpy
from avp.toolkit.frame import BlankFrame


def test_blank_frame():
    assert numpy.asarray(BlankFrame(1920, 1080), dtype="int32").sum() == 0
