# coding=utf-8
"""Tests for recursively removing docker units sequentially and in batch."""
import unittest
from random import choice
from urllib.parse import urljoin
from types import MappingProxyType

from packaging.version import Version
from pulp_smash import api, config
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import search_units, sync_repo

from pulp_2_tests.constants import (
    DOCKER_REMOVE_UPSTREAM_NAME,
    DOCKER_V2_FEED_URL,
)

from pulp_2_tests.tests.docker.api_v2.utils import gen_repo


# Docker Unit Counts Required for Verification Scenarios
DOCKER_REMOVE = MappingProxyType({
    'FULL': {
        'docker_manifest': 14,
        'docker_manifest_list': 4,
        'docker_blob': 8,
        'docker_tag': 18,
    },
    'NON_SHARED_MANIFEST_LIST': {
        'docker_manifest': 4,
        'docker_manifest_list': 2,
        'docker_blob': 8,
        'docker_tag': 0,
    },
    'NON_SHARED_MANIFEST_LIST_DELETE': {
        'docker_manifest': 2,
        'docker_manifest_list': 1,
        'docker_blob': 4,
        'docker_tag': 0,
    },
    'SHARED_MANIFEST_LIST_DELETE': {
        'docker_manifest': 2,
        'docker_manifest_list': 1,
        'docker_blob': 4,
        'docker_tag': 0,
    },
    'SHARED_MANIFEST_LIST': {
        'docker_manifest': 3,
        'docker_manifest_list': 2,
        'docker_blob': 6,
        'docker_tag': 0,
    },
    'NON_SHARED_MANIFEST': {
        'docker_manifest': 2,
        'docker_manifest_list': 0,
        'docker_blob': 4,
        'docker_tag': 0,
    },
    'SHARED_MANIFEST': {
        'docker_manifest': 2,
        'docker_manifest_list': 0,
        'docker_blob': 3,
        'docker_tag': 0,
    },
    'NON_SHARED_MANIFEST_DELETE': {
        'docker_manifest': 1,
        'docker_manifest_list': 0,
        'docker_blob': 2,
        'docker_tag': 0,
    },
    'SHARED_MANIFEST_DELETE': {
        'docker_manifest': 1,
        'docker_manifest_list': 0,
        'docker_blob': 2,
        'docker_tag': 0,
    },
    'NONE': {
        'docker_manifest': 0,
        'docker_manifest_list': 0,
        'docker_blob': 0,
        'docker_tag': 0,
    },
    'ALL_V2': {
        'docker_manifest': 5,
        'docker_manifest_list': 4,
        'docker_blob': 10,
        'docker_tag': 0,
    },
    'ALL_V2_MANIFEST_DELETE': {
        'docker_manifest': 0,
        'docker_manifest_list': 4,
        'docker_blob': 0,
        'docker_tag': 0,
    },
    'ALL_V2_BLOB_DELETE': {
        'docker_manifest': 5,
        'docker_manifest_list': 4,
        'docker_blob': 0,
        'docker_tag': 0,
    },
    'ALL_V2_MANIFEST_COPY': {
        'docker_manifest': 5,
        'docker_manifest_list': 0,
        'docker_blob': 10,
        'docker_tag': 0,
    },
    'ALL_V2_BLOB_COPY': {
        'docker_manifest': 0,
        'docker_manifest_list': 0,
        'docker_blob': 10,
        'docker_tag': 0,
    },
})

# """ All docker unit types passed to allow filter to determine removal."""
DOCKER_UNIT_TYPES = [
    'docker_tag',
    'docker_manifest_list',
    'docker_manifest',
    'docker_blob'
]

# All Docker SHA256s
#   The SHA256s are used as these do not change as the fixture or content is
#   synced into Pulp2.
#
#   If the fixture is changed, the new SHA256 values can be manually updated
#   using pulp-docker-inspector.py in
#   pulp-qe-tools/pulp2/tools/pulp-docker-inspector .
#
#   The pulp-docker-inspector could be integrated into the test to dynamically
#   determine the unit relations and SHA256s values. At this time, the level of
#   effort with limited reusability and the relative stability of the current
#   implementation is better value.
#
#   The fixture is generated on-demand from
#   pulp-fixtures:docker/hub/build_and_push.sh

