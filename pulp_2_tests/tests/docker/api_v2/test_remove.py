# coding=utf-8
"""Tests for removing docker units."""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import search_units, sync_repo

from pulp_2_tests.constants import DOCKER_V2_FEED_URL
from pulp_2_tests.tests.docker.api_v2.utils import gen_repo
from pulp_2_tests.tests.docker.utils import get_upstream_name

# Dummy Data - Need to datamine a DOCKER repo
DOCKER_REMOVE = {
    'INITIAL': {
        'docker_manifest': 14,
        'docker_manifest_list': 4,
        'docker_blob': 8,
        'docker_tag': 18
    },
    'NON-SHARED': {
    'docker_manifest': 4,
    'docker_manifest_list': 2,
    'docker_blob': 8,
    'docker_tag': 0
    }
}

DOCKER_UNIT_TYPES = [        
        'docker_tag',
        'docker_manifest_list',
        'docker_manifest',
        'docker_blob'
]

UPSTREAM_NAME = 'pulp/test-fixture-1'
NON_SHARED_MANIFEST_LIST = [ 
        'sha256:099e168f98f6989fef22b4e32066e8a1ffcdb3a3fe6fcfae1d5fccb285710a12',
        'sha256:378cbadefc7a77858091bdc07e26ce999a27d295b7b2cf9ae80f81bb6a84d8f9',
]

from pprint import pprint
from ipdb import set_trace

class RemoveV2ContentTestCase(unittest.TestCase):
    """Ensure content removal of Docker repository information.

    With the refactor of the docker importer's remove function to
    increase performance, content removal needs to be functional verified.

    The cases covered with content post-count verification for all units:

    1. Remove all tags.
    2. Remove all manifest_lists.
    3. Remove all manifests.
    4. Remove some non-shared manifest lists.
    5. Remove some non-shared manifest.
    6. Remove some shared manifests lists and verify shared units are not
       recursively removed.
    7. Remove some shared manifests and verify shared units are not
       recursively removed.
    """

    @classmethod
    def setUpClass(cls):
        """Set variables used by each test case."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

    def setUp(self):
        """Set variables used by each test case."""
        body = gen_repo(
            importer_config={
                'enable_v1': False,
                'enable_v2': True,
                'feed': DOCKER_V2_FEED_URL,
                'upstream_name': UPSTREAM_NAME,
            }
        )
        self.repo = self.client.post(REPOSITORY_PATH, body)
        self.addCleanup(self.client.delete, self.repo['_href'])
        sync_repo(self.cfg, self.repo)

    def create_and_copy_test_repo(self, source_repo, copy_units):
        """Return repo of repos for test."""
        body = gen_repo(
            importer_config={
                'enable_v1': False,
                'enable_v2': True,
            }
        )
        repo = self.client.post(REPOSITORY_PATH, body)
        self.copy_docker_units(repo, source_repo, copy_units)
        return repo

    def copy_docker_units(self, repo, source_repo, units):
        """Copy specified docker units."""
        criteria = {
            'type_ids': [
                'docker_tag',
                'docker_manifest_list',
                'docker_manifest',
                'docker_blob',
            ],
            'filters': {'unit': {'digest': {"$in": units}}},
        }
        self.client.post(
            urljoin(repo['_href'], 'actions/associate/'),
            {'source_repo_id': source_repo['id'], 'criteria': criteria},
        )

    def get_docker_units(self, repo, unit_type):
        """Return docker units filtered by type."""
        # Get unit counts
        
        units = {}
        for unit in unit_type:
         units[unit] = (len(search_units(
            self.cfg, repo, {'type_ids': [unit], 'filters': {'unit': {}}}
        )))
        return units

    def delete_docker_units(self, repo, units):
        """Delete docker units."""
        for unit in units:
            criteria = {
                'type_ids': [
                    'docker_tag',
                    'docker_manifest_list',
                    'docker_manifest',
                    'docker_blob',
                ],
                # 'filters': {'unit': {'_id': unit['unit_id']}},
                # "filters": {"unit": {"digest": {"$in": units}}}
                # "filters": {"unit": {"digest": {"$in": []}}
            }
            self.client.post(
                urljoin(repo['_href'], 'actions/unassociate/'),
                {'source_repo_id': repo['id'], 'criteria': criteria},
            )

    def test_00_test(self):
        """foo"""
        repo = self.create_and_copy_test_repo(self.repo, NON_SHARED_MANIFEST_LIST)
        self.addCleanup(self.client.delete, repo['_href'])

        docker_units = self.get_docker_units(repo, DOCKER_UNIT_TYPES)
        for unit in docker_units:
            with self.subTest(unit=unit):
             self.assertEqual(
                docker_units[unit], 
                DOCKER_REMOVE['NON-SHARED'][unit], 
                docker_units
            )

    # def test_01_remove_tag_list_all(self):
    #     """Sync docker repo and remove all tags."""
    #     # Verify initial unit count
    #     units = self.get_docker_units(self.repo, 'docker_tag')
    #     self.assertEqual(len(units), DOCKER_REMOVE['INITIAL']['TAG'], units)

    #     # Delete by tag - ensure there are no units left
    #     self.delete_docker_units(self.repo, units)

    #     # Count the remaining units
    #     remaining_units = self.get_docker_units(self.repo, 'docker_tag')
    #     self.assertEqual(len(remaining_units), 0, remaining_units)

    # def test_02_remove_manifest_list_all(self):
    #     """Sync docker repo and remove all manifest_lists."""
    #     # Verify initial unit count
    #     units = self.get_docker_units(self.repo, 'docker_manifest_list')
    #     self.assertEqual(len(units), DOCKER_REMOVE['INITIAL']['MANIFEST_LIST'], units)

    #     # Delete by tag - ensure there are no units left
    #     self.delete_docker_units(self.repo, units)

    #     # Count the remaining units
    #     remaining_units = self.get_docker_units(self.repo, 'docker_manifest_list')
    #     self.assertEqual(len(remaining_units), 0, remaining_units)

    # def test_03_remove_manifest_all(self):
    #     """Sync docker repo and remove all manifests."""
    #     # Verify initial unit count
    #     units = self.get_docker_units(self.repo, 'docker_manifest')
    #     self.assertEqual(len(units), DOCKER_REMOVE['INITIAL']['MANIFEST'], units)

    #     # Delete by tag - ensure there are no units left
    #     self.delete_docker_units(self.repo, units)

    #     # Count the remaining units
    #     remaining_units = self.get_docker_units(self.repo, 'docker_manifest')
    #     self.assertEqual(len(remaining_units), 0, remaining_units)

    # # pylint: disable=R0201
    # def test_04_remove_manifest_list_not_shared(self):
    #     """Sync docker repo and remove some non-shared manifest_lists."""
    #     raise unittest.SkipTest('Stubbed test case, Not Implemented Yet')

    # def test_05_remove_manifest_list_shared(self):
    #     """Sync docker repo and remove some shared manifest_lists."""
    #     raise unittest.SkipTest('Stubbed test case, Not Implemented Yet')

    # def test_06_remove_manifest_not_shared(self):
    #     """Sync docker repo and remove some non-shared manifests."""
    #     raise unittest.SkipTest('Stubbed test case, Not Implemented Yet')

    # def test_07_remove_manifest_shared(self):
    #     """Sync docker repo and remove some shared manifests."""
    #     raise unittest.SkipTest('Stubbed test case, Not Implemented Yet')
