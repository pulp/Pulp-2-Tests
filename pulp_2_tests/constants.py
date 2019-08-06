# coding=utf-8
"""Values usable by multiple test modules."""
from types import MappingProxyType  # used to form an immutable dictionary
from urllib.parse import quote_plus, urljoin

from pulp_smash.constants import PULP_FIXTURES_BASE_URL


DOCKER_IMAGE_URL = urljoin(PULP_FIXTURES_BASE_URL, 'docker/busybox:latest.tar')
"""The URL to a Docker image as created by ``docker save``."""

DOCKER_UPSTREAM_NAME_NOLIST = 'library/busybox'
"""The name of a Docker repository without a manifest list.

:data:`DOCKER_UPSTREAM_NAME` should be used when possible. However, this
constant is useful for backward compatibility. If Pulp is asked to sync a
repository, and:

* Pulp older than 2.14 is under test.
* The repository is configured to sync schema v2 content.
* The upstream repository has a manifest list.

…then Pulp will break when syncing. See `Pulp #2384
<https://pulp.plan.io/issues/2384>`_.
"""

DOCKER_UPSTREAM_NAME = 'dmage/manifest-list-test'
"""The name of a Docker repository.

This repository has several desirable properties:

* It is available via both :data:`DOCKER_V1_FEED_URL` and
  :data:`DOCKER_V2_FEED_URL`.
* It has a manifest list, where one entry has an architecture of amd64 and an
  os of linux. (The "latest" tag offers this.)
* It is relatively small.

This repository also has several shortcomings:

* This repository isn't an official repository. It's less trustworthy, and may
  be more likely to change with little or no notice.
* It doesn't have a manifest list where no list entries have an architecture of
  amd64 and an os of linux. (The "arm32v7" tag provides schema v1 content.)

One can get a high-level view of the content in this repository by executing:

.. code-block:: sh

    curl --location --silent \
    https://registry.hub.docker.com/v2/repositories/$this_constant/tags \
    | python -m json.tool
"""
DOCKER_REMOVE_UPSTREAM_NAME = 'pulp/test-fixture-1'
"""The name of a Docker repository.

This repository has several desirable properties:

* It is available via both :data:`DOCKER_V1_FEED_URL` and
  :data:`DOCKER_V2_FEED_URL`.
* It has a manifest list, manifest, and blobs in permutation to facilitate the
  testing of recursive removal.
* It is owned by Pulp and therefore can be updated and maintained.
* At long as the contents of the repo are not changed, the provided `SHA256`
  references will work for `docker/api_v2/test_remove.py`
* It is relatively small.

This repository also has several shortcomings:

* This repository isn't an official repository. It is a created repository to
  work with the abstraction tests Pulp2 needs to test recursive removal.
* The relation to all units inf the test has to be derived from the mongodb or
  a script can be run in pulp-qe-tools to provide a mapping to and from
  manifest_lists, manifests, and blobs. This is required to test shared and
  non-shared unit removal.

One can get a high-level view of the content in this repository by loading the
repository into Pulp and then using:

* https://github.com/PulpQE/pulp-qe-tools/tree/master/pulp2/tools/pulp-docker-inspector
"""
DOCKER_V2_FEED_URL = 'https://registry-1.docker.io'
"""The URL to a V2 Docker registry.

This URL can be used as the "feed" property of a Pulp Docker registry.
"""

DRPM = 'drpms/test-alpha-1.1-1_1.1-2.noarch.drpm'
"""The path to a DRPM file in one of the DRPM repositories.

This path may be joined with :data:`DRPM_SIGNED_FEED_URL` or
:data:`DRPM_UNSIGNED_FEED_URL`.
"""

DRPM_SIGNED_FEED_COUNT = 4
"""The number of packages available at :data:`DRPM_SIGNED_FEED_URL`."""

DRPM_SIGNED_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'drpm-signed/')
"""The URL to a signed DRPM repository."""

DRPM_SIGNED_URL = urljoin(DRPM_SIGNED_FEED_URL, DRPM)
"""The URL to a DRPM file.

Built from :data:`DRPM_SIGNED_FEED_URL` and :data:`DRPM`.
"""

DRPM_UNSIGNED_FEED_COUNT = 4
"""The number of packages available at :data:`DRPM_UNSIGNED_FEED_URL`."""

DRPM_UNSIGNED_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'drpm-unsigned/')
"""The URL to an unsigned DRPM repository."""

DRPM_UNSIGNED_URL = urljoin(DRPM_UNSIGNED_FEED_URL, DRPM)
"""The URL to a unsigned DRPM file.

Built from :data:`DRPM_UNSIGNED_FEED_URL` and :data:`DRPM`.
"""

