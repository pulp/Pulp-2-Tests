# coding=utf-8
"""Tests that sync and publish RPM repositories.

For information on repository sync and publish operations, see
`Synchronization`_ and `Publication`_.

.. _Publication:
    http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/publish.html
.. _Synchronization:
    http://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/repo/sync.html
"""
import inspect
import os
import unittest
from threading import Thread
from urllib.parse import urljoin

from packaging.version import Version
from pulp_smash import api, cli, config, exceptions, utils
from pulp_smash.pulp2.constants import (
    ORPHANS_PATH,
    REPOSITORY_PATH,
)
from pulp_smash.pulp2.utils import (
    publish_repo,
    search_units,
    sync_repo,
)

from requests.exceptions import HTTPError

from pulp_2_tests.constants import (
    DRPM_UNSIGNED_FEED_URL,
    RPM,
    RPM_ERRATUM_COUNT,
    RPM_INCOMPLETE_FILELISTS_FEED_URL,
    RPM_INCOMPLETE_OTHER_FEED_URL,
    RPM_MISSING_FILELISTS_FEED_URL,
    RPM_MISSING_OTHER_FEED_URL,
    RPM_MISSING_PRIMARY_FEED_URL,
    RPM_NAMESPACES,
    RPM_SHA_512_FEED_URL,
    RPM_SIGNED_FEED_COUNT,
    RPM_SIGNED_FEED_URL,
    RPM_UNSIGNED_FEED_COUNT,
    RPM_UNSIGNED_FEED_URL,
    RPM_UNSIGNED_URL,
    RPM_ZCHUNK_FEED_COUNT,
    RPM_ZCHUNK_FEED_URL,
    SRPM_SIGNED_FEED_URL,
)
from pulp_2_tests.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    get_repodata_repomd_xml,
    get_unit,
)
from pulp_2_tests.tests.rpm.utils import (
    check_issue_3104,
    check_issue_4529,
)
from pulp_2_tests.tests.rpm.utils import set_up_module as setUpModule  # pylint:disable=unused-import


