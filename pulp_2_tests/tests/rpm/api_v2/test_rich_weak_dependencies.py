# coding=utf-8
"""Test actions over repositories with rich and weak dependencies."""
import unittest

from packaging.version import Version
from pulp_smash import api, config
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import publish_repo, sync_repo

from pulp_2_tests.constants import (
    RPM_RICH_WEAK_FEED_URL,
    SRPM_RICH_WEAK_FEED_URL,
)
from pulp_2_tests.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_2_tests.tests.rpm.utils import set_up_module as setUpModule  # pylint:disable=unused-import


class SyncPublishTestCase(unittest.TestCase):
    """Sync and publish a repository with rich and weak dependencies."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        if cls.cfg.pulp_version < Version('2.17'):
            raise unittest.SkipTest('This test requires Pulp 2.17 or newer.')
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_rpm(self):
        """Sync and publish an RPM repo. See :meth:`do_test`."""
        self.do_test(RPM_RICH_WEAK_FEED_URL)

    def test_srpm(self):
        """Sync and publish an SRPM repo. See :meth:`do_test`."""
        self.do_test(SRPM_RICH_WEAK_FEED_URL)

    def do_test(self, feed):
        """Sync and publish a repository with rich and weak dependencies.

        This test targets the following issue:

        `Pulp Smash #901 <https://github.com/PulpQE/pulp-smash/issues/901>`_.
        """
        body = gen_repo(
            importer_config={'feed': feed},
            distributors=[gen_distributor()]
        )
        repo = self.client.post(REPOSITORY_PATH, body)
        self.addCleanup(self.client.delete, repo['_href'])
        sync_repo(self.cfg, repo)
        repo = self.client.get(repo['_href'], params={'details': True})
        with self.subTest(comment='verify last_publish after sync'):
            self.assertIsNone(repo['distributors'][0]['last_publish'])
        publish_repo(self.cfg, repo)
        repo = self.client.get(repo['_href'], params={'details': True})
        with self.subTest(comment='verify last_publish after publish'):
            self.assertIsNotNone(repo['distributors'][0]['last_publish'])
