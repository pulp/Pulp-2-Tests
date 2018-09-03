"""Tests search of the contents of a repository."""
import unittest

from packaging.version import Version

from pulp_smash import cli, config, utils
from pulp_smash.pulp2.utils import pulp_admin_login

from pulp_2_tests.constants import RPM_RICH_WEAK_FEED_URL
from pulp_2_tests.tests.rpm.cli.utils import sync_repo
from pulp_2_tests.tests.rpm.utils import rpm_rich_weak_dependencies
from pulp_2_tests.tests.rpm.utils import set_up_module as setUpModule  # pylint:disable=unused-import


class RichWeakTestCase(unittest.TestCase):
    """Search for contents in a Rich/Weak repository.

    This test targets `Pulp #3929`_ and `Pulp Smash #901`_. The
    `repository content`_ documentation describes the CLI content syntax.

    .. _Pulp #3929:  https://pulp.plan.io/issues/3929
    .. _Pulp Smash #901: https://github.com/PulpQE/pulp-smash/issues/901
    .. _repository content:
        https://docs.pulpproject.org/en/latest/user-guide/admin-client/repositories.html#content-search
    """

    @classmethod
    def setUpClass(cls):
        """Create a repository."""
        cfg = config.get_config()
        if cfg.pulp_version < Version('2.17'):
            raise unittest.SkipTest('This test requires Pulp 2.17 or newer.')
        if not rpm_rich_weak_dependencies(cfg):
            raise unittest.SkipTest('This test requires RPM 4.12 or newer.')
        pulp_admin_login(cfg)
        cls.client = cli.Client(cfg)
        cls.repo_id = utils.uuid4()
        cls.client.run(
            'pulp-admin rpm repo create --repo-id {0} '
            '--relative-url {0} --feed {1}'
            .format(cls.repo_id, RPM_RICH_WEAK_FEED_URL).split()
        )
        sync_repo(cfg, cls.repo_id)

    def test_positive_shows_required_fields(self):
        """Search contents of a richnweak repository matching package name.

        Asserts the required fields are present.
        """
        result = self.client.run(
            'pulp-admin rpm repo content rpm --repo-id {} '
            '--match name=Cobbler'
            .format(self.repo_id).split()
        )
        required_fields = ('Recommends:', 'Requires:', 'Provides:')
        for field in required_fields:
            with self.subTest(field=field):
                self.assertEqual(result.stdout.count(field), 1, result)

    @classmethod
    def tearDownClass(cls):
        """Delete the repository created by :meth:`setUpClass`."""
        cls.client.run(
            'pulp-admin rpm repo delete --repo-id {}'
            .format(cls.repo_id).split()
        )
