# -*- coding: utf-8 -*-

import os
import platform
import sys
import traceback
from typing import ClassVar, Optional, Tuple

import pkg_resources
from coverage import CoveragePlugin
from coverage.config import CoverageConfig
from packaging import version


class _PythonVersionExclusionPlugin(CoveragePlugin):
    _rules_opt_name: ClassVar[str] = 'coverage_conditional_plugin:rules'
    _ignore_opt_name: ClassVar[str] = 'report:exclude_lines'

    def configure(self, config: CoverageConfig) -> None:
        """
        Main hook for adding extra configuration.

        Part of the ``coverage`` public API.
        Called right after ``coverage_init`` function.
        """
        rules = filter(
            bool,
            config.get_option(self._rules_opt_name).splitlines(),
        )
        for rule in rules:
            self._process_rule(config, rule)

    def _process_rule(self, config: CoverageConfig, rule: str) -> None:
        code, marker = [part.strip() for part in rule.rsplit(':', 1)]
        if self._should_be_applied(code[1:-1]):  # removes quotes
            self._ignore_marker(config, marker)

    def _should_be_applied(self, code: str) -> bool:
        """
        Determens whether some specific marker should be applied or not.

        Uses ``exec`` on the code you pass with the marker.
        Be sure, that this code is safe.

        We also try to provide useful global functions
        to cover the most popular cases, like:

        - python version
        - OS name, platform, and version
        - helpers to work with installed packages

        Some examples:

        .. code:: ini

          [coverage:coverage_conditional_plugin]
          rules =
            "sys_version_info >= (3, 8)": py-gte-38
            "is_installed('mypy')": has-mypy

        So, code marked with `# pragma: py-gte-38` will be ignored
        for all version of Python prior to 3.8 release.
        And at the same time,
        this code will be included to the coverage on 3.8+ releases.

        """
        try:
            return eval(code, {  # noqa: WPS421, S307
                # Feel free to send PRs that extend this dict:
                'sys_version_info': sys.version_info,
                'os_name': os.name,
                'os_environ': os.environ,
                'platform_system': platform.system(),
                'platform_release': platform.release(),
                'is_installed': _is_installed,
                'package_version': _package_version,
            })
        except Exception:
            print(  # noqa: T001
                'Exception during conditional coverage evaluation:',
                traceback.format_exc(),
            )
            return False

    def _ignore_marker(self, config: CoverageConfig, marker: str) -> None:
        """Adds a marker to the ignore list."""
        exclude_lines = config.get_option(self._ignore_opt_name)
        exclude_lines.append(marker)
        config.set_option(self._ignore_opt_name, exclude_lines)


def _is_installed(package: str) -> bool:
    """Helper function to detect if some package is installed."""
    try:
        __import__(package)  # noqa: WPS421
    except ImportError:
        return False
    else:
        return True


def _package_version(
    package: str,
) -> Optional[Tuple[int, ...]]:
    """
    Helper function that fetches distribution version.

    Can throw multiple exceptions.
    Be careful, use ``is_installed`` before using this one.

    Returns parsed varsion to be easily worked with.
    """
    return version.parse(
        pkg_resources.get_distribution(package).version,
    ).release


def coverage_init(reg, options) -> None:
    """
    Entrypoint, part of the ``coverage`` API.

    This is called when we specify:

    .. code:: ini

      [coverage:run]
      plugins =
        coverage_conditional_plugin

    See also:
        https://coverage.readthedocs.io/en/latest/plugins.html

    """
    reg.add_configurer(_PythonVersionExclusionPlugin())