# This class is left public for documentation purposes.
class SyncRepoBaseTestCase(unittest.TestCase):
    """A parent class for repository syncronization test cases.

    :meth:`get_feed_url` should be overridden by concrete child classes. This
    method's response is used when setting the repository's importer feed URL.
    """

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository with a valid feed and sync it."""
        if inspect.getmro(cls)[0] == SyncRepoBaseTestCase:
            raise unittest.SkipTest('Abstract base class.')
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = cls.get_feed_url()
        cls.repo = cls.client.post(REPOSITORY_PATH, body)
        cls.report = sync_repo(cls.cfg, cls.repo)

    @classmethod
    def tearDownClass(cls):
        """Clean resources."""
        cls.client.delete(cls.repo['_href'])

    @staticmethod
    def get_feed_url():
        """Return an RPM repository feed URL. Should be overridden.

        :raises: ``NotImplementedError`` if not overridden by a child class.
        """
        raise NotImplementedError()

    def test_start_sync_code(self):
        """Assert the call to sync a repository returns an HTTP 202."""
        self.assertEqual(self.report.status_code, 202)

    def test_task_progress_report(self):
        """Assert no task's progress report contains error details.

        Other assertions about the final state of each task are handled by the
        client's response handler. (For more information, see the source of
        ``pulp_smash.api.safe_handler``.)
        """
        tasks = tuple(api.poll_spawned_tasks(self.cfg, self.report.json()))
        for i, task in enumerate(tasks):
            with self.subTest(i=i):
                error_details = task['progress_report']['yum_importer']['content']['error_details']  # pylint:disable=line-too-long
                self.assertEqual(error_details, [], task)


class SyncRpmRepoTestCase(SyncRepoBaseTestCase):
    """Test one can create and sync an RPM repository with an RPM feed."""

    @staticmethod
    def get_feed_url():
        """Return an RPM repository feed URL."""
        return RPM_SIGNED_FEED_URL

    # This is specific to the RPM repo. Leave in this test case.
    def test_unit_count_on_repo(self):
        """Verify that the sync added the correct number of units to the repo.

        Read the repository and examine its ``content_unit_counts`` attribute.
        Compare these attributes to metadata from the remote repository.
        Expected values are currently hard-coded into this test.
        """
        content_unit_counts = {
            'rpm': RPM_SIGNED_FEED_COUNT,
            'erratum': 4,
            'package_group': 2,
            'package_category': 1,
        }
        # langpack support was added in 2.9
        if self.cfg.pulp_version >= Version('2.9'):
            content_unit_counts['package_langpacks'] = 1
        repo = api.Client(self.cfg).get(self.repo['_href']).json()
        self.assertEqual(repo['content_unit_counts'], content_unit_counts)

    def test_no_change_in_second_sync(self):
        """Verify that syncing a second time has no changes.

        If the repository have not changed then Pulp must state that anything
        was changed when doing a second sync.
        """
        report = sync_repo(self.cfg, self.repo)
        tasks = tuple(api.poll_spawned_tasks(self.cfg, report.json()))
        with self.subTest(comment='spawned tasks'):
            self.assertEqual(len(tasks), 1)
        for count_type in ('added_count', 'removed_count', 'updated_count'):
            with self.subTest(comment=count_type):
                self.assertEqual(tasks[0]['result'][count_type], 0, tasks)


class SyncDrpmRepoTestCase(SyncRepoBaseTestCase):
    """Test one can create and sync an RPM repository with an DRPM feed."""

    @staticmethod
    def get_feed_url():
        """Return an DRPM repository feed URL."""
        return DRPM_UNSIGNED_FEED_URL


class SyncSrpmRepoTestCase(SyncRepoBaseTestCase):
    """Test one can create and sync an RPM repository with an SRPM feed."""

    @staticmethod
    def get_feed_url():
        """Return an SRPM repository feed URL."""
        return SRPM_SIGNED_FEED_URL


class SyncInvalidMetadataTestCase(unittest.TestCase):
    """Sync various repositories with invalid metadata.

    When a repository with invalid metadata is encountered, Pulp should
    gracefully fail. This test case targets `Pulp #1287
    <https://pulp.plan.io/issues/1287>`_.
    """

    @classmethod
    def tearDownClass(cls):
        """Delete orphan content units."""
        api.Client(config.get_config()).delete(ORPHANS_PATH)

    def test_incomplete_filelists(self):
        """Sync a repository with an incomplete ``filelists.xml`` file."""
        self.do_test(RPM_INCOMPLETE_FILELISTS_FEED_URL)

    def test_incomplete_other(self):
        """Sync a repository with an incomplete ``other.xml`` file."""
        self.do_test(RPM_INCOMPLETE_OTHER_FEED_URL)

    def test_missing_filelists(self):
        """Sync a repository that's missing its ``filelists.xml`` file."""
        self.do_test(RPM_MISSING_FILELISTS_FEED_URL)

    def test_missing_other(self):
        """Sync a repository that's missing its ``other.xml`` file."""
        self.do_test(RPM_MISSING_OTHER_FEED_URL)

    def test_missing_primary(self):
        """Sync a repository that's missing its ``primary.xml`` file."""
        self.do_test(RPM_MISSING_PRIMARY_FEED_URL)

    def do_test(self, feed_url):
        """Implement the logic described by each of the ``test*`` methods."""
        cfg = config.get_config()
        client = api.Client(cfg)
        body = gen_repo()
        body['importer_config']['feed'] = feed_url
        repo = client.post(REPOSITORY_PATH, body).json()
        self.addCleanup(client.delete, repo['_href'])

        with self.assertRaises(exceptions.TaskReportError) as context:
            sync_repo(cfg, repo)
        task = context.exception.task
        self.assertEqual(
            'NOT_STARTED',
            task['progress_report']['yum_importer']['content']['state'],
            task,
        )


