# coding=utf-8
"""Tests for how well Pulp can deal with duplicate uploads."""
import hashlib
import os
import unittest
from urllib.parse import urljoin, urlsplit

from packaging.version import Version

from pulp_smash import api, config, selectors, utils
from pulp_smash.pulp2.constants import REPOSITORY_PATH
from pulp_smash.pulp2.utils import search_units, upload_import_unit

from pulp_2_tests.constants import FILE_URL, FILE2_URL, RPM_UNSIGNED_URL
from pulp_2_tests.tests.rpm.api_v2.utils import gen_repo
from pulp_2_tests.tests.rpm.utils import set_up_module as setUpModule  # pylint:disable=unused-import


class DuplicateUploadsTestCase(unittest.TestCase):
    """Test how well Pulp can deal with duplicate unit uploads."""

    @classmethod
    def setUpClass(cls):
        """Set a class-wide variable."""
        cls.cfg = config.get_config()

    def test_rpm(self):
        """Upload duplicate RPM content.See :meth:`do_test`.

        This test targets the following issues:

        * `Pulp Smash #81 <https://github.com/PulpQE/pulp-smash/issues/81>`_
        * `Pulp #1406 <https://pulp.plan.io/issues/1406>`_
        """
        if not selectors.bug_is_fixed(1406, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/1406')
        self.do_test(RPM_UNSIGNED_URL, 'rpm', gen_repo())

    def test_iso(self):
        """Upload duplicate ISO content. See :meth:`do_test`.

        This test targets the following issues:

        * `Pulp Smash #582 <https://github.com/PulpQE/pulp-smash/issues/582>`_
        * `Pulp #2274 <https://pulp.plan.io/issues/2274>`_
        """
        if not selectors.bug_is_fixed(2274, self.cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/2274')
        body = {
            'id': utils.uuid4(),
            'importer_type_id': 'iso_importer',
            'distributors': [{
                'auto_publish': False,
                'distributor_id': utils.uuid4(),
                'distributor_type_id': 'iso_distributor',
            }],
        }
        iso = utils.http_get(FILE_URL)
        unit_key = {
            'checksum': hashlib.sha256(iso).hexdigest(),
            'name': os.path.basename(urlsplit(FILE_URL).path),
            'size': len(iso),
        }
        self.do_test(FILE_URL, 'iso', body, unit_key)

    def do_test(self, feed, type_id, body, unit_key=None):
        """Test how well Pulp can deal with duplicate unit uploads.

        Do the following:

        1. Create a new feed-less repository.
        2. Upload content and import it into the repository. Assert the upload
           and import was successful.
        3. Upload identical content and import it into the repository.

        The second upload should silently fail for all Pulp releases in the 2.x
        series.
        """
        if unit_key is None:
            unit_key = {}
        client = api.Client(self.cfg, api.json_handler)
        unit = utils.http_get(feed)
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        for _ in range(2):
            call_report = upload_import_unit(self.cfg, unit, {
                'unit_type_id': type_id,
                'unit_key': unit_key
            }, repo)
            self.assertIsNone(call_report['result'])


class DuplicateUploadAndCopyTestCase(unittest.TestCase):
    """Test same-name content uploads do not duplicate in `PULP_MANIFEST`."""

    def test_upload_copy_manifest(self):
        """Test same-name content uploads do not duplicate in `PULP_MANIFEST`.

        Steps:

        1. Create two new feed-less iso-repo repositories.
        2. Upload content and import it into the source repository. Assert
           the upload and import was successful.
        3. Copy the content to a target repo. Assert the copy was successful.
        4. Upload identically named but different content and import it into
           the source repository. Assert the upload and import was successful.
        5. Copy the content to the target repo.
        6. Assert the target manifest only has one entry for the content.
        """
        cfg = config.get_config()
        if cfg.pulp_version < Version('2.20'):
            raise unittest.SkipTest('This test requires Pulp 2.20 or newer.')
        client = api.Client(cfg, api.json_handler)

        # 1. Create two iso-repo
        repos = []
        iso = utils.http_get(FILE_URL)
        unit_key = {
            'checksum': hashlib.sha256(iso).hexdigest(),
            'name': os.path.basename(urlsplit(FILE_URL).path),
            'size': len(iso),
        }
        data = {
            'importer_type_id': 'iso_importer',
            'notes': {'_repo-type': 'iso-repo'},
        }
        repos.append(client.post(REPOSITORY_PATH, gen_repo(**data)))
        self.addCleanup(client.delete, repos[0]['_href'])
        repos.append(client.post(REPOSITORY_PATH, gen_repo(**data)))
        self.addCleanup(client.delete, repos[1]['_href'])

        # 2. Import the units into the source repo and verify
        call_report = upload_import_unit(cfg, iso, {
            'unit_type_id': 'iso',
            'unit_key': unit_key
        }, repos[0])
        self.assertIsNone(call_report['result'], call_report)

        # Only one iso unit should exist in the source repo
        units = search_units(cfg, repos[0], {'type_ids': ['iso']})
        self.assertEqual(len(units), 1, units)

        # 3. Sync to a target repository.
        client.post(urljoin(repos[1]['_href'], 'actions/associate/'), {
            'source_repo_id': repos[0]['id'],
            'override_config': {},
            'criteria': {'filters': {'unit': {}}, 'type_ids': ['iso']},
        })

        # Assert that the single ISO was copied.
        units = search_units(cfg, repos[1], {'type_ids': ['iso']})
        self.assertEqual(len(units), 1, units)

        # 4. Upload a same-name, but different ISO to the source repo
        iso2 = utils.http_get(FILE2_URL)
        unit_key = {
            'checksum': hashlib.sha256(iso2).hexdigest(),
            'name': os.path.basename(urlsplit(FILE_URL).path),
            'size': len(iso2),
        }
        call_report = upload_import_unit(cfg, iso2, {
            'unit_type_id': 'iso',
            'unit_key': unit_key
        }, repos[0])
        self.assertIsNone(call_report['result'])

        # 5. Copy the new iso from the source to target repo
        client.post(urljoin(repos[1]['_href'], 'actions/associate/'), {
            'source_repo_id': repos[0]['id'],
            'override_config': {},
            'criteria': {'filters': {'unit': {}}, 'type_ids': ['iso']},
        })
        # Assert the ISO packages was copied and only 1 unit exists.
        units = search_units(cfg, repos[1], {'type_ids': ['iso']})
        self.assertEqual(len(units), 1, units)
