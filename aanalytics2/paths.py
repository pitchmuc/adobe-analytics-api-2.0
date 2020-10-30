from aanalytics2 import modules

def find_path(path: str) -> modules.Optional[modules.Path]:
    """Checks if the file denoted by the specified `path` exists and returns the Path object
    for the file.

    If the file under the `path` does not exist and the path denotes an absolute path, tries
    to find the file by converting the absolute path to a relative path.

    If the file does not exist with either the absolute and the relative path, returns `None`.
    """
    if modules.Path(path).exists():
        return modules.Path(path)
    elif path.startswith('/') and modules.Path('.' + path).exists():
        return modules.Path('.' + path)
    elif path.startswith('\\') and modules.Path('.' + path).exists():
        return modules.Path('.' + path)
    else:
        return None
