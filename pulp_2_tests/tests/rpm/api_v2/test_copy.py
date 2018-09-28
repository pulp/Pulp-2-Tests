# coding=utf-8
"""Test cases that copy content units."""
import os
import time
import unittest
from urllib.parse import urljoin

from pulp_smash import api, cli, config, selectors, utils
from pulp_smash.pulp2.constants import REPOSITORY_PATH, ORPHANS_PATH
from pulp_smash.pulp2.utils import (
    publish_repo,
    search_units,
    sync_repo,
    upload_import_unit,
)

from pulp_2_tests.constants import (
    RPM_NAMESPACES,
    RPM_SIGNED_URL,
    RPM_UNSIGNED_FEED_URL,
    RPM_UPDATED_INFO_FEED_URL,
    RPM_YUM_METADATA_FILE,
)
from pulp_2_tests.tests.rpm.api_v2.utils import (
    gen_distributor,
    gen_repo,
    get_repodata_repomd_xml,
)
from pulp_2_tests.tests.rpm.utils import set_up_module as setUpModule  # pylint:disable=unused-import

_PATH = '/var/lib/pulp/published/yum/https/repos/'


class CopyErrataRecursiveTestCase(unittest.TestCase):
    """Test that recursive copy of erratas copies RPM packages."""

    def test_all(self):
        """Test that recursive copy of erratas copies RPM packages.

        This test targets the following issues:

        * `Pulp Smash #769 <https://github.com/PulpQE/pulp-smash/issues/769>`_
        * `Pulp #3004 <https://pulp.plan.io/issues/3004>`_

        Do the following:

        1. Create and sync a repository with errata, and RPM packages.
        2. Create second repository.
        3. Copy units from from first repository to second repository
           using ``recursive`` as true, and filter  ``type_id`` as
           ``erratum``.
        4. Assert that RPM packages were copied.
        """
        cfg = config.get_config()
        if not selectors.bug_is_fixed(3004, cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/3004')

        repos = []
        client = api.Client(cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_UPDATED_INFO_FEED_URL
        body['distributors'] = [gen_distributor()]
        repos.append(client.post(REPOSITORY_PATH, body))
        self.addCleanup(client.delete, repos[0]['_href'])
        sync_repo(cfg, repos[0])

        # Create a second repository.
        repos.append(client.post(REPOSITORY_PATH, gen_repo()))
        self.addCleanup(client.delete, repos[1]['_href'])

        # Copy data to second repository.
        client.post(urljoin(repos[1]['_href'], 'actions/associate/'), {
            'source_repo_id': repos[0]['id'],
            'override_config': {'recursive': True},
            'criteria': {'filters': {}, 'type_ids': ['erratum']},
        })

        # Assert that RPM packages were copied.
        units = search_units(cfg, repos[1], {'type_ids': ['rpm']})
        self.assertGreater(len(units), 0)


class MtimeTestCase(unittest.TestCase):
    """Test whether copied files retain their original mtime."""

    def test_all(self):
        """Test whether copied files retain their original mtime.

        This test targets the following issues:

        * `Pulp #2783 <https://pulp.plan.io/issues/2783>`_
        * `Pulp Smash #720 <https://github.com/PulpQE/pulp-smash/issues/720>`_

        Do the following:

        1. Create, sync and publish a repository, with ``generate_sqlite`` set
           to true.
        2. Get the ``mtime`` of the sqlite files.
        3. Upload an RPM package into the repository, and sync the repository.
        4. Get the ``mtime`` of the sqlite files again. Verify that the mtimes
           are the same.
        """
        cfg = config.get_config()
        if not selectors.bug_is_fixed(2783, cfg.pulp_version):
            self.skipTest('https://pulp.plan.io/issues/2783')

        # Create, sync and publish a repository.
        client = api.Client(cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_UNSIGNED_FEED_URL
        body['distributors'] = [gen_distributor()]
        body['distributors'][0]['distributor_config']['generate_sqlite'] = True
        repo = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo['_href'])
        repo = client.get(repo['_href'], params={'details': True})
        sync_repo(cfg, repo)
        publish_repo(cfg, repo)

        # Get the mtime of the sqlite files.
        cli_client = cli.Client(cfg, cli.echo_handler)
        cmd = '' if cli.is_root(cfg) else 'sudo '
        cmd += "bash -c \"stat --format %Y '{}'/*\"".format(os.path.join(
            _PATH,
            repo['distributors'][0]['config']['relative_url'],
            'repodata',
        ))
        # machine.session is used here to keep SSH session open
        mtimes_pre = (
            cli_client.machine.session().run(cmd)[1].strip().split().sort()
        )

        # Upload to the repo, and sync it.
        rpm = utils.http_get(RPM_SIGNED_URL)
        upload_import_unit(cfg, rpm, {'unit_type_id': 'rpm'}, repo)
        sync_repo(cfg, repo)

        # Get the mtime of the sqlite files again.
        time.sleep(1)
        # machine.session is used here to keep SSH session open
        mtimes_post = (
            cli_client.machine.session().run(cmd)[1].strip().split().sort()
        )
        self.assertEqual(mtimes_pre, mtimes_post)


class CopyYumMetadataFileTestCase(unittest.TestCase):
    """Test the copy of metadata units between repos."""

    def test_all(self):
        """Test whether metadata copied between repos are independent.

        This test targets the following issues:

        * `Pulp #1944 <https://pulp.plan.io/issues/1944>`_
        * `Pulp-2-Tests #91
          <https://github.com/PulpQE/Pulp-2-Tests/issues/91>`_

        Do the following:

        1. Create and sync a repository containing
           ``yum_repo_metadata_file``.
        2. Create another repo and copy yum metadata from
           first repo to second repo.
        3. Publish repo 2.
        4. Remove the metadata units from the first repo. Delete
           orphan packages.
        5. Publish repo 2 again and check whether the metadata is
           present in the second repo still.
        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        body = gen_repo(
            importer_config={'feed': RPM_YUM_METADATA_FILE},
            distributors=[gen_distributor()]
        )
        repo_1 = client.post(REPOSITORY_PATH, body)
        self.addCleanup(client.delete, repo_1['_href'])
        sync_repo(cfg, repo_1)
        repo_1 = client.get(repo_1['_href'], params={'details': True})

        # Create a second repository.
        body = gen_repo(
            distributors=[gen_distributor()]
        )
        repo_2 = client.post(REPOSITORY_PATH, body)
        repo_2 = client.get(repo_2['_href'], params={'details': True})
        self.addCleanup(client.delete, repo_2['_href'])

        # Copy data to second repository.
        client.post(urljoin(repo_2['_href'], 'actions/associate/'), {
            'source_repo_id': repo_1['id'],
            'override_config': {'recursive': True},
            'criteria': {
                'filters': {},
                'type_ids': ['yum_repo_metadata_file'],
            }
        })

        # Publish repo 2
        publish_repo(cfg, repo_2)
        # Removing metadata from repo 1 and deleting orphans.
        client.post(
            urljoin(repo_1['_href'], 'actions/unassociate/'),
            {'criteria': {'filters': {}}}
        )
        repo_1 = client.get(repo_1['_href'], params={'details': True})
        client.delete(ORPHANS_PATH)
        # Publish repo 2 again
        publish_repo(cfg, repo_2)
        repo_2 = client.get(repo_2['_href'], params={'details': True})

        # retrieve repodata of the published repo
        xml_element = get_repodata_repomd_xml(cfg, repo_2['distributors'][0])
        xpath = (
            '{{{namespace}}}data'.format(
                namespace=RPM_NAMESPACES['metadata/repo']
            )
        )
        yum_meta_data_element = [
            element
            for element in xml_element.findall(xpath)
            if element.attrib['type'] == 'productid'
        ]
        self.assertNotIn(
            'yum_repo_metadata_file',
            repo_1['content_unit_counts']
        )
        self.assertEqual(
            repo_2['content_unit_counts']['yum_repo_metadata_file'],
            1
        )
        self.assertGreater(len(yum_meta_data_element), 0)