# Two manifest lists with non-shared manifests and blobs.
NON_SHARED_MANIFEST_LIST = [
    'sha256:099e168f98f6989fef22b4e32066e8a1ffcdb3a3fe6fcfae1d5fccb285710a12',
    'sha256:378cbadefc7a77858091bdc07e26ce999a27d295b7b2cf9ae80f81bb6a84d8f9',
]

# Two manifests with non-shared blobs.
NON_SHARED_MANIFEST = [
    'sha256:41c79aa6021797316d1c44fabc4e3c0fa5d17b0f1000d1b5a1716cea90f66c53',
    'sha256:21e3caae28758329318c8a868a80daa37ad8851705155fc28767852c73d36af5',
]

# Two manifest lists with shared manifests and blobs.
SHARED_MANIFEST_LIST = [
    'sha256:099e168f98f6989fef22b4e32066e8a1ffcdb3a3fe6fcfae1d5fccb285710a12',
    'sha256:ab5c6191ca8a0adfa63c6cdc7d15765bcd6cad5e123369afa89c60e99b6c79d3',
]

# Two manifests with shared blobs.
SHARED_MANIFEST = [
    'sha256:21e3caae28758329318c8a868a80daa37ad8851705155fc28767852c73d36af5',
    'sha256:4c1b7b72b1353c8e4a3a07bad89e7e47144a50c6236757afb701d397fbe58284',
]

# Blobs to add and remove.
DOCKER_V2_BLOB = [
    'sha256:df5f2171d7a00260c6910231fd760f7b7d2afa576d1f2a674bf84496f1374e76',
    'sha256:d5d04916a1edf7f8a6d9781887bb610eeb8e5049b6bf6dd33f163b829d935797',
    'sha256:686209d53cbd832d0c9a5f77ae8acf87c58f7880581cf132f4022857d23e9182',
    'sha256:d21d863f69b5de1a973a41344488f2ec89a625f2624195f51b4e2d54a97fc53b',
    'sha256:be6e7d2ac7b720bdc7aeacbc214a4587fb751509e04b12d9b20929c306b39401',
    'sha256:f16a387bc629398e82b0cb791b02aa527fdead5789c07fe68df2f8871b55b165',
    'sha256:357aff548189b13f3803b0ecf9c755eea235b89de0baa2838b10f7ff6217db13',
    'sha256:489073334ba6f1e90cdaac80483ac1b009a13454926017f816ee9348dc4b64ef',
    'sha256:62432ba78980ebf9520c6d23f9089ce7632f60b6c98dada13520283417f6588f',
    'sha256:9e13c2bc05f31a8bc257402e5e334fd326e9ae0254e4b3a7da023f9dbe745771',
]

# Manifests using a combination of shared and non-shared blobs.
DOCKER_V2_MANIFEST = [
    'sha256:41c79aa6021797316d1c44fabc4e3c0fa5d17b0f1000d1b5a1716cea90f66c53',
    'sha256:21e3caae28758329318c8a868a80daa37ad8851705155fc28767852c73d36af5',
    'sha256:1ba8b0a51e8b7aa91f0497aa07beafc2a3d8c140abfc7aca01e6f3b589f8b3fc',
    'sha256:6e41099a8470bf055a99d1465feb91860bcfc4ded97942ea72f047e8cda1c678',
    'sha256:ef1ff02d3d46d664de1808b48e56804cd66e9f9195399187fcbc565cfb67234b',
]

# Manifest lists using a combination of shared and unshared lists.
DOCKER_V2_MANIFEST_LIST = [
    'sha256:099e168f98f6989fef22b4e32066e8a1ffcdb3a3fe6fcfae1d5fccb285710a12',
    'sha256:378cbadefc7a77858091bdc07e26ce999a27d295b7b2cf9ae80f81bb6a84d8f9',
    'sha256:ab5c6191ca8a0adfa63c6cdc7d15765bcd6cad5e123369afa89c60e99b6c79d3',
    'sha256:01721afd598847222243ac97d0a8c08ec77028e1666f468bbe0f35d37934f34f',
]


