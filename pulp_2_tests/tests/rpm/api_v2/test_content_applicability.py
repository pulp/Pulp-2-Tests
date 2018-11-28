# coding=utf-8
"""Tests for Pulp's `content applicability`_ feature.

.. _content applicability:
    http://docs.pulpproject.org/dev-guide/integration/rest-api/consumer/applicability.html
"""
import unittest
from types import MappingProxyType
from urllib.parse import urljoin

from jsonschema import validate
from pulp_smash import api, config
from pulp_smash.pulp2.constants import (
    CONSUMERS_ACTIONS_CONTENT_REGENERATE_APPLICABILITY_PATH,
    CONSUMERS_CONTENT_APPLICABILITY_PATH,
    CONSUMERS_PATH,
    REPOSITORY_PATH,
)
from pulp_smash.pulp2.utils import (
    publish_repo,
    sync_repo,
    upload_import_erratum,
    utils
)

from packaging.version import Version
from pulp_2_tests.constants import (
    MODULE_DATA_2,
    MODULE_ERRATA_RPM_DATA,
    MODULE_ARTIFACT_RPM_DATA,
    MODULE_ARTIFACT_RPM_DATA_2,
    RPM_UNSIGNED_FEED_URL,
    RPM_DATA,
    RPM2_DATA,
    RPM_WITH_MODULES_FEED_URL,
)
from pulp_2_tests.tests.rpm.api_v2.utils import (
    gen_consumer,
    gen_distributor,
    gen_repo,
)
from pulp_2_tests.tests.rpm.utils import set_up_module as setUpModule  # pylint:disable=unused-import

# MappingProxyType is used to make an immutable dict.
RPM_WITH_ERRATUM_METADATA = MappingProxyType({
    'name': RPM_DATA['name'],
    'epoch': RPM_DATA['epoch'],
    'version': RPM_DATA['version'],
    'release': int(RPM_DATA['release']),
    'arch': RPM_DATA['arch'],
    'vendor': RPM_DATA['metadata']['vendor'],
})
"""Metadata for an RPM with an associated erratum."""

RPM_WITHOUT_ERRATUM_METADATA = MappingProxyType({
    'name': RPM2_DATA['name'],
    'epoch': RPM2_DATA['epoch'],
    'version': RPM2_DATA['version'],
    'release': int(RPM2_DATA['release']),
    'arch': RPM2_DATA['arch'],
    'vendor': RPM2_DATA['metadata']['vendor'],
})
"""Metadata for an RPM without an associated erratum."""

MODULES_METADATA = MappingProxyType({
    'name': MODULE_ERRATA_RPM_DATA['rpm_name'],
    'stream': MODULE_ERRATA_RPM_DATA['stream_name'],
    'version': MODULE_ERRATA_RPM_DATA['version'],
    'context': MODULE_ERRATA_RPM_DATA['context'],
    'arch': MODULE_ERRATA_RPM_DATA['arch'],
})
"""Metadata for a Module."""

MODULES_METADATA_2 = MappingProxyType({
    'name': MODULE_DATA_2['name'],
    'stream': MODULE_DATA_2['stream'],
    'version': MODULE_DATA_2['version'],
    'context': MODULE_DATA_2['context'],
    'arch': MODULE_DATA_2['arch'],
})
"""Metadata for another Module."""

CONTENT_APPLICABILITY_REPORT_SCHEMA = {
    '$schema': 'http://json-schema.org/schema#',
    'title': 'Content Applicability Report',
    'description': (
        'Derived from: http://docs.pulpproject.org/'
        'dev-guide/integration/rest-api/consumer/applicability.html'
        '#query-content-applicability'
    ),
    'type': 'array',
    'items': {
        'type': 'object',
        'properties': {
            'applicability': {
                'type': 'object',
                'properties': {
                    'erratum': {
                        'type': 'array',
                        'items': {'type': 'string'}
                    },
                    'modulemd': {
                        'type': 'array',
                        'items': {'type': 'string'}
                    },
                    'rpm': {
                        'type': 'array',
                        'items': {'type': 'string'}
                    }
                }
            },
            'consumers': {
                'type': 'array',
                'items': {'type': 'string'}
            }
        }
    }
}
"""A schema for a content applicability report for a consumer.

Schema now includes modulemd profiles:

* `Pulp #3925 <https://pulp.plan.io/issues/3925>`_
"""