ERRATA_UPDATE_INFO = MappingProxyType(
    {
        'updated_date': '2014-07-28 00:00:00 UTC',
        'old_updated_date': '2013-07-28 00:00:00 UTC',
        'new_updated_date': '2015-07-28 00:00:00 UTC',
        'invalid_updated_date': '07-28-2014 00:00:00 UTC',
    }
)
"""Dates to be used to verify that update errata updates properly."""

FILE_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'file/')
"""The URL to a file repository."""

FILE_FEED_COUNT = 3
"""The number of packages available at :data:`FILE_FEED_URL`."""

FILE_INVALID_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'file-invalid/')
"""The URL to an invalid file repository."""

FILE_LARGE_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'file-large/')
"""The URL to a file repository containing a large number of files."""

FILE_MANY_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'file-many/')
"""The URL to a file repository containing many files."""

FILE_MANY_FEED_COUNT = 250
"""The number of packages available at :data:`FILE_MANY_FEED_URL`."""

FILE_MIXED_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'file-mixed/')
"""The URL to a file repository containing invalid and valid entries."""

FILE_URL = urljoin(FILE_FEED_URL, '1.iso')
"""The URL to an ISO file at :data:`FILE_FEED_URL`."""

FILE2_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'file2/')
"""The URL to a file repository."""

FILE2_URL = urljoin(FILE2_FEED_URL, '1.iso')
"""The URL to an ISO file at :data:`FILE2_FEED_URL`."""

MODULE_FIXTURES_PACKAGES = {'duck': 3, 'frog': 1, 'kangaroo': 2, 'walrus': 2}
"""The name and the number of the package versions listed in `modules.yaml`_.

    - duck-0.6-1.src.rpm
    - duck-0.7-1.src.rpm
    - duck-0.8-1.src.rpm
    - frog-0.1-1.src.rpm
    - kangaroo-0.2-1.src.rpm
    - kangaroo-0.3-1.src.rpm
    - walrus-0.71-1.src.rpm
    - walrus-5.21-1.src.rpm

.. _modules.yaml: https://github.com/PulpQE/pulp-fixtures/blob/master/rpm/assets/modules.yaml
"""

MODULE_FIXTURES_ERRATA = MappingProxyType(
    {
        'errata_count': 1,
        'errata_id': 'RHEA-2012:0059',
        'modules_count': 2,
        'rpm_count': 2,
        'total_available_units': 5,
    }
)
"""The information about a Modular Errata with RPM artifacts.

:data:`MODULE_FIXTURES_ERRATA['total_available_units']` = ``modules + rpm_count + erratum``

"""

MODULE_ERRATA_RPM_DATA = MappingProxyType(
    {
        'arch': 'x86_64',
        'collection_name': 'collection 0',
        'context': 'deadbeef',
        'description': 'Walrus Erratum; metadata-only',
        'from': 'betelgeuze',
        'issued': '2002-02-20 00:22:00',
        'rpm_name': 'walrus',
        'stream_name': '5.21',
        'updated': '2018-09-05 11:23:42',
        'version': '20180704144203',
    }
)
"""The custom errata information for uploading an errata file."""

MODULE_DATA_2 = MappingProxyType(
    {
        'arch': 'noarch',
        'context': 'deadbeef',
        'description': 'A module for the duck 0.8 package',
        'name': 'duck',
        'stream': '0',
        'version': '201809302113907',
    }
)
"""A custom module information."""

MODULE_FIXTURES_PACKAGE_STREAM = MappingProxyType(
    {
        'name': 'walrus',
        'stream': '0.71',
        'new_stream': '5.21',
        'rpm_count': 4,
        'total_available_units': 5,
        'module_defaults': 3,
    }
)
"""The name and the stream of the package listed in `modules.yaml`_.

.. _modules.yaml: https://github.com/PulpQE/pulp-fixtures/blob/master/rpm/assets/modules.yaml
"""

MODULE_ARTIFACT_RPM_DATA = MappingProxyType(
    {
        'name': 'walrus',
        'version': '5.21',
        'release': '1',
        'arch': 'noarch',
        'epoch': '0',
        'vendor': 'GPLv2',
        'src': 'http://www.fedoraproject.org',
    }
)
"""Details of the RPM file associated with ``MODULE_ERRATA_RPM_DATA``"""

MODULE_ARTIFACT_RPM_DATA_2 = MappingProxyType(
    {
        'name': 'duck',
        'version': '0.6',
        'release': 'livebeef',
        'arch': 'noarch',
        'epoch': '0',
        'vendor': 'GPLv2',
    }
)
"""Details of the RPM file associated with ``MODULE_DATA_2``"""

