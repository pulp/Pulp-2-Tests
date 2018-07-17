#!/usr/bin/env bash
#
# For each file found by `find`, generate a reStructuredText document in
# `docs/tests/`.
#
# NOTE: This script should be run from the repository root directory. That is,
# this script should be run from this script's parent directory.
#
set -euo pipefail

find pulp_2_tests/ -type f -name '*.py' | while read file_name; do
    # Transform file names to python module names. For example:
    #
    #     tests/__init__.py → tests
    #     tests/test_foo.py → tests.test_foo
    #
    # Note that file_name has no leading "./", as we omit it in find, above.
    module_name="${file_name%.py}"
    module_name="${module_name%/__init__}"
    module_name="${module_name//\//.}"

    # Generate stub *.rst file. (Tip: ${#foo} returns the length of foo.)
    cat >"docs/tests/${module_name}.rst" <<EOF
\`${module_name}\`
$(printf %${#module_name}s | tr ' ' =)==

Location: :doc:\`/index\` → :doc:\`/tests\` → :doc:\`/tests/${module_name}\`

.. automodule:: ${module_name}
EOF
done
