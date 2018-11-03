# coding=utf-8
"""Tests for how well Pulp can deal with duplicate uploads.

This module targets `Pulp #1406`_ and `Pulp Smash #81`_. The test procedure is
as follows:

1. Create a new feed-less repository.
2. Upload content and import it into the repository. Assert the upload and
   import was successful.
3. Upload identical content and import it into the repository.

The second upload should silently fail for all Pulp releases in the 2.x series.

.. _Pulp #1406: https://pulp.plan.io/issues/1406
.. _Pulp Smash #81: https://github.com/PulpQE/pulp-smash/issues/81
"""
import unittest

from pulp_smash import api, utils, config
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import DuplicateUploadsMixin

from pulp_2_tests.constants import PUPPET_MODULE_URL_1
from pulp_2_tests.tests.puppet.api_v2.utils import gen_repo
from pulp_2_tests.tests.puppet.utils import set_up_module as setUpModule  # pylint:disable=unused-import


class DuplicateUploadsTestCase(unittest.TestCase, DuplicateUploadsMixin):
    """Test how well Pulp can deal with duplicate content unit uploads."""

    @classmethod
    def setUpClass(cls):
        """Create a Puppet repository."""
        cls.cfg = config.get_config()
        cls.resources = set()
        unit = utils.http_get(PUPPET_MODULE_URL_1)
        import_params = {'unit_type_id': 'puppet_module'}
        cls.client = api.Client(cls.cfg, api.json_handler)
        repo = cls.client.post(REPOSITORY_PATH, gen_repo())
        cls.upload_import_unit_args = (cls.cfg, unit, import_params, repo)
        cls.resources.add(repo['_href'])

    @classmethod
    def tearDownClass(cls):
        """Delete all resources named by ``resources``."""
        for resource in cls.resources:
            cls.client.delete(resource)
