# coding=utf-8
"""Tests that perform actions over modular Errata repositories."""
import unittest
from collections import defaultdict
from urllib.parse import urljoin

from packaging.version import Version
from pulp_smash import api, config, utils
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import (
    publish_repo,
    search_units,
    sync_repo,
    upload_import_erratum,
    upload_import_unit,
)

from pulp_2_tests.constants import (
    MODULE_ERRATA_RPM_DATA,
    MODULE_FIXTURES_ERRATA,
    RPM_MODULAR_OLD_VERSION_URL,
    RPM_WITH_MODULES_FEED_COUNT,
    RPM_WITH_MODULES_FEED_URL,
)
from pulp_2_tests.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    get_repodata,
    get_xml_content_from_fixture
)
from pulp_2_tests.tests.rpm.utils import check_issue_4405


class ManageModularErrataTestCase(unittest.TestCase):
    """Manage Modular Errata content testcase.

    This test targets the following issues:

    * `Pulp-2-Tests #94 <https://github.com/PulpQE/Pulp-2-Tests/issues/94>`_.
    * `Pulp #3919 <https://pulp.plan.io/issues/3919>`_

    """

    @classmethod
    def setUpClass(cls):
        """Create class wide variables."""
        cls.cfg = config.get_config()
        if cls.cfg.pulp_version < Version('2.18'):
            raise unittest.SkipTest('This test requires Pulp 2.18 or newer.')
        if check_issue_4405(cls.cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/4405')
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_sync_publish_update_info(self):
        """Test sync,publish of Modular RPM repo and checks the update info.

        This testcase reads the updateinfo of the repository that is published
        and compares that against the ``updateinfo.xml`` present in the feed
        url.

        Steps involved:

        1. Create a repository with feed url containing modules.
        2. The repository should have a distributor to publish it.
        3. Once the repository is created, it is synced and published.
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

        This test provides the following:

        1. Check whether all the modules in the published repo contains a
           collection field.
        2. Check whether the collection field has proper name. The collection
           name computation is as below.

        The collection name is created using the information from fixtures that
        is stored in a set ``{<errata-id>:<module-name>}``.

        First, the set information is used in computing a set
        ``collections_from_fixtures`` that maps the repo_id to the
        collection-name.

        The collection-name set is computed using the logic
        ``<repo-id>_<index>_<module-name>``.  The module name is ``default``
        and the index is 0 for ursine RPMs.

        The set is created using set-comprehension and x-path. After creating
        the set, it appears as in the example below.

        .. code:: python

            collections_from_fixtures = {
                'RHEA..1' : 'repo_id_1_duck',
                'RHEA..2' : 'repo_id_2_duck',
                'RHEA..3' : 'repo_id_0_default'
            }

        This set is compared against the collection-name from the published
        repo's ``updateinfo``.
        """
        repo, update_list = self._set_repo_and_get_repo_data()

        # getting the updateinfo from the fixtures repo
        update_info_fixtures = get_xml_content_from_fixture(
            fixture_path=RPM_WITH_MODULES_FEED_URL,
            data_type='updateinfo',
        )

        # Errata ID to collection name map in updateinfo of published repo.
        collection_update_list = {
            update.find('./id').text:
            update.find('.//collection').attrib['short']
            for update in update_list.findall('update')
        }

        collections_from_fixtures = {
            update.find('id').text:
            'default' if update.find('.//module') is None
            else update.find('.//module').attrib['name']
            for update in
            update_info_fixtures.findall('.//update')
        }

        # indexes is used to increase the index of the module in the
        # collections
        indexes = defaultdict(lambda: 1)
        for key, val in tuple(collections_from_fixtures.items()):
            if val in indexes:
                indexes[val] += 1
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

    def test_search_errata(self):
        """Test whether ``updateinfo.xml`` has errata with modular information.

        This test does the following:

        1. Create and sync a repo with ``RPM_WITH_MODULES_FEED_URL``.
        2. Check whether ``updateinfo.xml`` has an errata with modules.
        3. Check whether search api returns modular content.
        3. Check whether search api returns modular erratum content.

        This test case targets:

        * `Pulp #4112 <https://pulp.plan.io/issues/4112>`_.
        """
        if self.cfg.pulp_version < Version('2.19'):
            raise unittest.SkipTest('This test requires Pulp 2.19 or newer.')

        # Step 1
        body = gen_repo(
            importer_config={'feed': RPM_WITH_MODULES_FEED_URL},
            distributors=[gen_distributor(auto_publish=True)]
        )
        repo = self.client.post(REPOSITORY_PATH, body)
        sync_repo(self.cfg, repo)
        self.addCleanup(self.client.delete, repo['_href'])
        repo = self.client.get(repo['_href'], params={'details': True})
        # Step 2
        update_info_file = get_repodata(
            self.cfg,
            repo['distributors'][0],
            'updateinfo'
        )
        modules = [
            dict(module.items())
            for module
            in update_info_file.findall('.//module')
        ]
        self.assertEqual(len(modules), RPM_WITH_MODULES_FEED_COUNT, modules)
        expected_fields = {'stream', 'version', 'arch', 'context', 'name'}
        self.assertTrue(
            all([expected_fields == set(module.keys()) for module in modules]),
            modules
        )
        # Step 3
        modular_units = search_units(
            self.cfg,
            repo,
            {'filters': {'unit': {'is_modular': True}}, 'type_ids': ['rpm']}
        )
        self.assertTrue(
            all(
                [
                    module
                    for module in modular_units
                    if module['repo_id'] == repo['id']
                ]
            ),
            modular_units
        )
        # Step 4
        erratum_units = search_units(
            self.cfg,
            repo,
            {
                'filters': {'unit': {'is_modular': True}},
                'type_ids': ['erratum']
            }
        )
        self.assertTrue(
            all(
                [
                    erratum
                    for erratum in erratum_units
                    if erratum['repo_id'] == repo['id']
                ]
            ),
            erratum_units
        )

    def test_copy_errata(self):
        """Test whether Errata modules are copied.

        This test does the following:

        1. It creates, syncs, and publishes a modules rpm repository.
        2. Creates another repo with no feed.
        3. Recursively copies an errata from one repo to another.
        4. Checks whether the errata information in the new repo is
           correct.
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

    def test_upload_errata(self):
        """Upload errata and check whether it got published in the repo.

        This test does the following:

        1. Create and sync a repo with ``RPM_WITH_MODULES_FEED_URL``.
        2. Upload a custom modular erratum to the repo. The custom
           module erratum is obtained from ``_get_erratum()``. Make sure that
           the erratum uploaded has a corresponding module in the feed url.
        3. Publish the repo after uploading the custom erratum.
        4. Verify whether the uploaded erratum is present in the
           published repo and also contains the modules in it.
        """
        # Step 1
        body = gen_repo(
            importer_config={'feed': RPM_WITH_MODULES_FEED_URL},
            distributors=[gen_distributor()]
        )
        repo_initial = self.client.post(REPOSITORY_PATH, body)
        self.addCleanup(self.client.delete, repo_initial['_href'])
        sync_repo(self.cfg, repo_initial)
        # getting the update info from the published repo
        repo_initial = self.client.get(
            repo_initial['_href'],
            params={'details': True}
        )

        # Step 2
        unit = self._gen_modular_errata()
        upload_import_erratum(self.cfg, unit, repo_initial)
        repo = self.client.get(
            repo_initial['_href'],
            params={'details': True}
        )

        # Step 3
        publish_repo(
            self.cfg, repo,
            {
                'id': repo['distributors'][0]['id'],
                'override_config': {'force_full': True},
            })

        # Step 4
        # upload_info_file - The ``uploadinfo.xml`` of the published repo.
        update_info_file = get_repodata(
            self.cfg,
            repo['distributors'][0],
            'updateinfo'
        )

        # errata_upload - get the errata is uploaded in step 2
        # from the updateinfo.xml.
        errata_upload = [
            update
            for update in update_info_file.findall('update')
            if update.find('id').text == unit['id']
        ]

        self.assertEqual(
            repo_initial['content_unit_counts']['erratum'] + 1,
            repo['content_unit_counts']['erratum'],
            'Erratum count mismatch after uploading.'
        )
        self.assertGreater(len(errata_upload), 0)
        self.assertIsNotNone(errata_upload[0].find('.//module'))

    def _set_repo_and_get_repo_data(self):
        """Create and Publish the required repo for this class.

        This method does the following:

        1. Create, sync and publish a repo with
           ``RPM_WITH_MODULES_FEED_URL``
        2. Get ``updateinfo.xml`` of the published repo.

        :returns: A tuple containing the repo that is created, along with
            the ``updateinfo.xml`` of the created repo.
        """
        body = gen_repo(
            importer_config={'feed': RPM_WITH_MODULES_FEED_URL},
            distributors=[gen_distributor(auto_publish=True)]
        )
        repo = self.client.post(REPOSITORY_PATH, body)
        self.addCleanup(self.client.delete, repo['_href'])
        sync_repo(self.cfg, repo)

        # getting the updateinfo from the published repo
        repo = self.client.get(repo['_href'], params={'details': True})
        return repo, get_repodata(
            self.cfg,
            repo['distributors'][0], 'updateinfo'
        )

    @staticmethod
    def _get_errata_rpm_mapping(xml):
        mapper = {}
        for update in xml.findall('update'):
            mapper[update.find('id').text] = [
                package.text for package in update.findall('.//filename')
            ]
        return mapper

    @staticmethod
    def _gen_modular_errata():
        """Generate and return a modular erratum with a unique ID."""
        return {
            'id': utils.uuid4(),
            'status': 'stable',
            'updated': MODULE_ERRATA_RPM_DATA['updated'],
            'rights': None,
            'from': MODULE_ERRATA_RPM_DATA['from'],
            'description': MODULE_ERRATA_RPM_DATA['description'],
            'title': MODULE_ERRATA_RPM_DATA['rpm_name'],
            'issued': MODULE_ERRATA_RPM_DATA['issued'],
            'relogin_suggested': False,
            'restart_suggested': False,
            'solution': None,
            'summary': None,
            'pushcount': '1',
            'version': '1',
            'references': [],
            'release': '1',
            'reboot_suggested': None,
            'type': 'enhancement',
            'severity': None,
            'pkglist': [{
                'name': MODULE_ERRATA_RPM_DATA['collection_name'],
                'short': '0',
                'module': {
                    'name': MODULE_ERRATA_RPM_DATA['rpm_name'],
                    'stream': MODULE_ERRATA_RPM_DATA['stream_name'],
                    'version': MODULE_ERRATA_RPM_DATA['version'],
                    'arch': MODULE_ERRATA_RPM_DATA['arch'],
                    'context': MODULE_ERRATA_RPM_DATA['context']
                },
                'packages': []
            }]
        }


class ModularErrataCopyTestCase(unittest.TestCase):
    """Test ``recursive`` and ``recursive_conservative`` flags during copy.

    This test targets the following issues:

    * `Pulp #4518 <https://pulp.plan.io/issues/4518>`_
    * `Pulp #4548 <https://pulp.plan.io/issues/4548>`_

    Recursive copy of ``RHEA-2012:0059`` should copy:

    * 2 modules: ``duck`` and ``kangaroo``.
    * 2 RPMS: ``kangaroo-0.3-1.noarch.rpm``, and ``duck-0.7-1.noarch.rpm``.

    Exercise the use of ``recursive`` and ``recursive_conservative``.
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        if cls.cfg.pulp_version < Version('2.19'):
            raise unittest.SkipTest('This test requires Pulp 2.19 or newer.')
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_recursive_noconservative_nodependency(self):
        """Recursive, non-conservative, and no old dependency."""
        repo = self.copy_modular_errata(True, False)
        self.make_assertions_nodependency(repo)

    def test_recursive_conservative_nodepdendency(self):
        """Recursive, conservative, and no old dependency."""
        repo = self.copy_modular_errata(True, True)
        self.make_assertions_nodependency(repo)

    def test_norecursive_conservative_nodepdendency(self):
        """Non-Recursive, conservative, and no old dependency."""
        repo = self.copy_modular_errata(False, True)
        self.make_assertions_nodependency(repo)

    def test_recursive_noconservative_dependency(self):
        """Recursive, non-conservative, and older version of RPM present."""
        repo = self.copy_modular_errata(True, False, True)
        self.make_assertions_dependency(repo)

    def test_norecursive_conservative_dependency(self):
        """Non-recursive, conservative, and older version of RPM present."""
        repo = self.copy_modular_errata(False, True, True)
        self.make_assertions_dependency(repo)

    def make_assertions_dependency(self, repo):
        """Make assertions over a repo with an older version of RPM present."""
        versions = sorted([
            unit['metadata']['version']
            for unit in search_units(self.cfg, repo, {'type_ids': ['rpm']})
            if unit['metadata']['name'] == 'duck'
        ])

        # 2 due to the older version already present on the repository.
        self.assertEqual(len(versions), 2, versions)

        self.assertEqual(
            repo['content_unit_counts']['erratum'],
            MODULE_FIXTURES_ERRATA['errata_count'],
            repo['content_unit_counts']
        )

        self.assertEqual(
            repo['content_unit_counts']['modulemd'],
            MODULE_FIXTURES_ERRATA['modules_count'],
            repo['content_unit_counts']
        )

        # older RPM package already present has to be added to total of RPM
        # packages after copy.
        self.assertEqual(
            repo['total_repository_units'],
            MODULE_FIXTURES_ERRATA['total_available_units'] + 1,
            repo
        )

    def make_assertions_nodependency(self, repo):
        """Make assertions over a repo without an older version RPM present."""
        self.assertEqual(
            repo['content_unit_counts']['erratum'],
            MODULE_FIXTURES_ERRATA['errata_count'],
            repo['content_unit_counts']
        )

        self.assertEqual(
            repo['content_unit_counts']['modulemd'],
            MODULE_FIXTURES_ERRATA['modules_count'],
            repo['content_unit_counts']
        )

        self.assertEqual(
            repo['total_repository_units'],
            MODULE_FIXTURES_ERRATA['total_available_units'],
            repo
        )

    def copy_modular_errata(
            self, recursive, recursive_conservative, old_dependency=False
    ):
        """Copy modular errata."""
        repos = []
        body = gen_repo(
            importer_config={'feed': RPM_WITH_MODULES_FEED_URL},
            distributors=[gen_distributor()]
        )
        repos.append(self.client.post(REPOSITORY_PATH, body))
        self.addCleanup(self.client.delete, repos[0]['_href'])
        sync_repo(self.cfg, repos[0])
        repos.append(self.client.post(REPOSITORY_PATH, gen_repo()))
        self.addCleanup(self.client.delete, repos[1]['_href'])

        override_config = {
            'recursive': recursive,
            'recursive_conservative': recursive_conservative
        }
        if old_dependency:
            rpm = utils.http_get(RPM_MODULAR_OLD_VERSION_URL)
            upload_import_unit(
                self.cfg,
                rpm,
                {'unit_type_id': 'rpm'}, repos[1]
            )
            units = search_units(self.cfg, repos[1], {'type_ids': ['rpm']})
            self.assertEqual(len(units), 1, units)

        self.client.post(urljoin(repos[1]['_href'], 'actions/associate/'), {
            'source_repo_id': repos[0]['id'],
            'override_config': override_config,
            'criteria': {
                'filters': {
                    'unit': {
                        'id': MODULE_FIXTURES_ERRATA['errata_id']
                    },
                },
                'type_ids': ['erratum'],
            },
        },)
        return self.client.get(repos[1]['_href'], params={'details': True})
