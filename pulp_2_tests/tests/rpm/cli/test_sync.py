# coding=utf-8
"""Tests that sync RPM repositories."""
import random
import unittest

from packaging.version import Version
from pulp_smash import cli, config, selectors, utils
from pulp_smash.pulp2.utils import pulp_admin_login, reset_pulp

from pulp_2_tests.constants import RPM_KICKSTART_FEED_URL, RPM_UNSIGNED_FEED_URL
from pulp_2_tests.tests.rpm.utils import check_issue_2620, set_up_module


def setUpModule():  # pylint:disable=invalid-name
    """Execute ``pulp-admin login`` and reset Pulp.

    For :class:`RemovedContentTestCase` to function correctly, we require that
    all of the content units on Pulp's filesystem belong to the repository
    created by that test case. Resetting Pulp guarantees that this is so.
    Ideally, all test cases would clean up after themselves so that no resets
    are necessary.
    """
    cfg = config.get_config()
    set_up_module()
    reset_pulp(cfg)
    pulp_admin_login(cfg)


class _BaseTestCase(unittest.TestCase):
    """Delete all orphans after each test completes.

    This requirement is so common that it should perhaps be moved to a
    ``BaseCLITestCase``.
    """

    @classmethod
    def tearDownClass(cls):
        """Delete orphan content units."""
        cli.Client(config.get_config()).run((
            'pulp-admin', 'orphan', 'remove', '--all'
        ))


class RemovedContentTestCase(_BaseTestCase):
    """Test whether Pulp can re-sync content into a repository.

    This test case targets `Pulp #1775`_ and the corresponding Pulp Smash
    issue, `Pulp Smash #243`_.

    1. Create and sync a repository. Select a content unit.
    2. Delete the content unit from the repository, and verify it's absent.
    3. Sync the repository, and verify that the content unit is present.

    .. _Pulp #1775: https://pulp.plan.io/issues/1775
    .. _Pulp Smash #243: https://github.com/PulpQE/pulp-smash/issues/243
    """

    def test_all(self):
        """Test whether Pulp can re-sync content into a repository."""
        cfg = config.get_config()
        if check_issue_2620(cfg):
            self.skipTest('https://pulp.plan.io/issues/2620')
        repo_id = utils.uuid4()
        client = cli.Client(cfg)
        client.run((
            'pulp-admin', 'rpm', 'repo', 'create', '--repo-id', repo_id,
            '--feed', RPM_UNSIGNED_FEED_URL,
        ))
        self.addCleanup(client.run, (
            'pulp-admin', 'rpm', 'repo', 'delete', '--repo-id', repo_id,
        ))
        sync_repo(cfg, repo_id)
        unit_name = random.choice(get_rpm_names(cfg, repo_id))

        # remove a content unit from the repository
        client.run((
            'pulp-admin', 'rpm', 'repo', 'remove', 'rpm', '--repo-id', repo_id,
            '--str-eq', 'name={}'.format(unit_name),
        ))
        with self.subTest(comment='verify the rpm has been removed'):
            self.assertNotIn(unit_name, get_rpm_names(cfg, repo_id))

        # add a content unit to the repository
        proc = sync_repo(cfg, repo_id)
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream):
                self.assertNotIn('Invalid properties:', getattr(proc, stream))
        with self.subTest(comment='verify the rpm has been restored'):
            self.assertIn(unit_name, get_rpm_names(cfg, repo_id))


