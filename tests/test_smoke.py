import sipl


def test_package_has_version() -> None:
    assert isinstance(sipl.__version__, str)
    assert sipl.__version__ != ""