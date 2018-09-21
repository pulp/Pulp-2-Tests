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
        _, update_list = self._set_repo_and_get_repo_data()

        # getting the update info from the fixtures repo
        update_info_fixtures = get_xml_content_from_fixture(
            fixture_path=RPM_WITH_MODULES_FEED_URL,
            data_type='updateinfo',
        )
        self.assertEqual(
            self._get_errata_rpm_mapping(update_list),
            self._get_errata_rpm_mapping(update_info_fixtures),
            'mismatch in the module packages.'
        )

    def test_collection_field(self):
        """Test the collection field in the update info.

        This test provides the following

        1. Check whether all the modules in the published repo
            contains a collection field.
        2. Check whether the collection field has proper name. The collection name computation
            is as below.

        The collection name is created using the information from fixtures that is stored in
        a set {<errata-id>:<module-name>}. First, the set information is used in computing
        a set ``collections_from_fixtures`` that maps the repo_id to the collection-name.
        The collection-name set is computed using the logic <repo-id>_<index>_<module-name>.
        The module name is ``default`` and the index is``0`` for ursine RPMs. The set is
        created using set-comprehension and x-path. After creating the set,
        it appears as in the example below.

        example :
        collections_from_fixtures = {
            'RHEA..1' : 'repo_id_1_duck',
            'RHEA..2' : 'repo_id_2_duck',
            'RHEA..3' : 'repo_id_0_default'
        }

        This set is compared against the collection-name from the published repo's ``updateinfo``.
        """
        repo, update_list = self._set_repo_and_get_repo_data()

        # getting the update info from the fixtures repo
        update_info_fixtures = get_xml_content_from_fixture(
            fixture_path=RPM_WITH_MODULES_FEED_URL,
            data_type='updateinfo',
        )

        # Errata ID to Collection name map in Updateinfo of published repo.
        collection_update_list = {
            update.find('./id').text: update.find('.//collection').attrib['short']
            for update in update_list.findall('update')
        }

        collections_from_fixtures = {
            update.find('id').text:
            'default' if update.find('.//module') is None
            else update.find('.//module').attrib['name']
            for update in
            update_info_fixtures.findall('.//update')
        }

        # ``indexes`` is used to increase the index of the module in the collections
        indexes = {}
        for key, val in collections_from_fixtures.items():
            if val in indexes:
                indexes[val] += 1
            else:
                indexes[val] = 1
            collections_from_fixtures[key] = (
                '{}_0_default'.format(repo['id'])
                if val == 'default'
                else '{}_{}_{}'.format(repo['id'], indexes[val], val)
            )

        self.assertEqual(
            collections_from_fixtures,
            collection_update_list,
            'collection names not proper'
        )

    def _set_repo_and_get_repo_data(self):
        """Create and Publish the required repo for this class.

        This method does the following:

        1. Create, Sync and Publish a repo with
            ``RPM_WITH_MODULES_FEED_URL``
        2. Get ``updateinfo`` xml of the published repo.

        :returns: A tuple containing the repo that is created, along with
            the ``updateinfo`` xml of the created repo.
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
        return repo, get_repodata(
            self.cfg,
            repo['distributors'][0], 'updateinfo'
        )

    @staticmethod
    def _get_errata_rpm_mapping(xml):
        mapper = {}
        for update in xml.findall('update'):
            temp = [package.text for package in update.findall('.//filename')]
            mapper[update.find('id').text] = temp
        return mapper
