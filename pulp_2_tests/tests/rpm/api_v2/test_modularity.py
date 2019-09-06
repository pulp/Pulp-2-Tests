# coding=utf-8
# pylint:disable=too-many-lines
"""Tests that perform actions over RPM modular repositories."""
import gzip
import io
import unittest
from collections import defaultdict
from types import MappingProxyType
from urllib.parse import urljoin
from xml.etree import ElementTree

import pytest
from jsonschema import validate
from packaging.version import Version

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.pulp2.constants import (
    CONSUMERS_ACTIONS_CONTENT_REGENERATE_APPLICABILITY_PATH,
    CONSUMERS_CONTENT_APPLICABILITY_PATH,
    CONSUMERS_PATH,
    REPOSITORY_PATH,
)

from pulp_smash.pulp2.utils import (
    publish_repo,
    search_units,
    sync_repo,
    upload_import_erratum,
    upload_import_unit,
)

from pulp_2_tests.constants import (
    MODULE_ARTIFACT_RPM_DATA,
    MODULE_ARTIFACT_RPM_DATA_2,
    MODULE_DATA_2,
    MODULE_ERRATA_RPM_DATA,
    MODULE_FIXTURES_DUCK_4_STREAM,
    MODULE_FIXTURES_DUCK_5_STREAM,
    MODULE_FIXTURES_DUCK_6_STREAM,
    MODULE_FIXTURES_ERRATA,
    MODULE_FIXTURES_PACKAGES,
    MODULE_FIXTURES_PACKAGE_STREAM,
    RPM_DATA,
    RPM_MODULAR_OLD_VERSION_URL,
    RPM_NAMESPACES,
    RPM_UNSIGNED_FEED_COUNT,
    RPM_UNSIGNED_FEED_URL,
    RPM_WITH_MODULAR_URL,
    RPM_WITH_MODULES_FEED_COUNT,
    RPM_WITH_MODULES_FEED_URL,
    RPM_WITH_MODULES_SHA1_FEED_URL,
    RPM_WITH_OLD_VERSION_URL,
    RPM_WITH_VENDOR_URL,
)
from pulp_2_tests.tests.rpm.api_v2.utils import (
    gen_consumer,
    gen_distributor,
    gen_repo,
    get_repodata,
    get_repodata_repomd_xml,
    get_xml_content_from_fixture,
)
from pulp_2_tests.tests.rpm.utils import (
    check_issue_4405,
    gen_yum_config_file,
    os_support_modularity,
)

pytestmark = pytest.mark.recursive_conservative  # pylint:disable=invalid-name


# MappingProxyType is used to make an immutable dict.
MODULES_METADATA = MappingProxyType({
    'name': MODULE_ERRATA_RPM_DATA['rpm_name'],
    'stream': MODULE_ERRATA_RPM_DATA['stream_name'],
    'version': MODULE_ERRATA_RPM_DATA['version'],
    'context': MODULE_ERRATA_RPM_DATA['context'],
    'arch': MODULE_ERRATA_RPM_DATA['arch'],
})
"""Metadata for a Module."""

MODULES_METADATA_2 = MappingProxyType({
    'name': MODULE_DATA_2['name'],
    'stream': MODULE_DATA_2['stream'],
    'version': MODULE_DATA_2['version'],
    'context': MODULE_DATA_2['context'],
    'arch': MODULE_DATA_2['arch'],
})
"""Metadata for another Module."""

# MappingProxyType is used to make an immutable dict.
RPM_WITH_ERRATUM_METADATA = MappingProxyType({
    'name': RPM_DATA['name'],
    'epoch': RPM_DATA['epoch'],
    'version': RPM_DATA['version'],
    'release': int(RPM_DATA['release']),
    'arch': RPM_DATA['arch'],
    'vendor': RPM_DATA['metadata']['vendor'],
})
"""Metadata for an RPM with an associated erratum."""

CONTENT_APPLICABILITY_REPORT_SCHEMA = {
    '$schema': 'http://json-schema.org/schema#',
    'title': 'Content Applicability Report',
    'description': (
        'Derived from: http://docs.pulpproject.org/'
        'dev-guide/integration/rest-api/consumer/applicability.html'
        '#query-content-applicability'
    ),
    'type': 'array',
    'items': {
        'type': 'object',
        'properties': {
            'applicability': {
                'type': 'object',
                'properties': {
                    'erratum': {
                        'type': 'array',
                        'items': {'type': 'string'}
                    },
                    'modulemd': {
                        'type': 'array',
                        'items': {'type': 'string'}
                    },
                    'rpm': {
                        'type': 'array',
                        'items': {'type': 'string'}
                    }
                }
            },
            'consumers': {
                'type': 'array',
                'items': {'type': 'string'}
            }
        }
    }
}
"""A schema for a content applicability report for a consumer.

Schema now includes modulemd profiles:

* `Pulp #3925 <https://pulp.plan.io/issues/3925>`_
"""