OPENSUSE_FEED_URL = 'https://download.opensuse.org/update/leap/42.3/oss/'
"""The URL to an openSUSE repository.

The repository contains at least one erratum.

.. WARNING:: This repository is large, and is served by a third party. Do not
    sync from this repository with the "immediate" or "background" download
    policies. Know that metadata parsing will be time-consuming.
"""

OSTREE_BRANCHES = ['rawhide', 'stable']
"""A branch in :data:`OSTREE_FEED`. See OSTree `Importer Configuration`_.

.. _Importer Configuration:
    http://docs.pulpproject.org/plugins/pulp_ostree/tech-reference/importer.html
"""

OSTREE_FEED = urljoin(PULP_FIXTURES_BASE_URL, 'ostree/small/')
"""The URL to a URL of OSTree branches. See OSTree `Importer Configuration`_.

.. _Importer Configuration:
    http://docs.pulpproject.org/plugins/pulp_ostree/tech-reference/importer.html
"""

PUPPET_MODULE_1 = {
    'author': 'pulpqe',
    'name': 'dummypuppet',
    'version': '0.1.0',
}
"""Information about a Puppet module available via Pulp Fixtures."""

PUPPET_MODULE_URL_1 = urljoin(
    urljoin(PULP_FIXTURES_BASE_URL, 'puppet/'),
    '{}-{}.tar.gz'.format(PUPPET_MODULE_1['author'], PUPPET_MODULE_1['name']),
)
"""The URL to a Puppet module module available via Pulp Fixtures.

Test cases that require a single module should use this URL, and test cases
that require a feed should use :data:`PUPPET_MODULE_URL_2`. Doing so shifts
load away from the Puppet Forge.

Why do both URLs exist? Because simulating the Puppet Forge's behaviour is
unreasonably hard.

Pulp Fixtures is designed to create data that can be hosted by a simple HTTP
server, such as ``python3 -m http.server``. A dynamic API, such as the `Puppet
Forge API`_, cannot be simulated. We could create a static tree of files, where
that tree of files is the same as what the Puppet Forge would provide in
response to a certain HTTP GET request. However:

* The `Puppet Forge API`_ will inevitably change over time as bugs are fixed
  and features are added. This will make a static facsimile of the Puppet Forge
  API outdated. This is more than a mere inconvenience: outdated information is
  also confusing!
* Without an in-depth understanding of each and every file the Puppet Forge
  yields, it is probable that static fixtures will be wrong from the get-go.

.. _Puppet Forge API: https://forgeapi.puppetlabs.com/
"""

PUPPET_FEED_2 = 'https://forge.puppet.com'
"""The URL to a repository of Puppet modules."""

PUPPET_MODULE_2 = {'author': 'puppetlabs', 'name': 'motd'}
"""Information about a Puppet module available at :data:`PUPPET_FEED_2`."""

PUPPET_MODULE_URL_2 = '{}/v3/files/{}-{}-%s.tar.gz'.format(
    PUPPET_FEED_2, PUPPET_MODULE_2['author'], PUPPET_MODULE_2['name']
)
"""The URL to a Puppet module available at :data:`PUPPET_FEED_2`.

A version string should be provided to `-%s.tar.gz` e.g::

    PUPPET_MODULE_URL_2 % '2.0.0'

"""
PUPPET_MODULE_EXTRANEOUS_FILE_URL = (
    'https://repos.fedorapeople.org/pulp/pulp/'
    'demo_repos/test_puppet_extraneous_file/'
)
"""The URL for puppet module containing extraneous files."""

PUPPET_MODULE_EXTRANEOUS_FILE_DATA = {
    'author': 'marcel',
    'name': 'passenger',
    'version': '0.5.0',
}
"""Information about a Puppet module available at :data:`PUPPET_FEED_2`."""

PUPPET_MODULE_EXTRANEOUS_FILE = urljoin(
    PUPPET_MODULE_EXTRANEOUS_FILE_URL,
    '{}-{}-{}.tar.gz'.format(
        PUPPET_MODULE_EXTRANEOUS_FILE_DATA['author'],
        PUPPET_MODULE_EXTRANEOUS_FILE_DATA['name'],
        PUPPET_MODULE_EXTRANEOUS_FILE_DATA['version'],
    ),
)
""" A Puppet module containing extraneous files."""

