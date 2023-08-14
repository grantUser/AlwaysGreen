import yaml


def read(path: str) -> None | dict:
    """Parses a yaml file to return it as a dict if it has content, None otherwise."""

    with open(path) as file:
        return yaml.safe_load(file)
