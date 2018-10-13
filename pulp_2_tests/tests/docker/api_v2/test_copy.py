# coding=utf-8
"""Tests for copying docker units between repositories."""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config, selectors
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import search_units, sync_repo

from pulp_2_tests.constants import DOCKER_V1_FEED_URL, DOCKER_V2_FEED_URL
from pulp_2_tests.tests.docker.api_v2.utils import gen_repo
from pulp_2_tests.tests.docker.utils import get_upstream_name, skip_if
from pulp_2_tests.tests.docker.utils import set_up_module as setUpModule  # pylint:disable=unused-import


class CopyV1ContentTestCase(unittest.TestCase):
    """Copy data between Docker repositories with schema v1 content."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        super().setUpClass()
        cls.cfg = config.get_config()
        cls.repo = {}
        cls.client = api.Client(cls.cfg, api.json_handler)

    @classmethod
    def tearDownClass(cls):
        """Clean up resources."""
        if cls.repo:
            api.Client(cls.cfg).delete(cls.repo['_href'])
        super().tearDownClass()

    def test_01_set_up(self):
        """Create a repository and populate with with schema v1 content."""
        body = gen_repo()
        body['importer_config'].update({
            'enable_v1': True,
            'enable_v2': False,
            'feed': DOCKER_V1_FEED_URL,
            'upstream_name': get_upstream_name(self.cfg),
        })
        type(self).repo = self.client.post(REPOSITORY_PATH, body)
        sync_repo(self.cfg, self.repo)
        type(self).repo = self.client.get(
            self.repo['_href'],
            params={'details': True}
        )

    @skip_if(bool, 'repo', False)
    def test_02_copy_images(self):
        """Copy tags from one repository to another.

        Assert the same number of images are present in both repositories.
        """
        repo = self.client.post(REPOSITORY_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])
        self.client.post(urljoin(repo['_href'], 'actions/associate/'), {
            'source_repo_id': self.repo['id'],
            'criteria': {'filters': {}, 'type_ids': ['docker_image']},
        })
        repo = self.client.get(repo['_href'], params={'details': True})
        self.assertEqual(
            self.repo['content_unit_counts']['docker_image'],
            repo['content_unit_counts'].get('docker_image', 0),
        )


class CopyV2ContentTestCase(unittest.TestCase):
    """Copy data between Docker repositories with schema v2 content."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        super().setUpClass()
        cls.cfg = config.get_config()
        cls.repo = {}
        cls.client = api.Client(cls.cfg, api.json_handler)

    @classmethod
    def tearDownClass(cls):
        """Clean up resources."""
        if cls.repo:
            api.Client(cls.cfg).delete(cls.repo['_href'])
        super().tearDownClass()

    def test_01_set_up(self):
        """Create a repository and populate with with schema v2 content."""
        body = gen_repo()
        body['importer_config'].update({
            'enable_v1': False,
            'enable_v2': True,
            'feed': DOCKER_V2_FEED_URL,
            'upstream_name': get_upstream_name(self.cfg),
        })
        type(self).repo = self.client.post(REPOSITORY_PATH, body)
        sync_repo(self.cfg, self.repo)
        type(self).repo = self.client.get(
            self.repo['_href'],
            params={'details': True}
        )

    @skip_if(bool, 'repo', False)
    def test_02_copy_tags(self):
        """Copy tags from one repository to another.

        Assert the same number of tags are present in both repositories.

        This test targets `Pulp #3892 <https://pulp.plan.io/issues/3892>`_.
        """
        if not selectors.bug_is_fixed(3892, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/3892')
        repo = self.client.post(REPOSITORY_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])
        self.client.post(urljoin(repo['_href'], 'actions/associate/'), {
            'source_repo_id': self.repo['id'],
            'criteria': {'filters': {}, 'type_ids': ['docker_tag']},
        })
        repo = self.client.get(repo['_href'], params={'details': True})
        self.assertEqual(
            self.repo['content_unit_counts']['docker_tag'],
            repo['content_unit_counts'].get('docker_tag', 0),
        )

    @skip_if(bool, 'repo', False)
    def test_02_copy_tags_user_metadata(self):
        """Copy tags with user_metadata from one repository to another.

        Assert the user metadata associated with a tag is present in
        both repositories.

        Steps:

        1. Add user metadata to the first tag in the source repo.
        2. Copy the tags from one repo to the other.
        3. Verify that the user_metadata is copied to the other repo.

        This test targets the following

        * `Pulp #3242 <https://pulp.plan.io/issues/3242>`_.
        * `Pulp-2-tests #72 <https://github.com/PulpQE/Pulp-2-Tests/issues/72>`_.
        """
        if not selectors.bug_is_fixed(3892, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/3892')

        # Step 1
        tag_first_repo = search_units(
            self.cfg, self.repo,
            {'type_ids': ['docker_tag']}
        )[0]

        user_metadata = {
            'dummy_key_1': 'dummy_value_1',
            'dummy_key_2': 'dummy_value_2',
        }
        self.set_user_metadata(tag_first_repo, user_metadata)

        # Step 2
        repo = self.client.post(REPOSITORY_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])
        self.client.post(urljoin(repo['_href'], 'actions/associate/'), {
            'source_repo_id': self.repo['id'],
            'criteria': {'filters': {}, 'type_ids': ['docker_tag']},
        })

        units = search_units(
            self.cfg, repo, {
                'type_ids': ['docker_tag'],
                'filters': {
                    'unit': {
                        'name': tag_first_repo['metadata']['name'],
                        'schema_version': tag_first_repo['metadata']['schema_version']
                    }
                },
            })

        # Step 3
        self.assertEqual(units[0]['metadata']['pulp_user_metadata'], user_metadata, units)

    @skip_if(bool, 'repo', False)
    def test_02_copy_manifests(self):
        """Copy manifests from one repository to another.

        Assert the same number of manifests are present in both repositories.
        """
        repo = self.client.post(REPOSITORY_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])
        self.client.post(urljoin(repo['_href'], 'actions/associate/'), {
            'criteria': {'filters': {}, 'type_ids': ['docker_manifest']},
            'source_repo_id': self.repo['id'],
        })
        repo = self.client.get(repo['_href'], params={'details': True})
        self.assertEqual(
            self.repo['content_unit_counts']['docker_manifest'],
            repo['content_unit_counts'].get('docker_manifest', 0),
        )

    @skip_if(bool, 'repo', False)
    def test_02_copy_manifest_lists(self):
        """Copy manifest lists from one repository to another.

        Assert the same number of manifest lists are present in both
        repositories. This test targets:

        * `Pulp #2384 <https://pulp.plan.io/issues/2384>`_
        * `Pulp #2385 <https://pulp.plan.io/issues/2385>`_
        * `Pulp #3892 <https://pulp.plan.io/issues/3892>`_
        """
        for issue_id in (2384, 2385, 3892):
            if not selectors.bug_is_fixed(issue_id, self.cfg.pulp_version):
                self.skipTest(
                    'https://pulp.plan.io/issues/{}'.format(issue_id)
                )
        repo = self.client.post(REPOSITORY_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])
        self.client.post(urljoin(repo['_href'], 'actions/associate/'), {
            'criteria': {'filters': {}, 'type_ids': ['docker_manifest_list']},
            'source_repo_id': self.repo['id'],
        })
        repo = self.client.get(repo['_href'], params={'details': True})
        self.assertEqual(
            self.repo['content_unit_counts']['docker_manifest_list'],
            repo['content_unit_counts'].get('docker_manifest_list', 0),
        )

    def set_user_metadata(self, tag, content):
        """Associate docker ``tag`` to user metadata ``content``.

        For information on setting user_metadata to ``tag`` refer `Docker Content Units`_.

        .. _Docker Content Units:
            https://docs.pulpproject.org/dev-guide/integration/rest-api/content/units.html
        """
        path = '/pulp/api/v2/content/units/{}/{}/pulp_user_metadata/'.format(
            tag['unit_type_id'], tag['unit_id']
        )
        self.client.put(path, content)