PUPPET_QUERY_2 = quote_plus(
    '-'.join(PUPPET_MODULE_2[key] for key in ('author', 'name'))
)
"""A query that can be used to search for Puppet modules.

Built from :data:`PUPPET_MODULE_2`.

Though the `Puppet Forge API`_ supports a variety of search types, Pulp
only supports the ability to search for modules. As a result, it is
impossible to create a Puppet repository and sync only an exact module or
set of modules. This query intentionally returns a small number of Puppet
modules. A query which selected a large number of modules would produce
tests that took a long time and abused the free Puppet Forge service.

Beware that the Pulp API takes given Puppet queries and uses them to construct
URL queries verbatim. Thus, if the user gives a query of "foo bar", the
following URL is constructed:

    https://forge.puppet.com/modules.json/q=foo bar

In an attempt to avoid this error, this query is encoded before being submitted
to Pulp.

.. _Puppet Forge API: https://forgeapi.puppetlabs.com/
"""

PYTHON_PYPI_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'python-pypi/')
"""The URL to the PyPI Python repository."""

PYTHON_EGG_URL = urljoin(
    PYTHON_PYPI_FEED_URL, 'packages/shelf-reader-0.1.tar.gz'
)
"""The URL to a Python egg at :data:`PYTHON_PYPI_FEED_URL`."""

PYTHON_WHEEL_URL = urljoin(
    PYTHON_PYPI_FEED_URL, 'packages/shelf_reader-0.1-py2-none-any.whl'
)
"""The URL to a Python egg at :data:`PYTHON_PYPI_FEED_URL`."""

RPM_DATA = MappingProxyType(
    {
        'name': 'bear',
        'epoch': '0',
        'version': '4.1',
        'release': '1',
        'arch': 'noarch',
        'metadata': {
            'release': '1',
            'license': 'GPLv2',
            'description': 'A dummy package of bear',
            'files': {'dir': [], 'file': ['/tmp/bear.txt']},
            'group': 'Internet/Applications',
            'size': {'installed': 43, 'package': 1846},
            'sourcerpm': 'bear-4.1-1.src.rpm',
            'summary': 'A dummy package of bear',
            'vendor': None,
        },
    }
)
"""Metadata for an RPM with an associated erratum.

The metadata tags that may be present in an RPM may be printed with:

.. code-block:: sh

    rpm --querytags

Metadata for an RPM can be printed with a command like the following:

.. code-block:: sh

    for tag in name epoch version release arch vendor; do
        echo "$(rpm -qp bear-4.1-1.noarch.rpm --qf "%{$tag}")"
    done

There are three ways to measure the size of an RPM:

installed size
    The size of all the regular files in the payload.
archive size
    The uncompressed size of the payload, including necessary CPIO headers.
package size
    The actual size of an RPM file, as returned by ``stat --format='%s' …``.

For more information, see the Fedora documentation on `RPM headers
<https://docs.fedoraproject.org/en-US/Fedora_Draft_Documentation/0.1/html/RPM_Guide/ch-package-structure.html#id623000>`_.
"""

RPM = '{}-{}{}-{}.{}.rpm'.format(
    RPM_DATA['name'],
    RPM_DATA['epoch'] + '!' if RPM_DATA['epoch'] != '0' else '',
    RPM_DATA['version'],
    RPM_DATA['release'],
    RPM_DATA['arch'],
)
"""The name of an RPM file.

See :data:`pulp_2_tests.constants.RPM_SIGNED_URL`.
"""

RPM2_DATA = MappingProxyType(
    {
        'name': 'camel',
        'epoch': '0',
        'version': '0.1',
        'release': '1',
        'arch': 'noarch',
        'metadata': {
            'release': '1',
            'license': 'GPLv2',
            'description': 'A dummy package of camel',
            'files': {'dir': [], 'file': ['/tmp/camel.txt']},
            'group': 'Internet/Applications',
            'size': '42',
            'sourcerpm': 'camel-0.1-1.src.rpm',
            'summary': 'A dummy package of camel',
            'vendor': None,
        },
    }
)

RPM2 = '{}-{}{}-{}.{}.rpm'.format(
    RPM2_DATA['name'],
    RPM2_DATA['epoch'] + '!' if RPM_DATA['epoch'] != '0' else '',
    RPM2_DATA['version'],
    RPM2_DATA['release'],
    RPM2_DATA['arch'],
)
"""The name of an RPM. See :data:`pulp_2_tests.constants.RPM2_UNSIGNED_URL`."""

RPM_RICH_WEAK = 'PanAmerican-1-0.noarch.rpm'
"""The path to an RPM with rich/weak dependency in one of the RPM repositories.

This path may be joined with :data:`RPM_RICH_WEAK_FEED_URL`.
"""

