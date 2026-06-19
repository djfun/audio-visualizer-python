from PyQt6 import QtWidgets
from pytestqt import qtbot
from pytest import fixture
from . import command

from avp.libcomponent import BaseComponent
from avp.toolkit import connectWidget


@fixture
def coreWithBaseComp(qtbot, command):
    """
    Fixture providing a Command object with BaseComponent component added.
    Adding a BaseComponent component is not usually possible,
    because it lives outside the `avp.components` module,
    but we force it to work by manually instantiating the object.
    This allows us to test BaseComponent methods without using a subclass.
    """
    baseComp = BaseComponent(-1, command.core)
    baseComp.widget(command)
    command.core.insertComponent(0, baseComp, command)
    yield command.core


def addSpinBox(comp, name):
    widget = QtWidgets.QSpinBox()
    widget.setObjectName(name)
    comp.page.horizontalLayout_2.addWidget(widget)

    # Metaclass normally calls connectWidget after a call to widget()
    # For some reason this doesn't work with the BaseComponent
    # comp.widget(comp.loader)
    connectWidget(widget, comp.update)
    return widget


def test_libcomponent_basecomp_added(coreWithBaseComp):
    """Add BaseComponent to core"""
    assert len(coreWithBaseComp.selectedComponents) == 1


def test_libcomponent_addWidget_after_widget_method(coreWithBaseComp):
    comp = coreWithBaseComp.selectedComponents[0]
    name = "spinBox_testValue"
    widget = addSpinBox(comp, name)
    comp.trackWidgets({"testValue": widget})
    widget.setValue(50)
    assert comp.testValue == 50


def test_libcomponent_relativeWidgetFloats(coreWithBaseComp):
    comp = coreWithBaseComp.selectedComponents[0]
    name = "spinBox_testValue"
    widget = addSpinBox(comp, name)
    comp.trackWidgets(
        {"testValue": widget},
        relativeWidgets=["testValue"],
    )
    widget.setValue(50)
    assert comp._relativeWidgetFloats["testValue"] == comp.floatValForAttr("testValue")
