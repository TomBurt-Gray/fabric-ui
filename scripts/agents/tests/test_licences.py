from agents import licences


def test_inventory_lists_django_with_version_and_licence() -> None:
    rows = {row["name"].lower(): row for row in licences.inventory()}
    assert rows["django"]["version"].startswith("5.2.")
    assert rows["django"]["licence"] != "Unknown"