RPM2_RICH_DEPENDENCY = ['Scotch', 'contireau', 'icecubes', 'tablespoon-sugar']
"""The names rich dependencies associate with :data:`RPM2_RICH_WEAK_DATA`."""

RPM2_WEAK_DEPENDENCY = ['orange-bits']
"""The name weak dependencies associate with :data:`RPM2_RICH_WEAK_DATA`."""

RPM2_RICH_WEAK_TOTAL_DEPENDENCIES = len(RPM2_RICH_DEPENDENCY) + len(
    RPM2_WEAK_DEPENDENCY
)
"""The total of rich and weak dependencies :data:`RPM2_RICH_WEAK_DATA`."""

RPM2_RICH_WEAK_DATA = MappingProxyType(
    {
        'name': 'Cobbler',
        'rich_dependency': len(RPM2_RICH_DEPENDENCY),
        'weak_dependency': len(RPM2_WEAK_DEPENDENCY),
        'total_dependencies': RPM2_RICH_WEAK_TOTAL_DEPENDENCIES,
        'total_installed_packages': RPM2_RICH_WEAK_TOTAL_DEPENDENCIES + 1,
    }
)
"""Data for an RPM package with rich/weak dependency."""

RPM_WITH_VENDOR_DATA = MappingProxyType(
    {
        'name': 'rpm-with-vendor',
        'epoch': '0',
        'version': '1',
        'release': '1.fc25',
        'arch': 'noarch',
        'metadata': {
            'release': '1',
            'license': 'Public Domain',
            'description': 'This RPM has a vendor',
            'files': {'dir': [], 'file': []},
            'group': None,
            'size': None,
            'sourcerpm': None,
            'summary': None,
            'vendor': 'Pulp Fixtures',
        },
    }
)

RPM_WITH_VENDOR = '{}-{}{}-{}.{}.rpm'.format(
    RPM_WITH_VENDOR_DATA['name'],
    RPM_WITH_VENDOR_DATA['epoch'] + '!' if RPM_DATA['epoch'] != '0' else '',
    RPM_WITH_VENDOR_DATA['version'],
    RPM_WITH_VENDOR_DATA['release'],
    RPM_WITH_VENDOR_DATA['arch'],
)
"""The name of an RPM.

See :data:`pulp_2_tests.constants.RPM_WITH_VENDOR_URL`.
"""

RPM_ALT_LAYOUT_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-alt-layout/')
"""The URL to a signed RPM repository. See :data:`RPM_SIGNED_URL`."""

RPM_INCOMPLETE_FILELISTS_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL, 'rpm-incomplete-filelists/'
)
"""The URL to a repository with an incomplete ``filelists.xml`` file."""

RPM_INCOMPLETE_OTHER_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL, 'rpm-incomplete-other/'
)
"""The URL to a repository with an incomplete ``other.xml`` file."""

RPM_ERRATUM_ID = 'RHEA-2012:0058'
"""The ID of an erratum.

The package contained on this erratum is defined by
:data:`pulp_2_tests.constants.RPM_ERRATUM_RPM_NAME` and the erratum is present
on repository which feed is :data:`pulp_2_tests.constants.RPM_SIGNED_FEED_URL`.
"""

RPM_ERRATUM_RPM_NAME = 'gorilla'
"""The name of the RPM named by :data:`pulp_2_tests.constants.RPM_ERRATUM_ID`."""

RPM_ERRATUM_COUNT = 4
"""The number of errata in :data:`RPM_UNSIGNED_FEED_URL`."""

RPM_INVALID_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-invalid-rpm/')
"""The URL to an invalid RPM repository."""

RPM_INVALID_URL = urljoin(RPM_INVALID_FEED_URL, 'invalid.rpm')
"""The URL to an invalid RPM package."""

RPM_KICKSTART_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-kickstart/')
"""The URL to a KICKSTART repository.

.. NOTE:: This repository is not generated by `pulp-fixtures`_.
"""

RPM_LARGE_UPDATEINFO = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-long-updateinfo/')
"""The URL to RPM with a large updateinfo.xml."""

RPM_MIRRORLIST_LARGE = (
    'https://mirrors.fedoraproject.org/metalink?repo=epel-7&arch=x86_64'
)
"""A mirrorlist referencing a large RPM repository.

.. NOTE:: The mirrors referenced by this mirrorlist are not operated by Pulp QE.
    They're public resources and should be sparingly used.
"""

RPM_MIRRORLIST_BAD = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-mirrorlist-bad')
"""The URL to a mirrorlist file containing only invalid entries."""

