# coding=utf-8
"""Tests that perform actions over modular Errata repositories."""
import unittest

from packaging.version import Version
from pulp_smash import api, config
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import sync_repo

from pulp_2_tests.constants import RPM_WITH_MODULES_FEED_URL
from pulp_2_tests.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    get_repodata,
    get_xml_content_from_fixture,
)


class ManageModularErrataTestCase(unittest.TestCase):
    """Manage Modular Errata content testcase.

    This test targets the following issue.

    `Pulp-2-Tests #94 <https://github.com/PulpQE/Pulp-2-Tests/issues/94>`_.
    """

    @classmethod
    def setUpClass(cls):
        """Create class wide variables."""
        cls.cfg = config.get_config()
        if cls.cfg.pulp_version < Version('2.17'):
            raise unittest.SkipTest('This test requires Pulp 2.17 or newer.')
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_sync_publish_update_info(self):
        """Test sync,publish of Modular RPM repo and checks the update info.

        This testcase reads the updateinfo of the repository that is published
        and compares that against the updateinfo.xml present in the rpm url.

        Steps involved:

        1. Create a repository with feed url containing modules.
        2. The repository should have a distributor to publish it.
        3. Once the repository is created, it is sync and published.
        4. Get the ``updateinfo`` from the repodata of the published repo.
        5. Compare this against the ``update_info.xml`` in the fixtures repo.
        """
        body = gen_repo(
            importer_config={'feed': RPM_WITH_MODULES_FEED_URL},
            distributors=[gen_distributor(auto_publish=True)]
        )
        repo = self.client.post(REPOSITORY_PATH, body)
        self.addCleanup(self.client.delete, repo['_href'])
        sync_repo(self.cfg, repo)

        # getting the update info from the published repo
        repo = self.client.get(repo['_href'], params={'details': True})
        update_list = get_repodata(
            self.cfg,
            repo['distributors'][0], 'updateinfo'
        )

        # getting the update info from the fixtures repo
        update_info_file = get_xml_content_from_fixture(
            fixture_path=RPM_WITH_MODULES_FEED_URL,
            data_type='updateinfo',
        )
        self.assertEqual(
            self._get_errata_rpm_mapping(update_list),
            self._get_errata_rpm_mapping(update_info_file),
            'mismatch in the module packages.'
        )

    @staticmethod
    def _get_errata_rpm_mapping(xml):
        mapper = {}
        for update in xml.findall('update'):
            temp = [package.text for package in update.findall('.//filename')]
            mapper[update.find('id').text] = temp
        return mapper