class ForceSyncTestCase(_BaseTestCase):
    """Test a forced full sync on Pulp.

    This test case targets `Pulp #1982`_ , `Pulp #4409`_ and `Pulp Smash #353`_.
    The test procedure is as follows:

    1. Create and sync a repository.
    2. Remove some number of units from ``/var/lib/pulp/content/units/`` sub-directory.
       Verify they are missing.
    3. Sync the repository. Verify the units are still missing.
    4. Sync the repository with ``--force-full true``. Verify all units are
       present.

    This test case has added distribution units and could be expanded to other unit types.

    .. _Pulp #1982: https://pulp.plan.io/issues/1982
    .. _Pulp #4409: https://pulp.plan.io/issues/4409
    .. _Pulp Smash #353: https://github.com/PulpQE/pulp-smash/issues/353
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide config."""
        cls.cfg = config.get_config()

    def test_rpm_content_units(self):
        """Test a forced full sync on Pulp.

        Using the tuple to target rpms units
        and looking for the .rpm extension, respectively.
        """
        if not selectors.bug_is_fixed(1982, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/1982')
        self._do_test(('rpm', 'rpm'), RPM_UNSIGNED_FEED_URL)

    def test_distribution_content_units(self):
        """Test a forced full sync on Pulp.

        Using the tuple to target distribution units
        and looking for the .img extension, respectively.

        The test fixture includes kickstart information as
        well as the use of a PULP_DISTRIBUTION.xml file to target
        additional files not listed in ``[.]treeinfo``. In this example,
        the ``isolinux/`` directory is added which contains additional
        .img files for the test.

        For more information about distribution units and the test
        fixture, see `Pulp #4409`_.

        .. _Pulp #4409: https://pulp.plan.io/issues/4409
        """
        if self.cfg.pulp_version < Version('2.19'):
            raise unittest.SkipTest('This test requires Pulp 2.19 or newer.')
        self._do_test(('distribution', 'img'), RPM_KICKSTART_FEED_URL)

    def _do_test(self, unit_type, feed):
        """Test whether one can force Pulp to perform a full sync."""
        # Create and sync a repository.
        client = cli.Client(self.cfg)
        repo_id = utils.uuid4()
        client.run((
            'pulp-admin', 'rpm', 'repo', 'create', '--repo-id', repo_id,
            '--feed', feed,
        ))
        self.addCleanup(client.run, (
            'pulp-admin', 'rpm', 'repo', 'delete', '--repo-id', repo_id,
        ))
        sync_repo(self.cfg, repo_id)

        # Delete a random unit from the filesystem.
        units = self._list_units(self.cfg, unit_type)
        unit = random.choice(units)
        cmd = []
        cmd.extend(('rm', '-rf', unit))
        client.run(cmd, sudo=True)
        with self.subTest(comment='verify the unit has been removed'):
            self.assertEqual(len(self._list_units(self.cfg, unit_type)), len(units) - 1, unit)

        # Sync the repository without --force-full.
        sync_repo(self.cfg, repo_id)
        with self.subTest(comment='verify the unit has not yet been restored'):
            self.assertEqual(len(self._list_units(self.cfg, unit_type)), len(units) - 1, unit)

        # Sync the repository with --force-full.
        sync_repo(self.cfg, repo_id, force_sync=True)
        with self.subTest(comment='verify the unit has been restored'):
            self.assertEqual(len(self._list_units(self.cfg, unit_type)), len(units), unit)

    @staticmethod
    def _list_units(cfg, unit_type):
        """Return a list of units in ``/var/lib/pulp/content/units/``.

        The unit type can be a number of different types.

        Examples are:
        * distribution
        * rpm
        * modulemd
        * modulemd_defaults

        This method should be extensible to take any ``unit_type`` and
        operate as required.
        """
        return cli.Client(cfg).run((
            'find',
            '/var/lib/pulp/content/units/{}'.format(unit_type[0]),
            '-type',
            'f',
            '-name', '*.{}'.format(unit_type[1])
        )).stdout.splitlines()


def get_rpm_names(cfg, repo_id):
    """Get a list of names of all packages in a repository.

    :param cfg: Information about a Pulp
        deployment.
    :param repo_id: A RPM repository ID.
    :returns: The names of all modules in a repository, as an ``list``.
    """
    keyword = 'Name:'
    proc = cli.Client(cfg).run((
        'pulp-admin', 'rpm', 'repo', 'content', 'rpm', '--repo-id', repo_id
    ))
    return [
        line.split(keyword)[1].strip() for line in proc.stdout.splitlines()
        if keyword in line
    ]


def sync_repo(cfg, repo_id, force_sync=False):
    """Sync an RPM repository.

    :param cfg: Information about a Pulp
        deployment.
    :param repo_id: A RPM repository ID.
    :param repo_id: A boolean flag to denote if is a force-full sync.
    :returns: A ``pulp_smash.cli.CompletedProcess``.
    """
    cmd = ['pulp-admin', 'rpm', 'repo', 'sync', 'run', '--repo-id', repo_id]
    if force_sync:
        cmd.append('--force-full')
    return cli.Client(cfg).run(cmd)