class BasicTestCase(unittest.TestCase):
    """Perform simple applicability generation tasks."""

    @classmethod
    def setUpClass(cls):
        """Create and sync a repository.

        The regular test methods that run after this can create consumers that
        bind to this repository.
        """
        cls.cfg = config.get_config()
        client = api.Client(cls.cfg, api.json_handler)
        body = gen_repo()
        body['importer_config']['feed'] = RPM_UNSIGNED_FEED_URL
        body['distributors'] = [gen_distributor()]
        cls.repo = client.post(REPOSITORY_PATH, body)
        try:
            cls.repo = client.get(cls.repo['_href'], params={'details': True})
            sync_repo(cls.cfg, cls.repo)
            publish_repo(cls.cfg, cls.repo)
            cls.repo = client.get(cls.repo['_href'], params={'details': True})
        except:  # noqa:E722
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        """Delete the repository created by :meth:`setUpClass`."""
        api.Client(cls.cfg).delete(cls.repo['_href'])

    def test_positive(self):
        """Verify content is made available when appropriate.

        Specifically, do the following:

        1. Create a consumer.
        2. Bind the consumer to the repository created in :meth:`setUpClass`.
        3. Create a consumer profile where:

           * two packages are installed,
           * both packages' versions are lower than what's offered by the
             repository,
           * one of the corresponding packages in the repository has an
             applicable erratum, and
           * the other corresponding package in the repository doesn't have an
             applicable erratum.

        4. Regenerate applicability for the consumer.
        5. Fetch applicability for the consumer. Verify that both packages are
           listed as eligible for an upgrade.
        """
        # Create a consumer.
        client = api.Client(self.cfg, api.json_handler)
        consumer = client.post(CONSUMERS_PATH, gen_consumer())
        self.addCleanup(client.delete, consumer['consumer']['_href'])

        # Bind the consumer.
        client.post(urljoin(consumer['consumer']['_href'], 'bindings/'), {
            'distributor_id': self.repo['distributors'][0]['id'],
            'notify_agent': False,
            'repo_id': self.repo['id'],
        })

        # Create a consumer profile.
        rpm_with_erratum_metadata = RPM_WITH_ERRATUM_METADATA.copy()
        rpm_with_erratum_metadata['version'] = '4.0'
        rpm_without_erratum_metadata = RPM_WITHOUT_ERRATUM_METADATA.copy()
        rpm_without_erratum_metadata['version'] = '0.0.1'
        client.post(urljoin(consumer['consumer']['_href'], 'profiles/'), {
            'content_type': 'rpm',
            'profile': [
                rpm_with_erratum_metadata,
                rpm_without_erratum_metadata,
            ]
        })

        # Regenerate applicability.
        client.post(CONSUMERS_ACTIONS_CONTENT_REGENERATE_APPLICABILITY_PATH, {
            'consumer_criteria': {
                'filters': {'id': {'$in': [consumer['consumer']['id']]}}
            }
        })

        # Fetch applicability.
        applicability = client.post(CONSUMERS_CONTENT_APPLICABILITY_PATH, {
            'criteria': {
                'filters': {'id': {'$in': [consumer['consumer']['id']]}}
            },
        })
        validate(applicability, CONTENT_APPLICABILITY_REPORT_SCHEMA)
        with self.subTest(comment='verify erratum listed in report'):
            self.assertEqual(
                len(applicability[0]['applicability']['erratum']),
                1,
                applicability[0]['applicability']['erratum'],
            )
        with self.subTest(comment='verify modulemd listed in report'):
            self.assertEqual(
                len(applicability[0]['applicability']['modulemd']),
                0,
                applicability[0]['applicability']['modulemd'],
            )
        with self.subTest(comment='verify RPMs listed in report'):
            self.assertEqual(
                len(applicability[0]['applicability']['rpm']),
                2,
                applicability[0]['applicability']['rpm'],
            )
        with self.subTest(comment='verify consumers listed in report'):
            self.assertEqual(
                applicability[0]['consumers'],
                [consumer['consumer']['id']],
            )

    def test_negative(self):
        """Verify content isn't made available when appropriate.

        Do the same as :meth:`test_positive`, except that both packages'
        versions are equal to what's offered by the repository.
        """
        # Create a consumer.
        client = api.Client(self.cfg, api.json_handler)
        consumer = client.post(CONSUMERS_PATH, gen_consumer())
        self.addCleanup(client.delete, consumer['consumer']['_href'])

        # Bind the consumer.
        client.post(urljoin(consumer['consumer']['_href'], 'bindings/'), {
            'distributor_id': self.repo['distributors'][0]['id'],
            'notify_agent': False,
            'repo_id': self.repo['id'],
        })

        # Create a consumer profile.
        client.post(urljoin(consumer['consumer']['_href'], 'profiles/'), {
            'content_type': 'rpm',
            'profile': [
                # The JSON serializer can't handle MappingProxyType objects.
                dict(RPM_WITH_ERRATUM_METADATA),
                dict(RPM_WITHOUT_ERRATUM_METADATA),
            ]
        })

        # Regenerate applicability.
        client.post(CONSUMERS_ACTIONS_CONTENT_REGENERATE_APPLICABILITY_PATH, {
            'consumer_criteria': {
                'filters': {'id': {'$in': [consumer['consumer']['id']]}}
            }
        })

        # Fetch applicability.
        applicability = client.post(CONSUMERS_CONTENT_APPLICABILITY_PATH, {
            'content_types': ['rpm'],
            'criteria': {
                'filters': {'id': {'$in': [consumer['consumer']['id']]}}
            },
        })
        validate(applicability, CONTENT_APPLICABILITY_REPORT_SCHEMA)
        with self.subTest(comment='verify RPMs listed in report'):
            self.assertEqual(len(applicability[0]['applicability']['rpm']), 0)
        with self.subTest(comment='verify consumers listed in report'):
            self.assertEqual(
                applicability[0]['consumers'],
                [consumer['consumer']['id']],
            )


