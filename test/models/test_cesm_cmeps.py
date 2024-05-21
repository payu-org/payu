import os
import pytest

from payu.models.cesm_cmeps import Runconfig

@pytest.mark.parametrize(
    "section, variable, expected",
    [
        ("ALLCOMP_attributes", "OCN_model", "mom"),
        ("CLOCK_attributes", "restart_n", "1"),
        ("DOES_NOT_EXIST", "OCN_model", None),
        ("ALLCOMP_attributes", "DOES_NOT_EXIST", None),
    ]
)
def test_runconfig_get(section, variable, expected):
    """Test getting values from a nuopc.runconfig file"""
    runconfig_path = os.path.join('test', 'resources', 'nuopc.runconfig')
    runconfig = Runconfig(runconfig_path)

    assert runconfig.get(section, variable) == expected

def test_runconfig_get_default():
    """Test getting default values from a nuopc.runconfig file"""
    runconfig_path = os.path.join('test', 'resources', 'nuopc.runconfig')
    runconfig = Runconfig(runconfig_path)

    assert runconfig.get("DOES_NOT_EXIST", "DOES_NOT_EXIST", value="default") == "default"

@pytest.mark.parametrize(
    "section, variable, new_variable",
    [
        ("ALLCOMP_attributes", "OCN_model", "pop"),
        ("CLOCK_attributes", "restart_n", "2"),
    ]
)
def test_runconfig_set(section, variable, new_variable):
    """Test setting values in a nuopc.runconfig file"""
    runconfig_path = os.path.join('test', 'resources', 'nuopc.runconfig')
    runconfig = Runconfig(runconfig_path)

    runconfig.set(section, variable, new_variable)

    assert runconfig.get(section, variable) == new_variable

def test_runconfig_set_error():
    """Test error setting values in a nuopc.runconfig file that don't exist"""
    runconfig_path = os.path.join('test', 'resources', 'nuopc.runconfig')
    runconfig = Runconfig(runconfig_path)

    with pytest.raises(
        NotImplementedError,
        match='Cannot set value of variable that does not already exist'
        ):
        runconfig.set("DOES_NOT_EXIST", "OCN_model", "value")
        runconfig.set("ALLCOMP_attributes", "DOES_NOT_EXIST", "value")

def test_runconfig_set_write_get():
    """Test updating the values in a nuopc.runconfig file"""
    runconfig_path = os.path.join('test', 'resources', 'nuopc.runconfig')
    runconfig = Runconfig(runconfig_path)

    assert runconfig.get("CLOCK_attributes", "restart_n") == "1"

    runconfig.set("CLOCK_attributes", "restart_n", "2")

    runconfig_path_tmp = "nuopc.runconfig.tmp"
    runconfig.write(runconfig_path_tmp)

    runconfig_updated = Runconfig(runconfig_path_tmp)
    assert runconfig.get("CLOCK_attributes", "restart_n") == "2"

    os.remove(runconfig_path_tmp)
