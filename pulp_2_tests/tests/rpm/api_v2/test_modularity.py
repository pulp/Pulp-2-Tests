# coding=utf-8
"""Tests that perform actions over RPM modular repositories."""
import unittest
from urllib.parse import urljoin

from packaging.version import Version
from pulp_smash import api, cli, config
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import publish_repo, sync_repo

from pulp_2_tests.constants import (
    MODULE_FIXTURES_PACKAGES,
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
        body = gen_repo()
        body['importer_config']['feed'] = RPM_WITH_MODULES_FEED_URL
        body['distributors'] = [gen_distributor()]
        repo = self.client.post(REPOSITORY_PATH, body)
        self.addCleanup(self.client.delete, repo['_href'])
        sync_repo(self.cfg, repo)
        repo = self.client.get(repo['_href'], params={'details': True})

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
        lines = cli_client.run((
            sudo + ('dnf', 'module', 'list', '--all')
        )).stdout.splitlines()
        for key, value in MODULE_FIXTURES_PACKAGES.items():
            with self.subTest(package=key):
                module = [line for line in lines if key in line]
                self.assertEqual(len(module), value, module)
