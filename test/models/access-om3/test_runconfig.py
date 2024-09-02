import os
import pytest
import shutil

from test.common import tmpdir
from payu.models.cesm_cmeps import Runconfig


@pytest.fixture()
def runconfig_path():
    return os.path.join('test', 'resources', 'nuopc.runconfig')


@pytest.fixture()
def runconfig(runconfig_path):
    return Runconfig(runconfig_path)


# Runconfig tests:

@pytest.mark.parametrize(
    "section, variable, expected",
    [
        ("ALLCOMP_attributes", "OCN_model", "mom"),
        ("CLOCK_attributes", "restart_n", "1"),
        ("DOES_NOT_EXIST", "OCN_model", None),
        ("ALLCOMP_attributes", "DOES_NOT_EXIST", None),
        ("allcomp_attributes", "OCN_model", None), # verify case sensitivity in section
        ("ALLCOMP_attributes", "ocn_model", None), # verify case sensitivity in variable
        ("ATM_attributes", "perpetual", ".false."), # correctly read booleans
        ("ICE_attributes", "eps_imesh", "1e-13"), # correctly read commented value
        ("MED_attributes", "histaux_atm2med_file1_flds", "Faxa_swndr:Faxa_swvdr:Faxa_swndf:Faxa_swvdf"), # correctly read long colon separated value
    ]
)
def test_runconfig_get(section, variable, expected, runconfig):
    """Test getting values from a nuopc.runconfig file"""
    assert runconfig.get(section, variable) == expected


def test_runconfig_get_default(runconfig):
    """Test getting default values from a nuopc.runconfig file"""
    assert runconfig.get("DOES_NOT_EXIST", "DOES_NOT_EXIST", value="default") == "default"


def test_runconfig_get_component_list(runconfig):
    """Test getting component_list from a nuopc.runconfig file"""
    COMP_LIST = ['MED', 'ATM', 'ICE', 'OCN', 'ROF']
    assert runconfig.get_component_list() == COMP_LIST


@pytest.mark.parametrize(
    "section, variable, new_variable",
    [
        ("ALLCOMP_attributes", "OCN_model", "pop"),
        ("CLOCK_attributes", "restart_n", "2"),
    ]
)
def test_runconfig_set(section, variable, new_variable, runconfig):
    """Test setting values in a nuopc.runconfig file"""
    runconfig.set(section, variable, new_variable)

    assert runconfig.get(section, variable) == new_variable


def test_runconfig_set_error(runconfig):
    """Test error setting values in a nuopc.runconfig file that don't exist"""
    with pytest.raises(
        NotImplementedError,
        match='Cannot set value of variable that does not already exist'
        ):
        runconfig.set("DOES_NOT_EXIST", "OCN_model", "value")
        runconfig.set("ALLCOMP_attributes", "DOES_NOT_EXIST", "value")


def test_runconfig_set_write_get(runconfig):
    """Test updating the values in a nuopc.runconfig file"""

    tmpdir.mkdir()

    assert runconfig.get("CLOCK_attributes", "restart_n") == "1"

    runconfig.set("CLOCK_attributes", "restart_n", "2")

    runconfig_path_tmp = os.path.join(tmpdir, "nuopc.runconfig.tmp")
    runconfig.write(file=runconfig_path_tmp)

    runconfig_updated = Runconfig(runconfig_path_tmp)
    assert runconfig_updated.get("CLOCK_attributes", "restart_n") == "2"

    os.remove(runconfig_path_tmp)

    shutil.rmtree(tmpdir)
