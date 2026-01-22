from avp import __version__
from tomllib import load
import os


def test_version_number_matches():
    with open(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "..", "pyproject.toml"
        ),
        "rb",
    ) as fp:
        config = load(fp)
    assert config["project"]["version"] == __version__