class CheckIsModularFlagAfterSyncTestCase(unittest.TestCase):
    """Check is_modular flag unit is present after syncing."""

    def test_all(self):
        """Verify whether the is_modular flag is present in rpm units.

        This test does the following:

        1. Create and sync a modular repository.
        2. Filter the modular and non_modular units using
           :meth:`pulp_smash.pulp2.utils.search_units`.
        3. Check whether the modular and non_modular units returned
           by this filter is accurate.

        This test case targets:

        * `Pulp #4049 <https://pulp.plan.io/issues/4049>`_.
        * `Pulp #4146 <https://pulp.plan.io/issues/4146>`_.
        """
        cfg = config.get_config()
        if cfg.pulp_version < Version('2.18'):
            raise unittest.SkipTest('This test requires Pulp 2.18 or newer.')
        client = api.Client(cfg, api.json_handler)
        body = gen_repo(
            importer_config={'feed': RPM_WITH_MODULES_FEED_URL},
            distributors=[gen_distributor()]
        )
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        sync_repo(cfg, repo)
        repo = client.get(repo['_href'], params={'details': True})
        modular_units = search_units(
            cfg, repo, {
                'filters': {'unit': {'is_modular': True}},
                'type_ids': ['rpm'],
            }
        )

        non_modular_units = search_units(
            cfg, repo, {
                'filters': {'unit': {'is_modular': False}},
                'type_ids': ['rpm'],
            }
        )

        # Check the number of modular units returned by `is_modular` as True.
        self.assertEqual(
            len(modular_units),
            sum(MODULE_FIXTURES_PACKAGES.values()),
            modular_units
        )
        # Check the number of modular units returned by `is_modular` as False.
        self.assertEqual(
            len(non_modular_units),
            RPM_UNSIGNED_FEED_COUNT - sum(MODULE_FIXTURES_PACKAGES.values()),
            non_modular_units
        )


class CheckIsModularFlagAfterRPMUploadTestCase(unittest.TestCase):
    """Check is_modular flag unit is present after RPM upload."""

    def test_all(self):
        """Verify whether the is_modular flag is present in rpm units.

        This test does the following:

        1. Upload a modular RPM
        2. Upload a non-modular RPM
        3. Filter the modular and non_modular units using
           :meth:`pulp_smash.pulp2.utils.search_units`
        4. Check whether the modular and non_modular units returned
           by this filter is accurate.

        This test case targets:

        * `Pulp #4869 <https://pulp.plan.io/issues/4869>`_.
        * `Pulp #4930 <https://pulp.plan.io/issues/4930>`_.
        """
        cfg = config.get_config()
        if cfg.pulp_version < Version('2.20'):
            raise unittest.SkipTest('This test requires Pulp 2.20 or newer.')
        if not selectors.bug_is_fixed(4869, cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/4869')

        # Setup Client and gen_repo
        client = api.Client(cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])

        # RPM Gets
        modular_rpm = utils.http_get(RPM_WITH_MODULAR_URL)
        non_modular_rpm = utils.http_get(RPM_WITH_VENDOR_URL)

        # Upload Units
        upload_import_unit(cfg, modular_rpm, {'unit_type_id': 'rpm'}, repo)
        upload_import_unit(cfg, non_modular_rpm, {'unit_type_id': 'rpm'}, repo)

        # Find Modular unit counts
        modular_units = search_units(
            cfg, repo, {
                'filters': {'unit': {'is_modular': True}},
                'type_ids': ['rpm'],
            }
        )
        non_modular_units = search_units(
            cfg, repo, {
                'filters': {'unit': {'is_modular': False}},
                'type_ids': ['rpm'],
            }
        )

        # Check the number of modular units returned by `is_modular` as True.
        self.assertEqual(len(modular_units), 1, modular_units)

        # Check the number of modular units returned by `is_modular` as False.
        self.assertEqual(len(non_modular_units), 1, non_modular_units)


