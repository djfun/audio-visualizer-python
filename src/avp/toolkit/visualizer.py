"""Functions used to transform and manipulate audio for use by visualizers"""

from copy import copy
import numpy


def createSpectrumArray(
    component,
    completeAudioArray,
    sampleSize,
    smoothConstantDown,
    smoothConstantUp,
    scale,
    progressBarUpdate,
    progressBarSetText,
):
    lastSpectrum = None
    spectrumArray = {}
    for i in range(0, len(completeAudioArray), sampleSize):
        if component.canceled:
            break
        lastSpectrum = transformData(
            i,
            completeAudioArray,
            sampleSize,
            smoothConstantDown,
            smoothConstantUp,
            lastSpectrum,
            scale,
        )
        spectrumArray[i] = copy(lastSpectrum)

        progress = int(100 * (i / len(completeAudioArray)))
        if progress >= 100:
            progress = 100
        progressText = f"Analyzing audio: {str(progress)}%"
        progressBarSetText.emit(progressText)
        progressBarUpdate.emit(int(progress))
    return spectrumArray


def transformData(
    i,
    completeAudioArray,
    sampleSize,
    smoothConstantDown,
    smoothConstantUp,
    lastSpectrum,
    scale,
):
    if len(completeAudioArray) < (i + sampleSize):
        sampleSize = len(completeAudioArray) - i

    window = numpy.hanning(sampleSize)
    data = completeAudioArray[i : i + sampleSize][::1] * window
    paddedSampleSize = 2048
    paddedData = numpy.pad(data, (0, paddedSampleSize - sampleSize), "constant")
    spectrum = numpy.fft.fft(paddedData)
    sample_rate = 44100
    frequencies = numpy.fft.fftfreq(len(spectrum), 1.0 / sample_rate)

    y = abs(spectrum[0 : int(paddedSampleSize / 2) - 1])

    # filter the noise away
    # y[y<80] = 0

    with numpy.errstate(divide="ignore"):
        y = scale * numpy.log10(y)

    y[numpy.isinf(y)] = 0

    if lastSpectrum is not None:
        lastSpectrum[y < lastSpectrum] = y[
            y < lastSpectrum
        ] * smoothConstantDown + lastSpectrum[y < lastSpectrum] * (
            1 - smoothConstantDown
        )

        lastSpectrum[y >= lastSpectrum] = y[
            y >= lastSpectrum
        ] * smoothConstantUp + lastSpectrum[y >= lastSpectrum] * (1 - smoothConstantUp)
    else:
        lastSpectrum = y

    x = frequencies[0 : int(paddedSampleSize / 2) - 1]

    return lastSpectrum
