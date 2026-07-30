import pytest

from auth import auth_manager


@pytest.fixture(autouse=True)
def disable_authentication_by_default():
    auth_manager.configure("")
    yield
    auth_manager.configure("")