class CheckModulesYamlTestCase(unittest.TestCase):
    """Check whether modules.yaml is available if appropriate."""

    @classmethod
    def setUpClass(cls):
        """Create class wide variables."""
        cls.cfg = config.get_config()
        if cls.cfg.pulp_version < Version('2.18.1'):
            raise unittest.SkipTest('This test requires Pulp 2.18.1 or newer.')
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_no_modules_yaml_generated_non_modular(self):
        """Verify no ``modules.yaml`` is generated for non modular content.

        This test does the following

        1. Create and sync a non-modular content.
        2. Publish the synced content.
        3. Check whether no modules.yaml is generated for published content.

        This test case targets:

        * `Pulp #4252 <https://pulp.plan.io/issues/4252>`_.
        * `Pulp #4350 <https://pulp.plan.io/issues/4350>`_.
        """
        body = gen_repo(
            importer_config={'feed': RPM_UNSIGNED_FEED_URL},
            distributors=[gen_distributor(auto_publish=True)]
        )
        # Step 1 and 2
        repo = self.client.post(REPOSITORY_PATH, body)
        self.addCleanup(self.client.delete, repo['_href'])
        sync_repo(self.cfg, repo)
        repo = self.client.get(repo['_href'], params={'details': True})
        # Step 3
        files = self.list_repo_data_files(self.cfg, repo)
        # check no modules.yaml.gz is found
        self.assertFalse(bool(files))
        modules_elements = self.get_modules_elements_repomd(
            self.cfg,
            repo['distributors'][0]
        )
        self.assertFalse(bool(modules_elements))

    def test_sha1_modules_yaml(self):
        """Verify whether the published modular content has appropriate sha.

        This test does the following:

        1. Create and sync a modular content with sha1 checksum.
        2. Publish the synced content
        3. Check whether the modules.yaml is sha1 checked.

        This test targets the following:

        * `Pulp #4351 <https://pulp.plan.io/issues/4351>`_.
        """
        body = gen_repo(
            importer_config={'feed': RPM_WITH_MODULES_SHA1_FEED_URL},
            distributors=[gen_distributor(auto_publish=True)]
        )
        # Step 1 and 2
        repo = self.client.post(REPOSITORY_PATH, body)
        self.addCleanup(self.client.delete, repo['_href'])
        sync_repo(self.cfg, repo)
        repo = self.client.get(repo['_href'], params={'details': True})
        module_file = self.list_repo_data_files(self.cfg, repo)[0]
        sha_vals = self.get_sha1_vals_file(self.cfg, module_file)
        # sha_vals[0] contains the sha1 checksum of the file
        # sha_vals[1] contains the filepath containing the checked file
        self.assertIn(sha_vals[0], sha_vals[1])

    @staticmethod
    def list_repo_data_files(cfg, repo):
        """Return a list of all the files present inside repodata dir."""
        return cli.Client(cfg).run((
            'find',
            '/var/lib/pulp/published/yum/master/yum_distributor/{}/'.format(
                repo['id']
            ),
            '-type',
            'f',
            '-name',
            '*modules.yaml.gz'
        ), sudo=True).stdout.splitlines()

    @staticmethod
    def get_modules_elements_repomd(cfg, distributor):
        """Return a list of elements present inside the repomd.xml."""
        repomd_xml = get_repodata_repomd_xml(cfg, distributor)
        xpath = (
            "{{{namespace}}}data[@type='{type_}']".format(
                namespace=RPM_NAMESPACES['metadata/repo'],
                type_='modules'
            )
        )
        return repomd_xml.findall(xpath)

    @staticmethod
    def get_sha1_vals_file(cfg, filepath):
        """Return a list containing sha1 checksum of the file and filepath."""
        return cli.Client(cfg).run((
            'sha1sum',
            filepath
        ), sudo=True).stdout.split()