class ChangeFeedTestCase(unittest.TestCase):
    """Sync a repository, change its feed, and sync it again.

    Specifically, the test case procedure is as follows:

    1. Create three repositories — call them A, B and C.
    2. Populate repository A and B with identical content, and publish them.
    3. Set C's feed to repository A. Sync and publish repository C.
    4. Set C's feed to repository B. Sync and publish repository C.
    5. Download an RPM from repository C.

    The entire procedure should succeed. This test case targets `Pulp #1922
    <https://pulp.plan.io/issues/1922>`_.
    """

    @classmethod
    def setUpClass(cls):
        """Set config and client used by each test case."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_all(self):
        """Sync a repository, change its feed, and sync it again."""
        if check_issue_3104(self.cfg):
            self.skipTest('https://pulp.plan.io/issues/3104')

        # Create, sync and publish repositories A and B.
        repos = []
        for _ in range(2):
            body = gen_repo()
            body['importer_config']['feed'] = RPM_UNSIGNED_FEED_URL
            body['distributors'] = [gen_distributor()]
            repos.append(self.create_sync_publish_repo(body))

        # Create repository C, let it sync from repository A, and publish it.
        body = gen_repo()
        body['importer_config']['feed'] = self.get_feed(repos[0])
        body['importer_config']['ssl_validation'] = False
        body['distributors'] = [gen_distributor()]
        repo = self.create_sync_publish_repo(body)

        # Update repository C.
        feed = self.get_feed(repos[1])
        self.client.put(repo['importers'][0]['_href'], {
            'importer_config': {'feed': feed}
        })
        repo = self.client.get(repo['_href'], params={'details': True})
        self.assertEqual(repo['importers'][0]['config']['feed'], feed)

        # Sync and publish repository C.
        sync_repo(self.cfg, repo)
        publish_repo(self.cfg, repo)

        rpm = utils.http_get(RPM_UNSIGNED_URL)
        response = get_unit(self.cfg, repo['distributors'][0], RPM)
        with self.subTest():
            self.assertIn(
                response.headers['content-type'],
                ('application/octet-stream', 'application/x-rpm')
            )
        with self.subTest():
            self.assertEqual(rpm, response.content)

    def create_sync_publish_repo(self, body):
        """Create, sync and publish a repository.

        Also, schedule the repository for deletion.

        :param body: A dict of information to use when creating the repository.
        :return: A detailed dict of information about the repository.
        """
        repo = self.client.post(REPOSITORY_PATH, body)
        self.addCleanup(self.client.delete, repo['_href'])
        repo = self.client.get(repo['_href'], params={'details': True})
        sync_repo(self.cfg, repo)
        publish_repo(self.cfg, repo)
        return repo

    def get_feed(self, repo):
        """Build the feed to an RPM repository's distributor."""
        feed = urljoin(self.cfg.get_base_url(), 'pulp/repos/')
        return urljoin(feed, repo['distributors'][0]['config']['relative_url'])


