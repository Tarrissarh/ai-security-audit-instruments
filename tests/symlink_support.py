"""Create test symlinks, reporting unavailable Windows privileges as skipped tests."""

import os
from pathlib import Path
import unittest


def symlink_or_skip(
    case: unittest.TestCase,
    link: Path,
    target: Path | str,
    *,
    target_is_directory: bool = False,
) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as error:
        if os.name == 'nt' and getattr(error, 'winerror', None) == 1314:
            case.skipTest('Windows symlink creation privilege unavailable')
        raise
    except NotImplementedError:
        case.skipTest('symlink creation unsupported')