RPM_MIRRORLIST_GOOD = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-mirrorlist-good')
"""The URL to a mirrorlist file containing only valid entries."""

RPM_MIRRORLIST_MIXED = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-mirrorlist-mixed')
"""The URL to a mirrorlist file containing invalid and valid entries."""

RPM_MISSING_FILELISTS_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL, 'rpm-missing-filelists/'
)
"""A repository that's missing its ``filelists.xml`` file."""

RPM_MISSING_OTHER_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL, 'rpm-missing-other/'
)
"""A repository that's missing its ``other.xml`` file."""

RPM_MISSING_PRIMARY_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL, 'rpm-missing-primary/'
)
"""A repository that's missing its ``primary.xml`` file."""

RPM_NAMESPACES = {
    'metadata/common': 'http://linux.duke.edu/metadata/common',
    'metadata/filelists': 'http://linux.duke.edu/metadata/filelists',
    'metadata/other': 'http://linux.duke.edu/metadata/other',
    'metadata/repo': 'http://linux.duke.edu/metadata/repo',
    'metadata/rpm': 'http://linux.duke.edu/metadata/rpm',
}
"""Namespaces used by XML-based RPM metadata.

Many of the XML files generated by the ``createrepo`` utility make use of these
namespaces. Some of the files that use these namespaces are listed below:

metadata/common
    Used by ``repodata/primary.xml``.

metadata/filelists
    Used by ``repodata/filelists.xml``.

metadata/other
    Used by ``repodata/other.xml``.

metadata/repo
    Used by ``repodata/repomd.xml``.

metadata/rpm
    Used by ``repodata/repomd.xml``.
"""

RPM_PKGLISTS_UPDATEINFO_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL, 'rpm-pkglists-updateinfo/'
)
"""A repository whose updateinfo file has multiple ``<pkglist>`` sections."""

RPM_PACKAGES_UPDATEINFO_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL, 'rpm-packages-updateinfo/'
)
"""A repository whose updateinfo file has multiple ``<pkglist>`` sections.

``<pkglist>`` has different package names than the ones present in
RPM_PKGLISTS_UPDATEINFO_FEED_URL.
"""

ERRATA_PACKAGES_UPDATEINFO = {
    'errata': 'RHEA-2012:0055',
    'packages': [
        'dolphin-3.10.232-1.noarch.rpm',
        'penguin-0.9.1-1.noarch.rpm',
        'pike-2.2-1.noarch.rpm',
        'shark-0.1-1.noarch.rpm',
        'walrus-5.21-1.noarch.rpm',
        'whale-0.2-1.noarch.rpm',
    ],
}
"""This errata appears in 2 different repositories. List all packages
mentioned in both repositories.

See::data:`pulp_2_tests.constants.RPM_PKGLISTS_UPDATEINFO_FEED_URL` and
:data:`pulp_2_tests.constants.RPM_PACKAGES_UPDATEINFO_FEED_URL`.
"""

RPM_PKG_RICH_WEAK_VERSION = '4.12'
"""The version of the RPM package manager that introduced weak dependencies resolution."""

RPM_RICH_WEAK_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-richnweak-deps/')
"""The URL to an RPM repository with weak and rich dependencies."""

RPM_SIGNED_FEED_COUNT = 35
"""The number of packages available at :data:`RPM_SIGNED_FEED_URL`."""

RPM_SIGNED_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-signed/')
"""The URL to a signed RPM repository. See :data:`RPM_SIGNED_URL`."""

RPM_SIGNED_URL = urljoin(RPM_SIGNED_FEED_URL, RPM)
"""The URL to an RPM file.

Built from :data:`RPM_SIGNED_FEED_URL` and :data:`RPM`.
"""

RPM_UNSIGNED_FEED_COUNT = 35
"""The number of packages available at :data:`RPM_UNSIGNED_FEED_URL`."""

RPM_UNSIGNED_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-unsigned/')
"""The URL to an unsigned RPM repository. See :data:`RPM_SIGNED_URL`."""

RPM_UNSIGNED_URL = urljoin(RPM_UNSIGNED_FEED_URL, RPM)
"""The URL to an unsigned RPM file.

Built from :data:`RPM_UNSIGNED_FEED_URL` and :data:`RPM`.
"""

RPM_SHA_512_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-with-sha-512/')
"""The URL to an RPM repository with sha512 checksum."""

RPM_UPDATED_INFO_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL, 'rpm-updated-updateinfo/'
)
"""A repository whose updateinfo file has an errata section."""

RPM2_UNSIGNED_URL = urljoin(RPM_UNSIGNED_FEED_URL, RPM2)
"""The URL to an unsigned RPM file.

Built from :data:`RPM_UNSIGNED_FEED_URL` and :data:`RPM2`.
"""