class RemoveV2ContentTestCase(unittest.TestCase):
    """Ensure content removal of Docker repository information.

    With the refactor of the docker importer's remove function to
    increase performance, content removal needs to be functional verified.

    The cases covered with content count verification for all units:

    1. Remove all manifest_lists sequentially.
    2. Remove all manifests sequentially.
    3. Remove all blobs sequentially.
    4. Remove all manifest_lists batch.
    5. Remove all manifests batch.
    6. Remove all blobs batch.
    7. Remove some non-shared manifest lists.
    8. Remove some non-shared manifest.
    9. Remove some shared manifests lists and verify shared units are not
       recursively removed.
    10. Remove some shared manifests and verify shared units are not
        recursively removed.

    The fixture includes:

    * 2 relatively independent manifest lists (no shared manifests,
      no shared blobs between them)
    * 2 manifest lists that share some (but not all) manifests, and those
      manifest share some (but not all) blobs. This only requires the creation
      of 1 manifest list that shares some content with one of the first
      “independent manifest lists”.
    * 2 relatively independent manifests
    * 2 manifests that share (some but not all) blobs

    In order to sync the content, each content unit must be recursively related
    to at least 1 tag.

    ML = Manifest List
    M = Manifest
    B = Blob

    Fixture:

    * ML_I
        * M_A
            * B_1
            * B_2
        * M_B
            * B_3
            * B_4
    * ML_II
        * M_C
            * B_5
            * B_6
        * M_D
            * B_7
            * B_8
    * ML_III
        * M_A
            * B_1
            * B_2
        * M_C
            * B_5
            * B_6
    * M_E
        * B_1
        * B_9

    Tags: 1 for each “top level” (ML_I, ML_II, ML_III, M_E)

    This test case targets:

    * `Pulp #4549 <https://pulp.plan.io/issues/4549>`_.
    * `Pulp #5161 <https://pulp.plan.io/issues/5161>`_.
    * `Pulp #5181 <https://pulp.plan.io/issues/5181>`_.
    """

    @classmethod
    def setUpClass(cls):
        """Set cfg and api for each test."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo(
            importer_config={
                'enable_v1': False,
                'enable_v2': True,
                'feed': DOCKER_V2_FEED_URL,
                'upstream_name': DOCKER_REMOVE_UPSTREAM_NAME,
            }
        )
        cls.repo = cls.client.post(REPOSITORY_PATH, body)
        sync_repo(cls.cfg, cls.repo)

    @classmethod
    def tearDownClass(cls):
        """Clean resources."""
        cls.client.delete(cls.repo['_href'])

    def create_and_copy_test_repo(self, source_repo, copy_units):
        """Return test repo to copy units to test."""
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
        """Copy specified docker units from source to dest."""
        criteria = {
            'type_ids': DOCKER_UNIT_TYPES,
            'filters': {'unit': {'digest': {'$in': units}}},
        }
        self.client.post(
            urljoin(repo['_href'], 'actions/associate/'),
            {'source_repo_id': source_repo['id'], 'criteria': criteria},
        )

    def get_docker_units_count(self, repo, unit_type):
        """Return docker units filtered by type."""
        units = {}
        for unit in unit_type:
            units[unit] = (len(search_units(
                self.cfg,
                repo,
                {'type_ids': [unit], 'filters': {'unit': {}}},
            )))
        return units

    def search_docker_units(self, repo, unit_type):
        """Return docker units filtered by type."""
        return search_units(
            self.cfg, repo, {'type_ids': [unit_type], 'filters': {'unit': {}}}
        )

    def delete_docker_units_sequential(self, repo, units):
        """Sequentially delete docker units."""
        for unit in units:
            criteria = {
                'type_ids': DOCKER_UNIT_TYPES,
                'filters': {'unit': {'_id': unit['unit_id']}},
            }
            self.client.post(
                urljoin(repo['_href'], 'actions/unassociate/'),
                {'source_repo_id': repo['id'], 'criteria': criteria},
            )

    def delete_docker_units(self, repo, units):
        """Batch delete docker units."""
        criteria = {
            'type_ids': DOCKER_UNIT_TYPES,
            'filters': {'unit': {'digest': {'$in': units}}},
        }
        self.client.post(
            urljoin(repo['_href'], 'actions/unassociate/'),
            {'source_repo_id': repo['id'], 'criteria': criteria},
        )

    def count_docker_units(self, repo, state):
        """Count and verify the number of docker_units based on reference."""
        docker_units_count = self.get_docker_units_count(
            repo,
            DOCKER_UNIT_TYPES,
        )
        for key, value in docker_units_count.items():
            with self.subTest(key=key):
                self.assertEqual(
                    value,
                    DOCKER_REMOVE[state][key],
                    docker_units_count,
                )

    def test_01_remove_manifest_list_all_sequential(self):
        """Sync docker repo and remove all manifest_lists sequentially."""
        # Create and Verify initial unit count
        repo = self.create_and_copy_test_repo(
            self.repo,
            DOCKER_V2_MANIFEST_LIST,
        )
        self.addCleanup(self.client.delete, repo['_href'])
        self.count_docker_units(repo, 'ALL_V2')

        # Delete by type, sequentially.
        units = self.search_docker_units(repo, 'docker_manifest_list')
        self.delete_docker_units_sequential(repo, units)

        # Count the remaining units
        self.count_docker_units(repo, 'NONE')

    def test_02_remove_manifest_all_sequential(self):
        """Sync docker repo and remove all manifests sequentially."""
        # Create and Verify initial unit count
        repo = self.create_and_copy_test_repo(
            self.repo,
            DOCKER_V2_MANIFEST_LIST,
        )
        self.addCleanup(self.client.delete, repo['_href'])
        self.count_docker_units(repo, 'ALL_V2')

        # Delete by type, sequentially.
        units = self.search_docker_units(repo, 'docker_manifest')
        self.delete_docker_units_sequential(repo, units)

        # Count the remaining units. Grand-parent units should remain.
        self.count_docker_units(repo, 'ALL_V2_MANIFEST_DELETE')

    def test_03_remove_blob_all_sequential(self):
        """Sync docker repo and remove all blobs sequentially."""
        # Create and Verify initial unit count
        repo = self.create_and_copy_test_repo(
            self.repo,
            DOCKER_V2_MANIFEST_LIST,
        )
        self.addCleanup(self.client.delete, repo['_href'])
        self.count_docker_units(repo, 'ALL_V2')

        # Delete by type, sequentially.
        units = self.search_docker_units(repo, 'docker_blob')
        self.delete_docker_units_sequential(repo, units)

        # Count the remaining units. Grand-parent units should remain.
        self.count_docker_units(repo, 'ALL_V2_BLOB_DELETE')

    def test_04_remove_manifest_list_all_batch(self):
        """Sync docker repo and remove all manifest_lists in batch."""
        # Batch requires 2.21 hot-fix patch in #4549
        if self.cfg.pulp_version < Version('2.21'):
            raise unittest.SkipTest(
                'This test requires Pulp 2.21 or newer.'
            )

        # Create and Verify initial unit count
        repo = self.create_and_copy_test_repo(
            self.repo,
            DOCKER_V2_MANIFEST_LIST,
        )
        self.addCleanup(self.client.delete, repo['_href'])
        self.count_docker_units(repo, 'ALL_V2')

        # Delete by SHA256 in batch
        self.delete_docker_units(repo, DOCKER_V2_MANIFEST_LIST)

        # Count the remaining units
        self.count_docker_units(repo, 'NONE')

    def test_05_remove_manifest_all_batch(self):
        """Sync docker repo and remove all manifests in batch."""
        # Batch requires 2.21 hot-fix patch in #4549
        if self.cfg.pulp_version < Version('2.21'):
            raise unittest.SkipTest(
                'This test requires Pulp 2.21 or newer.'
            )

        # Create and Verify initial unit count
        repo = self.create_and_copy_test_repo(self.repo, DOCKER_V2_MANIFEST)
        self.addCleanup(self.client.delete, repo['_href'])
        self.count_docker_units(repo, 'ALL_V2_MANIFEST_COPY')

        # Delete by SHA256 in batch
        self.delete_docker_units(repo, DOCKER_V2_MANIFEST)

        # Count the remaining units
        self.count_docker_units(repo, 'NONE')

    def test_06_remove_blob_all_batch(self):
        """Sync docker repo and remove all blobs in batch."""
        # Batch requires 2.21 hot-fix patch in #4549
        if self.cfg.pulp_version < Version('2.21'):
            raise unittest.SkipTest(
                'This test requires Pulp 2.21 or newer.'
            )

        # Create and Verify initial unit count
        repo = self.create_and_copy_test_repo(self.repo, DOCKER_V2_BLOB)
        self.addCleanup(self.client.delete, repo['_href'])
        self.count_docker_units(repo, 'ALL_V2_BLOB_COPY')

        # Delete by SHA256 in batch
        self.delete_docker_units(repo, DOCKER_V2_BLOB)

        # Count the remaining units
        self.count_docker_units(repo, 'NONE')

    def test_07_remove_manifest_list_not_shared(self):
        """Sync docker repo and remove some non-shared manifest_lists."""
        # Create and Verify initial unit count
        repo = self.create_and_copy_test_repo(
            self.repo, NON_SHARED_MANIFEST_LIST
        )
        self.addCleanup(self.client.delete, repo['_href'])
        self.count_docker_units(repo, 'NON_SHARED_MANIFEST_LIST')

        # Delete by SHA256 in batch of 1 SHA256
        self.delete_docker_units(repo, [choice(NON_SHARED_MANIFEST_LIST)])

        # Count the remaining unshared units from the second manifest.
        self.count_docker_units(repo, 'NON_SHARED_MANIFEST_LIST_DELETE')

    def test_08_remove_manifest_list_shared(self):
        """Sync docker repo and remove some shared manifest_lists."""
        # Create and Verify initial unit count
        repo = self.create_and_copy_test_repo(self.repo, SHARED_MANIFEST_LIST)
        self.addCleanup(self.client.delete, repo['_href'])
        self.count_docker_units(repo, 'SHARED_MANIFEST_LIST')

        # Delete by SHA256 in batch of 1 SHA256
        self.delete_docker_units(repo, [choice(SHARED_MANIFEST_LIST)])

        # Count the remaining shared units from the second manifest.
        self.count_docker_units(repo, 'SHARED_MANIFEST_LIST_DELETE')

    def test_09_remove_manifest_not_shared(self):
        """Sync docker repo and remove some non-shared manifests."""
        # Create and Verify initial unit count
        repo = self.create_and_copy_test_repo(self.repo, NON_SHARED_MANIFEST)
        self.addCleanup(self.client.delete, repo['_href'])
        self.count_docker_units(repo, 'NON_SHARED_MANIFEST')

        # Delete by SHA256 in batch of 1 SHA256
        self.delete_docker_units(repo, [choice(NON_SHARED_MANIFEST)])

        # Count the remaining shared units from the second manifest.
        self.count_docker_units(repo, 'NON_SHARED_MANIFEST_DELETE')

    def test_10_remove_manifest_shared(self):
        """Sync docker repo and remove some shared manifests."""
        # Create and Verify initial unit count
        repo = self.create_and_copy_test_repo(self.repo, SHARED_MANIFEST)
        self.addCleanup(self.client.delete, repo['_href'])
        self.count_docker_units(repo, 'SHARED_MANIFEST')

        # Delete by SHA256 in batch of 1 SHA256
        self.delete_docker_units(repo, [choice(SHARED_MANIFEST)])

        # Count the remaining shared units from the second manifest.
        self.count_docker_units(repo, 'SHARED_MANIFEST_DELETE')
