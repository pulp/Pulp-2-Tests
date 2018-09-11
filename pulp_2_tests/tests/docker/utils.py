# coding=utf-8
"""Utilities for Docker tests."""
import os
import json
from functools import partial
from unittest import SkipTest

from packaging.version import Version
from pulp_smash import cli, selectors, utils
from pulp_smash.pulp2 import utils as pulp2_utils

from pulp_2_tests.constants import (
    DOCKER_UPSTREAM_NAME,
    DOCKER_UPSTREAM_NAME_NOLIST,
)


def set_up_module():
    """Skip tests if Pulp 2 isn't under test or if Docker isn't installed."""
    pulp2_utils.require_pulp_2(SkipTest)
    pulp2_utils.require_issue_3159(SkipTest)
    pulp2_utils.require_issue_3687(SkipTest)
    pulp2_utils.require_unit_types({'docker_image'}, SkipTest)


def get_upstream_name(cfg):
    """Return a Docker upstream name.

    Return ``pulp_2_tests.constants.DOCKER_UPSTREAM_NAME_NOLIST`` if Pulp is
    older than version 2.14. Otherwise, return
    ``pulp_2_tests.constants.DOCKER_UPSTREAM_NAME``. See the documentation
    for those constants for more information.
    """
    if cfg.pulp_version < Version('2.14'):
        return DOCKER_UPSTREAM_NAME_NOLIST
    return DOCKER_UPSTREAM_NAME


def write_manifest_list(cfg, manifest_list):
    """Write out a content source to JSON file.

    :param cfg: The Pulp deployment on
        which to create a repository.
    :param manifest_list: A detailed dict of information about the manifest
        list.
    :return: The path to created file, and the path to dir that stores the
        file.
    """
    sudo = '' if cli.is_root(cfg) else 'sudo'
    client = cli.Client(cfg)
    dir_path = client.run('mktemp --directory'.split()).stdout.strip()
    file_path = os.path.join(dir_path, utils.uuid4() + '.json')
    manifest_list_json = json.dumps(manifest_list)
    # machine.session is used here to keep SSH session open
    client.machine.session().run(
        "{} echo '{}' > {}".format(
            sudo,
            manifest_list_json,
            file_path
        )
    )
    return file_path, dir_path


def os_is_f26(cfg, pulp_host=None):
    """Tell whether the given Pulp host's OS is F26."""
    return (utils.get_os_release_id(cfg, pulp_host) == 'fedora' and
            utils.get_os_release_version_id(cfg, pulp_host) == '26')


skip_if = partial(selectors.skip_if, exc=SkipTest)  # pylint:disable=invalid-name
"""The ``@skip_if`` decorator, customized for unittest.

``pulp_smash.selectors.skip_if`` is test runner agnostic. This function is
identical, except that ``exc`` has been set to ``unittest.SkipTest``.
"""