class ModularApplicabilityTestCase(unittest.TestCase):
    """Perform modular repo applicability generation tasks.

    Specifically, do the following:

    1. Create a consumer.
    2. Bind the consumer to the modular repository
       ``RPM_WITH_MODULES_FEED_URL``.
    3. Create a consumer profile with:
       * List of RPMs
       * List of Modules.
    4. Regenerate applicability for the consumer.
    5. Fetch applicability for the consumer. Verify that the packages
       are eligible for upgrade.

    This test targets the following:

    * `Pulp #4158 <https://pulp.plan.io/issues/4158>`_
    * `Pulp #4179 <https://pulp.plan.io/issues/4179>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create and sync a repository.

        The regular test methods that run after this can create consumers that
        bind to this repository.
        """
        cls.cfg = config.get_config()
        if cls.cfg.pulp_version < Version('2.18'):
            raise unittest.SkipTest('This test requires Pulp 2.18 or newer.')
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_modular_rpm(self):
        """Verify content is made available if appropriate.

        This Tests the following:

        1. Create a consumer profile with an RPM version less than the
           module.
        2. Bind the consumer to the modular repo.
        3. Verify the content is applicable.
        """
        # Reduce the versions to check whether newer version applies.
        rpm_with_modules_metadata = MODULE_ARTIFACT_RPM_DATA.copy()
        rpm_with_modules_metadata['version'] = '5'
        modules_metadata = MODULES_METADATA.copy()
        applicability = self.do_test(
            [modules_metadata],
            [rpm_with_modules_metadata]
        )
        validate(applicability, CONTENT_APPLICABILITY_REPORT_SCHEMA)
        with self.subTest(comment='verify Modules listed in report'):
            self.assertEqual(
                len(applicability[0]['applicability']['modulemd']),
                1,
                applicability[0]['applicability']['modulemd'],
            )

    def test_mixed_rpm(self):
        """Verify content is made available for both modular/non modular RPMs.

        This Tests the following:

        1. Create a consumer profile containing both modular and non modular
           RPMs.
        2. Bind the consumer to the modular repo.
        3. Verify the content is applicable.
        """
        # Reduce the versions to check whether newer version applies.
        rpm_with_modules_metadata = MODULE_ARTIFACT_RPM_DATA.copy()
        rpm_with_modules_metadata['version'] = '5'
        modules_metadata = MODULES_METADATA.copy()
        rpm_with_erratum_metadata = RPM_WITH_ERRATUM_METADATA.copy()
        rpm_with_erratum_metadata['version'] = '4.0'
        applicability = self.do_test(
            [modules_metadata],
            [rpm_with_modules_metadata, rpm_with_modules_metadata]
        )
        validate(applicability, CONTENT_APPLICABILITY_REPORT_SCHEMA)
        with self.subTest(comment='verify Modules listed in report'):
            self.assertEqual(
                len(applicability[0]['applicability']['modulemd']),
                1,
                applicability[0]['applicability']['modulemd'],
            )
        with self.subTest(comment='verify Modules listed in report'):
            self.assertEqual(
                len(applicability[0]['applicability']['rpm']),
                1,
                applicability[0]['applicability']['rpm'],
            )

    def test_dependent_modules(self):
        """Verify dependent modules are made available.

        1. Bind the consumer with the modular repo.
        2. Update the consumer profile with dependent modules.
        3. Verify that the content is made available for the consumer.
        """
        # Reduce the versions to check whether newer version applies.
        rpm_with_modules_metadata = MODULE_ARTIFACT_RPM_DATA.copy()
        rpm_with_modules_metadata['version'] = '5'

        rpm_with_modules_metadata_2 = MODULE_ARTIFACT_RPM_DATA_2.copy()
        rpm_with_modules_metadata['version'] = '0.5'

        modules_metadata = MODULES_METADATA.copy()
        modules_metadata_2 = MODULES_METADATA_2.copy()
        applicability = self.do_test(
            [modules_metadata, modules_metadata_2],
            [rpm_with_modules_metadata, rpm_with_modules_metadata_2]
        )
        validate(applicability, CONTENT_APPLICABILITY_REPORT_SCHEMA)
        with self.subTest(comment='verify Modules listed in report'):
            self.assertEqual(
                len(applicability[0]['applicability']['modulemd']),
                2,
                applicability[0]['applicability']['modulemd'],
            )

    def test_erratum_modules(self):
        """Verify erratum modules are applicable.

        1. Bind the consumer with erratum modular repo.
        2. Verify the content is applicable.
        """
        # Reduce the versions to check whether newer version applies.
        rpm_with_modules_metadata = MODULE_ARTIFACT_RPM_DATA.copy()
        rpm_with_modules_metadata['version'] = '5'
        modules_metadata = MODULES_METADATA.copy()
        erratum = ModularApplicabilityTestCase.gen_modular_errata()
        applicability = self.do_test(
            [modules_metadata],
            [rpm_with_modules_metadata],
            erratum
        )
        validate(applicability, CONTENT_APPLICABILITY_REPORT_SCHEMA)
        with self.subTest(comment='verify Modules listed in report'):
            self.assertEqual(
                len(applicability[0]['applicability']['erratum']),
                1,
                applicability[0]['applicability']['erratum'],
            )

    def test_negative(self):
        """Verify content is not made available when inappropriate.

        Do the same as :meth:`test_modular_rpm`, except that the version should
        be higher than what is offered by the module.
        """
        rpm_with_modules_metadata = MODULE_ARTIFACT_RPM_DATA.copy()
        rpm_with_modules_metadata['version'] = '7'
        modules_metadata = MODULES_METADATA.copy()
        applicability = self.do_test(
            [modules_metadata],
            [rpm_with_modules_metadata],
        )
        validate(applicability, CONTENT_APPLICABILITY_REPORT_SCHEMA)
        with self.subTest(comment='verify Modules listed in report'):
            self.assertEqual(
                len(applicability[0]['applicability']['modulemd']),
                0,
                applicability[0]['applicability']['modulemd'],
            )

    def do_test(self, modules_profile, rpm_profile, erratum=None):
        """Regenerate and fetch applicability for the given modules and Rpms.

        This method does the following:
        1. Create a Modular Repo in pulp
        2. Create a consumer and bind them to the modular repo.
        3. Create consumer profiles for the passed modules and rpms.
        4. Regenerate and return the fetched applicablity.

        :param modules_profile: A list of modules for the consumer profile.
        :param rpm_profile: A list of rpms for the consumer profile.
        :param erratum: An Erratum to be added to the repo.

        :returns: A dict containing the consumer ``applicability``.
        """
        body = gen_repo(
            importer_config={'feed': RPM_WITH_MODULES_FEED_URL},
            distributors=[gen_distributor(auto_publish=True)]
        )
        repo = self.client.post(REPOSITORY_PATH, body)
        sync_repo(self.cfg, repo)
        repo = self.client.get(repo['_href'], params={'details': True})
        if erratum is not None:
            upload_import_erratum(self.cfg, erratum, repo)
        self.addCleanup(self.client.delete, repo['_href'])

        # Create a consumer.
        consumer = self.client.post(CONSUMERS_PATH, gen_consumer())
        self.addCleanup(self.client.delete, consumer['consumer']['_href'])

        # Bind the consumer.
        self.client.post(urljoin(consumer['consumer']['_href'], 'bindings/'), {
            'distributor_id': repo['distributors'][0]['id'],
            'notify_agent': False,
            'repo_id': repo['id'],
        })

        # Create a consumer profile with RPM
        if rpm_profile:
            self.client.post(urljoin(consumer['consumer']['_href'], 'profiles/'), {
                'content_type': 'rpm',
                'profile': rpm_profile
            })

        # Create a consumer profile with modules.
        if modules_profile:
            self.client.post(urljoin(consumer['consumer']['_href'], 'profiles/'), {
                'content_type': 'modulemd',
                'profile': modules_profile
            })

        # Regenerate applicability.
        self.client.post(CONSUMERS_ACTIONS_CONTENT_REGENERATE_APPLICABILITY_PATH, {
            'consumer_criteria': {
                'filters': {'id': {'$in': [consumer['consumer']['id']]}}
            }
        })

        # Fetch and Return applicability.
        return self.client.post(CONSUMERS_CONTENT_APPLICABILITY_PATH, {
            'criteria': {
                'filters': {'id': {'$in': [consumer['consumer']['id']]}}
            },
        })

    @staticmethod
    def gen_modular_errata():
        """Generate and return a modular erratum with RPM."""
        return {
            'id': utils.uuid4(),
            'status': 'stable',
            'updated': MODULE_ERRATA_RPM_DATA['updated'],
            'rights': None,
            'from': MODULE_ERRATA_RPM_DATA['from'],
            'description': MODULE_ERRATA_RPM_DATA['description'],
            'title': MODULE_ERRATA_RPM_DATA['rpm_name'],
            'issued': MODULE_ERRATA_RPM_DATA['issued'],
            'relogin_suggested': False,
            'restart_suggested': False,
            'solution': None,
            'summary': None,
            'pushcount': '1',
            'version': '1',
            'references': [],
            'release': '1',
            'reboot_suggested': None,
            'type': 'enhancement',
            'severity': None,
            'pkglist': [{
                'name': MODULE_ERRATA_RPM_DATA['collection_name'],
                'short': '0',
                'module': {
                    'name': MODULE_ERRATA_RPM_DATA['rpm_name'],
                    'stream': MODULE_ERRATA_RPM_DATA['stream_name'],
                    'version': MODULE_ERRATA_RPM_DATA['version'],
                    'arch': MODULE_ERRATA_RPM_DATA['arch'],
                    'context': MODULE_ERRATA_RPM_DATA['context']
                },
                'packages': [
                    {
                        'arch': MODULE_ARTIFACT_RPM_DATA['arch'],
                        'name': MODULE_ARTIFACT_RPM_DATA['name'],
                        'release': MODULE_ARTIFACT_RPM_DATA['release'],
                        'version': MODULE_ARTIFACT_RPM_DATA['version'],
                        'src': MODULE_ARTIFACT_RPM_DATA['src']
                    }
                ]
            }]
        }