class CopyModularDefaultsTestCase(unittest.TestCase):
    """Test ``recursive`` and ``recursive_conservative`` flags during copy.

    This test targets the following issues:

    * `Pulp Smash #1122 <https://github.com/PulpQE/pulp-smash/issues/1122>`_
    * `Pulp #4543 <https://pulp.plan.io/issues/4543>`_

    Recursive or conservative copy of ``modulemd_defaults``
    should always only copy:

    * 3 modules: ``duck``, ``kangaroo``, ``walrus``

    Exercise the use of ``recursive and ``recursive_conservative``.
    """

    @classmethod
    def setUpClass(cls):
        """Create class wide variables."""
        cls.cfg = config.get_config()
        if cls.cfg.pulp_version < Version('2.19'):
            raise unittest.SkipTest('This test requires Pulp 2.19 or newer.')
        if check_issue_4405(cls.cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/4405')
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_copy_modulemd_defaults(self):
        """Test copy of modulemd_defaults in RPM repository."""
        repo = self.copy_units(False, False)
        self.check_module_total_units(repo)

    def test_copy_modulemd_defaults_recursive(self):
        """Test copy of modulemd_defaults in RPM repository."""
        repo = self.copy_units(True, False)
        self.check_module_total_units(repo)

    def test_copy_modulemd_defaults_conservative(self):
        """Test copy of modulemd_defaults in RPM repository."""
        repo = self.copy_units(False, True)
        self.check_module_total_units(repo)

    def test_copy_modulemd_defaults_recursive_conservative(self):
        """Test copy of modulemd_defaults in RPM repository."""
        repo = self.copy_units(True, True)
        self.check_module_total_units(repo)

    def check_module_total_units(self, repo):
        """Test copy of modulemd_defaults in RPM repository."""
        self.assertEqual(
            repo['content_unit_counts']['modulemd_defaults'],
            MODULE_FIXTURES_PACKAGE_STREAM['module_defaults'],
            repo['content_unit_counts']
        )
        self.assertEqual(
            repo['total_repository_units'],
            MODULE_FIXTURES_PACKAGE_STREAM['module_defaults'],
            repo['total_repository_units']
        )
        self.assertNotIn('rpm', repo['content_unit_counts'])

    def copy_units(self, recursive, recursive_conservative, old_dependency=False):
        """Create two repositories and copy content between them."""
        criteria = {
            'filters': {},
            'type_ids': ['modulemd_defaults'],
        }
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
        # Add `old_dependency` for OLD RPM on B
        if old_dependency:
            rpm = utils.http_get(RPM_WITH_OLD_VERSION_URL)
            upload_import_unit(
                self.cfg,
                rpm,
                {'unit_type_id': 'rpm'}, repos[1]
            )
            units = search_units(self.cfg, repos[1], {'type_ids': ['rpm']})
            self.assertEqual(len(units), 1, units)

        self.client.post(urljoin(repos[1]['_href'], 'actions/associate/'), {
            'source_repo_id': repos[0]['id'],
            'override_config': {
                'recursive': recursive,
                'recursive_conservative': recursive_conservative,
            },
            'criteria': criteria
        })
        return self.client.get(repos[1]['_href'], params={'details': True})


class CopyModulesTestCase(unittest.TestCase):
    """Test copy of modules, and its artifacts.

    This test targets the following issues:

    * `Pulp Smash #1122 <https://github.com/PulpQE/pulp-smash/issues/1122>`_
    * `Pulp #4543 <https://pulp.plan.io/issues/4543>`_
    * `Pulp #4995 <https://pulp.plan.io/issues/4995>`_

    Regressions occurred in copying of any RPMs and modules when
    other repository modules, modular RPMs, and ursine RPMs would "shadow
    solve" dependencies. The result would be unexpected modules,
    module streams, "shadow" modular RPMs, and ursine RPMs being copied.

    This test addresses copying modules and verifying the correct count of
    modules, RPMs and total units copied.

    Additional abstracted modules with modular and ursine RPMs were added in
    pulp-fixtures to be tested in Pulp 2.20 to cover these additional cases.

    The following Modules, modular RPMS, and ursine RPMs are used in this
    test case. Only the explicit counts for each MODULE_FIXTURE
    should be copied for each.

    Modules::

        [walrus-0.71]
        └── walrus-0.71

        [walrus-5.21]
        └── walrus-5.21

        [duck-4]
        └── duck-0.8

        [duck-5]
        └── duck-0.8

        [duck-6]
        └── duck-0.8
        └── frog-0.1

    Dependent RPMs of the provided RPM from ``walrus-0.71``::

        walrus-0.71
        └── whale
               ├── shark
               └── stork

    The modular RPM ``walrus-5.21`` has no modular or ursine RPM dependencies.

    The moduar RPM ``duck-0.8`` and ``frog-0.1`` has no modular or ursine RPM
    dependencies.

    Exercise the use of ``recursive`` and ``recursive_conservative`` with a
    target repo having no rpms or ``old_rpm`` versions for each
    ``MODULE_FIXTURE``.
    """

    @classmethod
    def setUpClass(cls):
        """Create class wide variables."""
        cls.cfg = config.get_config()
        if cls.cfg.pulp_version < Version('2.19'):
            raise unittest.SkipTest(
                'This test requires Pulp 2.19 or newer.'
            )
        if check_issue_4405(cls.cfg):
            raise unittest.SkipTest('https://pulp.plan.io/issues/4405')
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.COPY_MODULES_LIST = [MODULE_FIXTURES_PACKAGE_STREAM]
        if cls.cfg.pulp_version >= Version('2.20'):
            if not selectors.bug_is_fixed(4962, cls.cfg.pulp_version):
                raise unittest.SkipTest('https://pulp.plan.io/issues/4962')
            cls.COPY_MODULES_LIST.append(MODULE_FIXTURES_DUCK_4_STREAM)
            cls.COPY_MODULES_LIST.append(MODULE_FIXTURES_DUCK_5_STREAM)
            cls.COPY_MODULES_LIST.append(MODULE_FIXTURES_DUCK_6_STREAM)

    def test_copy_modulemd_recursive_nonconservative_no_old_rpm(self):
        """Test modular copy using override_config and no old RPMs."""
        for module in self.COPY_MODULES_LIST:
            with self.subTest(modules=module['name']):
                repo = self.copy_units(True, False, False, module)
                self.check_module_rpm_total_units(repo, module)

    def test_copy_modulemd_recursive_nonconservative_old_rpm(self):
        """Test modular copy using override_config and old RPMs."""
        for module in self.COPY_MODULES_LIST:
            with self.subTest(modules=module['name']):
                repo = self.copy_units(True, False, True, module)
                self.check_module_rpm_total_units(repo, module)

    def test_copy_modulemd_recursive_conservative_no_old_rpm(self):
        """Test modular copy using override_config and no old RPMs."""
        for module in self.COPY_MODULES_LIST:
            with self.subTest(modules=module['name']):
                repo = self.copy_units(True, True, False, module)
                self.check_module_rpm_total_units(repo, module)

    def test_copy_modulemd_nonrecursive_conservative_old_rpm(self):
        """Test modular copy using override_config and old RPMs."""
        for module in self.COPY_MODULES_LIST:
            with self.subTest(modules=module['name']):
                repo = self.copy_units(False, True, True, module)
                self.check_module_rpm_total_units(repo, module)

    def test_copy_modulemd_recursive_conservative_old_rpm(self):
        """Test modular copy using override_config and old RPMs."""
        for module in self.COPY_MODULES_LIST:
            with self.subTest(modules=module['name']):
                repo = self.copy_units(True, True, True, module)
                self.check_module_rpm_total_units(repo, module)

    def check_module_rpm_total_units(self, repo, module):
        """Test copy of modulemd in RPM repository."""
        # Core verifications (in order):
        # - Number of modules copied (current design to be 1)
        # - Modular and Ursine RPMs copied as provided or dependent on the
        #   module or module's RPM dependencies
        # - Total units (Module and RPMs) copied
        checks = [
            (repo['content_unit_counts']['modulemd'], 1),
            (repo['content_unit_counts']['rpm'], module['rpm_count']),
            (repo['total_repository_units'], module['total_available_units']),
        ]

        # for loop to give a breakout for any and each individual failures
        # Allows easier troubleshooting to pin point libsolv problems
        for check in checks:
            with self.subTest(check=check):
                self.assertEqual(check[0], check[1], module)

    def copy_units(self, recursive, recursive_conservative, old_rpm, module):
        """Create two repositories and copy content between them."""
        criteria = {
            'filters': {'unit': {
                'name': module['name'],
                'stream': module['stream']
            }},
            'type_ids': ['modulemd'],
        }
        repos = []
        body = gen_repo(
            importer_config={'feed': module['feed']},
            distributors=[gen_distributor()]
        )
        repos.append(self.client.post(REPOSITORY_PATH, body))
        self.addCleanup(self.client.delete, repos[0]['_href'])
        sync_repo(self.cfg, repos[0])
        repos.append(self.client.post(REPOSITORY_PATH, gen_repo()))
        self.addCleanup(self.client.delete, repos[1]['_href'])
        # Add `old_rpm` for OLD RPM on B
        if old_rpm:
            rpm = utils.http_get(module['old'])
            upload_import_unit(
                self.cfg, rpm,
                {'unit_type_id': 'rpm'},
                repos[1]
            )
            units = search_units(
                self.cfg,
                repos[1],
                {'type_ids': ['rpm']}
            )
            self.assertEqual(len(units), 1, units)

        self.client.post(urljoin(repos[1]['_href'], 'actions/associate/'), {
            'source_repo_id': repos[0]['id'],
            'override_config': {
                'recursive': recursive,
                'recursive_conservative': recursive_conservative,
            },
            'criteria': criteria
        })
        return self.client.get(repos[1]['_href'], params={'details': True})


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

    def test_sync_and_republish_repo(self):
        """Test sync and re-publish modular RPM repository.

        This test targets the following issue:

        `Pulp #4477 <https://pulp.plan.io/issues/4477>`_

        Steps:

        1. Create a repo pointing to modular feed and sync it.
        2. Get the number of modules present in the repo updateinfo file.
        3. Delete the repo.
        4. Recreate the repo with a different name and sync it.
        5. Get the number of modules present in the repo updateinfo file.
        6. Assert that the number of modules has not increased.
        """
        if self.cfg.pulp_version < Version('2.19'):
            raise unittest.SkipTest('This test requires Pulp 2.19 or newer.')

        # Step 1
        repo1 = self.create_sync_modular_repo(cleanup=False)
        publish_repo(self.cfg, repo1)
        # Step 2
        update_info_file1 = get_repodata(
            self.cfg,
            repo1['distributors'][0],
            'updateinfo'
        )
        first_repo_modules = update_info_file1.findall('.//module')
        self.assertEqual(
            len(first_repo_modules),
            RPM_WITH_MODULES_FEED_COUNT,
            first_repo_modules
        )
        # Step 3
        self.client.delete(repo1['_href'])
        # Step 4
        repo2 = self.create_sync_modular_repo()
        publish_repo(self.cfg, repo2)
        # Step 5
        update_info_file2 = get_repodata(
            self.cfg,
            repo2['distributors'][0],
            'updateinfo'
        )
        second_repo_modules = update_info_file2.findall('.//module')
        self.assertEqual(
            len(second_repo_modules),
            RPM_WITH_MODULES_FEED_COUNT,
            second_repo_modules
        )
        # step 6
        self.assertEqual(len(first_repo_modules), len(second_repo_modules))

    def create_sync_modular_repo(self, cleanup=True):
        """Create a repo with feed pointing to modular data and sync it.

        :returns: repo data that is created and synced with modular content.
        """
        body = gen_repo(
            importer_config={'feed': RPM_WITH_MODULES_FEED_URL},
            distributors=[gen_distributor()]
        )
        repo = self.client.post(REPOSITORY_PATH, body)
        if cleanup:
            self.addCleanup(self.client.delete, repo['_href'])
        sync_repo(self.cfg, repo)
        return self.client.get(repo['_href'], params={'details': True})

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
        # after removing a module 'X', the number of RPMS in the repo should
        # decrease by the number of RPMS present in 'X'.
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


class ModularApplicabilityTestCase(unittest.TestCase):
    """Perform modular repo applicability generation tasks.

    Specifically, do the following:

    1. Create a consumer.
    2. Bind the consumer to the modular repository
       ``RPM_WITH_MODULES_FEED_URL``.
    3. Create a consumer profile with:
       * List of RPMs.
       * List of Modules.
    4. Regenerate applicability for the consumer.
    5. Fetch applicability for the consumer. Verify that the packages
       are eligible for upgrade.

    This test targets the following:

    * `Pulp #4158 <https://pulp.plan.io/issues/4158>`_
    * `Pulp #4179 <https://pulp.plan.io/issues/4179>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        if cls.cfg.pulp_version < Version('2.18'):
            raise unittest.SkipTest('This test requires Pulp 2.18 or newer.')
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_modular_rpm(self):
        """Verify content is made available if appropriate.

        This test does the following:

        1. Create a consumer profile with an RPM version less than the
           module.
        2. Bind the consumer to the modular repo.
        3. Verify the content is applicable.
        """
        # Reduce the versions to check whether newer version applies.
        rpm_with_modules_metadata = MODULE_ARTIFACT_RPM_DATA.copy()
        rpm_with_modules_metadata['version'] = '5'
        modules_metadata = MODULES_METADATA.copy()
        applicability = self.do_test(
            [modules_metadata],
            [rpm_with_modules_metadata]
        )
        validate(applicability, CONTENT_APPLICABILITY_REPORT_SCHEMA)
        with self.subTest(comment='verify Modules listed in report'):
            self.assertEqual(
                len(applicability[0]['applicability']['modulemd']),
                1,
                applicability[0]['applicability']['modulemd'],
            )

    def test_negative_modular_rpm(self):
        """Verify content is not made available when inappropriate.

        Do the same as :meth:`test_modular_rpm`, except that the version should
        be higher than what is offered by the module.
        """
        rpm_with_modules_metadata = MODULE_ARTIFACT_RPM_DATA.copy()
        rpm_with_modules_metadata['version'] = '7'
        modules_metadata = MODULES_METADATA.copy()
        applicability = self.do_test(
            [modules_metadata],
            [rpm_with_modules_metadata],
        )
        validate(applicability, CONTENT_APPLICABILITY_REPORT_SCHEMA)
        with self.subTest(comment='verify Modules listed in report'):
            self.assertEqual(
                len(applicability[0]['applicability']['modulemd']),
                0,
                applicability[0]['applicability']['modulemd'],
            )

    def test_mixed_rpm(self):
        """Verify content is made available for both modular/non modular RPMs.

        This test does the following:

        1. Create a consumer profile containing both modular and non modular
           RPMs.
        2. Bind the consumer to the modular repo.
        3. Verify the content is applicable.
        """
        # Reduce the versions to check whether newer version applies.
        rpm_with_modules_metadata = MODULE_ARTIFACT_RPM_DATA.copy()
        rpm_with_modules_metadata['version'] = '5'
        modules_metadata = MODULES_METADATA.copy()
        rpm_with_erratum_metadata = RPM_WITH_ERRATUM_METADATA.copy()
        rpm_with_erratum_metadata['version'] = '4.0'
        applicability = self.do_test(
            [modules_metadata],
            [rpm_with_modules_metadata, rpm_with_modules_metadata]
        )
        validate(applicability, CONTENT_APPLICABILITY_REPORT_SCHEMA)
        with self.subTest(comment='verify Modules listed in report'):
            self.assertEqual(
                len(applicability[0]['applicability']['modulemd']),
                1,
                applicability[0]['applicability']['modulemd'],
            )
        with self.subTest(comment='verify Modules listed in report'):
            self.assertEqual(
                len(applicability[0]['applicability']['rpm']),
                1,
                applicability[0]['applicability']['rpm'],
            )

    def test_dependent_modules(self):
        """Verify dependent modules are made available.

        This test does the following:

        1. Bind the consumer with the modular repo.
        2. Update the consumer profile with dependent modules.
        3. Verify that the content is made available for the consumer.
        """
        # Reduce the versions to check whether newer version applies.
        rpm_with_modules_metadata = MODULE_ARTIFACT_RPM_DATA.copy()
        rpm_with_modules_metadata['version'] = '5'

        rpm_with_modules_metadata_2 = MODULE_ARTIFACT_RPM_DATA_2.copy()
        rpm_with_modules_metadata['version'] = '0.5'

        modules_metadata = MODULES_METADATA.copy()
        modules_metadata_2 = MODULES_METADATA_2.copy()
        applicability = self.do_test(
            [modules_metadata, modules_metadata_2],
            [rpm_with_modules_metadata, rpm_with_modules_metadata_2]
        )
        validate(applicability, CONTENT_APPLICABILITY_REPORT_SCHEMA)
        with self.subTest(comment='verify Modules listed in report'):
            self.assertEqual(
                len(applicability[0]['applicability']['modulemd']),
                2,
                applicability[0]['applicability']['modulemd'],
            )

    def test_erratum_modules(self):
        """Verify erratum modules are applicable.

        This test does the following:

        1. Bind the consumer with erratum modular repo.
        2. Verify the content is applicable.
        """
        # Reduce the versions to check whether newer version applies.
        rpm_with_modules_metadata = MODULE_ARTIFACT_RPM_DATA.copy()
        rpm_with_modules_metadata['version'] = '5'
        modules_metadata = MODULES_METADATA.copy()
        erratum = self.gen_modular_errata()
        applicability = self.do_test(
            [modules_metadata],
            [rpm_with_modules_metadata],
            erratum
        )
        validate(applicability, CONTENT_APPLICABILITY_REPORT_SCHEMA)
        with self.subTest(comment='verify Modules listed in report'):
            self.assertEqual(
                len(applicability[0]['applicability']['erratum']),
                1,
                applicability[0]['applicability']['erratum'],
            )

    def do_test(self, modules_profile, rpm_profile, erratum=None):
        """Regenerate and fetch applicability for the given modules and RPMs.

        This method does the following:

        1. Create a modular repo.
        2. Create a consumer and bind them to the modular repo.
        3. Create consumer profiles for the passed modules and rpms.
        4. Regenerate and return the fetched applicability.

        :param modules_profile: A list of modules for the consumer profile.
        :param rpm_profile: A list of RPMs for the consumer profile.
        :param erratum: An Erratum to be added to the repo.

        :returns: A dict containing the consumer ``applicability``.
        """
        body = gen_repo(
            importer_config={'feed': RPM_WITH_MODULES_FEED_URL},
            distributors=[gen_distributor(auto_publish=True)]
        )
        repo = self.client.post(REPOSITORY_PATH, body)
        sync_repo(self.cfg, repo)
        repo = self.client.get(repo['_href'], params={'details': True})
        if erratum is not None:
            upload_import_erratum(self.cfg, erratum, repo)
        self.addCleanup(self.client.delete, repo['_href'])

        # Create a consumer.
        consumer = self.client.post(CONSUMERS_PATH, gen_consumer())
        self.addCleanup(self.client.delete, consumer['consumer']['_href'])

        # Bind the consumer.
        self.client.post(urljoin(consumer['consumer']['_href'], 'bindings/'), {
            'distributor_id': repo['distributors'][0]['id'],
            'notify_agent': False,
            'repo_id': repo['id'],
        })

        # Create a consumer profile with RPM
        if rpm_profile:
            self.client.post(
                urljoin(consumer['consumer']['_href'], 'profiles/'),
                {'content_type': 'rpm', 'profile': rpm_profile}
            )

        # Create a consumer profile with modules.
        if modules_profile:
            self.client.post(
                urljoin(consumer['consumer']['_href'], 'profiles/'),
                {'content_type': 'modulemd', 'profile': modules_profile}
            )

        # Regenerate applicability.
        self.client.post(
            CONSUMERS_ACTIONS_CONTENT_REGENERATE_APPLICABILITY_PATH,
            {
                'consumer_criteria': {
                    'filters': {'id': {'$in': [consumer['consumer']['id']]}}}
            },
        )

        # Fetch and Return applicability.
        return self.client.post(CONSUMERS_CONTENT_APPLICABILITY_PATH, {
            'criteria': {
                'filters': {'id': {'$in': [consumer['consumer']['id']]}}
            },
        })

    @staticmethod
    def gen_modular_errata():
        """Generate and return a modular erratum with RPM."""
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
                'packages': [
                    {
                        'arch': MODULE_ARTIFACT_RPM_DATA['arch'],
                        'name': MODULE_ARTIFACT_RPM_DATA['name'],
                        'release': MODULE_ARTIFACT_RPM_DATA['release'],
                        'version': MODULE_ARTIFACT_RPM_DATA['version'],
                        'src': MODULE_ARTIFACT_RPM_DATA['src']
                    }
                ]
            }]
        }


class ModularErrataCopyTestCase(unittest.TestCase):
    """Test ``recursive`` and ``recursive_conservative`` flags during copy.

    This test targets the following issues:

    * `Pulp #4518 <https://pulp.plan.io/issues/4518>`_
    * `Pulp #4548 <https://pulp.plan.io/issues/4548>`_
    * `Pulp #5055 <https://pulp.plan.io/issues/5055>`_

    Recursive copy of ``RHEA-2012:0059`` should copy:

    * 2 modules: ``duck`` and ``kangaroo``.
    * 2 modulemd_defaults ``duck`` and ``kangaroo``.
    * 2 RPMS: ``kangaroo-0.3-1.noarch.rpm``, and ``duck-0.7-1.noarch.rpm``.

    Copy of ``module_defaults`` introduced in Pulp 2.21.

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

        if self.cfg.pulp_version >= Version('2.21'):

            self.assertEqual(
                repo['content_unit_counts']['modulemd_defaults'],
                MODULE_FIXTURES_ERRATA['module_defaults_count'],
                repo['content_unit_counts']
            )

        # older RPM package already present has to be added to total of RPM
        # packages after copy.
        total_available_units = MODULE_FIXTURES_ERRATA['total_available_units'] + 1
        if self.cfg.pulp_version < Version('2.21'):
            # Pulp 2.21  introduced copy of module_defaults. There are 2.
            total_available_units -= MODULE_FIXTURES_ERRATA['module_defaults_count']

        self.assertEqual(
            repo['total_repository_units'],
            total_available_units,
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

        if self.cfg.pulp_version >= Version('2.21'):

            self.assertEqual(
                repo['content_unit_counts']['modulemd_defaults'],
                MODULE_FIXTURES_ERRATA['module_defaults_count'],
                repo['content_unit_counts']
            )

        total_available_units = MODULE_FIXTURES_ERRATA['total_available_units']
        if self.cfg.pulp_version < Version('2.21'):
            # Pulp 2.21  introduced copy of module_defaults. There are 2.
            total_available_units -= MODULE_FIXTURES_ERRATA['module_defaults_count']

        self.assertEqual(
            repo['total_repository_units'],
            total_available_units,
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


class PackageManagerModuleListTestCase(unittest.TestCase):
    """Package manager can read module list from a Pulp repository."""

    def test_all(self):
        """Package manager can read module list from a Pulp repository."""
        cfg = config.get_config()
        if cfg.pulp_version < Version('2.17'):
            raise unittest.SkipTest('This test requires Pulp 2.17 or newer.')
        if not os_support_modularity(cfg):
            raise unittest.SkipTest(
                'This test requires an OS that supports modularity.'
            )
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
    """Upload a module.yaml file and test upload import in Pulp repository."""

    @classmethod
    def setUpClass(cls):
        """Create class wide variables."""
        cls.cfg = config.get_config()
        if cls.cfg.pulp_version < Version('2.17'):
            raise unittest.SkipTest('This test requires Pulp 2.17 or newer.')
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_upload_module(self):
        """Verify whether uploaded module.yaml is updated in the pulp repo."""
        # Create a normal repo without any data.
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
        """Verify changing the modules default content of modules.yaml.

        Do not modifies the repo.
        """
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

        Given a detailed dict of information about a published repository,
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
        with io.BytesIO(unit) as compressed:
            with gzip.GzipFile(fileobj=compressed) as decompressed:
                unit = decompressed.read()
        return unit