RPM_WITH_MODULAR_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL, 'rpm-with-modular/'
)
"""The URL to a modular RPM repository.

.. NOTE:: This repository is not generated by `pulp-fixtures`_.

.. _pulp-fixtures: https://repos.fedorapeople.org/pulp/pulp/fixtures/
"""

RPM_WITH_MODULAR_URL = urljoin(
    RPM_WITH_MODULAR_FEED_URL,
    'nodejs-10.15.2-1.module_f30+3181+3be24b3a.x86_64.rpm',
)

RPM_WITH_MODULES_FEED_COUNT = 3
"""The number of modules available at :data:`RPM_WITH_MODULES_FEED_URL`."""

RPM_WITH_MODULES_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL, 'rpm-with-modules/'
)
"""The URL to a modular RPM repository."""

RPM_MODULAR_OLD_VERSION_URL = urljoin(
    RPM_WITH_MODULES_FEED_URL, 'duck-0.6-1.noarch.rpm'
)
"""duck RPM package has 3 versions, the modular errata mentioned the version
``duck-0.7-1.noarch.rpm``. The URL to the older version."""

RPM_MODULAR_NEW_VERSION_URL = urljoin(
    RPM_WITH_MODULES_FEED_URL, 'duck-0.8-1.noarch.rpm'
)
"""duck RPM package has 3 versions, the modular errata mentioned the version
``duck-0.7-1.noarch.rpm``. The URL to the newer version."""

RPM_WITH_MODULES_SHA1_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL, 'rpm-with-sha-1-modular/'
)
"""The URL to a modular RPM repository with SHA1 checksum."""

RPM_WITH_PULP_DISTRIBUTION_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL, 'rpm-with-pulp-distribution/'
)
"""The URL to a RPM repository with a PULP_DISTRIBUTION.xml file."""

RPM_WITH_NON_ASCII_URL = urljoin(
    PULP_FIXTURES_BASE_URL,
    'rpm-with-non-ascii/rpm-with-non-ascii-1-1.fc25.noarch.rpm',
)
"""The URL to an RPM with non-ascii metadata in its header."""

RPM_WITH_NON_UTF_8_URL = urljoin(
    PULP_FIXTURES_BASE_URL,
    'rpm-with-non-utf-8/rpm-with-non-utf-8-1-1.fc25.noarch.rpm',
)
"""The URL to an RPM with non-UTF-8 metadata in its header."""

RPM_WITH_VENDOR_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-with-vendor/')
"""A repository whose primary.xml file has an vendor section."""

RPM_WITH_VENDOR_URL = urljoin(
    RPM_WITH_VENDOR_FEED_URL, 'rpm-with-vendor-1-1.fc25.noarch.rpm'
)
"""The URL of an RPM with a specified vendor in its header."""

RPM_WITH_OLD_VERSION_URL = urljoin(
    RPM_UNSIGNED_FEED_URL, 'walrus-0.71-1.noarch.rpm'
)
"""walrus RPM package has 2 versions. The URL to the older version."""

RPM_WITH_OLD_VERSION_DUCK_URL = urljoin(
    RPM_UNSIGNED_FEED_URL, 'duck-0.7-1.noarch.rpm'
)
"""duck RPM package has 4 versions. The URL to an older version."""

RPM_ZCHUNK_FEED_COUNT = 35
"""The number of packages available at :data:`RPM_ZCHUNK_FEED_URL`."""

RPM_ZCHUNK_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-zchunk/')
"""A URL which serves zchunk files for Pulp.

Pulp should ignore the zchunk (.zck) archives in Pulp2.

Pulp2 is not intended to work with these archive types.

.. NOTE:: This repository is not generated by `pulp-fixtures`_.

.. _pulp-fixtures: https://repos.fedorapeople.org/pulp/pulp/fixtures/
"""

SRPM_DUPLICATE_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'srpm-duplicate/')
"""The URL to an SRPM repository with duplicate RPMs in repodata."""

SRPM_RICH_WEAK_FEED_URL = urljoin(
    PULP_FIXTURES_BASE_URL, 'srpm-richnweak-deps/'
)
"""The URL to an SRPM repository with weak and rich dependencies."""

SRPM = 'test-srpm02-1.0-1.src.rpm'
"""An SRPM file at :data:`pulp_2_tests.constants.SRPM_SIGNED_FEED_URL`."""

SRPM_SIGNED_FEED_COUNT = 3
"""The number of packages available at :data:`SRPM_SIGNED_FEED_URL`."""