class SyncInParallelTestCase(unittest.TestCase):
    """Sync several repositories in parallel."""

    def test_all(self):
        """Sync several repositories in parallel.

        Specifically, do the following:

        1. Create several repositories. Ensure each repository has an importer
           whose feed references a repository containing one or more errata.
        2. Sync each repository. Assert each sync completed successfully.
        3. Get a summary of information about each repository, and assert the
           repo has an appropriate number of errata.

        `Pulp #2721`_ describes how a race condition can occur when multiple
        repos with identical errata are synced at the same time. This test case
        attempts to trigger that race condition.

        .. _Pulp #2721: https://pulp.plan.io/issues/2721
        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        repos = []  # append() is thread-safe

        def create_repo():
            """Create a repository and schedule its deletion.

            Append a dict of information about the repository to ``repos``.
            """
            body = gen_repo()
            body['importer_config']['feed'] = RPM_UNSIGNED_FEED_URL
            repo = client.post(REPOSITORY_PATH, body)
            self.addCleanup(client.delete, repo['_href'])
            repos.append(repo)

        def get_repo(repo):
            """Get information about a repository. Append it to ``repos``.

            :param repo: A dict of information about a repository.
            """
            repos.append(client.get(repo['_href']))

        threads = tuple(Thread(target=create_repo) for _ in range(5))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        threads = tuple(
            Thread(target=sync_repo, args=(cfg, repo)) for repo in repos
        )
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        threads = tuple(
            Thread(target=get_repo, args=(repo,)) for repo in repos
        )
        repos.clear()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        for repo in repos:
            with self.subTest():
                self.assertEqual(
                    repo['content_unit_counts']['erratum'],
                    RPM_ERRATUM_COUNT,
                )


class ErrorReportTestCase(unittest.TestCase):
    """Test whether an error report contains sufficient information."""

    def test_invalid_feed_error_message(self):
        """Test whether an error report contains sufficient information.

        Do the following:

        1. Create and sync a repository using an invalid feed URL.
        2. Get a reference to the task containing error information.
        3. Assert that:

           * The error description is sufficiently verbose. See `Pulp #1376`_
             and `Pulp Smash #525`_.
           * The traceback is non-null. See `Pulp #1455`_.

        .. _Pulp #1376: https://pulp.plan.io/issues/1376
        .. _Pulp #1455: https://pulp.plan.io/issues/1455
        .. _Pulp Smash #525: https://github.com/PulpQE/pulp-smash/issues/525
        """
        task = self.run_task(gen_repo(importer_config={'feed': utils.uuid4()}))

        with self.subTest(comment='check task error description'):
            tokens = ['scheme', 'must', 'be', 'http', 'https', 'file']
            self.assertTrue(
                all(
                    [
                        token
                        in task['error']['description'].lower()
                        for token in tokens
                    ]
                )
            )

    def test_missing_filelists_error_message(self):
        """Test whether an error report contains sufficient information.

        Do the following:

        1. Create and sync a repository using a missing filelist feed URL.
        2. Get a reference to the task containing error information.
        3. Assert that:

           * The error description is sufficiently verbose. See `Pulp #4262`_
           * The traceback is non-null. See `Pulp #1455`_.

        .. _Pulp #4262: https://pulp.plan.io/issues/4262
        """
        cfg = config.get_config()
        if cfg.pulp_version < Version('2.19'):
            raise unittest.SkipTest('This test requires Pulp 2.19 or newer.')

        repo_body = gen_repo(
            importer_config={'feed': RPM_MISSING_FILELISTS_FEED_URL}
        )
        task = self.run_task(repo_body)

        with self.subTest(comment='check task error description'):
            tokens = ['error', 'metadata', 'not', 'found']
            self.assertTrue(
                all(
                    [
                        token
                        in task['error']['description'].lower()
                        for token in tokens
                    ]
                )
            )

    def run_task(self, repo_body):
        """Implement the logic described by each of the ``test*`` methods."""
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        repo = client.post(REPOSITORY_PATH, repo_body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})

        with self.assertRaises(exceptions.TaskReportError) as context:
            sync_repo(cfg, repo)

        task = context.exception.task

        with self.subTest(comment='check task traceback'):
            self.assertIsNotNone(task['traceback'], task)

        return task


class NonExistentRepoTestCase(unittest.TestCase):
    """Perform actions on non-existent repositories.

    This test targets `Pulp Smash #157
    <https://github.com/PulpQE/pulp-smash/issues/157>`_.
    """

    def setUp(self):
        """Set variables used by each test case."""
        self.cfg = config.get_config()
        self.repo = {'_href': urljoin(REPOSITORY_PATH, utils.uuid4())}

    def test_sync(self):
        """Sync a non-existent repository."""
        with self.assertRaises(HTTPError):
            sync_repo(self.cfg, self.repo)

    def test_publish(self):
        """Publish a non-existent repository."""
        with self.assertRaises(HTTPError):
            publish_repo(self.cfg, self.repo, {'id': utils.uuid4()})


class SyncSha512RPMPackageTestCase(unittest.TestCase):
    """Test whether user can sync RPM repo with sha512 checksum."""

    def test_all(self):
        """Test whether RPM repo with sha512 checksum is synced correctly.

        Do the following:

        1. Create a repo pointing to ``RPM_SHA_512_FEED_URL``.
        2. Sync the repo and verify whether it is synced correctly.
        3. Auto Publish the repo and check whether the ``repomd.xml`` contains
           all checksum objects of type ``sha512``.

        This test targets `Pulp Plan #4007
        <https://pulp.plan.io/issues/4007>`_.
        """
        cfg = config.get_config()
        if cfg.pulp_version < Version('2.18'):
            raise unittest.SkipTest('This test requires Pulp 2.18 or newer.')
        client = api.Client(cfg, api.json_handler)
        body = gen_repo(
            importer_config={'feed': RPM_SHA_512_FEED_URL},
            distributors=[gen_distributor(auto_publish=True)]
        )
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        sync_repo(cfg, repo)
        repo = client.get(repo['_href'], params={'details': True})

        # retrieving the published repo
        xml_element = get_repodata_repomd_xml(cfg, repo['distributors'][0])
        xpath = (
            '{{{namespace}}}data/{{{namespace}}}checksum'.format(
                namespace=RPM_NAMESPACES['metadata/repo']
            )
        )
        checksum_type = {
            element.attrib['type']
            for element in xml_element.findall(xpath)
        }
        self.assertEqual(checksum_type, {'sha512'}, checksum_type)
        self.assertEqual(
            repo['content_unit_counts']['rpm'],
            RPM_UNSIGNED_FEED_COUNT,
            repo['content_unit_counts']['rpm'],
        )


class SyncZchunkRepoSkipTestCase(unittest.TestCase):
    """Sync feed with ``zchunks`` and ensure no ``zchunk`` units exist.

    A new compression type for repodata exists in Fedora 30 called
    ``zchunks``. These can be created with patches made to
    ``createrepo_c --zck``.

    Pulp 2 will ignore this repodata archive type to preserve the quality of
    the existing data. At the time of writing this test, ``zchunk`` data is
    in addition to standard repodata. There are currently no cases of
    repodata only containing ``zchunk`` archives.

    For the scope of this test, units are checked in the published location.
    This prevents finding duplicate units from other repositories outside the
    scope of the test while still testing the logic the units were not
    synced.

    This test targets the following issues:

    `Pulp #4529 <https://pulp.plan.io/issues/4529>`_
    `Pulp #4530 <https://pulp.plan.io/issues/4530>`_

    Steps:

    1. Create a repo point to a ``zchunk`` feed. Synch and publish the repo.
    2. Assert no published with the ``.zck`` extension.
    3. Assert all other units with the repo exist.

    """

    def test_zchunk_sync(self):
        """Sync a repo and verify Pulp 2 does not sync ``.zck`` data."""
        cfg = config.get_config()
        if check_issue_4529(cfg):
            self.skipTest('https://pulp.plan.io/issues/4529')
        client = api.Client(cfg, api.json_handler)

        # Sync Repo
        # Publish to ensure search path is constant
        body = gen_repo(
            importer_config={'feed': RPM_ZCHUNK_FEED_URL},
            distributors=[gen_distributor(auto_publish=True)]
        )
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        sync_repo(cfg, repo)

        # Check there are no search_units found of .zck
        self.assertFalse(
            cli.Client(cfg).run((
                'find',
                os.path.join(
                    '/var/lib/pulp/published/yum/master/yum_distributor/',
                    repo['id']
                ),
                '-type',
                'f',
                '-name',
                '*.zck'
            ), sudo=True).stdout.splitlines())

        # Verify other content units were copied
        copied_unit_ids = [
            unit['metadata']['name']
            for unit in search_units(cfg, repo, {'type_ids': ['rpm']})
        ]
        self.assertEqual(
            len(copied_unit_ids),
            RPM_ZCHUNK_FEED_COUNT,
            copied_unit_ids
        )
