from . import audioData


def test_readAudioFile_data(audioData):
    assert len(audioData[0]) == 218453


def test_readAudioFile_duration(audioData):
    assert audioData[1] == 3.95
