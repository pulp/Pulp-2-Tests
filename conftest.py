"""Conftest file. Modifying test running activities."""


def pytest_collection_modifyitems(items, config):
    """Remove a certain class to run."""
    deselected = []
    for item in items:
        if item.cls.__name__ == 'BaseAPICrudTestCase':
            deselected.append(item)
    config.hook.pytest_deselected(items=deselected)
    items[:] = [item for item in items if item not in deselected]
