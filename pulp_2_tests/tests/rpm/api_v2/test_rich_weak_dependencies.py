# coding=utf-8
"""Test actions over repositories with rich and weak dependencies."""
import unittest
from urllib.parse import urljoin

from packaging.version import Version
from pulp_smash import api, cli, config, utils
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import (
    publish_repo,
    search_units,
    sync_repo,
    upload_import_unit,
)

from pulp_2_tests.constants import (
    RPM_RICH_WEAK,
    RPM_RICH_WEAK_FEED_URL,
    RPM2_RICH_WEAK_DATA,
    SRPM_RICH_WEAK_FEED_URL,
)
from pulp_2_tests.tests.rpm.api_v2.utils import gen_distributor, gen_repo
from pulp_2_tests.tests.rpm.utils import (
    gen_yum_config_file,
    rpm_rich_weak_dependencies,
)
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


class UploadRPMTestCase(unittest.TestCase):
    """Test whether one can upload a RPM with rich/weak into a repository.

    Specifically, this method does the following:

    1. Create an RPM repository.
    2. Upload an RPM with rich/weak dependencies into the repository.
    3. Search for all content units in the repository.
    """

    def test_all(self):
        """Import a RPM with rich/weak dependencies into a repository.

        Search it for content units.
        """
        cfg = config.get_config()
        if cfg.pulp_version < Version('2.17'):
            raise unittest.SkipTest('This test requires Pulp 2.17 or newer.')
        client = api.Client(cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        rpm = utils.http_get(urljoin(RPM_RICH_WEAK_FEED_URL + '/', RPM_RICH_WEAK))
        upload_import_unit(cfg, rpm, {'unit_type_id': 'rpm'}, repo)
        units = search_units(cfg, repo)

        # Test if RPM has been uploaded successfully
        self.assertEqual(len(units), 1)

        # Test if RPM extracted correct metadata for creating filename
        self.assertEqual(units[0]['metadata']['filename'], RPM_RICH_WEAK)


class PackageManagerCosumeRPMTestCase(unittest.TestCase):
    """Test whether package manager can consume RPM with rich/weak from Pulp."""

    def test_all(self):
        """Package manager can consume RPM with rich/weak dependencies from Pulp."""
        cfg = config.get_config()
        if cfg.pulp_version < Version('2.17'):
            raise unittest.SkipTest('This test requires Pulp 2.17 or newer.')
        if not rpm_rich_weak_dependencies(cfg):
            raise unittest.SkipTest('This test requires RPM 4.12 or newer.')
        client = api.Client(cfg, api.json_handler)
        body = gen_repo(
            importer_config={'feed': RPM_RICH_WEAK_FEED_URL},
            distributors=[gen_distributor()]
        )
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        sync_repo(cfg, repo)
        publish_repo(cfg, repo)
        verify = cfg.get_hosts('api')[0].roles['api'].get('verify')
        sudo = () if cli.is_root(cfg) else ('sudo',)
        repo_path = gen_yum_config_file(
            cfg,
            baseurl=urljoin(cfg.get_base_url(), urljoin(
                'pulp/repos/',
                repo['distributors'][0]['config']['relative_url']
            )),
            name=repo['_href'],
            enabled=1,
            gpgcheck=0,
            metadata_expire=0,  # force metadata to load every time
            repositoryid=repo['id'],
            sslverify='yes' if verify else 'no',
        )
        cli_client = cli.Client(cfg)
        self.addCleanup(cli_client.run, sudo + ('rm', repo_path))
        rpm_name = 'Cobbler'
        pkg_mgr = cli.PackageManager(cfg)
        pkg_mgr.install(rpm_name)
        self.addCleanup(pkg_mgr.uninstall, rpm_name)
        rpm = cli_client.run(('rpm', '-q', rpm_name)).stdout.strip().split('-')
        self.assertEqual(rpm_name, rpm[0])


class CopyRecursiveUnitsTestCase(unittest.TestCase):
    """Test copy units for a repository rich/weak dependencies.

    This test targets the following issue:

    `Pulp Smash #1107 <https://github.com/PulpQE/pulp-smash/issues/1107>`_.
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        if cls.cfg.pulp_version < Version('2.17'):
            raise unittest.SkipTest('This test requires Pulp 2.17 or newer.')
        if not rpm_rich_weak_dependencies(cls.cfg):
            raise unittest.SkipTest('This test requires RPM 4.12 or newer.')
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_recursive(self):
        """Test recursive copy of units for a repository with rich/weak depdendencies.

        See :meth:`do_test`."
        """
        repo = self.do_test(True)
        dst_unit_ids = [
            unit['metadata']['name'] for unit in
            search_units(self.cfg, repo, {'type_ids': ['rpm']})]
        self.assertEqual(
            len(dst_unit_ids),
            RPM2_RICH_WEAK_DATA['total_installed_packages'],
            dst_unit_ids
        )

    def test_non_recursive(self):
        """Test simple copy of an unit for a repository with rich/weak depdendencies.

        See :meth:`do_test`."
        """
        repo = self.do_test(False)
        dst_unit_ids = [
            unit['metadata']['name'] for unit in
            search_units(self.cfg, repo, {'type_ids': ['rpm']})]
        self.assertEqual(len(dst_unit_ids), 1, dst_unit_ids)

    def do_test(self, recursive):
        """Copy of units for a repository with rich/weak dependencies."""
        repos = []
        body = gen_repo(
            importer_config={'feed': RPM_RICH_WEAK_FEED_URL},
            distributors=[gen_distributor()]
        )
        repos.append(self.client.post(REPOSITORY_PATH, body))
        self.addCleanup(self.client.delete, repos[0]['_href'])
        sync_repo(self.cfg, repos[0])
        body = gen_repo()
        repos.append(self.client.post(REPOSITORY_PATH, body))
        self.addCleanup(self.client.delete, repos[1]['_href'])
        self.client.post(urljoin(repos[1]['_href'], 'actions/associate/'), {
            'source_repo_id': repos[0]['id'],
            'override_config': {'recursive': recursive},
            'criteria': {
                'filters': {'unit': {'name': RPM2_RICH_WEAK_DATA['name']}},
                'type_ids': ['rpm'],
            },
        })
        return self.client.get(repos[1]['_href'], params={'details': True})
