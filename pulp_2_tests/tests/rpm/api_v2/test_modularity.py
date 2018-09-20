# coding=utf-8
"""Tests that perform actions over RPM modular repositories."""
import unittest
from urllib.parse import urljoin
from xml.etree import ElementTree

from packaging.version import Version
from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import (
    publish_repo,
    sync_repo,
    upload_import_unit,
)

from pulp_2_tests.constants import (
    MODULE_FIXTURES_PACKAGES,
    MODULE_FIXTURES_PACKAGE_STREAM,
    RPM_NAMESPACES,
    RPM_UNSIGNED_FEED_URL,
    RPM_WITH_MODULES_FEED_URL,
)
from pulp_2_tests.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    get_repodata,
)
from pulp_2_tests.tests.rpm.utils import (
    gen_yum_config_file,
    os_support_modularity,
)
from pulp_2_tests.tests.rpm.utils import set_up_module as setUpModule  # pylint:disable=unused-import


class ManageModularContentTestCase(unittest.TestCase):
    """Manage modular content tests cases.

    This test targets the following issue:

    `Pulp Smash #1122 <https://github.com/PulpQE/pulp-smash/issues/1122>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class wide variables."""
        cls.cfg = config.get_config()
        if cls.cfg.pulp_version < Version('2.17'):
            raise unittest.SkipTest('This test requires Pulp 2.17 or newer.')
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_sync_publish_repo(self):
        """Test sync and publish modular RPM repository."""
        repo = self.create_sync_modular_repo()
        # Assert that `modulemd` and `modulemd_defaults` are present on the
        # repository.
        self.assertIsNotNone(repo['content_unit_counts']['modulemd'])
        self.assertIsNotNone(repo['content_unit_counts']['modulemd_defaults'])

        publish_repo(self.cfg, repo)

        get_repodata(
            self.cfg,
            repo['distributors'][0],
            'modules',
            api.safe_handler,
        )

    def test_copy_modulemd_recur(self):
        """Test copy of modulemd in RPM repository in recursive mode."""
        criteria = {
            'filters': {'unit': {
                'name': MODULE_FIXTURES_PACKAGE_STREAM['name'],
                'stream': MODULE_FIXTURES_PACKAGE_STREAM['stream']
            }},
            'type_ids': ['modulemd'],
        }
        repo = self.copy_content_between_repos(True, criteria)
        self.assertEqual(repo['content_unit_counts']['modulemd'], 1)
        self.assertEqual(
            repo['content_unit_counts']['rpm'],
            MODULE_FIXTURES_PACKAGE_STREAM['rpm_count'],
            repo['content_unit_counts']['rpm']
        )
        self.assertEqual(
            repo['total_repository_units'],
            MODULE_FIXTURES_PACKAGE_STREAM['total_available_units'],
            repo['total_repository_units']
        )

    def test_copy_modulemd_non_recur(self):
        """Test copy of modulemd in RPM repository in non recursive mode."""
        criteria = {
            'filters': {'unit': {
                'name': MODULE_FIXTURES_PACKAGE_STREAM['name'],
                'stream': MODULE_FIXTURES_PACKAGE_STREAM['stream']
            }},
            'type_ids': ['modulemd'],
        }
        repo = self.copy_content_between_repos(False, criteria)
        self.assertEqual(
            repo['content_unit_counts']['modulemd'],
            1,
            repo['content_unit_counts']['modulemd']
        )
        self.assertEqual(
            repo['total_repository_units'],
            1,
            repo['total_repository_units']
        )
        self.assertNotIn('rpm', repo['content_unit_counts'])

    def test_copy_modulemd_defaults(self):
        """Test copy of modulemd_defaults in RPM repository."""
        criteria = {
            'filters': {},
            'type_ids': ['modulemd_defaults'],
        }
        repo = self.copy_content_between_repos(True, criteria)
        self.assertEqual(
            repo['content_unit_counts']['modulemd_defaults'],
            3,
            repo['content_unit_counts'])
        self.assertEqual(
            repo['total_repository_units'],
            3,
            repo['total_repository_units']
        )
        self.assertNotIn('rpm', repo['content_unit_counts'])

    def create_sync_modular_repo(self):
        """Create a repo with feed pointing to modular data and sync it.

        :returns: repo data that is created and synced with modular content.
        """
        body = gen_repo()
        body['importer_config']['feed'] = RPM_WITH_MODULES_FEED_URL
        body['distributors'] = [gen_distributor()]
        repo = self.client.post(REPOSITORY_PATH, body)
        self.addCleanup(self.client.delete, repo['_href'])
        sync_repo(self.cfg, repo)
        return self.client.get(repo['_href'], params={'details': True})

    def copy_content_between_repos(self, recursive, criteria):
        """Create two repos and copy content between them."""
        # repo1
        repo1 = self.create_sync_modular_repo()

        # repo2
        body = gen_repo()
        repo2 = self.client.post(REPOSITORY_PATH, body)
        self.addCleanup(self.client.delete, repo2['_href'])
        repo2 = self.client.get(repo2['_href'], params={'details': True})

        # Copy repo1 to repo2
        self.client.post(
            urljoin(repo2['_href'], 'actions/associate/'),
            {
                'source_repo_id': repo1['id'],
                'override_config': {'recursive': recursive},
                'criteria': criteria
            }
        )
        return self.client.get(repo2['_href'], params={'details': True})

    def test_remove_modulemd(self):
        """Test sync and remove modular RPM repository."""
        if not selectors.bug_is_fixed(3985, self.cfg.pulp_version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/3985')
        repo_initial = self.create_sync_modular_repo()
        criteria = {
            'filters': {'unit': {
                'name': MODULE_FIXTURES_PACKAGE_STREAM['name'],
                'stream': MODULE_FIXTURES_PACKAGE_STREAM['stream']
            }},
            'type_ids': ['modulemd'],
        }
        repo = self.remove_module_from_repo(repo_initial, criteria)
        self.assertEqual(
            repo['content_unit_counts']['modulemd'],
            repo_initial['content_unit_counts']['modulemd'] - 1,
            repo['content_unit_counts'])
        # after removing a module 'X', the number of rpms in the repo should
        # decrease by the number of rpms present in 'X'.
        self.assertEqual(
            repo['content_unit_counts']['rpm'],
            repo_initial['content_unit_counts']['rpm'] - 1,
            repo['content_unit_counts'])
        self.assertIsNotNone(
            repo['last_unit_removed'],
            repo['last_unit_removed']
        )

    def test_remove_modulemd_defaults(self):
        """Test sync and remove modular RPM repository."""
        repo_initial = self.create_sync_modular_repo()
        criteria = {
            'filters': {},
            'type_ids': ['modulemd_defaults'],
        }
        repo = self.remove_module_from_repo(repo_initial, criteria)
        self.assertNotIn(
            'modulemd_defaults',
            repo['content_unit_counts'],
            repo['content_unit_counts'])

        self.assertEqual(
            repo['total_repository_units'],
            (repo_initial['total_repository_units'] -
             repo_initial['content_unit_counts']['modulemd_defaults']),
            repo['total_repository_units']
        )
        self.assertIsNotNone(
            repo['last_unit_removed'],
            repo['last_unit_removed']
        )

    def remove_module_from_repo(self, repo, criteria):
        """Remove modules from repo."""
        self.client.post(
            urljoin(repo['_href'], 'actions/unassociate/'),
            {'criteria': criteria}
        )
        return self.client.get(repo['_href'], params={'details': True})


class PackageManagerModuleListTestCase(unittest.TestCase):
    """Package manager can read module list from a Pulp repo."""

    def test_all(self):
        """Verify whether package manager can read module list from a Pulp repo."""
        cfg = config.get_config()
        if cfg.pulp_version < Version('2.17'):
            raise unittest.SkipTest('This test requires at least Pulp 2.17 or newer.')
        if not os_support_modularity(cfg):
            raise unittest.SkipTest('This test requires an OS that supports modularity.')
        client = api.Client(cfg, api.json_handler)
        body = gen_repo(
            importer_config={'feed': RPM_WITH_MODULES_FEED_URL},
            distributors=[gen_distributor()]
        )

        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        sync_repo(cfg, repo)
        publish_repo(cfg, repo)
        repo = client.get(repo['_href'], params={'details': True})
        repo_path = gen_yum_config_file(
            cfg,
            baseurl=urljoin(cfg.get_base_url(), urljoin(
                'pulp/repos/',
                repo['distributors'][0]['config']['relative_url']
            )),
            name=repo['_href'],
            repositoryid=repo['id']
        )
        cli_client = cli.Client(cfg)
        self.addCleanup(cli_client.run, ('rm', repo_path), sudo=True)
        lines = cli_client.run((
            ('dnf', 'module', 'list', '--all')
        ), sudo=True).stdout.splitlines()
        for key, value in MODULE_FIXTURES_PACKAGES.items():
            with self.subTest(package=key):
                module = [line for line in lines if key in line]
                self.assertEqual(len(module), value, module)


class UploadModuleTestCase(unittest.TestCase):
    """Upload a module.yaml file and test upload import in Pulp repo."""

    @classmethod
    def setUpClass(cls):
        """Create class wide variables."""
        cls.cfg = config.get_config()
        if cls.cfg.pulp_version < Version('2.17'):
            raise unittest.SkipTest('This test requires Pulp 2.17 or newer.')
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_upload_module(self):
        """Verify whether uploaded module.yaml is reflected in the pulp repo."""
        # Create a normal Repo without any data.
        body = gen_repo(
            importer_config={'feed': RPM_UNSIGNED_FEED_URL},
            distributors=[gen_distributor()]
        )
        repo = self.client.post(REPOSITORY_PATH, body)
        repo = self.client.get(repo['_href'], params={'details': True})
        self.addCleanup(self.client.delete, repo['_href'])
        sync_repo(self.cfg, repo)

        # download modules.yaml and upload it to pulp_repo
        unit = self._get_module_yaml_file(RPM_WITH_MODULES_FEED_URL)
        upload_import_unit(self.cfg, unit, {
            'unit_key': {},
            'unit_type_id': 'modulemd',
        }, repo)
        repo = self.client.get(repo['_href'], params={'details': True})
        # Assert that `modulemd` and `modulemd_defaults` are present on the
        # repository.
        self.assertIsNotNone(repo['content_unit_counts']['modulemd'])
        self.assertIsNotNone(repo['content_unit_counts']['modulemd_defaults'])

    def test_one_default_per_repo(self):
        """Verify changing the modules default content of modules.yaml do not affects repo."""
        # create repo
        body = gen_repo(
            importer_config={'feed': RPM_WITH_MODULES_FEED_URL},
            distributors=[gen_distributor()]
        )
        repo = self.client.post(REPOSITORY_PATH, body)
        repo = self.client.get(repo['_href'], params={'details': True})
        self.addCleanup(self.client.delete, repo['_href'])
        sync_repo(self.cfg, repo)

        # Modify Modules.yaml and upload
        unit = self._get_module_yaml_file(RPM_WITH_MODULES_FEED_URL)
        unit_string = unit.decode('utf-8')
        unit_string = unit_string.replace(
            'stream: {}'.format(MODULE_FIXTURES_PACKAGE_STREAM['stream']),
            'stream: {}'.format(MODULE_FIXTURES_PACKAGE_STREAM['new_stream'])
        )
        unit = unit_string.encode()
        upload_import_unit(self.cfg, unit, {
            'unit_key': {},
            'unit_type_id': 'modulemd',
        }, repo)
        repo = self.client.get(repo['_href'], params={'details': True})
        self.assertEqual(
            repo['content_unit_counts']['modulemd_defaults'],
            3,
            repo['content_unit_counts'])

    @staticmethod
    def _get_module_yaml_file(path):
        """Return the path to ``modules.yaml``, relative to repository root.

        Given a detailed dict of information about a published, repository,
        parse that repository's ``repomd.xml`` file and tell the path to the
        repository's ``[…]-modules.yaml`` file. The path is likely to be in the
        form ``repodata/[…]-modules.yaml.gz``.
        """
        repo_path = urljoin(path, 'repodata/repomd.xml')
        response = utils.http_get(repo_path)
        root_elem = ElementTree.fromstring(response)

        # <ns0:repomd xmlns:ns0="http://linux.duke.edu/metadata/repo">
        #     <ns0:data type="modules">
        #         <ns0:checksum type="sha256">[…]</ns0:checksum>
        #         <ns0:location href="repodata/[…]-modules.yaml.gz" />
        #         …
        #     </ns0:data>
        #     …

        xpath = '{{{}}}data'.format(RPM_NAMESPACES['metadata/repo'])
        data_elements = [
            elem for elem in root_elem.findall(xpath)
            if elem.get('type') == 'modules'
        ]
        xpath = '{{{}}}location'.format(RPM_NAMESPACES['metadata/repo'])
        relative_path = data_elements[0].find(xpath).get('href')
        unit = utils.http_get(urljoin(path, relative_path))
        return unit
