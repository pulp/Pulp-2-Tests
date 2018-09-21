# coding=utf-8
"""Tests that perform actions over modular Errata repositories."""
import unittest
from urllib.parse import urljoin

from packaging.version import Version
from pulp_smash import api, config
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import (
    search_units,
    sync_repo,
)

from pulp_2_tests.constants import (
    RPM_WITH_MODULES_FEED_URL,
    MODULE_FIXTURES_ERRATA
)
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
           contains a collection field
        2. Check whether the collection field is unique
        """
        repo, update_list = self._set_repo_and_get_repo_data()

        # getting the update info from the fixtures repo
        update_info_fixtures = get_xml_content_from_fixture(
            fixture_path=RPM_WITH_MODULES_FEED_URL,
            data_type='updateinfo',
        )

        # collections from published repo
        collection_update_list = {
            update.find('./id').text: update.find('.//collection').attrib['short']
            for update in update_list.findall('update')
        }

        # collections from fixtures
        # the below dict comprehension computes the following
        # It gets the collection elements from the fixtures `updateinfo`,
        # gets the module names from each collection and maps it to update ID.
        # If module name doesn't exist, it replaces it as default
        # else module name is stored.
        # example : collections_from_fixtures = {
        #                                        'RHEA..1' : 'duck',
        #                                        'RHEA..2' : 'default'
        #                                       }
        collections_from_fixtures = {
            update.find('id').text:
            'default' if update.find('.//module') is None
            else update.find('.//module').attrib['name']
            for update in
            update_info_fixtures.findall('.//update')
        }
        # Adding repo_id, indexes and module_name for the collection
        # example : collections_from_fixtures = {
        #                                        'RHEA..1' : 'repo_id_1_duck',
        #                                        'RHEA..2' : 'repo_id_2_duck'
        #                                       }
        indexes = {}
        for key in collections_from_fixtures:
            val = collections_from_fixtures[key]
            if val in indexes:
                indexes[val] += 1
            else:
                indexes[val] = 1
            collections_from_fixtures[key] = '{}_0_default'.format(repo['id']) \
                if val == 'default' \
                else '{}_{}_{}'.format(repo['id'], indexes[val], val)

        self.assertEqual(
            collections_from_fixtures,
            collection_update_list,
            'collection names not proper'
        )

    def test_copy_errata(self):
        """Test whether Errata modules are copied.

        This Test does the following.

        1. It creates,syncs, and publishes a modules rpm repository
        2. Creates another repo with no feed
        3. Recursively copies an errata from one repo to another
        4. Checks whether the errata information in the new repo is
        correct
        """
        repo_1, _ = self._set_repo_and_get_repo_data()

        # Creating an empty repo2
        body = gen_repo(distributors=[gen_distributor(auto_publish=True)])
        repo_2 = self.client.post(REPOSITORY_PATH, body)
        self.addCleanup(self.client.delete, repo_2['_href'])

        criteria = {
            'filters': {
                'unit': {
                    'id': MODULE_FIXTURES_ERRATA['errata_id']
                }},
            'type_ids': ['erratum']
        }

        # Copy errata data recursively from repo1 to repo2
        self.client.post(urljoin(repo_2['_href'], 'actions/associate/'), {
            'source_repo_id': repo_1['id'],
            'override_config': {'recursive': True},
            'criteria': criteria
        })
        repo_2 = self.client.get(repo_2['_href'], params={'details': True})

        self.assertEqual(
            repo_2['total_repository_units'],
            MODULE_FIXTURES_ERRATA['total_available_units'],
            repo_2
        )

        self.assertEqual(
            search_units(self.cfg, repo_1, criteria)[0]['metadata']['pkglist'],
            search_units(self.cfg, repo_2, criteria)[0]['metadata']['pkglist'],
            'Copied erratum doesn''t contain the same module/rpms'
        )

    def _set_repo_and_get_repo_data(self):
        """Create and Publish the required repo for this class.

        This method does the following:
        1. Create, Sync and Publish a repo with
            ``RPM_WITH_MODULES_FEED_URL``
        2. get ``updateinfo`` xml of the published repo.
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