SRPM_SIGNED_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'srpm-signed/')
"""The URL to a signed SRPM repository."""

SRPM_SIGNED_URL = urljoin(SRPM_SIGNED_FEED_URL, SRPM)
"""The URL to an SRPM file.

Built from :data:`SRPM_SIGNED_FEED_URL` and :data:`SRPM`.
"""

SRPM_UNSIGNED_FEED_COUNT = 3
"""The number of packages available at :data:`SRPM_UNSIGNED_FEED_COUNT`."""

SRPM_UNSIGNED_FEED_URL = urljoin(PULP_FIXTURES_BASE_URL, 'srpm-unsigned/')
"""The URL to an unsigned SRPM repository."""

SRPM_UNSIGNED_URL = urljoin(SRPM_UNSIGNED_FEED_URL, SRPM)
"""The URL to an unsigned SRPM file.

Built from :data:`SRPM_UNSIGNED_FEED_URL` and :data:`SRPM`.
"""

PULP_LARGE_RPM_REPO = (
    'https://repos.fedorapeople.org/pulp/pulp/rpm_large_metadata/'
)
"""A URL which serves the large RPM files for Pulp.

.. NOTE:: This repository is not generated by `pulp-fixtures`_.

.. _pulp-fixtures: https://repos.fedorapeople.org/pulp/pulp/fixtures/
"""

RPM_LARGE_METADATA = 'nodejs-babel-preset-es2015-6.6.0-2.el6.noarch.rpm'
"""RPM with filelists size more than 9MB and less than 15 MB."""

RPM_LARGE_METADATA_FEED = urljoin(PULP_LARGE_RPM_REPO, RPM_LARGE_METADATA)
"""Feed URL for ``RPM_LARGE_METADATA``."""

RPM_YUM_METADATA_FILE = 'https://repos.fedorapeople.org/pulp/pulp/demo_repos/test_yum_meta_data_file/'  # pylint:disable=line-too-long
"""The URL to an RPM with YUM Metadata file.

.. NOTE:: This repository is not generated by `pulp-fixtures`_.

.. _pulp-fixtures:
    https://repos.fedorapeople.org/pulp/pulp/fixtures/
"""

MODULE_FIXTURES_PACKAGE_STREAM = MappingProxyType(
    {
        'name': 'walrus',
        'stream': '0.71',
        'new_stream': '5.21',
        'rpm_count': 4,
        'total_available_units': 5,
        'module_defaults': 3,
        'feed': RPM_WITH_MODULES_FEED_URL,
        'old': RPM_WITH_OLD_VERSION_URL,
    }
)
"""The name and the stream of the package listed in `modules.yaml`_.

.. _modules.yaml: https://github.com/PulpQE/pulp-fixtures/blob/master/rpm/assets/modules.yaml
"""

MODULE_FIXTURES_DUCK_4_STREAM = MappingProxyType(
    {
        'name': 'duck',
        'stream': '4',
        'new_stream': '4',
        'rpm_count': 1,
        'total_available_units': 2,
        'module_defaults': 1,
        'feed': RPM_WITH_MODULES_FEED_URL,
        'old': RPM_WITH_OLD_VERSION_DUCK_URL,
    }
)
"""The name and the stream of the package listed in `modules.yaml`_.

.. _modules.yaml: https://github.com/PulpQE/pulp-fixtures/blob/master/rpm/assets/modules.yaml
"""

MODULE_FIXTURES_DUCK_5_STREAM = MappingProxyType(
    {
        'name': 'duck',
        'stream': '5',
        'new_stream': '5',
        'rpm_count': 1,
        'total_available_units': 2,
        'module_defaults': 1,
        'feed': RPM_WITH_MODULES_FEED_URL,
        'old': RPM_WITH_OLD_VERSION_DUCK_URL,
    }
)
"""The name and the stream of the package listed in `modules.yaml`_.

.. _modules.yaml: https://github.com/PulpQE/pulp-fixtures/blob/master/rpm/assets/modules.yaml
"""

MODULE_FIXTURES_DUCK_6_STREAM = MappingProxyType(
    {
        'name': 'duck',
        'stream': '6',
        'new_stream': '6',
        'rpm_count': 2,
        'total_available_units': 3,
        'module_defaults': 1,
        'feed': RPM_WITH_MODULES_FEED_URL,
        'old': RPM_WITH_OLD_VERSION_DUCK_URL,
    }
)
"""The name and the stream of the package listed in `modules.yaml`_.

.. _modules.yaml: https://github.com/PulpQE/pulp-fixtures/blob/master/rpm/assets/modules.yaml
"""
